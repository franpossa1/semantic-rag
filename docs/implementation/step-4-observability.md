# Step 4 — Observability + Streaming

## Objective

Add production-grade observability (tracing, latency logging, usage tracking) and streaming responses to the RAG pipeline. This demonstrates you think about systems in production, not just prototypes.

---

## 4.1 — Structured Tracing

### Concept

Every `/ask` request should produce a **trace** — a structured log of each pipeline step with timing information.

### Trace Structure

```python
{
    "trace_id": "uuid-here",
    "timestamp": "2026-02-05T17:00:00Z",
    "question": "How do I create a POST endpoint?",
    "library_filter": "fastapi",
    "steps": [
        {
            "name": "retrieval_semantic",
            "duration_ms": 45,
            "details": {"n_results": 20}
        },
        {
            "name": "retrieval_bm25",
            "duration_ms": 12,
            "details": {"n_results": 20}
        },
        {
            "name": "fusion_rrf",
            "duration_ms": 2,
            "details": {"n_candidates": 30}
        },
        {
            "name": "reranking",
            "duration_ms": 150,
            "details": {"n_input": 10, "n_output": 5}
        },
        {
            "name": "llm_generation",
            "duration_ms": 2300,
            "details": {
                "model": "moonshot-v1-8k",
                "prompt_tokens": 1200,
                "completion_tokens": 350,
                "total_tokens": 1550
            }
        }
    ],
    "total_duration_ms": 2509,
    "status": "success"
}
```

### Implementation: `src/services/tracer.py`

```python
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class TraceStep:
    name: str
    duration_ms: float = 0
    details: dict = field(default_factory=dict)

@dataclass
class Trace:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    question: str = ""
    steps: list[TraceStep] = field(default_factory=list)
    total_duration_ms: float = 0
    status: str = "pending"
    
    def start_step(self, name: str) -> "TraceStepContext":
        """Return a context manager that times a step."""
        return TraceStepContext(self, name)
    
    def to_dict(self) -> dict:
        """Convert trace to dict for API response and storage."""
        ...

class TraceStepContext:
    """Context manager for timing a trace step."""
    
    def __init__(self, trace: Trace, name: str):
        self.trace = trace
        self.name = name
        self.step = TraceStep(name=name)
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self.step
    
    def __exit__(self, *args):
        self.step.duration_ms = (time.perf_counter() - self.start_time) * 1000
        self.trace.steps.append(self.step)
```

### Usage in Generation Service

```python
async def ask(self, request: AskRequest) -> AskResponse:
    trace = Trace(question=request.question)
    
    with trace.start_step("retrieval") as step:
        results = search_service(query=request.question, ...)
        step.details = {"n_results": len(results.results)}
    
    with trace.start_step("llm_generation") as step:
        response = await self.client.chat.completions.create(...)
        step.details = {
            "model": self.model,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }
    
    trace.status = "success"
    trace.total_duration_ms = sum(s.duration_ms for s in trace.steps)
    
    # Store trace and include in response
    self.trace_store.append(trace)
    ...
```

---

## 4.2 — Trace Storage and Retrieval

### In-Memory Store (MVP)

```python
class TraceStore:
    """Simple in-memory trace storage. Replace with DB in production."""
    
    def __init__(self, max_traces: int = 1000):
        self.traces: list[Trace] = []
        self.max_traces = max_traces
    
    def add(self, trace: Trace) -> None:
        self.traces.append(trace)
        if len(self.traces) > self.max_traces:
            self.traces = self.traces[-self.max_traces:]
    
    def get_recent(self, limit: int = 50) -> list[dict]:
        return [t.to_dict() for t in self.traces[-limit:]]
    
    def get_stats(self) -> dict:
        """Aggregate statistics.
        
        Returns:
        {
            "total_queries": 150,
            "avg_latency_ms": 2500,
            "avg_retrieval_ms": 50,
            "avg_generation_ms": 2300,
            "p95_latency_ms": 4000,
            "queries_per_library": {"fastapi": 60, "langchain": 50, "python": 20, null: 20},
        }
        """
        ...
```

### Endpoints

```python
@app.get("/traces")
async def get_traces(limit: int = 50):
    """Get recent traces for debugging and analysis."""
    return trace_store.get_recent(limit)

@app.get("/stats")
async def get_stats():
    """Get aggregate pipeline statistics."""
    return trace_store.get_stats()
```

---

## 4.3 — Streaming Responses (SSE)

### Why Streaming

- LLM generation takes 2-5 seconds. Without streaming, the user stares at a spinner.
- With streaming, tokens appear as they're generated — much better UX.
- Shows production thinking.

### FastAPI SSE Endpoint

```python
from fastapi.responses import StreamingResponse
import json

@app.post("/ask/stream")
async def ask_stream(request: AskRequest):
    """Streaming RAG endpoint using Server-Sent Events.
    
    Returns an SSE stream with two event types:
    1. "token" events: Individual tokens as they arrive from the LLM
    2. "sources" event: The source chunks used (sent before tokens start)
    3. "done" event: Final event with trace information
    
    SSE format:
    data: {"type": "sources", "data": [...]}
    
    data: {"type": "token", "data": "The"}
    
    data: {"type": "token", "data": " answer"}
    
    data: {"type": "done", "data": {"trace_id": "...", "total_ms": 2500}}
    """
    
    async def event_generator():
        # 1. Retrieve context (non-streaming part)
        results = search_service(...)
        
        # 2. Send sources first
        yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"
        
        # 3. Stream LLM tokens
        stream = await generation_svc.client.chat.completions.create(
            ..., stream=True
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
        
        # 4. Send done event with trace
        yield f"data: {json.dumps({'type': 'done', 'data': trace_info})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
```

### Streamlit Streaming Integration

Update `app.py` to consume the SSE stream:

```python
import sseclient  # pip install sseclient-py

def stream_response(question, library, limit, temperature):
    """Consume SSE stream from /ask/stream endpoint."""
    response = requests.post(
        f"{API_URL}/ask/stream",
        json={...},
        stream=True,
    )
    
    client = sseclient.SSEClient(response)
    sources = []
    
    for event in client.events():
        data = json.loads(event.data)
        if data["type"] == "sources":
            sources = data["data"]
        elif data["type"] == "token":
            yield data["data"]  # Streamlit will display this incrementally
        elif data["type"] == "done":
            break
    
    return sources

# In the chat UI:
with st.chat_message("assistant"):
    response_placeholder = st.empty()
    full_response = ""
    for token in stream_response(prompt, ...):
        full_response += token
        response_placeholder.markdown(full_response + "▌")
    response_placeholder.markdown(full_response)
```

---

## 4.4 — Streamlit Dashboard Page (Optional Enhancement)

Add a second page to Streamlit showing pipeline health:

```python
# pages/dashboard.py (Streamlit multi-page app)

st.title("Pipeline Dashboard")

stats = requests.get(f"{API_URL}/stats").json()

col1, col2, col3 = st.columns(3)
col1.metric("Total Queries", stats["total_queries"])
col2.metric("Avg Latency", f"{stats['avg_latency_ms']:.0f}ms")
col3.metric("P95 Latency", f"{stats['p95_latency_ms']:.0f}ms")

# Latency breakdown bar chart
# Queries per library pie chart
# Recent traces table
```

---

## Dependencies

Add to `pyproject.toml`:
- `sseclient-py` (for Streamlit SSE consumption)

---

## Verification

1. **Tracing works**: `POST /ask` → response includes trace with step timings
2. **Traces endpoint**: `GET /traces` returns recent traces
3. **Stats endpoint**: `GET /stats` returns aggregate metrics
4. **Streaming works**: `POST /ask/stream` returns SSE events progressively
5. **Streamlit streaming**: Chat UI shows tokens appearing one by one
6. **Latency breakdown**: Can identify which step (retrieval vs generation) is the bottleneck
