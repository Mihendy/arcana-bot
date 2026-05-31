"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings for API, bot, external integrations and storage."""

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
    logs_dir: str = "logs"
    admin_tg_id: int = 0
    daily_card_hour_msk: int = 6
    daily_card_timezone: str = "Europe/Moscow"
    bot_public_url: str = "https://t.me/arcana_r_bot"
    api_public_base_url: str
    s3_endpoint_url: str = Field(
        default="http://127.0.0.1:9000",
        validation_alias=AliasChoices("S3_ENDPOINT_URL", "MINIO_ENDPOINT"),
    )
    s3_public_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("S3_PUBLIC_BASE_URL"),
    )
    s3_access_key: str = Field(
        default="minioadmin",
        validation_alias=AliasChoices("S3_ACCESS_KEY", "MINIO_ACCESS_KEY"),
    )
    s3_secret_key: str = Field(
        default="minioadmin",
        validation_alias=AliasChoices("S3_SECRET_KEY", "MINIO_SECRET_KEY"),
    )
    s3_bucket: str = Field(
        default="arcana-media",
        validation_alias=AliasChoices("S3_BUCKET", "MINIO_BUCKET"),
    )
    s3_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("S3_REGION", "MINIO_REGION"),
    )
    s3_use_ssl: bool = Field(
        default=False,
        validation_alias=AliasChoices("S3_USE_SSL", "MINIO_SECURE"),
    )

    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""

    bot_token: str
    telegram_proxy: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout_seconds: float = 30.0
    premium_price_stars: int = 79
    premium_price_rub: int = 159

    vk_group_token: str = ""
    vk_group_id: int = 0
    vk_api_version: str = "5.199"
    vk_public_url: str = ""  # e.g. https://vk.com/your_group

    cards_assets_dir: str = "app/assets/cards"
    fonts_assets_dir: str = "app/assets/fonts"
    output_dir: str = "data/output"

    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "arcana_bot"
    db_user: str = "arcana_user"
    db_password: str = "arcana_password"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Build async SQLAlchemy DSN for PostgreSQL.

        Returns:
            str: Async database URL for runtime engine.
        """
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def alembic_database_url(self) -> str:
        """Build sync DSN for Alembic migrations.

        Returns:
            str: Synchronous PostgreSQL URL for migrations.
        """
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cards_assets_path(self) -> Path:
        """Resolve absolute path to tarot card image assets.

        Returns:
            Path: Cards assets directory path.
        """
        return (Path(__file__).resolve().parents[2] / self.cards_assets_dir).resolve()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fonts_assets_path(self) -> Path:
        """Resolve absolute path to fonts assets directory.

        Returns:
            Path: Fonts assets directory path.
        """
        return (Path(__file__).resolve().parents[2] / self.fonts_assets_dir).resolve()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def output_dir_path(self) -> Path:
        """Resolve absolute path to generated spread output directory.

        Returns:
            Path: Output directory for generated files.
        """
        return (Path(__file__).resolve().parents[2] / self.output_dir).resolve()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def logs_dir_path(self) -> Path:
        """Resolve absolute path to logs directory.

        Returns:
            Path: Logs directory path.
        """
        return (Path(__file__).resolve().parents[2] / self.logs_dir).resolve()

settings = Settings()
