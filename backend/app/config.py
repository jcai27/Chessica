"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_prefix: str = "/api/v1"
    project_name: str = "Chessica API"
    allow_origins: list[str] = ["*"]
    websocket_url: str = "wss://localhost:8000"
    database_url: str = "sqlite:///../chessica.db"
    redis_url: str | None = None
    engine_default_depth: int = 3


settings = Settings()
