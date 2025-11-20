"""Lightweight schema helpers for incremental changes."""

from __future__ import annotations

from typing import Set

from sqlalchemy import text
from sqlalchemy.engine import Engine

DEFAULT_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def ensure_multiplayer_columns(engine: Engine) -> None:
    """
    Add multiplayer-related columns to sessions if they are missing.
    Works for SQLite and Postgres.
    """
    with engine.begin() as conn:
        dialect = conn.dialect.name
        existing: Set[str] = set()
        if dialect == "sqlite":
            rows = conn.execute(text("PRAGMA table_info(sessions)")).mappings()
            existing = {row["name"] for row in rows}
        else:
            rows = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'sessions'"
                )
            ).mappings()
            existing = {row["column_name"] for row in rows}

        def add_column(sql: str) -> None:
            conn.execute(text(f"ALTER TABLE sessions ADD COLUMN {sql}"))

        if "player_white_id" not in existing:
            add_column("player_white_id TEXT")
        if "player_black_id" not in existing:
            add_column("player_black_id TEXT")
        if "is_multiplayer" not in existing:
            add_column("is_multiplayer BOOLEAN NOT NULL DEFAULT 0")
        if "result" not in existing:
            add_column("result TEXT")
        if "winner" not in existing:
            add_column("winner TEXT")
        if "initial_fen" not in existing:
            add_column(f"initial_fen TEXT NOT NULL DEFAULT '{DEFAULT_START_FEN}'")
