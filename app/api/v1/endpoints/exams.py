"""Exam management endpoints."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ProjectContext, require_permission
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.exam import (
    ExamFilter,
    ExamRecordCreate,
    ExamRecordResponse,
    ExamRecordUpdate,
    ExamSummary,
)
from app.services.exam import ExamService

router = APIRouter()


@router.post("", response_model=ExamRecordResponse)
async def create_exam_record(
    request: ExamRecordCreate,
    context: Annotated[ProjectContext, Depends(require_permission("exam:create"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Create a single exam record.
    Validates that marks_obtained <= max_marks.
    Requires exam.create permission.
    """
    service = ExamService(db)
    return await service.create_record(context.project_id, request)


@router.get("", response_model=PaginatedResponse[ExamRecordResponse])
async def list_exam_records(
    context: Annotated[ProjectContext, Depends(require_permission("exam:view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    student_id: str | None = None,
    exam_name: str | None = None,
    subject: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    List exam records with filtering and pagination.
    Requires exam.view permission.
    """
    service = ExamService(db)
    filters = ExamFilter(
        student_id=student_id,
        exam_name=exam_name,
        subject=subject,
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


@router.get("/summary", response_model=ExamSummary)
async def get_exam_summary(
    context: Annotated[ProjectContext, Depends(require_permission("exam:view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    exam_name: str = Query(...),
    subject: str = Query(...),
):
    """
    Get exam summary statistics (average, pass/fail counts, etc.).
    Requires exam.view permission.
    """
    service = ExamService(db)
    return await service.get_exam_summary(
        context.project_id,
        exam_name=exam_name,
        subject=subject,
    )


@router.get("/{record_id}", response_model=ExamRecordResponse)
async def get_exam_record(
    record_id: UUID,
    context: Annotated[ProjectContext, Depends(require_permission("exam:view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get exam record by ID.
    Requires exam.view permission.
    """
    service = ExamService(db)
    record = await service.get_record(record_id, context.project_id)
    return ExamRecordResponse.model_validate(record)


@router.patch("/{record_id}", response_model=ExamRecordResponse)
async def update_exam_record(
    record_id: UUID,
    request: ExamRecordUpdate,
    context: Annotated[ProjectContext, Depends(require_permission("exam:update"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Update an exam record.
    Validates that marks_obtained <= max_marks.
    Requires exam.update permission.
    """
    service = ExamService(db)
    return await service.update_record(record_id, context.project_id, request)


@router.delete("/{record_id}", response_model=MessageResponse)
async def delete_exam_record(
    record_id: UUID,
    context: Annotated[ProjectContext, Depends(require_permission("exam:delete"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Delete an exam record.
    Requires exam.delete permission.
    """
    service = ExamService(db)
    await service.delete_record(record_id, context.project_id)
    return MessageResponse(message="Exam record deleted successfully")
