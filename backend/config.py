from pydantic import model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    secret_key: str = "dev-secret-key"
    log_level: str = "INFO"
    sql_echo: bool = False            # log every SQL statement (noisy; for debugging)
    # Seed made-up budget allocations for local development (database/demo_data.py). Rows are
    # stored with is_demo=true and the dashboard shows a red "DEMO DATA — NOT REAL" banner.
    demo_mode: bool = False

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

    # Alerts & Notifications
    alert_telegram_token: str | None = None
    alert_telegram_chat_id: str | None = None
    alert_email_smtp_url: str | None = None
    critical_gap_threshold_pct: int = 20
    warning_gap_threshold_pct: int = 40

    # Saved copies of source documents (PDF/HTML/JSON), named by SHA-256
    raw_snapshot_dir: str = "raw_snapshots"

    # AI Integration
    gemini_api_key: str | None = None

    @model_validator(mode="after")
    def _no_demo_in_production(self):
        if self.demo_mode and self.app_env.lower() == "production":
            raise ValueError("DEMO_MODE=true is not allowed when APP_ENV=production")
        return self

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
