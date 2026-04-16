"""Application settings loaded from environment variables."""

from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings for API, bot, and database."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Arcana Bot"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    bot_token: str = "replace-with-real-bot-token"
    bot_mode: Literal["polling", "webhook"] = "polling"
    webhook_base_url: str = "https://example.com"
    webhook_path: str = "/telegram/webhook"
    webhook_secret_token: str = ""

    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "arcana_bot"
    db_user: str = "arcana_user"
    db_password: str = "arcana_password"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy DSN for PostgreSQL."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def alembic_database_url(self) -> str:
        """Sync DSN often used by Alembic migrations."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def webhook_url(self) -> str:
        """Full webhook URL for Telegram."""
        return f"{self.webhook_base_url.rstrip('/')}/{self.webhook_path.lstrip('/')}"


settings = Settings()
