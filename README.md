## Local development with Docker

### Requirements
- Docker Desktop installed and running.

### Run the app with Docker Compose
1. Create the `.env` file at the repo root (already included in this repo):
   ```env
   PORT=8000
   ```
2. Build and start:
   ```bash
   docker compose up --build
   ```
3. Open in the browser:
   ```
   http://localhost:8000/
   ```

### Stop containers
```bash
docker compose down
```

### Run with Docker only (no compose)
```bash
docker build -t semantic-rag .
docker run --rm -p 8000:8000 semantic-rag
```
