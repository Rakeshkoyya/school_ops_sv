"""Evo Points schemas for gamification."""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.evo_point import EvoTransactionType
from app.schemas.common import BaseSchema


class EvoPointTransactionBase(BaseSchema):
    """Base schema for evo point transactions."""

    amount: int = Field(..., description="Points amount (positive for credit)")
    reason: str = Field(..., min_length=3, max_length=500, description="Reason for the transaction")


class EvoPointAdminCredit(EvoPointTransactionBase):
    """Schema for admin crediting points to a user."""

    pass


class EvoPointAdminDebit(EvoPointTransactionBase):
    """Schema for admin debiting points from a user."""

    pass


class EvoPointTransactionResponse(BaseSchema):
    """Full transaction response schema."""

    id: int
    user_id: int
    project_id: int | None
    transaction_type: EvoTransactionType
    amount: int
    balance_after: int
    reason: str
    task_id: int | None
    performed_by_id: int | None
    extra_data: dict[str, Any] | None
    created_at: datetime

    # Enriched fields
    user_name: str | None = None
    performed_by_name: str | None = None
    task_title: str | None = None


class EvoPointBalanceResponse(BaseSchema):
    """User's evo points balance response."""

    user_id: int
    user_name: str
    current_balance: int
    recent_transactions: list[EvoPointTransactionResponse] = []


class EvoPointLeaderboardEntry(BaseSchema):
    """Entry in evo points leaderboard."""

    rank: int
    user_id: int
    user_name: str
    evo_points: int


class EvoPointLeaderboardResponse(BaseSchema):
    """Evo points leaderboard response."""

    entries: list[EvoPointLeaderboardEntry]
    current_user_rank: int | None = None


class TaskCompletionResult(BaseSchema):
    """Result of completing a task with evo points info."""

    task_id: int
    points_earned: int | None = None
    new_balance: int | None = None
    was_late: bool = False
    original_points: int | None = None
    reduction_applied: int | None = None
