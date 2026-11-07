from functools import lru_cache 

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        case_sensitive=False,
        extra='ignore',
        encoding='utf-8'
    ) 

    app_env: str = "dev"
    api_key: str = "dev-key"
    rate_limit_per_minute: int = 20

    # llms
    chat_model: str = "openai:gpt-5-mini"
    small_model: str = "openai:gpt-5-nano"
    fallback_model: str = "openai:gpt-5-nano"
    embeddings_model: str = "openai:text-embeddings-3-small"

    qdrant_url: str = "http://localhost:6333"
    qdrant_alias: str = "docs_live"
    postgres_url: str | None = None  # None -> in-memory checkpoints and memory (dev only)
    redis_url: str | None = None  # None -> caches and rate limit are off

    # Optional tools: each is skipped when its setting is empty.
    tavily_api_key: str | None = None
    github_mcp_url: str | None = None
    github_mcp_token: str | None = None
    file_issue_repo: str | None = None
    file_issue_token: str | None = None
    issue_filer_ids: str = ""  # comma-separated user ids

    # Seconds to keep a cached result, per tool. A tool not listed here is never cached.
    tool_cache_ttls: dict[str, int] = {
        "tavily_search": 900,
        "list_issues": 300,
        "search_issues": 300,
    }
    
    answer_cache_ttl: int = 3600
    embedding_cache_dir: str = "data/embedding_cache"

    @model_validator(mode='after')
    def _no_default_key(self) -> "Settings":
        if self.app_env == "prod" and self.api_key == "dev-key":
            raise ValueError("Set the API_KEY to a real secret when APP_ENV='prod'")
        return self 

    @property
    def issue_filers(self) -> set[str]:
        return {u.strip() for u in self.issue_filer_ids.split(",") if u.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

        


