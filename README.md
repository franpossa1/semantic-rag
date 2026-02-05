# Semantic RAG

A production-quality Retrieval-Augmented Generation (RAG) system built over technical documentation (LangChain, FastAPI, Python) as an AI Engineer portfolio project.

## Architecture

```
User → Streamlit (chat UI) → FastAPI (REST API)
                                 ├── POST /ingest   → Ingest Service → ChromaDB
                                 ├── POST /search   → Search Service → ChromaDB
                                 └── POST /ask      → Search Service → ChromaDB
                                                            ↓
                                                     Generation Service → Kimi 2.5 API
                                                            ↓
                                                     Response + Sources
```

## Tech Stack

| Component         | Technology                          |
|-------------------|-------------------------------------|
| Backend           | FastAPI (async)                     |
| Vector DB         | ChromaDB (PersistentClient, local)  |
| Embedding Model   | `all-MiniLM-L6-v2` (sentence-transformers, local) |
| LLM               | Kimi 2.5 (OpenAI-compatible API)    |
| Frontend          | Streamlit (same repo, separate process) |
| Data Validation   | Pydantic v2                         |
| Package Manager   | uv                                  |
| Python Version    | 3.13+                               |
| Containerization  | Docker + Docker Compose             |

## Data Sources

This RAG system indexes technical documentation from three major Python libraries:

### 1. LangChain
- **Repository**: `langchain-ai/docs`
- **Documentation Path**: `reference/python/docs/`
- **Branch**: `main`
- **File Types**: `.md`, `.mdx`
- **Content**: Concepts, how-to guides, API references, tutorials for LangChain, LangGraph, and LangSmith
- **Approximate Files**: ~180

### 2. FastAPI
- **Repository**: `fastapi/fastapi`
- **Documentation Path**: `docs/en/docs/`
- **Branch**: `master`
- **File Types**: `.md`
- **Content**: Tutorials, advanced guides, API reference, deployment docs
- **Approximate Files**: ~145

### 3. Python
- **Repository**: `python/cpython`
- **Documentation Path**: `Doc/tutorial/`
- **Branch**: `main`
- **File Types**: `.rst`
- **Content**: Official Python tutorial (stdlib, language reference)
- **Approximate Files**: ~17

## Quick Start

### Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker Desktop (optional, for containerized deployment)

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Environment

Copy `.env.example` to `.env` and set your variables:

```bash
cp .env.example .env
```

Edit `.env`:
```env
PORT=8000
KIMI_API_KEY=your-kimi-api-key-here
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=moonshot-v1-8k
CHROMA_PATH=./data
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### 3. Fetch Documentation (One-time setup)

Before running the API, download the technical documentation:

```bash
# Download all libraries (LangChain, FastAPI, Python)
python fetch_docs.py

# Or download a specific library
python fetch_docs.py --library fastapi

# Force re-download (overwrite existing files)
python fetch_docs.py --force
```

This will download ~340 documentation files to `raw/docs/` (gitignored).

### 4. Run Development Server

```bash
# Using uv
uv run dev

# Or directly
fastapi dev main:app
```

The API will be available at `http://localhost:8000`

### 5. Access API Documentation

Open your browser:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Start all services
docker compose up --build

# Stop
docker compose down
```

### Using Docker Only

```bash
# Build
docker build -t semantic-rag .

# Run
docker run --rm -p 8000:8000 --env-file .env semantic-rag
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ingest` | POST | Index documents into ChromaDB |
| `/search` | POST | Semantic search with metadata filters |
| `/ask` | POST | RAG query with generated response |
| `/health` | GET | Health check |

## Documentation Scraper

The `DocsScraper` class (`src/services/scraper.py`) handles downloading technical documentation from GitHub repositories.

### CLI Usage (Recommended)

Use the included `fetch_docs.py` script for one-line execution:

```bash
# Download all libraries
python fetch_docs.py

# Download specific library only
python fetch_docs.py --library fastapi

# Force re-download (overwrite existing)
python fetch_docs.py --force

# Custom output directory
python fetch_docs.py --output ./my_docs

# See all options
python fetch_docs.py --help
```

### Programmatic Usage

```python
from src.services.scraper import DocsScraper

# Initialize scraper
scraper = DocsScraper(output_dir="raw/docs")

# Download all configured libraries
results = await scraper.fetch_all()
# Returns: {"langchain": 184, "fastapi": 145, "python": 17}

# Download specific library
await scraper.fetch_library_docs(
    library="fastapi",
    owner="fastapi", 
    repo="fastapi",
    docs_path="docs/en/docs",
    branch="master",
    extensions=[".md"]
)
```

### Features

- **Async downloads**: Uses `httpx.AsyncClient` for concurrent requests
- **Rate limiting**: 0.1s delay between requests to avoid GitHub rate limits
- **Idempotency**: Skips existing files unless `force=True`
- **Authentication**: Supports `GITHUB_TOKEN` environment variable for higher API limits
- **Size filtering**: Skips files > 500KB (likely auto-generated)
- **Progress tracking**: Prints download progress for each library

### Configuration

Library sources are defined in `LIBRARY_SOURCES` in `src/services/scraper.py`:

```python
LIBRARY_SOURCES = [
    {
        "library": "langchain",
        "owner": "langchain-ai",
        "repo": "docs",
        "docs_path": "reference/python/docs",
        "branch": "main",
        "extensions": [".md", ".mdx"],
    },
    # ... more sources
]
```

## Project Structure

```
semantic-rag/
├── main.py                     # FastAPI app entry point
├── app.py                      # Streamlit frontend
├── pyproject.toml              # Python dependencies
├── Dockerfile                  # Container image
├── docker-compose.yml          # Multi-service orchestration
├── .env / .env.example         # Environment configuration
├── raw/                        # Downloaded docs (gitignored)
│   └── docs/                   # Generated by scraper
│       ├── langchain/
│       ├── fastapi/
│       └── python/
├── data/                       # ChromaDB persistent storage
├── src/                        # Source code
│   ├── config.py               # Pydantic settings
│   ├── models/                 # Pydantic request/response models
│   ├── db/                     # Database handlers
│   ├── services/               # Business logic
│   │   ├── scraper.py          # Documentation downloader
│   │   ├── ingest.py           # Document indexing
│   │   ├── search.py           # Semantic search
│   │   └── generation.py       # LLM generation
│   └── pipeline/               # Processing pipelines
├── notebooks/                  # Jupyter exploration
└── docs/                       # Implementation documentation
```

## Development

### Run Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
ruff format .

# Lint
ruff check .

# Type check
mypy src/
```

## License

MIT License - See LICENSE file for details.

## Author

Francisco Possamai - AI Engineer Portfolio Project
