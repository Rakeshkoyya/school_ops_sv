"""Database connection and session management."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base class."""

    pass


# Create sync engine
# Note: echo=False to disable SQL logging; use app.services.upload logger for debug logs
# Optimized for Neon serverless with pooled connections
engine = create_engine(
    str(settings.DATABASE_URL),
    echo=False,
    pool_pre_ping=True,
    pool_size=5,              # Smaller pool since Neon handles pooling
    max_overflow=10,
    pool_recycle=300,         # Recycle connections every 5 mins to avoid stale connections
    pool_timeout=30,          # Wait up to 30s for a connection from pool
    connect_args={
        "connect_timeout": 10,       # Fail fast if can't connect in 10s
        "keepalives": 1,             # Enable TCP keepalives
        "keepalives_idle": 30,       # Start keepalive after 30s idle
        "keepalives_interval": 10,   # Send keepalive every 10s
        "keepalives_count": 5,       # Give up after 5 failed keepalives
    },
)

# Create sync session factory
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """Get database session dependency."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Type alias for dependency injection
DbSession = Annotated[Session, Depends(get_db)]
