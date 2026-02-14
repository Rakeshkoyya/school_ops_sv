"""Evo Points endpoints for gamification."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import ProjectContext, get_current_user, require_permission
from app.models.evo_point import EvoTransactionType
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.evo_point import (
    EvoPointAdminCredit,
    EvoPointAdminDebit,
    EvoPointBalanceResponse,
    EvoPointLeaderboardResponse,
    EvoPointTransactionResponse,
)
from app.services.evo_point import EvoPointService

router = APIRouter()


@router.get("/me", response_model=EvoPointBalanceResponse)
def get_my_evo_points(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(10, ge=1, le=100),
):
    """
    Get current user's evo points balance and recent transactions.
    """
    service = EvoPointService(db)
    return service.get_user_balance_with_transactions(
        user_id=context.user_id,
        project_id=context.project_id,
        limit=limit,
    )


@router.get("/leaderboard", response_model=EvoPointLeaderboardResponse)
def get_leaderboard(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(10, ge=1, le=100),
):
    """
    Get evo points leaderboard.
    """
    service = EvoPointService(db)
    return service.get_leaderboard(
        project_id=context.project_id,
        limit=limit,
        current_user_id=context.user_id,
    )


@router.get("/users/{user_id}", response_model=EvoPointBalanceResponse)
def get_user_evo_points(
    user_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("evo_points:manage"))],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(10, ge=1, le=100),
):
    """
    Get a specific user's evo points balance and transactions.
    Requires evo_points:manage permission.
    """
    service = EvoPointService(db)
    return service.get_user_balance_with_transactions(
        user_id=user_id,
        project_id=context.project_id,
        limit=limit,
    )


@router.post("/users/{user_id}/credit", response_model=EvoPointTransactionResponse)
def credit_evo_points(
    user_id: int,
    request: EvoPointAdminCredit,
    context: Annotated[ProjectContext, Depends(require_permission("evo_points:manage"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Credit evo points to a user (admin action).
    Requires evo_points:manage permission.
    """
    service = EvoPointService(db)
    return service.admin_credit(
        user_id=user_id,
        amount=request.amount,
        reason=request.reason,
        performed_by_id=context.user_id,
        project_id=context.project_id,
    )


@router.post("/users/{user_id}/debit", response_model=EvoPointTransactionResponse)
def debit_evo_points(
    user_id: int,
    request: EvoPointAdminDebit,
    context: Annotated[ProjectContext, Depends(require_permission("evo_points:manage"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Debit evo points from a user (admin action).
    Requires evo_points:manage permission.
    """
    service = EvoPointService(db)
    return service.admin_debit(
        user_id=user_id,
        amount=request.amount,
        reason=request.reason,
        performed_by_id=context.user_id,
        project_id=context.project_id,
    )


@router.get("/transactions", response_model=PaginatedResponse[EvoPointTransactionResponse])
def list_transactions(
    context: Annotated[ProjectContext, Depends(require_permission("evo_points:manage"))],
    db: Annotated[Session, Depends(get_db)],
    user_id: int | None = None,
    transaction_type: EvoTransactionType | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    List all evo point transactions (admin view).
    Requires evo_points:manage permission.
    """
    service = EvoPointService(db)
    transactions, total = service.get_transactions(
        project_id=context.project_id,
        user_id=user_id,
        transaction_type=transaction_type,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=transactions,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )
