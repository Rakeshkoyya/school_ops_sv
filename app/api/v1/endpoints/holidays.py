"""Holiday and user leave management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    CurrentUserContext,
    get_project_context,
    require_permission,
    require_project_admin,
)
from app.schemas.common import MessageResponse
from app.schemas.holiday import (
    ProjectHolidayCreate,
    ProjectHolidayResponse,
    UserLeaveCreate,
    UserLeaveResponse,
)
from app.services.holiday import HolidayService, UserLeaveService

router = APIRouter()


# ==================== Holiday Endpoints ====================


@router.get("/holidays", response_model=list[ProjectHolidayResponse])
def list_holidays(
    context: Annotated[CurrentUserContext, Depends(require_permission("holiday:view"))],
    db: Annotated[Session, Depends(get_db)],
    year: int | None = Query(None, description="Filter by year"),
    month: int | None = Query(None, description="Filter by month (1-12)"),
):
    """
    List all holidays for the project.
    
    Requires holiday:view permission.
    
    Optional filters:
    - year: Filter holidays for a specific year
    - month: Filter holidays for a specific month (requires year)
    """
    service = HolidayService(db)
    return service.list_holidays(
        project_id=context.project_id,
        year=year,
        month=month,
    )


@router.post("/holidays", response_model=ProjectHolidayResponse)
def create_holiday(
    request: ProjectHolidayCreate,
    context: Annotated[CurrentUserContext, Depends(require_permission("holiday:create"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create a new project holiday.
    
    Requires holiday:create permission.
    
    If the holiday date is today or in the past, automatically cancels
    all pending recurring tasks for that date.
    """
    service = HolidayService(db)
    return service.create_holiday(
        project_id=context.project_id,
        holiday_data=request,
        created_by_id=context.user_id,
    )


@router.delete("/holidays/{holiday_id}", response_model=MessageResponse)
def delete_holiday(
    holiday_id: int,
    context: Annotated[CurrentUserContext, Depends(require_permission("holiday:delete"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Delete a holiday.
    
    Requires holiday:delete permission.
    
    Note: Does not restore previously cancelled tasks.
    """
    service = HolidayService(db)
    deleted = service.delete_holiday(
        project_id=context.project_id,
        holiday_id=holiday_id,
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Holiday not found",
        )
    
    return MessageResponse(message="Holiday deleted successfully")


# ==================== User Leave Endpoints ====================


@router.get("/leaves", response_model=list[UserLeaveResponse])
def list_leaves(
    context: Annotated[CurrentUserContext, Depends(require_permission("holiday:view"))],
    db: Annotated[Session, Depends(get_db)],
    user_id: int | None = Query(None, description="Filter by user ID"),
    year: int | None = Query(None, description="Filter by year"),
    month: int | None = Query(None, description="Filter by month (1-12)"),
):
    """
    List user leaves for the project.
    
    Requires holiday:view permission.
    
    Optional filters:
    - user_id: Filter leaves for a specific user
    - year: Filter leaves for a specific year
    - month: Filter leaves for a specific month (requires year)
    """
    service = UserLeaveService(db)
    return service.list_leaves(
        project_id=context.project_id,
        user_id=user_id,
        year=year,
        month=month,
    )


@router.post("/leaves", response_model=UserLeaveResponse)
def create_leave(
    request: UserLeaveCreate,
    context: Annotated[CurrentUserContext, Depends(require_permission("holiday:create"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create a new user leave.
    
    Requires holiday:create permission.
    
    If the leave date is today or in the past, automatically cancels
    the user's pending recurring tasks for that date.
    """
    service = UserLeaveService(db)
    return service.create_leave(
        project_id=context.project_id,
        leave_data=request,
        created_by_id=context.user_id,
    )


@router.delete("/leaves/{leave_id}", response_model=MessageResponse)
def delete_leave(
    leave_id: int,
    context: Annotated[CurrentUserContext, Depends(require_permission("holiday:delete"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Delete a user leave.
    
    Requires holiday:delete permission.
    
    Note: Does not restore previously cancelled tasks.
    """
    service = UserLeaveService(db)
    deleted = service.delete_leave(
        project_id=context.project_id,
        leave_id=leave_id,
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave not found",
        )
    
    return MessageResponse(message="Leave deleted successfully")
