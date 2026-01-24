"""Project (tenant) model."""

import enum

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin


class ProjectStatus(str, enum.Enum):
    """Project status enumeration."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class Project(Base, IDMixin, TimestampMixin):
    """Project (school/tenant) model."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    theme_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus),
        default=ProjectStatus.ACTIVE,
        nullable=False,
    )

    # Relationships
    # passive_deletes=True tells SQLAlchemy to let the database handle CASCADE deletes
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        back_populates="project",
        lazy="selectin",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name})>"
