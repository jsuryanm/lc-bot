# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

LangChain Docs Copilot: multi-agent RAG assistant over the LangChain documentation. Python 3.12+, managed with `uv`. Early stage: only `app/core` and `app/rag` exist. `main.py` is a stub. `tests/` is empty.

[docs/1_setup.md](docs/1_setup.md) and [docs/2_config.md](docs/2_config.md) describe the **target** design, including `app/api`, `app/agent`, `app/cache`, `ui/app.py`, and `evals/`. None of those exist yet. Treat the docs as a plan, not as current state. They also use older names, e.g. `pip install -e`, `02-configuration.md`, and an `anthropic:` default model that differs from the code.

## Commands

```bash
uv venv && uv sync                      # install (dev extras: uv sync --extra dev)
./scripts/get_docs.sh                   # clone langchain-ai/docs into data/langchain-docs
docker compose -f docker-compose.dev.yml up -d   # Qdrant :6333, Postgres :5432, Redis :6379

python -m app.rag.ingest build --repo data/langchain-docs --dry-run   # planned CLI; ingest.py is still a WIP stub
pytest -q                               # asyncio_mode=auto, testpaths=tests
pytest tests/path/test_x.py::test_name  # single test
ruff check . && ruff format .           # line-length 100, rules E,F,I,B,UP (E501, B008 ignored)
```

`data/` holds the cloned docs repo (with its own unrelated Python scripts). `ruff` excludes it. Don't edit or lint it.

## Architecture

**Config** ([app/core/config.py](app/core/config.py)): a single pydantic-settings `Settings`, read from env or `.env`, cached by `get_settings()`. Models are `"provider:model"` strings passed to LangChain's `init_chat_model` / `init_embeddings`. Optional tools (Tavily, GitHub MCP, issue filing) are disabled when their settings are empty. `APP_ENV=prod` refuses the default `API_KEY`.

**Models** ([app/core/models.py](app/core/models.py)): `embeddings(cache=True)` wraps the dense embedder in `CacheBackedEmbeddings` backed by `LocalFileStore` (sha256 keys, namespaced by model name), so re-ingestion never re-embeds unchanged text.

**RAG** (`app/rag/`):
- [mdx.py](app/rag/mdx.py): parses Mintlify MDX pages into `Page` objects (frontmatter, per-language splitting for python/javascript, MDX cleanup, URL derivation).
- [store.py](app/rag/store.py): Qdrant hybrid search with a dense vector plus a sparse BM25 vector (fastembed) per chunk. Payload indexes on `metadata.{language,product,page_path}`. `DocsIndex` is what agents use: hybrid search, plus fetch a whole page by reassembling its chunks.
- [ingest.py](app/rag/ingest.py): builds a new versioned collection (`docs_<version>`).

**Index versioning**: searches always go through the alias (`QDRANT_ALIAS`, default `docs_live`), never a concrete collection. Ingestion builds a fresh `docs_*` collection, then `promote()` repoints the alias atomically. Rollback is `promote(old_collection)`. Planned: keep the 3 newest versions. Changing the embedding model or chunking (2000 chars / 200 overlap) requires a full re-index, because vector dims must match.

## Gotchas

- `embeddings_model` in `Settings` defaults to `openai:text-embeddings-3-small`, with an extra "s". The correct id is `text-embedding-3-small`, and `.env.example` uses `EMBEDDING_MODEL`. Since the env var name must match the field name, `.env`'s `EMBEDDING_MODEL` is **ignored** (`extra='ignore'`). Verify before trusting it.
- `app/core/logging.py` imports `loguru`, which is not in `pyproject.toml` dependencies.
- `app/core/models.py` and `app/rag/store.py` call `get_settings()` at import time, so a missing or invalid `.env` fails at import.
