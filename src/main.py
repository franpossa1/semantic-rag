from fastapi import FastAPI
from pydantic import BaseModel
from src.services.search import search_service

app = FastAPI()

class QueryRequest(BaseModel):
    query: str
    limit: int = 5

@app.post("/search")
async def search(request: QueryRequest):
    return search_service(request.query, limit=request.limit)
