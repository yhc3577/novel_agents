from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "novel-agents"
    debug: bool = False
    api_prefix: str = "/api"

    database_url: str = "postgresql+asyncpg://novel:novel@localhost:5432/novel_agents"

    # KV 缓存/锁（US-28）：redis_url 非空 → RedisStore；否则 → PG 回源；kv_cache_enabled=false → NullStore（禁用）
    redis_url: str | None = None
    kv_cache_enabled: bool = True

    jwt_secret: str = "dev-secret-change-me-please-set-a-random-32b-plus-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # providers.api_key 加密密钥（Fernet）。未显式设置时，开发环境由 jwt_secret 派生。
    fernet_key: str | None = None

    models_yaml: str = "config/models.yaml"

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
