# Step 1.4 — Generation Service (RAG Chain with Kimi 2.5)

## Objective

Build the generation layer that takes a user question, retrieves relevant documentation chunks via the search service, constructs a prompt with context, calls the Kimi 2.5 LLM, and returns a grounded answer with source citations.

## Dependencies

- `src/services/search.py` (from Step 1.3)
- `src/models/generation.py` (new — Pydantic models)
- `src/services/prompt.py` (new — prompt templates)
- `openai` package (already in pyproject.toml — Kimi 2.5 is OpenAI-compatible)

---

## Kimi 2.5 API Details

Kimi 2.5 (by Moonshot AI) exposes an **OpenAI-compatible API**. Use the `openai` Python SDK with custom `base_url`.

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("KIMI_API_KEY"),
    base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
)

response = await client.chat.completions.create(
    model=os.getenv("KIMI_MODEL", "moonshot-v1-8k"),
    messages=[...],
    temperature=0.3,
    max_tokens=2048,
)
```

**Important**: Verify the exact base_url and model name with the user. Common Kimi options:
- `moonshot-v1-8k` (8K context)
- `moonshot-v1-32k` (32K context)
- `moonshot-v1-128k` (128K context)

For RAG with ~5 chunks of ~1000 chars each, `moonshot-v1-8k` is sufficient.

---

## Pydantic Models: `src/models/generation.py`

```python
from pydantic import BaseModel, Field

class AskRequest(BaseModel):
    """Request model for the /ask RAG endpoint."""
    question: str = Field(..., min_length=1, max_length=2000, description="User question in natural language")
    library: str | None = Field(default=None, description="Optional: filter context to a specific library")
    limit: int = Field(default=5, ge=1, le=10, description="Number of context chunks to retrieve")
    temperature: float = Field(default=0.3, ge=0.0, le=1.0, description="LLM temperature")

class SourceChunk(BaseModel):
    """A source document used to generate the answer."""
    text: str
    library: str
    source_file: str
    section: str
    subsection: str
    relevance_score: float

class AskResponse(BaseModel):
    """Response model for the /ask RAG endpoint."""
    question: str
    answer: str
    sources: list[SourceChunk]
    model: str
    usage: dict | None = None  # Token usage from the API if available
```

---

## Prompt Templates: `src/services/prompt.py`

```python
SYSTEM_PROMPT = """You are a helpful technical documentation assistant. You answer questions about programming libraries (LangChain, FastAPI, and Python) based ONLY on the provided context.

Rules:
1. Answer ONLY based on the provided context. If the context doesn't contain enough information to answer, say so explicitly.
2. When referencing information, mention which library and section it comes from.
3. If code examples are present in the context, include them in your answer when relevant.
4. Be concise but thorough. Use markdown formatting.
5. If the question is ambiguous, interpret it in the most useful way given the available context.
6. Never make up information that isn't in the context."""

def build_context_prompt(chunks: list[dict]) -> str:
    """Build the context section of the prompt from retrieved chunks.
    
    Format each chunk as:
    ---
    Source: {library} — {source_file} > {section} > {subsection}
    
    {chunk_text}
    ---
    
    Join all chunks with newlines.
    """
    ...

def build_user_prompt(question: str, context: str) -> str:
    """Build the user message combining context and question.
    
    Format:
    ## Context
    
    {context}
    
    ## Question
    
    {question}
    
    ## Instructions
    
    Answer the question based on the context above. Cite your sources.
    """
    ...
```

---

## Implementation: `src/services/generation.py`

### Class: `GenerationService`

```python
import os
from openai import AsyncOpenAI
from src.services.search import search_service
from src.services.prompt import SYSTEM_PROMPT, build_context_prompt, build_user_prompt
from src.models.generation import AskRequest, AskResponse, SourceChunk
from src.db.chromadb import ChromaDBHandler

class GenerationService:
    """RAG generation service: retrieve context + generate answer with LLM."""

    def __init__(self, db: ChromaDBHandler):
        self.db = db
        self.client = AsyncOpenAI(
            api_key=os.getenv("KIMI_API_KEY"),
            base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
        )
        self.model = os.getenv("KIMI_MODEL", "moonshot-v1-8k")

    async def ask(self, request: AskRequest) -> AskResponse:
        """Full RAG pipeline: retrieve → build prompt → generate → respond.
        
        Steps:
        1. Call search_service to retrieve top-K relevant chunks
           - Pass request.library as filter if provided
           - Pass request.limit as number of chunks
        
        2. Build the context from retrieved chunks using build_context_prompt()
        
        3. Build the messages array:
           messages = [
               {"role": "system", "content": SYSTEM_PROMPT},
               {"role": "user", "content": build_user_prompt(question, context)},
           ]
        
        4. Call Kimi 2.5 API:
           response = await self.client.chat.completions.create(
               model=self.model,
               messages=messages,
               temperature=request.temperature,
               max_tokens=2048,
           )
        
        5. Extract the answer: response.choices[0].message.content
        
        6. Build SourceChunk objects from the search results
        
        7. Return AskResponse with:
           - question
           - answer
           - sources (the chunks used)
           - model name
           - usage (token counts from API response, if available)
        """
        ...

    async def ask_stream(self, request: AskRequest):
        """Streaming version of ask() for real-time response.
        
        Same as ask() steps 1-3, but in step 4 use stream=True:
        
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=2048,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        
        This will be used by the Streamlit frontend (Step 1.6) and 
        the streaming endpoint (Step 4 — Observability + Streaming).
        
        For now in Step 1, implement this method but the endpoint can 
        use the non-streaming ask() version. Streaming endpoint comes in Step 4.
        """
        ...
```

---

## Error Handling

1. **No context found**: If search returns 0 results, still call the LLM but modify the user prompt to say: "No relevant documentation was found for this question. Please let the user know."

2. **API errors**: Wrap the OpenAI call in try/except. Catch `openai.APIError`, `openai.RateLimitError`, `openai.APIConnectionError`. Return a clear error message to the user.

3. **Timeout**: Set a reasonable timeout on the API call (30 seconds). The OpenAI SDK supports `timeout` parameter.

```python
self.client = AsyncOpenAI(
    api_key=os.getenv("KIMI_API_KEY"),
    base_url=os.getenv("KIMI_BASE_URL"),
    timeout=30.0,
)
```

---

## Configuration: `src/config.py`

Create a centralized config using Pydantic Settings:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    port: int = 8000
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k"
    chroma_path: str = "./data"
    embedding_model: str = "all-MiniLM-L6-v2"
    raw_docs_path: str = "raw/docs"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

**Important**: Add `pydantic-settings` to `pyproject.toml` dependencies.

All services should import `settings` from `src/config.py` instead of using `os.getenv()` directly.

---

## Verification

1. **Unit test flow**: Call `ask()` with a question like "How do I create a POST endpoint in FastAPI?" → should return an answer citing FastAPI docs with source chunks.

2. **No context scenario**: Ask "What is the best pizza in New York?" → should respond saying the context doesn't contain relevant information.

3. **Library filter**: Ask with `library="langchain"` → sources should only be from LangChain.

4. **Token usage**: Verify that the response includes token count information.

5. **Error handling**: Set an invalid API key → should return a clear error, not crash.

---

## Dependencies

Add to `pyproject.toml`:
- `pydantic-settings` (for Settings class)
- `openai` (already present)

## .env Updates

Add to `.env.example`:
```env
PORT=8000
KIMI_API_KEY=your-kimi-api-key-here
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=moonshot-v1-8k
CHROMA_PATH=./data
EMBEDDING_MODEL=all-MiniLM-L6-v2
```
