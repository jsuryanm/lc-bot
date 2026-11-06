# 2. Configuration

All settings live in `app/core/config.py` (class `Settings`). Each one is read from an environment
variable of the same name in upper case, or from `.env`. Nothing else in the code reads the
environment, with two small exceptions noted below. Copy `.env.example` to `.env` to start.

## Models

Models are `"provider:model"` strings handled by LangChain's `init_chat_model` and `init_embeddings`.
Changing provider is a config change. You also need that provider's package installed and its API key set.

| Variable | Default | Used for |
|---|---|---|
| `CHAT_MODEL` | `anthropic:claude-sonnet-5-5` | The supervisor on hard questions |
| `SMALL_MODEL` | `anthropic:claude-haiku-5-5` | Planner, easy questions, subagents, summaries, memory extraction |
| `FALLBACK_MODEL` | `openai:gpt-5.5` | Used when the chat model keeps failing |
| `EMBEDDING_MODEL` | `openai:text-embedding-3-small` | Dense vectors for docs and the answer cache |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | empty | Read by the provider packages, not by our code |

> **Important:** if you change `EMBEDDING_MODEL`, the vector size may change. Build a new index
> (`python -m app.rag.ingest build ...`). Old collections cannot be searched with a different model.
> The answer cache also stores vectors; delete the `answer_cache` collection in Qdrant after changing it.

Model names change often. Check your provider's current list before relying on the defaults.

## Services

| Variable | Default | Notes |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Vector database |
| `QDRANT_ALIAS` | `docs_live` | The name the app searches. It points at the live collection ([RAG guide](05-rag-ingestion.md)) |
| `POSTGRES_URL` | empty | Empty means in-memory checkpoints and memory (lost on restart) |
| `REDIS_URL` | empty | Empty means in-process caches and **no rate limiting** |

## App and security

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `dev` | `prod` refuses to start with the default `API_KEY` |
| `API_KEY` | `dev-key` | Shared secret sent as `X-API-Key`. The UI and API must agree |
| `RATE_LIMIT_PER_MINUTE` | `20` | Per user, needs Redis |
| `API_URL` | `http://localhost:8000` | **Read by the UI only** (`ui/app.py`), not by `Settings` |

Authentication here is a shared secret for a single-tenant demo. The caller states who the user is
with `X-User-Id`. Before exposing this to real users, replace `current_user` in `app/api/security.py`
with JWT or OAuth. Nothing else changes, because the rest of the app only sees a `User`.

## Optional tools

Each tool is **off** until its settings are filled in. Leaving them empty is a normal configuration.

| Variable | Turns on |
|---|---|
| `TAVILY_API_KEY` | Web search, restricted to LangChain domains, for the issue investigator |
| `GITHUB_MCP_URL`, `GITHUB_MCP_TOKEN` | GitHub tools loaded through `langchain.mcp` for the issue investigator. Use a **read-only** token |
| `FILE_ISSUE_REPO` (`owner/repo`), `FILE_ISSUE_TOKEN` | The `file_issue` tool. Every call needs human approval |
| `ISSUE_FILER_IDS` | Comma-separated user ids that may even see `file_issue`. Others never see it |

If the GitHub MCP server cannot be reached at startup, the app logs the error and starts without
those tools. Answers get weaker, but the app stays up.

## Caches

| Variable | Default | Meaning |
|---|---|---|
| `TOOL_CACHE_TTLS` | `{"tavily_search":900,"list_issues":300,"search_issues":300}` | JSON map of tool name to seconds. **A tool not listed is never cached** |
| `ANSWER_CACHE_TTL` | `3600` | Seconds a saved answer to a first question stays valid |
| `EMBEDDING_CACHE_DIR` | `data/embedding_cache` | Used during ingestion so unchanged text is never embedded twice |

Set `TOOL_CACHE_TTLS` as JSON in `.env`:

```
TOOL_CACHE_TTLS={"tavily_search":900,"search_issues":300}
```

Never add a tool that changes something (such as `file_issue`) to this map.
How the caches work and why each exists: [Architecture](03-architecture.md#caching).

## Tracing (optional)

| Variable | Default | Notes |
|---|---|---|
| `LANGSMITH_TRACING` | `false` | `true` sends traces to LangSmith |
| `LANGSMITH_API_KEY` | empty | Also needed for `/feedback` to attach scores to traces |
| `LANGSMITH_PROJECT` | `docs-copilot` | Project name in LangSmith |

`app/api/main.py` reads `LANGSMITH_API_KEY` directly from the environment to decide whether feedback
goes to LangSmith or only to the log.

## Production only

Used by `docker-compose.yml`. See [Deploy on AWS](08-deploy-aws.md).

| Variable | Notes |
|---|---|
| `POSTGRES_PASSWORD` | Required. Compose builds `POSTGRES_URL` from it |
| `DOMAIN` | Your domain for automatic HTTPS. Empty means plain HTTP on port 80 |
| `BASIC_AUTH_USER`, `BASIC_AUTH_HASH` | Login for the web UI, enforced by Caddy. Write each `$` in the hash as `$$` |
| `MCP_DOCS_TOKEN` | Optional bearer token for the docs MCP server |

## Fixed in code, on purpose

These are not settings because changing them changes behaviour in ways that need a code review and new tests.

| Value | Where | Why fixed |
|---|---|---|
| Model call limit 8, tool call limit 12 per run | `app/agent/supervisor.py` | Stops runaway loops |
| Answer cache similarity 0.95 | `app/cache/answers.py` | Higher means fewer but safer cache hits |
| `PROMPT_VERSION` | `app/agent/prompts.py` | Bump it when you change a prompt; old cached answers stop matching |
| Chunk size 2000 / overlap 200 characters | `app/rag/ingest.py` | Tied to the index. Changing it means re-indexing and re-running evals |
| Keep 3 newest index versions | `app/rag/ingest.py` | Rollback window |
