"""Task and TaskCategory models."""

import enum
from datetime import date, datetime, time

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, Time
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


class RecurrenceType(str, enum.Enum):
    """Recurrence type for recurring tasks."""

    DAILY = "daily"
    WEEKLY = "weekly"
    ONCE = "once"


class EvoReductionType(str, enum.Enum):
    """How evo points reduce after task due time."""

    NONE = "NONE"          # No reduction - full points even if late
    GRADUAL = "GRADUAL"    # Points decay linearly to zero over extension period
    FIXED = "FIXED"        # Fixed reduced score after due time


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
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Hex color like #FF5733

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
    due_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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

    # Recurring task support
    recurring_template_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("recurring_task_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Creator tracking
    created_by_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Evo Points - Gamification fields
    evo_points: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Points awarded on completion (null = use project default)
    evo_reduction_type: Mapped[EvoReductionType] = mapped_column(
        Enum(EvoReductionType),
        default=EvoReductionType.NONE,
        nullable=False,
    )  # How points reduce after due time
    evo_extension_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # GRADUAL: when points hit zero; FIXED: grace period end
    evo_fixed_reduction_points: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # FIXED: the reduced point value after due time

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
    recurring_template: Mapped["RecurringTaskTemplate | None"] = relationship(
        "RecurringTaskTemplate",
        back_populates="generated_tasks",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title={self.title}, status={self.status})>"


class RecurringTaskTemplate(Base, IDMixin, TimestampMixin, ProjectScopedMixin):
    """Template for recurring tasks that auto-generate daily/weekly."""

    __tablename__ = "recurring_task_templates"

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("task_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Recurrence settings
    recurrence_type: Mapped[RecurrenceType] = mapped_column(
        Enum(
            "daily", "weekly", "once",
            name="recurrencetype",
            create_type=False,  # Enum already exists in DB
        ),
        nullable=False,
    )
    days_of_week: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # e.g., "0,1,2,3,4" for Mon-Fri (0=Monday)
    scheduled_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )  # For "once" recurrence type

    # Time settings (stored as TIME, combined with date during generation)
    created_on_time: Mapped[time | None] = mapped_column(
        Time, nullable=True
    )  # When task becomes visible
    start_time: Mapped[time | None] = mapped_column(
        Time, nullable=True
    )  # When work should start
    due_time: Mapped[time | None] = mapped_column(
        Time, nullable=True
    )  # Deadline time

    # Assignment
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Control
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_generated_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Creator tracking
    created_by_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Evo Points - Gamification fields (inherited by generated tasks)
    evo_points: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Points awarded on task completion
    evo_reduction_type: Mapped[EvoReductionType] = mapped_column(
        Enum(EvoReductionType),
        default=EvoReductionType.NONE,
        nullable=False,
    )  # How points reduce after due time
    evo_extension_time: Mapped[time | None] = mapped_column(
        Time, nullable=True
    )  # GRADUAL: when points hit zero; FIXED: grace period end (combined with date)
    evo_fixed_reduction_points: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # FIXED: the amount to deduct after due time

    # Relationships
    category: Mapped["TaskCategory | None"] = relationship(
        "TaskCategory",
        lazy="selectin",
    )
    assigned_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[assigned_to_user_id],
        lazy="selectin",
    )
    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="selectin",
    )
    generated_tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="recurring_template",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<RecurringTaskTemplate(id={self.id}, title={self.title}, type={self.recurrence_type})>"


# Import to avoid circular imports
from app.models.rbac import Role
from app.models.user import User
