# Step 1.5 — FastAPI Endpoint Wiring

## Objective

Connect all services (scraper, ingest, search, generation) to FastAPI endpoints. Refactor `main.py` to use a clean structure with proper dependency injection and error handling.

## Dependencies

- All services from Steps 1.1–1.4
- `src/config.py` (Settings)
- `src/db/chromadb.py` (ChromaDBHandler)

---

## Refactored `main.py`

```python
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from src.config import settings
from src.db.chromadb import ChromaDBHandler
from src.services.scraper import DocsScraper
from src.services.ingest import IngestService
from src.services.search import search_service
from src.services.generation import GenerationService
from src.models.search import SearchRequest, SearchResponse
from src.models.generation import AskRequest, AskResponse

# --- App Lifespan (initialize shared resources) ---

db: ChromaDBHandler | None = None
generation_svc: GenerationService | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown shared resources."""
    global db, generation_svc
    print("Initializing ChromaDB...")
    db = ChromaDBHandler(path=settings.chroma_path)
    generation_svc = GenerationService(db=db)
    print(f"ChromaDB ready. Collection count: {db.count()}")
    yield
    print("Shutting down...")

app = FastAPI(
    title="Semantic RAG",
    description="RAG system over technical documentation (LangChain, FastAPI, Python)",
    version="0.1.0",
    lifespan=lifespan,
)
```

---

## Endpoints

### `GET /health`

```python
@app.get("/health")
async def health():
    """Health check endpoint.
    
    Returns:
    - status: "ok"
    - documents_indexed: total count from ChromaDB collection
    - embedding_model: name of the model in use
    - llm_model: name of the LLM in use
    """
    return {
        "status": "ok",
        "documents_indexed": db.count() if db else 0,
        "embedding_model": settings.embedding_model,
        "llm_model": settings.kimi_model,
    }
```

### `POST /ingest/fetch-docs`

```python
@app.post("/ingest/fetch-docs")
async def fetch_docs():
    """Download raw documentation from GitHub.
    
    Calls DocsScraper.fetch_all().
    Returns count of files downloaded per library.
    
    This is a long-running operation (minutes). 
    For MVP, just run it synchronously and let the client wait.
    Future improvement: background task with status polling.
    """
    try:
        scraper = DocsScraper(output_dir=settings.raw_docs_path)
        counts = await scraper.fetch_all()
        return {"status": "success", "files_downloaded": counts}
    except Exception as e:
        print(f"Error fetching docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### `POST /ingest/index`

```python
@app.post("/ingest/index")
async def index_docs(force: bool = False):
    """Chunk and index downloaded docs into ChromaDB.
    
    Args:
        force: If true, delete existing collection and re-index from scratch.
    
    Calls IngestService.ingest_all() or clear_and_reingest() based on force flag.
    Returns count of chunks indexed per library.
    """
    try:
        ingest_svc = IngestService(db_handler=db, raw_docs_path=settings.raw_docs_path)
        if force:
            counts = await ingest_svc.clear_and_reingest()
        else:
            counts = await ingest_svc.ingest_all()
        return {"status": "success", "chunks_indexed": counts, "total": sum(counts.values())}
    except Exception as e:
        print(f"Error indexing docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### `POST /search`

```python
@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Semantic search over indexed documentation.
    
    Supports optional filters by library and section.
    Returns ranked results with similarity scores and metadata.
    """
    try:
        return search_service(
            query=request.query,
            limit=request.limit,
            library=request.library,
            section=request.section,
            db=db,
        )
    except Exception as e:
        print(f"Error searching: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### `POST /ask`

```python
@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """RAG endpoint: retrieve context + generate answer with LLM.
    
    Full pipeline:
    1. Search for relevant documentation chunks
    2. Build prompt with retrieved context
    3. Call Kimi 2.5 LLM
    4. Return answer with source citations
    """
    try:
        return await generation_svc.ask(request)
    except Exception as e:
        print(f"Error generating answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Global Variables vs Dependency Injection

For the MVP, use module-level globals initialized in the lifespan handler. This is simple and works.

The `db` and `generation_svc` instances are created once at startup and shared across all requests. This is safe because:
- ChromaDB PersistentClient is thread-safe
- OpenAI AsyncClient is designed for concurrent use
- SentenceTransformer model is loaded once, inference is stateless

**Future improvement** (Step 5): Use FastAPI's dependency injection system with `Depends()` for cleaner testing.

---

## CORS (for Streamlit frontend)

Add CORS middleware to allow Streamlit (running on a different port) to call the API:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to Streamlit's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Cleanup

1. **Remove old `src/main.py`**: The root `main.py` is the entry point. `src/main.py` was a duplicate and should be removed or repurposed.
2. **Update `src/__init__.py`**: Remove the old "Sprint Analytics" docstring. Update to reflect the semantic-rag project.
3. **Update `src/db/__init__.py`**: Make sure it exports `ChromaDBHandler` correctly.

---

## .env.example Update

Ensure `.env.example` has all required vars:

```env
PORT=8000
KIMI_API_KEY=your-kimi-api-key-here
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=moonshot-v1-8k
CHROMA_PATH=./data
EMBEDDING_MODEL=all-MiniLM-L6-v2
RAW_DOCS_PATH=raw/docs
```

---

## Verification

1. **Start server**: `fastapi dev main:app`
2. **Health check**: `GET /health` → returns status ok with document count
3. **Fetch docs**: `POST /ingest/fetch-docs` → downloads docs (may take a few minutes)
4. **Index docs**: `POST /ingest/index` → chunks and indexes, returns counts
5. **Search**: `POST /search` with body `{"query": "how to create endpoints", "limit": 3}` → returns results
6. **Ask**: `POST /ask` with body `{"question": "How do I handle path parameters in FastAPI?"}` → returns generated answer with sources
7. **Filtered ask**: `POST /ask` with body `{"question": "What is a chain?", "library": "langchain"}` → answer from LangChain docs only
8. **Swagger UI**: Visit `http://localhost:8000/docs` → all endpoints visible and testable
