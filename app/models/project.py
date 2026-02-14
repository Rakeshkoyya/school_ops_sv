"""Project (tenant) model."""

import enum

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String, Text
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
    
    # Default task view style for this project (can be overridden by user preference)
    default_task_view_style_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("task_view_styles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Evo Points - Default for tasks in this project
    default_evo_points: Mapped[int] = mapped_column(
        Integer,
        default=0,
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
