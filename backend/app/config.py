"""Application configuration via environment variables."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parents[1]


def _normalize_windows_path(path_str: str) -> str:
    normalized = path_str.replace("\\", "/")
    if normalized.startswith("/mnt/"):
        _, _, drive, *rest = normalized.split("/")
        drive = drive.upper()
        remainder = "/".join(rest)
        return f"{drive}:\\" + remainder.replace("/", "\\")
    if normalized.startswith("\\mnt\\"):
        drive = normalized[5].upper()
        remainder = normalized[7:]
        return f"{drive}:\\{remainder}"
    return path_str


def _default_stockfish_path() -> str:
    path = BASE_DIR / "bin" / ("stockfish.exe" if os.name == "nt" else "stockfish")
    resolved = str(path.resolve())
    if os.name == "nt" or "PROGRAMFILES" in os.environ:
        resolved = _normalize_windows_path(resolved)
    return resolved


class Settings(BaseSettings):
    api_prefix: str = "/api/v1"
    project_name: str = "Chessica API"
    allow_origins: list[str] = ["http://localhost:4173", "https://chessica-gamma.vercel.app"]
    websocket_url: str = "wss://localhost:8000"
    database_url: str = "sqlite:///../chessica.db"
    redis_url: str | None = None
    engine_default_depth: int = 3
    stockfish_path: str = _default_stockfish_path()
    engine_move_time_limit: float = 0.6
    coach_llm_url: str | None = None
    coach_llm_api_key: str | None = None
    coach_llm_model: str = "mistral:instruct"


settings = Settings()
