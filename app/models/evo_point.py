"""Evo Points transaction model for gamification."""

import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin


class EvoTransactionType(str, enum.Enum):
    """Type of evo points transaction."""

    TASK_REWARD = "task_reward"      # Points earned from completing a task
    ADMIN_CREDIT = "admin_credit"    # Admin manually credits points
    ADMIN_DEBIT = "admin_debit"      # Admin manually debits points


class EvoPointTransaction(Base, IDMixin, TimestampMixin):
    """Ledger-style transaction log for evo points (append-only)."""

    __tablename__ = "evo_point_transactions"

    # User receiving/losing points
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Project scope (nullable for super-admin actions)
    project_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Transaction details
    transaction_type: Mapped[EvoTransactionType] = mapped_column(
        Enum(EvoTransactionType),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # Positive for credit, can store negative for debit
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Running balance snapshot
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # Human-readable description

    # Task reference (for TASK_REWARD type)
    task_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Admin who performed credit/debit (for ADMIN_CREDIT/ADMIN_DEBIT)
    performed_by_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Extra metadata (e.g., original points, reduction details, late completion info)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
    project: Mapped["Project | None"] = relationship(
        "Project",
        lazy="selectin",
    )
    task: Mapped["Task | None"] = relationship(
        "Task",
        lazy="selectin",
    )
    performed_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[performed_by_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<EvoPointTransaction(id={self.id}, user_id={self.user_id}, type={self.transaction_type}, amount={self.amount})>"
