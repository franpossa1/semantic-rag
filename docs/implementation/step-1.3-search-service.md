# Step 1.3 — Search Service with Metadata Filters

## Objective

Build a search service that queries ChromaDB with semantic search, supports metadata filtering (by library, section), and returns structured results via Pydantic response models.

## Dependencies

- `src/db/chromadb.py` (ChromaDBHandler from Step 1.2)
- `src/models/search.py` (new — Pydantic models)

---

## Pydantic Models: `src/models/search.py`

```python
from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    """Request model for search endpoint."""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query in natural language")
    limit: int = Field(default=5, ge=1, le=20, description="Number of results to return")
    library: str | None = Field(default=None, description="Filter by library: langchain, fastapi, python")
    section: str | None = Field(default=None, description="Filter by top-level section")

class SearchResult(BaseModel):
    """A single search result."""
    text: str = Field(..., description="The chunk content")
    score: float = Field(..., description="Similarity score (lower = more similar for ChromaDB distances)")
    metadata: dict = Field(..., description="Chunk metadata (library, source_file, section, subsection, etc.)")

class SearchResponse(BaseModel):
    """Response model for search endpoint."""
    query: str
    results: list[SearchResult]
    total_results: int
    filters_applied: dict
```

---

## Implementation: `src/services/search.py`

### Function: `search_service`

```python
from src.db.chromadb import ChromaDBHandler
from src.models.search import SearchRequest, SearchResponse, SearchResult

def search_service(
    query: str,
    limit: int = 5,
    library: str | None = None,
    section: str | None = None,
    db: ChromaDBHandler | None = None,
) -> SearchResponse:
    """Execute semantic search over indexed documentation.
    
    1. Build a ChromaDB `where` filter from the optional parameters:
       - If library is provided: {"library": library}
       - If section is provided: {"section": section}
       - If both: {"$and": [{"library": library}, {"section": section}]}
       - If neither: No filter (search all)
    
    2. Call ChromaDB collection.query() with:
       - query_texts=[query]
       - n_results=limit
       - where=<filter> (if any)
       - include=["documents", "metadatas", "distances"]
    
    3. Transform ChromaDB response into SearchResponse:
       - ChromaDB returns lists nested in lists (because it supports batch queries)
       - Access results via results["documents"][0], results["metadatas"][0], results["distances"][0]
       - Map to SearchResult objects
       - Distance = lower is better (cosine distance). Convert to similarity score if desired:
         score = 1 - distance (for cosine)
    
    4. Return SearchResponse with query, results, count, and applied filters.
    """
    ...
```

### Key Implementation Details:

1. **ChromaDB where filter syntax**:
   ```python
   # Single filter
   where = {"library": "fastapi"}
   
   # Multiple filters (AND)
   where = {"$and": [{"library": "fastapi"}, {"section": "Tutorial"}]}
   
   # No filter
   where = None
   ```

2. **ChromaDB query response structure**:
   ```python
   {
       "ids": [["id1", "id2", "id3"]],
       "documents": [["text1", "text2", "text3"]],
       "metadatas": [[{...}, {...}, {...}]],
       "distances": [[0.45, 0.62, 0.78]],
   }
   ```
   Note: Everything is nested in an outer list (index 0) because query_texts accepts multiple queries.

3. **Score handling**: ChromaDB returns distances (lower = better). Convert to a 0-1 similarity score:
   ```python
   similarity = 1 - distance  # for cosine distance
   ```
   Clamp between 0 and 1.

4. **Empty results**: If the collection is empty or no results match, return an empty list, not an error.

5. **Invalid library filter**: If the user passes a library name that doesn't exist, the query will simply return no results. No need to validate against a fixed list.

---

## ChromaDB Handler Updates

Add a `search_with_filters` method to `ChromaDBHandler`:

```python
def search_with_filters(
    self,
    query: str,
    limit: int = 5,
    where: dict | None = None,
    collection_name: str = "technical_docs",
) -> dict:
    """Search with optional metadata filters.
    
    Args:
        query: Search text
        limit: Max results
        where: ChromaDB where filter dict
        collection_name: Which collection to search
    
    Returns:
        Raw ChromaDB query results dict
    """
    collection = self.get_collection(collection_name)
    kwargs = {
        "query_texts": [query],
        "n_results": limit,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    return collection.query(**kwargs)
```

---

## Verification

Test cases to verify after implementation:

1. **Basic search**: `search_service("How to create an endpoint")` → returns results from multiple libraries
2. **Filtered search**: `search_service("dependency injection", library="fastapi")` → only FastAPI results
3. **Empty query handling**: Should raise validation error (min_length=1)
4. **No results**: `search_service("xyzabc123nonsense")` → empty results list, no error
5. **Limit works**: `search_service("python tutorial", limit=2)` → exactly 2 results
6. **Scores are reasonable**: Results should have scores between 0 and 1, sorted by relevance
7. **Metadata present**: Every result should have library, source_file, section, subsection

---

## Integration Point

This service will be used by:
- `POST /search` endpoint (Step 1.5) — direct search
- `src/services/generation.py` (Step 1.4) — retrieval step of RAG chain
