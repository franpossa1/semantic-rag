from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello from semantic-rag!"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/update")
async def update():
    return {"status": "Future update PDF's index"}
