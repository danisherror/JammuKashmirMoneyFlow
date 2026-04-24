from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    secret_key: str = "dev-secret-key"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/jk_money_flow"
    sync_database_url: str = "postgresql://postgres:password@localhost:5432/jk_money_flow"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Scheduler
    scheduler_enabled: bool = True
    mgnrega_fetch_hour: int = 6
    cga_fetch_day: int = 26

    # Cache TTLs (seconds)
    cache_ttl_short: int = 1800
    cache_ttl_medium: int = 86400
    cache_ttl_long: int = 604800

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
