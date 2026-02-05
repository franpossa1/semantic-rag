# Semantic RAG - Agent Development Guide

This guide is for agentic coding assistants working on the semantic-rag project.

## Project Overview

Retrieval-Augmented Generation (RAG) MVP using:
- **FastAPI** - Async web framework
- **ChromaDB** - Vector database for embeddings
- **OpenAI** - Embeddings and AI operations
- **PyPDF2** - PDF processing
- **Pydantic** - Data validation

**IMPORTANT: MVP project. Focus on speed. Use print() for debugging, not loggers. Don't generate tests unless explicitly requested.**

---

## Build & Development Commands

```bash
# Install dependencies
uv sync

# Run development server (auto-reload)
fastapi dev main:app

# Run production server
fastapi run main:app

# Docker: build and start
docker compose up --build

# Docker: stop
docker compose down
```

### Environment Setup
- Copy `.env.example` to `.env` and set `PORT=8000`
- `.env` is gitignored for security

---

## Code Style Guidelines

### Imports
Group in order: stdlib, third-party, local. Use absolute imports.

```python
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
from chromadb import PersistentClient

from my_module import helper_function
```

### Type Hints
All function signatures must have type hints. Use Python 3.13 union syntax (`|`).

```python
async def process_pdf(file: UploadFile) -> dict[str, str]:
    return {"status": "ok"}
```

### Naming Conventions
- **Functions/Variables**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Endpoints**: kebab-case in URLs

### Async/Await
All FastAPI route handlers MUST be async. Use async for I/O operations.

```python
@app.post("/query")
async def query_endpoint(query: str) -> dict:
    results = await chroma_client.query(query)
    return {"results": results}
```

### Error Handling
Use simple try/except. Return appropriate HTTP status codes. Don't over-engineer.

```python
@app.post("/ingest")
async def ingest_document(file: UploadFile):
    try:
        content = await file.read()
        print(f"Processing: {file.filename}")
        return {"status": "success"}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
```

### FastAPI Patterns
Use Pydantic models for request/response. Return dict or Pydantic models.

```python
class QueryRequest(BaseModel):
    query: str
    limit: int = 10

@app.post("/search")
async def search(request: QueryRequest, book_id: str | None = None):
    return search_service(request.query, limit=request.limit)
```

### ChromaDB Usage
Use PersistentClient with local directory `./chroma_db`. Use metadata for filtering.

```python
client = PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("documents")

collection.add(
    documents=[text],
    metadatas=[{"source": "book1.pdf", "page": 1}],
    ids=["doc1"]
)

results = collection.query(
    query_texts=["search term"],
    where={"source": "book1.pdf"}
)
```

### File Organization
- `main.py` - FastAPI app initialization and routes
- `src/services/` - Feature modules (search.py, ingest.py, etc.)
- `src/db/` - Database operations
- `src/models/` - Pydantic models

---

## Testing

**Do not write unit tests unless explicitly requested.**

If tests exist:
```bash
# Run all tests
pytest

# Run single test file
pytest tests/test_specific.py

# Run single test
pytest tests/test_specific.py::test_function_name -v
```

---

## Docker Considerations
- App runs on `$PORT` environment variable (default 8000)
- Uses Hypercorn: `hypercorn main:app --bind 0.0.0.0:$PORT`
- All dependencies must be in `pyproject.toml`
