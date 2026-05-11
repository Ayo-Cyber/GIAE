"""Database engine + session factory.

Postgres in production / Docker; SQLite is supported as a fallback for local
single-process dev (set DATABASE_URL=sqlite:///./giae_api.db).

The Celery worker is sync (Biopython, pyhmmer, torch are all blocking C code),
so we deliberately stick with the sync SQLAlchemy engine. An async engine would
buy nothing here and force a rewrite of the worker.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://giae:giae@localhost:5432/giae",
)

_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    poolclass=None if _is_sqlite else QueuePool,
    pool_size=10 if not _is_sqlite else 0,
    max_overflow=20 if not _is_sqlite else 0,
    pool_pre_ping=not _is_sqlite,
    pool_recycle=1800 if not _is_sqlite else -1,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
