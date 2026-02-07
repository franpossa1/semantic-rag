# Semantic RAG — Implementation Overview

## Project Goal

Build a production-quality Retrieval-Augmented Generation (RAG) system over technical documentation (LangChain, FastAPI, Python) as an AI Engineer portfolio project.

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

## Project Structure (Target)

```
semantic-rag/
├── main.py                     # FastAPI app entry point
├── app.py                      # Streamlit frontend
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env / .env.example
├── raw/
│   └── docs/
│       ├── langchain/          # Raw markdown docs
│       ├── fastapi/
│       └── python/
├── data/                       # ChromaDB persistent storage
├── src/
│   ├── __init__.py
│   ├── config.py               # Pydantic Settings (env vars)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── search.py           # Search request/response models
│   │   └── generation.py       # Generation request/response models
│   ├── db/
│   │   ├── __init__.py
│   │   └── chromadb.py         # ChromaDB handler (refactored)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── scraper.py          # Download docs from GitHub
│   │   ├── ingest.py           # Chunking + indexing pipeline
│   │   ├── search.py           # Search with filters
│   │   ├── generation.py       # LLM generation (RAG chain)
│   │   └── prompt.py           # Prompt templates
│   └── pipeline/
│       └── __init__.py
├── notebooks/
│   └── exploration.ipynb
└── docs/
    └── implementation/         # These docs
```

## Code Conventions

- **Async**: All FastAPI route handlers MUST be async.
- **Type hints**: All function signatures with Python 3.13 union syntax (`str | None`).
- **Imports**: stdlib → third-party → local. Absolute imports.
- **Naming**: snake_case functions/vars, PascalCase classes, UPPER_SNAKE_CASE constants, kebab-case URLs.
- **Error handling**: Simple try/except, print() for debugging (MVP).
- **No tests** unless explicitly requested.
- **No loggers** — use print() for debugging.

## Implementation Phases

| Phase | Description | Docs |
|-------|-------------|------|
| **Step 1.1** | Fetch technical docs from GitHub | `step-1.1-fetch-docs.md` |
| **Step 1.2** | Ingest service (chunking + indexing) | `step-1.2-ingest-service.md` |
| **Step 1.3** | Search service with metadata filters | `step-1.3-search-service.md` |
| **Step 1.4** | Generation service (RAG chain with Kimi 2.5) | `step-1.4-generation-service.md` |
| **Step 1.5** | FastAPI endpoint wiring | `step-1.5-fastapi-wiring.md` |
| **Step 1.6** | Streamlit chat UI | `step-1.6-streamlit-ui.md` |
| **Step 2** | Hybrid Search + Re-ranking | `step-2-hybrid-search.md` |
| **Step 3** | Evaluation Pipeline (RAGAS) | `step-3-evaluation.md` |
| **Step 4** | Observability + Streaming | `step-4-observability.md` |
| **Step 5** | Polish (README, CI/CD, Docker) | `step-5-polish.md` |

## Environment Variables

```env
PORT=8000
KIMI_API_KEY=<your-kimi-api-key>
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=moonshot-v1-8k
CHROMA_PATH=./data
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## Key Decisions Log

1. **Local embeddings over OpenAI**: Shows ability to manage models locally, no API cost for embeddings.
2. **Kimi 2.5 for generation**: User has API access. OpenAI-compatible SDK.
3. **Streamlit in same repo**: Single repo for portfolio simplicity. Runs as separate process via docker-compose.
4. **ChromaDB local**: No external DB dependency. Portable.
5. **Technical docs as dataset**: Real enterprise use case. Clean data. Demonstrable to recruiters.
6. **Markdown chunking by headers**: Natural structure of documentation. Preserves context.
