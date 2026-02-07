# Step 1.1 — Fetch Technical Documentation

## Objective

Download raw Markdown documentation from three libraries (LangChain, FastAPI, Python) and store them locally in `raw/docs/{library}/` for later processing by the ingest pipeline.

## Target Sources

### 1. LangChain
- **Repo**: `langchain-ai/langchain`
- **Docs path**: `docs/docs/` (Markdown files)
- **What to download**: All `.md` and `.mdx` files recursively
- **Expected content**: Concepts, how-to guides, API references, tutorials
- **URL pattern**: `https://api.github.com/repos/langchain-ai/langchain/git/trees/master?recursive=1` to list files, then raw download

### 2. FastAPI
- **Repo**: `fastapi/fastapi`
- **Docs path**: `docs/en/docs/` (Markdown files)
- **What to download**: All `.md` files recursively
- **Expected content**: Tutorials, advanced guides, API reference, deployment docs

### 3. Python
- **Repo**: `python/cpython`
- **Docs path**: `Doc/` (reStructuredText `.rst` files)
- **Alternative**: Use pre-converted markdown from `python/python-docs-community` or download `.rst` and convert
- **Recommended approach**: Use the Python official docs in HTML and convert to text, OR use a curated subset (stdlib tutorial, language reference) to keep scope manageable
- **Simpler alternative**: Download the Python tutorial section only (`Doc/tutorial/`) — this is sufficient and keeps the dataset balanced

## Output Structure

```
raw/
└── docs/
    ├── langchain/
    │   ├── concepts/
    │   │   ├── architecture.md
    │   │   └── ...
    │   ├── how_to/
    │   │   └── ...
    │   └── tutorials/
    │       └── ...
    ├── fastapi/
    │   ├── tutorial/
    │   │   ├── first-steps.md
    │   │   └── ...
    │   └── advanced/
    │       └── ...
    └── python/
        ├── tutorial/
        │   ├── introduction.md
        │   └── ...
        └── stdlib/
            └── ...
```

## Implementation: `src/services/scraper.py`

### Class: `DocsScraper`

```python
class DocsScraper:
    """Downloads documentation from GitHub repos."""

    def __init__(self, output_dir: str = "raw/docs"):
        self.output_dir = output_dir

    async def fetch_github_tree(self, owner: str, repo: str, branch: str = "main") -> list[dict]:
        """Fetch the full file tree of a GitHub repo using the Git Trees API.
        
        Uses: GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1
        Returns list of file entries with path, type, size.
        No auth needed for public repos (but rate-limited to 60 req/hr).
        If the user has a GITHUB_TOKEN env var, use it for higher limits.
        """
        ...

    async def download_file(self, owner: str, repo: str, branch: str, file_path: str) -> str:
        """Download a single raw file from GitHub.
        
        Uses: https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}
        Returns the file content as string.
        """
        ...

    async def fetch_library_docs(self, library: str, owner: str, repo: str, docs_path: str, branch: str = "main", extensions: list[str] = [".md", ".mdx"]) -> int:
        """Download all docs for a library.
        
        1. Fetch the repo tree
        2. Filter files that start with docs_path and match extensions
        3. Download each file
        4. Save to raw/docs/{library}/ preserving directory structure
        5. Return count of files downloaded
        
        Add a small delay between requests to avoid rate limiting (0.1s).
        Print progress: "Downloading {library}: {current}/{total} files"
        """
        ...

    async def fetch_all(self) -> dict[str, int]:
        """Download docs for all three libraries.
        
        Returns dict with counts: {"langchain": 150, "fastapi": 80, "python": 30}
        """
        ...
```

### Library Configuration

Define a config dict or list at module level:

```python
LIBRARY_SOURCES = [
    {
        "library": "langchain",
        "owner": "langchain-ai",
        "repo": "langchain",
        "docs_path": "docs/docs",
        "branch": "master",
        "extensions": [".md", ".mdx"],
    },
    {
        "library": "fastapi",
        "owner": "fastapi",
        "repo": "fastapi",
        "docs_path": "docs/en/docs",
        "branch": "master",
        "extensions": [".md"],
    },
    {
        "library": "python",
        "owner": "python",
        "repo": "cpython",
        "docs_path": "Doc/tutorial",
        "branch": "main",
        "extensions": [".rst"],
    },
]
```

### Important Notes

1. **Rate limiting**: GitHub API without auth = 60 requests/hour. The tree API is 1 request, but raw file downloads count. If needed, use a `GITHUB_TOKEN` env var.
2. **RST files (Python)**: Download as-is. The ingest service will handle conversion or parse them differently. RST is still text and can be chunked.
3. **MDX files (LangChain)**: These are Markdown with JSX components. Treat as Markdown — strip JSX tags during ingestion, not here. The scraper should just save raw files.
4. **File size**: Skip files larger than 500KB (likely auto-generated or data files).
5. **Idempotency**: If the file already exists locally, skip it. Add a `--force` flag to re-download.
6. **httpx**: Use `httpx.AsyncClient` for async HTTP requests (already available via FastAPI dependencies or add to pyproject.toml).

### Dependencies

Add to `pyproject.toml` if not present:
- `httpx` (async HTTP client — may already be included via FastAPI[standard])

### Verification

After running, verify:
- `raw/docs/langchain/` has 100+ `.md`/`.mdx` files
- `raw/docs/fastapi/` has 50+ `.md` files
- `raw/docs/python/` has 10+ `.rst` files
- No empty files
- Directory structure is preserved

### Usage

The scraper should be callable both as:
1. **Imported service**: `await DocsScraper().fetch_all()`
2. **From an endpoint**: `POST /ingest/fetch-docs` (wired in step 1.5)

This step does NOT process or index the documents — it only downloads them.
