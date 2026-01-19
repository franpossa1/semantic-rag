# Semantic RAG - Agent Development Guide

This guide is for agentic coding assistants working on the semantic-rag project.

## Project Overview

This is a Retrieval-Augmented Generation (RAG) MVP built with:
- **FastAPI** - Async web framework
- **ChromaDB** - Vector database for embeddings
- **OpenAI** - Embeddings and AI operations
- **Pydantic** - Data validation
- **Hypercorn** - ASGI server for production
- **PyPDF2** - PDF processing

**IMPORTANT: This is an MVP project. Focus on speed and functionality. Do not generate unit tests unless explicitly requested. Use print() for debugging, not loggers.**

---

## Build & Development Commands

### Local Development
```bash
# Install dependencies
uv sync

# Run development server (with auto-reload)
fastapi dev main:app

# Run production server
fastapi run main:app

# Run with uv directly (alternative)
uv run fastapi dev main:app
```

### Docker Development
```bash
# Build and start with Docker Compose
docker compose up --build

# Stop containers
docker compose down

# Build image only
docker build -t semantic-rag .
```

### Environment Setup
- Copy `.env.example` to `.env` and set `PORT=8000`
- The `.env` file is gitignored for security

---

## Code Style Guidelines

### Imports
- Use absolute imports from project root
- Group imports in this order: stdlib, third-party, local
- Use type hints for all function signatures

```python
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
from chromadb import PersistentClient

from my_module import helper_function
```

### Type Hints
- Use type hints for all function parameters and return values
- Leverage Pydantic models for request/response validation
- Use Python 3.13 type features (unions with `|`, generics)

```python
async def process_pdf(file: UploadFile) -> dict[str, str]:
    return {"status": "ok"}
```

### Naming Conventions
- **Functions/Variables**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Endpoints**: kebab-case in URLs, snake_case in Python

```python
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

class DocumentEmbedder:
    def process_document(self, document_id: str) -> None:
        pass

@app.post("/upload-document")
async def upload_document(file: UploadFile) -> dict:
    pass
```

### Async/Await
- All FastAPI route handlers MUST be async
- Use async for I/O operations (file reading, database, API calls)
- Use `asyncio` utilities when needed

```python
@app.post("/query")
async def query_endpoint(query: str) -> dict:
    results = await chroma_client.query(query)
    return {"results": results}
```

### Error Handling
- For MVP: Use simple error handling with try/except
- Use print() for debugging and error output
- Return appropriate HTTP status codes from FastAPI
- Don't over-engineer error handling

```python
@app.post("/ingest")
async def ingest_document(file: UploadFile):
    try:
        content = await file.read()
        print(f"Processing file: {file.filename}, size: {len(content)}")
        # Process content
        return {"status": "success"}
    except Exception as e:
        print(f"Error processing file: {e}")
        raise HTTPException(status_code=400, detail=str(e))
```

### FastAPI Patterns
- Use Pydantic models for request bodies
- Use path/query parameters with type hints
- Return dict or Pydantic models from routes

```python
class QueryRequest(BaseModel):
    query: str
    limit: int = 10

@app.post("/search")
async def search(request: QueryRequest, book_id: str | None = None) -> list[dict]:
    results = await search_chroma(request.query, limit=request.limit, book_id=book_id)
    return results
```

### ChromaDB Usage
- Use PersistentClient for local development
- Store embeddings in local directory (default: `./chroma_db`)
- Use metadata for filtering (e.g., by book/source)

```python
client = PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("documents")

# Add document with metadata
collection.add(
    documents=[text],
    metadatas=[{"source": "book1.pdf", "page": 1}],
    ids=["doc1"]
)

# Query with metadata filter
results = collection.query(
    query_texts=["search term"],
    where={"source": "book1.pdf"}
)
```

### File Organization
- Keep main.py for FastAPI app initialization and root routes
- Organize features by function (e.g., `ingest.py`, `search.py`)
- Use separate modules for database operations, PDF processing, etc.

### Docker Considerations
- App runs on `$PORT` environment variable (default 8000)
- Uses Hypercorn as ASGI server: `hypercorn main:app --bind 0.0.0.0:$PORT`
- Ensure all dependencies are in pyproject.toml

### Performance Notes
- Batch ChromaDB operations when possible
- Use async file operations for PDF uploads
- Consider caching frequent queries in production

---

## Testing

**Do not write unit tests unless explicitly requested.** This is an MVP project. Manual testing with the API endpoints is sufficient.

If tests are added in the future, they would use:
```bash
# Run all tests (when implemented)
pytest

# Run single test file
pytest tests/test_specific.py

# Run single test
pytest tests/test_specific.py::test_function_name -v
```

---

## Common Patterns

### PDF Processing
```python
from PyPDF2 import PdfReader

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text
```

### OpenAI Embeddings
```python
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
```

### File Upload Endpoint
```python
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files allowed")
    
    content = await file.read()
    text = extract_text_from_pdf(content)
    embedding = get_embedding(text)
    
    # Store in ChromaDB
    collection.add(
        documents=[text],
        metadatas=[{"filename": file.filename}],
        ids=[f"doc_{time.time()}"]
    )
    
    return {"status": "uploaded", "filename": file.filename}
```
