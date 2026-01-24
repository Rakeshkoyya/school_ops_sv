"""Base model utilities and mixins."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class IDMixin:
    """Mixin providing BigInteger primary key with auto-increment."""

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )


class TimestampMixin:
    """Mixin providing created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ProjectScopedMixin:
    """Mixin for models that belong to a project."""

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False,
    )
