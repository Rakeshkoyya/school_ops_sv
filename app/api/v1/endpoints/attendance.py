"""Attendance management endpoints."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ProjectContext, require_permission
from app.models.attendance import AttendanceStatus
from app.schemas.attendance import (
    AttendanceFilter,
    AttendanceRecordCreate,
    AttendanceRecordResponse,
    AttendanceRecordUpdate,
    AttendanceSummary,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.attendance import AttendanceService

router = APIRouter()


@router.post("", response_model=AttendanceRecordResponse)
async def create_attendance_record(
    request: AttendanceRecordCreate,
    context: Annotated[ProjectContext, Depends(require_permission("attendance:create"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create a single attendance record.
    Requires attendance.create permission.
    """
    service = AttendanceService(db)
    return await service.create_record(context.project_id, request)


@router.get("", response_model=PaginatedResponse[AttendanceRecordResponse])
async def list_attendance_records(
    context: Annotated[ProjectContext, Depends(require_permission("attendance:view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    student_id: str | None = None,
    status: AttendanceStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    List attendance records with filtering and pagination.
    Requires attendance.view permission.
    """
    service = AttendanceService(db)
    filters = AttendanceFilter(
        student_id=student_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    records, total = await service.list_records(
        context.project_id,
        filters=filters,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=records,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/summary", response_model=AttendanceSummary)
async def get_attendance_summary(
    context: Annotated[ProjectContext, Depends(require_permission("attendance:view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
    student_id: str | None = None,
):
    """
    Get attendance summary statistics for a date range.
    Requires attendance.view permission.
    """
    service = AttendanceService(db)
    return await service.get_summary(
        context.project_id,
        date_from=date_from,
        date_to=date_to,
        student_id=student_id,
    )


@router.get("/{record_id}", response_model=AttendanceRecordResponse)
async def get_attendance_record(
    record_id: UUID,
    context: Annotated[ProjectContext, Depends(require_permission("attendance:view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get attendance record by ID.
    Requires attendance.view permission.
    """
    service = AttendanceService(db)
    record = await service.get_record(record_id, context.project_id)
    return AttendanceRecordResponse.model_validate(record)


@router.patch("/{record_id}", response_model=AttendanceRecordResponse)
async def update_attendance_record(
    record_id: UUID,
    request: AttendanceRecordUpdate,
    context: Annotated[ProjectContext, Depends(require_permission("attendance:update"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Update an attendance record.
    Requires attendance.update permission.
    """
    service = AttendanceService(db)
    return await service.update_record(record_id, context.project_id, request)


@router.delete("/{record_id}", response_model=MessageResponse)
async def delete_attendance_record(
    record_id: UUID,
    context: Annotated[ProjectContext, Depends(require_permission("attendance:delete"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Delete an attendance record.
    Requires attendance.delete permission.
    """
    service = AttendanceService(db)
    await service.delete_record(record_id, context.project_id)
    return MessageResponse(message="Attendance record deleted successfully")
