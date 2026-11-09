from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Instagram Backend"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"
    database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    auth_jwt_secret: str | None = None
    auth_jwt_issuer: str = "instagram-backend"
    auth_jwt_audience: str = "instagram-api"
    auth_access_token_ttl_seconds: int = 900
    auth_refresh_token_ttl_days: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
