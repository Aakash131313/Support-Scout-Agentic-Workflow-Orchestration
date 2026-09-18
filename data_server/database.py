"""Database engine and session management.

`get_session` resolves the engine at call time rather than closing over a module-level
global, which is what lets the API contract tests run against an isolated in-memory
database instead of the real file.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DATABASE_PATH = Path("data_server/supportscout.db")


def database_url() -> str:
    configured = os.getenv("SUPPORT_DATA_DATABASE_URL")
    if configured:
        return configured
    DEFAULT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DATABASE_PATH}"


def build_engine(url: str | None = None):
    resolved = url or database_url()
    connect_args = {"check_same_thread": False} if resolved.startswith("sqlite") else {}
    return create_engine(resolved, connect_args=connect_args)


engine = build_engine()

#: Overridable at runtime so tests can point the app at a temporary database.
_active_engine = engine


def set_engine(new_engine) -> None:
    """Point session creation at a different engine (used by the test suite)."""
    global _active_engine
    _active_engine = new_engine


def get_engine():
    return _active_engine


def create_db_and_tables(db_engine=None) -> None:
    SQLModel.metadata.create_all(db_engine or get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
