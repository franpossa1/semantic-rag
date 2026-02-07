# Step 2 — Hybrid Search + Re-ranking

## Objective

Upgrade the retrieval pipeline from pure semantic search to a hybrid approach combining semantic (dense) and keyword (sparse) search, followed by a cross-encoder re-ranking stage. This significantly improves retrieval quality.

## Why This Matters

- **Semantic search alone** misses exact keyword matches (e.g., searching "FastAPI" may not prioritize docs that literally mention "FastAPI" if the embedding focuses on meaning)
- **Keyword search alone** misses semantic similarity (e.g., "web framework" won't match "FastAPI" even though they're related)
- **Hybrid = best of both worlds**
- **Re-ranking** with a cross-encoder provides a second, more accurate scoring pass on the top-K results

---

## Architecture Change

```
Current (Step 1):
  Query → Semantic Search (ChromaDB) → Results

After Step 2:
  Query → Semantic Search (ChromaDB) ──┐
                                        ├── Fusion (RRF) → Cross-Encoder Re-rank → Final Results
  Query → Keyword Search (BM25) ───────┘
```

---

## 2.1 — BM25 Keyword Search

### Option A: In-memory BM25 with `rank-bm25` library

```python
# pip install rank-bm25
from rank_bm25 import BM25Okapi

class BM25Index:
    """In-memory BM25 index over document chunks."""
    
    def __init__(self):
        self.documents: list[dict] = []  # [{id, text, metadata}]
        self.index: BM25Okapi | None = None
    
    def build(self, documents: list[dict]) -> None:
        """Build BM25 index from list of document dicts.
        
        Tokenize each document's text by whitespace + lowercasing.
        Store documents for retrieval by index position.
        """
        self.documents = documents
        tokenized = [doc["text"].lower().split() for doc in documents]
        self.index = BM25Okapi(tokenized)
    
    def search(self, query: str, limit: int = 10) -> list[tuple[dict, float]]:
        """Search the BM25 index.
        
        Returns list of (document_dict, bm25_score) tuples, sorted by score descending.
        """
        tokenized_query = query.lower().split()
        scores = self.index.get_scores(tokenized_query)
        # Get top-K indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:limit]
        return [(self.documents[i], scores[i]) for i in top_indices if scores[i] > 0]
```

### Building the BM25 Index

The BM25 index needs to be built from all documents in ChromaDB at startup or after ingestion:

```python
# In the lifespan handler or after ingest:
collection = db.get_collection("technical_docs")
all_docs = collection.get(include=["documents", "metadatas"])

bm25_index = BM25Index()
bm25_index.build([
    {"id": id, "text": text, "metadata": meta}
    for id, text, meta in zip(all_docs["ids"], all_docs["documents"], all_docs["metadatas"])
])
```

**Note**: This loads all documents into memory. For the expected ~1000 chunks, this is fine. For larger datasets, consider using an external search engine like Elasticsearch.

---

## 2.2 — Reciprocal Rank Fusion (RRF)

RRF is a simple and effective way to combine ranked lists from different retrieval methods.

```python
def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, float]]],  # list of [(doc_id, score)]
    k: int = 60,  # RRF constant
) -> list[tuple[str, float]]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion.
    
    For each document, its RRF score = sum over all lists of: 1 / (k + rank)
    where rank is the 1-indexed position in each list.
    
    Args:
        ranked_lists: Each list contains (doc_id, original_score) tuples, ordered by rank.
        k: RRF smoothing constant (default 60, standard value from the original paper).
    
    Returns:
        Fused list of (doc_id, rrf_score) sorted by RRF score descending.
    """
    rrf_scores: dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, (doc_id, _) in enumerate(ranked_list, start=1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank)
    
    return sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
```

---

## 2.3 — Cross-Encoder Re-ranking

After fusion, take the top-N results and re-rank them with a cross-encoder for maximum precision.

```python
from sentence_transformers import CrossEncoder

class Reranker:
    """Cross-encoder re-ranker for improving retrieval precision."""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)
    
    def rerank(self, query: str, documents: list[dict], limit: int = 5) -> list[dict]:
        """Re-rank documents using cross-encoder.
        
        Args:
            query: The user's original query
            documents: List of document dicts with "text" key
            limit: Number of top results to return after re-ranking
        
        Process:
        1. Create (query, document_text) pairs
        2. Score all pairs with the cross-encoder
        3. Sort by cross-encoder score descending
        4. Return top-limit results with updated scores
        
        The cross-encoder model `ms-marco-MiniLM-L-6-v2` is:
        - Small and fast (~22MB)
        - Trained on MS MARCO passage ranking
        - Good enough for re-ranking 20-50 candidates
        """
        pairs = [(query, doc["text"]) for doc in documents]
        scores = self.model.predict(pairs)
        
        # Attach scores and sort
        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)
        
        reranked = sorted(documents, key=lambda d: d["rerank_score"], reverse=True)
        return reranked[:limit]
```

---

## 2.4 — Updated Search Pipeline

Refactor `src/services/search.py` to support the full hybrid pipeline:

```python
async def hybrid_search(
    query: str,
    limit: int = 5,
    library: str | None = None,
    use_reranking: bool = True,
    db: ChromaDBHandler,
    bm25: BM25Index,
    reranker: Reranker | None = None,
) -> SearchResponse:
    """Full hybrid search pipeline.
    
    1. Semantic search via ChromaDB (top 20 candidates)
    2. BM25 keyword search (top 20 candidates)
    3. Reciprocal Rank Fusion to combine both lists
    4. Cross-encoder re-ranking on top 10 fused results
    5. Return top `limit` results
    """
    ...
```

---

## Updated Models

Add to `SearchRequest`:
```python
class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    library: str | None = None
    section: str | None = None
    use_reranking: bool = True  # NEW: toggle re-ranking
    search_mode: str = "hybrid"  # NEW: "semantic", "keyword", or "hybrid"
```

Add to `SearchResult`:
```python
class SearchResult(BaseModel):
    text: str
    score: float
    rerank_score: float | None = None  # NEW: cross-encoder score
    search_source: str  # NEW: "semantic", "keyword", or "both"
    metadata: dict
```

---

## Dependencies

Add to `pyproject.toml`:
- `rank-bm25` (BM25 implementation)
- `sentence-transformers` already includes CrossEncoder

---

## Verification

1. **Compare search modes**: Same query with `search_mode="semantic"` vs `"keyword"` vs `"hybrid"` — hybrid should return the best combination
2. **Keyword-dependent queries**: "FastAPI dependency injection" should rank docs containing those exact keywords higher in hybrid mode
3. **Semantic queries**: "web framework for building APIs" should still find FastAPI docs even without the word "FastAPI"
4. **Re-ranking impact**: Compare results with and without re-ranking — re-ranked results should be more relevant
5. **Performance**: The full hybrid pipeline should complete in <2 seconds for typical queries

---

## Key Trade-offs to Discuss in Interviews

- **Why RRF over other fusion methods?** Simple, parameter-free (just k=60), and proven effective across many benchmarks.
- **Why not a learned fusion model?** Overkill for this scale. RRF is the industry standard for hybrid search.
- **Why cross-encoder re-ranking?** Bi-encoders (used in initial retrieval) are fast but less accurate. Cross-encoders compare query-document pairs directly, giving much better relevance scores, but are too slow for initial retrieval over thousands of docs.
- **Memory trade-off of BM25**: All docs in memory. Fine for <100K docs. For larger scale, use Elasticsearch or equivalent.
