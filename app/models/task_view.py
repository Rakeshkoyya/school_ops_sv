"""Task View Style models for customizable task list views."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, ProjectScopedMixin, TimestampMixin


# Available task columns that can be configured in views
TASK_COLUMNS = [
    {"field": "checkbox", "label": "Complete", "default_visible": True, "default_order": 0, "default_width": "40px"},
    {"field": "title", "label": "Task", "default_visible": True, "default_order": 1, "default_width": None},  # Auto width
    {"field": "description", "label": "Description", "default_visible": True, "default_order": 2, "default_width": None},
    {"field": "status", "label": "Status", "default_visible": True, "default_order": 3, "default_width": "120px"},
    {"field": "category", "label": "Category", "default_visible": True, "default_order": 4, "default_width": "140px"},
    {"field": "created_at", "label": "Created", "default_visible": True, "default_order": 5, "default_width": "120px"},
    {"field": "created_by", "label": "Created By", "default_visible": True, "default_order": 6, "default_width": "130px"},
    {"field": "assignee", "label": "Assignee", "default_visible": True, "default_order": 7, "default_width": "150px"},
    {"field": "due_datetime", "label": "Due Date", "default_visible": True, "default_order": 8, "default_width": "120px"},
    {"field": "evo_points", "label": "Evo Points", "default_visible": False, "default_order": 9, "default_width": "100px"},
    {"field": "timer", "label": "Timer", "default_visible": True, "default_order": 10, "default_width": "100px"},
    {"field": "actions", "label": "Actions", "default_visible": True, "default_order": 11, "default_width": "80px"},
]


def get_default_column_config() -> list[dict]:
    """Get the default column configuration with all columns visible."""
    return [
        {
            "field": col["field"], 
            "visible": col["default_visible"], 
            "order": col["default_order"],
            "width": col["default_width"],
        }
        for col in TASK_COLUMNS
    ]


class TaskViewStyle(Base, IDMixin, TimestampMixin, ProjectScopedMixin):
    """Project-scoped task view style model.
    
    Stores a named configuration of which task columns to display
    and in what order. Each project can have multiple view styles,
    with one optionally set as the project default.
    """

    __tablename__ = "task_view_styles"

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # JSON array of column configs: [{"field": "title", "visible": true, "order": 0}, ...]
    column_config: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=get_default_column_config,
    )
    
    # System default views cannot be deleted (seeded per project)
    is_system_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # Creator of this view style
    created_by_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="selectin",
    )
    
    user_preferences: Mapped[list["UserTaskViewPreference"]] = relationship(
        "UserTaskViewPreference",
        back_populates="view_style",
        lazy="selectin",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<TaskViewStyle(id={self.id}, name={self.name}, project_id={self.project_id})>"


class UserTaskViewPreference(Base, IDMixin, TimestampMixin):
    """User's preferred task view style per project.
    
    Stores which view style a user has selected as their personal
    preference for viewing tasks in a specific project.
    """

    __tablename__ = "user_task_view_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project_view_preference"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    view_style_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("task_view_styles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
    project: Mapped["Project"] = relationship(
        "Project",
        foreign_keys=[project_id],
        lazy="selectin",
    )
    view_style: Mapped["TaskViewStyle"] = relationship(
        "TaskViewStyle",
        foreign_keys=[view_style_id],
        back_populates="user_preferences",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<UserTaskViewPreference(user_id={self.user_id}, project_id={self.project_id}, view_style_id={self.view_style_id})>"
