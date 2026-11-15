from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Instagram Backend"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"
    database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    # No committed or implicit fallback: deployments must supply this secret.
    auth_jwt_secret: str | None = None
    auth_jwt_issuer: str = "instagram-backend"
    auth_jwt_audience: str = "instagram-api"
    auth_access_token_ttl_seconds: int = 900
    auth_refresh_token_ttl_days: int = 30

    media_storage_endpoint_url: str = "http://localhost:9000"
    media_storage_public_endpoint_url: str = "http://localhost:9000"
    media_storage_bucket: str = "instagram-media"
    media_storage_region: str = "us-east-1"
    media_storage_access_key: str = "minioadmin"
    media_storage_secret_key: str = "minioadmin"
    media_upload_ttl_seconds: int = 900
    media_download_ttl_seconds: int = 900
    media_max_upload_bytes: int = 10_485_760
    media_cleanup_grace_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def validate_security_settings() -> None:
    secret = settings.auth_jwt_secret
    if (
        secret is None
        or len(secret.encode("utf-8")) < 32
        or secret == "replace-with-a-random-secret-at-least-32-bytes"
    ):
        raise RuntimeError(
            "AUTH_JWT_SECRET must be explicitly configured with a random "
            "value of at least 32 bytes; do not use the .env.example placeholder"
        )
