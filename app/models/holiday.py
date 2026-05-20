"""Holiday and user leave models."""
from datetime import date
from sqlalchemy import BigInteger, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin, ProjectScopedMixin


class ProjectHoliday(Base, IDMixin, TimestampMixin, ProjectScopedMixin):
    """Project-wide holiday dates."""
    
    __tablename__ = "project_holidays"
    __table_args__ = (
        UniqueConstraint("project_id", "holiday_date", name="uq_project_holiday_date"),
    )
    
    # Fields
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    holiday_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_by_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="holidays")
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])


class UserLeave(Base, IDMixin, TimestampMixin, ProjectScopedMixin):
    """Individual user leave dates."""
    
    __tablename__ = "user_leaves"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", "leave_date", name="uq_project_user_leave_date"),
    )
    
    # Fields
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leave_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_by_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="user_leaves")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="leaves")
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
