"""Task and TaskCategory models."""

import enum
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, ProjectScopedMixin, TimestampMixin


class TaskStatus(str, enum.Enum):
    """Task status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class TaskType(str, enum.Enum):
    """Task type enumeration."""

    GENERIC = "generic"  # System-generated, auto-completable tasks
    MANUAL = "manual"    # Admin-assigned tasks with manual completion
    SELF = "self"        # Self-added tasks by users


class GenericTaskKey(str, enum.Enum):
    """Keys for generic (auto-completable) tasks."""

    MARK_ATTENDANCE = "mark_attendance"
    DAILY_EXAM_TRACKER = "daily_exam_tracker"


class TaskCategory(Base, IDMixin, TimestampMixin, ProjectScopedMixin):
    """Project-scoped task category model."""

    __tablename__ = "task_categories"

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="category",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<TaskCategory(id={self.id}, name={self.name})>"


class Task(Base, IDMixin, TimestampMixin, ProjectScopedMixin):
    """Task model with user or role assignment."""

    __tablename__ = "tasks"

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("task_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Assignment - either user or role (not both required)
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_to_role_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Auto-task support
    auto_rule_key: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Creator tracking
    created_by_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Relationships
    category: Mapped["TaskCategory | None"] = relationship(
        "TaskCategory",
        back_populates="tasks",
    )
    assigned_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[assigned_to_user_id],
        lazy="selectin",
    )
    assigned_role: Mapped["Role | None"] = relationship(
        "Role",
        foreign_keys=[assigned_to_role_id],
        lazy="selectin",
    )
    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title={self.title}, status={self.status})>"


# Import to avoid circular imports
from app.models.rbac import Role
from app.models.user import User
