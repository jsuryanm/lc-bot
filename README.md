# LangChain Docs-Copilot 

## 1. Setup 
- Setup python virtual environment with uv package manager
Commands 
```
uv venv
uv sync
```

- Run script `get_docs.sh` to download the langchain documentation

For local development run `docker-compose.dev.yml`  file to start services (postgres, redis, qdrant):
```
docker compose -f docker-compose.dev.yml up -d
```

## 2. Ingesting the documentation
Builds Qdrant index from clone of `langchain-ai/docs`

```
python -m app.rag.ingest build --repo data/langchain-docs [--dry-run] [--no-switch]
    python -m app.rag.ingest list
    python -m app.rag.ingest switch docs_202610301200_abc1234     # also the rollback command
```

