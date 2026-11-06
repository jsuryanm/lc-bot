# 1. Setup

You will run the databases in Docker, the API and UI directly on your machine, and build the docs index once.

## Prerequisites

| Need | Version | Check |
|---|---|---|
| Python | 3.12 or newer | `python --version` |
| Docker with Compose v2 | any recent | `docker compose version` |
| Git | any | `git --version` |
| A model API key | Anthropic and/or OpenAI | see [Configuration](02-configuration.md) |

The default configuration uses Anthropic for chat and OpenAI for embeddings and as the fallback, so it
needs both keys. To use one provider only, change the model strings in `.env`.

## Steps

```mermaidQ
flowchart LR
    A[1. Install] --> B[2. Configure .env]
    B --> C[3. Start databases]
    C --> D[4. Get the docs]
    D --> E[5. Build the index]
    E --> F[6. Run API and UI]
```

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the tests to confirm the install. They need no API keys and no network:

```bash
pytest -q
```

### 2. Configure

```bash
cp .env.example .env
```

Open `.env` and set at least `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`. Everything else has a working
default for local use. Details: [Configuration](02-configuration.md).

### 3. Start the databases

```bash
docker compose -f docker-compose.dev.yml up -d
```

This starts Qdrant (port 6333), Postgres (5432) and Redis (6379), published to `127.0.0.1` only.
Postgres and Redis are optional: leave `POSTGRES_URL` or `REDIS_URL` empty in `.env` and the app uses
in-memory state instead. In-memory state is lost when the API restarts, so use Postgres to see real
memory and resumable conversations.

### 4. Get the LangChain docs

```bash
./scripts/get_docs.sh
```

This clones `langchain-ai/docs` into `data/langchain-docs`. Why and what is inside:
[RAG: getting and ingesting the LangChain docs](05-rag-ingestion.md).

### 5. Build the index

Check what will be indexed first. This writes nothing and costs nothing:

```bash
python -m app.rag.ingest build --repo data/langchain-docs --dry-run
```

Then build it. This calls the embedding API for every chunk. For the Python docs that is roughly
14,700 chunks and 12 million characters, which is on the order of a few million tokens. Check your
embedding provider's price first. The first run also downloads the small BM25 model that `fastembed` uses.

```bash
python -m app.rag.ingest build --repo data/langchain-docs
```

### 6. Run the API and UI

Two terminals, both with the virtual environment active:

```bash
# Terminal 1
uvicorn app.api.main:app --reload --port 8000

# Terminal 2
streamlit run ui/app.py
```

Open <http://localhost:8501> and ask: *How do I require human approval before a tool runs?*

Quick checks:

```bash
curl localhost:8000/healthz            # {"status":"ok"}
curl localhost:8000/readyz             # 200 when Qdrant and memory are reachable
```

## Try the API without the UI

```bash
curl -N localhost:8000/chat \
  -H 'X-API-Key: dev-key' -H 'X-User-Id: me' -H 'Content-Type: application/json' \
  -d '{"thread_id": "demo", "question": "How do I stream agent output?"}'
```

`-N` turns off curl's buffering so you see events as they arrive. The event types are listed in
[API and UI](06-api-and-ui.md).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `readyz` returns 503 with `qdrant: error` | Qdrant is not running | `docker compose -f docker-compose.dev.yml up -d` |
| Answers say the docs do not cover the question, for everything | No index, or the alias points nowhere | `python -m app.rag.ingest list`, then build or `switch` |
| `ValueError: Set API_KEY ...` at startup | `APP_ENV=prod` with the default key | Set a real `API_KEY` |
| 401 from the API | The UI and API use different `API_KEY` values | Make `.env` and the UI's environment match |
| A JavaScript question gets weak answers | The index was built for Python only | Rebuild with `--languages python javascript` |
| First chat is slow | Models and clients are warming up | Normal; later requests are faster |
