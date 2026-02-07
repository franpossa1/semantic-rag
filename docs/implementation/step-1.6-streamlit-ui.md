# Step 1.6 — Streamlit Chat UI

## Objective

Build a Streamlit-based chat interface that connects to the FastAPI backend, allowing users to ask questions about technical documentation and see answers with source citations in real time.

## Location

`app.py` in the project root (same repo, separate process).

## Dependencies

Add to `pyproject.toml`:
- `streamlit` (latest)
- `requests` (for calling FastAPI — should already be available, but add explicitly if not)

---

## Implementation: `app.py`

### App Structure

```python
import streamlit as st
import requests

API_URL = "http://localhost:8000"  # FastAPI backend

# --- Page Config ---
st.set_page_config(
    page_title="Semantic RAG — Technical Docs Assistant",
    page_icon="📚",
    layout="wide",
)

# --- Sidebar ---
# Library filter selector
# Health status display
# Document count

# --- Main Chat Area ---
# Chat history
# Input box
# Answer + Sources display
```

### Sidebar

```python
with st.sidebar:
    st.title("📚 Semantic RAG")
    st.markdown("Technical documentation assistant for **LangChain**, **FastAPI**, and **Python**.")
    
    st.divider()
    
    # Library filter
    library_filter = st.selectbox(
        "Filter by library",
        options=["All", "langchain", "fastapi", "python"],
        index=0,
    )
    # Convert "All" to None for the API
    selected_library = None if library_filter == "All" else library_filter
    
    # Number of context chunks
    num_chunks = st.slider("Context chunks", min_value=1, max_value=10, value=5)
    
    # Temperature
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.3, step=0.1)
    
    st.divider()
    
    # Health check / stats
    try:
        health = requests.get(f"{API_URL}/health", timeout=5).json()
        st.metric("Documents Indexed", health.get("documents_indexed", 0))
        st.caption(f"Embedding: {health.get('embedding_model', 'N/A')}")
        st.caption(f"LLM: {health.get('llm_model', 'N/A')}")
        st.success("Backend connected")
    except Exception:
        st.error("Backend not reachable. Start FastAPI server first.")
```

### Chat Interface

```python
# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message:
            with st.expander(f"📖 Sources ({len(message['sources'])})"):
                for source in message["sources"]:
                    st.markdown(f"**{source['library']}** — `{source['source_file']}`")
                    st.markdown(f"*{source['section']} > {source['subsection']}*")
                    st.caption(f"Relevance: {source['relevance_score']:.2f}")
                    st.code(source['text'][:500], language=None)  # Preview
                    st.divider()

# Chat input
if prompt := st.chat_input("Ask about LangChain, FastAPI, or Python..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Call the /ask endpoint
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{API_URL}/ask",
                    json={
                        "question": prompt,
                        "library": selected_library,
                        "limit": num_chunks,
                        "temperature": temperature,
                    },
                    timeout=60,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data["answer"]
                    sources = data.get("sources", [])
                    
                    # Display answer
                    st.markdown(answer)
                    
                    # Display sources in expander
                    if sources:
                        with st.expander(f"📖 Sources ({len(sources)})"):
                            for source in sources:
                                st.markdown(f"**{source['library']}** — `{source['source_file']}`")
                                st.markdown(f"*{source['section']} > {source['subsection']}*")
                                st.caption(f"Relevance: {source['relevance_score']:.2f}")
                                st.code(source['text'][:500], language=None)
                                st.divider()
                    
                    # Save to history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                    })
                else:
                    error_msg = f"Error: {response.status_code} — {response.text}"
                    st.error(error_msg)
                    
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to backend. Make sure FastAPI is running on port 8000.")
            except requests.exceptions.Timeout:
                st.error("Request timed out. The LLM may be taking too long.")
            except Exception as e:
                st.error(f"Unexpected error: {e}")
```

---

## Running

### Development (two terminals):

**Terminal 1 — FastAPI backend:**
```bash
fastapi dev main:app
```

**Terminal 2 — Streamlit frontend:**
```bash
streamlit run app.py --server.port 8501
```

### Docker Compose (future — Step 5):

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./raw:/app/raw

  frontend:
    build: .
    command: streamlit run app.py --server.port 8501 --server.address 0.0.0.0
    ports:
      - "8501:8501"
    environment:
      - API_URL=http://api:8000
    depends_on:
      - api
```

---

## UI Features

1. **Chat history**: Persisted in `st.session_state` during the session
2. **Source citations**: Expandable section below each answer showing the chunks used
3. **Library filter**: Sidebar dropdown to scope search to a specific library
4. **Adjustable parameters**: Number of context chunks and temperature
5. **Health indicator**: Shows if backend is connected and how many docs are indexed
6. **Error handling**: Clear messages for connection errors, timeouts, and API errors

---

## UX Notes

- The spinner ("Thinking...") appears while waiting for the API response
- Sources show the library name, file path, section hierarchy, and a preview of the chunk text
- Relevance score is displayed so users understand the retrieval quality
- Chat input is disabled while processing (Streamlit default behavior)

---

## Configuration

The `API_URL` should be configurable via environment variable for Docker:

```python
import os
API_URL = os.getenv("API_URL", "http://localhost:8000")
```

---

## Verification

1. **Start both servers** (FastAPI + Streamlit)
2. **Sidebar shows**: Backend connected, document count > 0
3. **Ask a question**: "How do I create a POST endpoint in FastAPI?" → answer appears with sources
4. **Filter by library**: Select "langchain" → ask a question → sources only from LangChain
5. **Chat history**: Previous messages remain visible
6. **Error handling**: Stop FastAPI → Streamlit shows "Backend not reachable" error
7. **Multiple questions**: Have a conversation with multiple questions
