# Step 3 — Evaluation Pipeline (RAGAS)

## Objective

Build an automated evaluation system that measures the quality of the RAG pipeline using established metrics. This demonstrates engineering maturity — you don't just build a system, you can measure and improve it.

---

## Why Evaluation Matters

Without evaluation, you can't answer:
- "Is hybrid search actually better than semantic-only?"
- "Does re-ranking improve answer quality?"
- "Is 5 chunks better than 3?"
- "Did my last change make things better or worse?"

Evaluation turns subjective "this seems good" into objective metrics.

---

## Framework: RAGAS

RAGAS (Retrieval Augmented Generation Assessment) is the standard framework for evaluating RAG systems. It provides metrics that measure different aspects of quality.

### Core Metrics

| Metric | What it Measures | Range |
|--------|-----------------|-------|
| **Faithfulness** | Is the answer grounded in the retrieved context? (no hallucinations) | 0–1 |
| **Answer Relevancy** | Is the answer relevant to the question? | 0–1 |
| **Context Precision** | Are the retrieved chunks relevant to the question? (retrieval quality) | 0–1 |
| **Context Recall** | Does the retrieved context contain all info needed to answer? | 0–1 |

### Dependencies

Add to `pyproject.toml`:
- `ragas`
- `datasets` (Hugging Face datasets — required by RAGAS)

---

## 3.1 — Evaluation Dataset

Create a hand-curated dataset of question-answer-context triples. Store as JSON in `data/eval/`.

### File: `data/eval/eval_dataset.json`

```json
{
  "questions": [
    {
      "id": "eval_001",
      "question": "How do I create a POST endpoint in FastAPI?",
      "ground_truth": "In FastAPI, you create a POST endpoint using the @app.post() decorator on an async function. You define the request body using a Pydantic model.",
      "expected_library": "fastapi",
      "difficulty": "easy"
    },
    {
      "id": "eval_002",
      "question": "What is a LangChain chain and how do I create one?",
      "ground_truth": "A LangChain chain is a sequence of calls to components like LLMs, tools, or other chains. You can create one using the LCEL (LangChain Expression Language) pipe operator or the legacy Chain classes.",
      "expected_library": "langchain",
      "difficulty": "medium"
    },
    {
      "id": "eval_003",
      "question": "How do I handle path parameters and query parameters together in FastAPI?",
      "ground_truth": "In FastAPI, path parameters are defined in the route path with curly braces and as function arguments with type hints. Query parameters are any function arguments not in the path. FastAPI automatically distinguishes between them.",
      "expected_library": "fastapi",
      "difficulty": "easy"
    },
    {
      "id": "eval_004",
      "question": "What are the different types of memory in LangChain?",
      "ground_truth": "LangChain provides several memory types including ConversationBufferMemory (stores full history), ConversationSummaryMemory (stores summaries), ConversationBufferWindowMemory (stores last K interactions), and ConversationEntityMemory (tracks entities).",
      "expected_library": "langchain",
      "difficulty": "medium"
    },
    {
      "id": "eval_005",
      "question": "How do Python list comprehensions work?",
      "ground_truth": "List comprehensions provide a concise way to create lists. The syntax is [expression for item in iterable if condition]. They can include multiple for clauses and optional if clauses for filtering.",
      "expected_library": "python",
      "difficulty": "easy"
    }
  ]
}
```

**Recommendation**: Create 20-30 questions covering:
- 8-10 per library (balanced coverage)
- Mix of easy, medium, hard difficulty
- Some cross-library questions ("How would I use LangChain with FastAPI?")
- Some questions that the docs DON'T cover (to test faithfulness — should say "I don't know")

---

## 3.2 — Evaluation Service

### File: `src/services/evaluation.py`

```python
import json
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset
from src.services.generation import GenerationService
from src.services.search import search_service
from src.models.generation import AskRequest

class EvaluationService:
    """Automated evaluation of the RAG pipeline using RAGAS metrics."""

    def __init__(self, generation_svc: GenerationService, db):
        self.generation_svc = generation_svc
        self.db = db

    def load_eval_dataset(self, path: str = "data/eval/eval_dataset.json") -> list[dict]:
        """Load the evaluation dataset from JSON."""
        with open(path) as f:
            return json.load(f)["questions"]

    async def generate_eval_samples(self, questions: list[dict]) -> dict:
        """Run the RAG pipeline on each eval question and collect results.
        
        For each question:
        1. Call search_service to get retrieved contexts
        2. Call generation_svc.ask() to get the generated answer
        3. Store: question, answer, contexts, ground_truth
        
        Returns a dict in RAGAS expected format:
        {
            "question": [...],
            "answer": [...],
            "contexts": [[...], [...], ...],
            "ground_truth": [...]
        }
        """
        ...

    async def run_evaluation(self, eval_path: str = "data/eval/eval_dataset.json") -> dict:
        """Run full evaluation pipeline.
        
        1. Load eval dataset
        2. Generate answers for all questions
        3. Convert to Hugging Face Dataset format
        4. Run RAGAS evaluate() with metrics:
           - faithfulness
           - answer_relevancy
           - context_precision
           - context_recall
        5. Return results as dict with overall scores and per-question scores
        
        Returns:
        {
            "overall": {
                "faithfulness": 0.85,
                "answer_relevancy": 0.90,
                "context_precision": 0.75,
                "context_recall": 0.80,
            },
            "per_question": [
                {
                    "id": "eval_001",
                    "question": "How do I...",
                    "faithfulness": 0.9,
                    "answer_relevancy": 0.95,
                    ...
                },
                ...
            ]
        }
        """
        ...

    async def compare_configurations(
        self, 
        configs: list[dict],
        eval_path: str = "data/eval/eval_dataset.json"
    ) -> list[dict]:
        """Run evaluation with different search configurations and compare.
        
        Example configs:
        [
            {"name": "semantic_only", "search_mode": "semantic", "use_reranking": False},
            {"name": "hybrid", "search_mode": "hybrid", "use_reranking": False},
            {"name": "hybrid_reranked", "search_mode": "hybrid", "use_reranking": True},
        ]
        
        This is incredibly valuable for demonstrating that your improvements 
        (hybrid search, re-ranking) actually improve quality with numbers.
        """
        ...
```

---

## 3.3 — Evaluation Endpoint

Add to FastAPI:

```python
@app.post("/evaluate")
async def evaluate_rag(eval_path: str = "data/eval/eval_dataset.json"):
    """Run RAGAS evaluation on the eval dataset.
    
    Returns overall metrics and per-question scores.
    Warning: This is slow (calls LLM for each question + RAGAS metrics).
    """
    ...
```

---

## 3.4 — Evaluation Notebook

Create `notebooks/evaluation.ipynb` for interactive evaluation and visualization:

1. **Cell 1**: Run evaluation, get results
2. **Cell 2**: Display overall metrics as a bar chart
3. **Cell 3**: Per-question heatmap (questions × metrics)
4. **Cell 4**: Compare configurations (semantic vs hybrid vs hybrid+reranking)
5. **Cell 5**: Identify worst-performing questions for improvement

Use `matplotlib` (already in pyproject.toml) for visualizations.

---

## RAGAS Configuration Note

RAGAS uses an LLM internally to compute some metrics (faithfulness, answer_relevancy). You need to configure it to use Kimi 2.5 or another LLM:

```python
from ragas.llms import LangchainLLMWrapper
from langchain_openai import ChatOpenAI

# Use Kimi 2.5 as the evaluator LLM
eval_llm = ChatOpenAI(
    model="moonshot-v1-8k",
    openai_api_key=settings.kimi_api_key,
    openai_api_base=settings.kimi_base_url,
)

# Pass to RAGAS
result = evaluate(
    dataset=dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=LangchainLLMWrapper(eval_llm),
)
```

**Important**: This may require adding `langchain-openai` to dependencies, or check if RAGAS supports direct OpenAI client configuration.

---

## Verification

1. **Eval dataset exists**: `data/eval/eval_dataset.json` with 20+ questions
2. **Evaluation runs**: `POST /evaluate` returns metrics without errors
3. **Metrics are reasonable**: Faithfulness > 0.7, Answer Relevancy > 0.7 for a working system
4. **Comparison works**: Can compare semantic vs hybrid and see numeric differences
5. **Notebook renders**: Evaluation notebook produces charts

---

## Interview Talking Points

- "I evaluate my RAG with RAGAS metrics: faithfulness, answer relevancy, context precision, and context recall"
- "Hybrid search improved context precision by X% over semantic-only"
- "Re-ranking improved faithfulness by Y% because it provides more relevant context to the LLM"
- "I created a curated evaluation dataset to ensure reproducible measurements"
