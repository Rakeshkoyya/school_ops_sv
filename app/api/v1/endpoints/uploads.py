"""Upload endpoints for Excel file processing."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import ProjectContext, require_permission
from app.core.exceptions import UploadError
from app.models.audit import AuditAction
from app.models.upload import Upload, UploadStatus, UploadType
from app.schemas.common import PaginatedResponse
from app.schemas.upload import (
    UploadErrorResponse,
    UploadFilter,
    UploadResult,
    UploadWithDetails,
)
from app.services.audit import AuditService
from app.services.notification import notify_upload_failed
from app.services.upload import UploadService

router = APIRouter()


@router.post("/attendance", response_model=UploadResult)
def upload_attendance(
    context: Annotated[ProjectContext, Depends(require_permission("attendance:upload"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
    file: UploadFile = File(...),
):
    """
    Upload attendance data from Excel file.
    
    - Allows partial success (invalid rows are skipped)
    - Upload metadata is always saved
    - Requires attendance:upload permission
    
    Expected columns: student_id, student_name, attendance_date, status, remarks (optional)
    """
    # Validate file
    if not file.filename:
        raise UploadError("No file provided")

    if not file.filename.endswith(".xlsx"):
        raise UploadError("Only .xlsx files are allowed")

    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise UploadError(f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    service = UploadService(db)
    result = service.process_attendance_upload(
        project_id=context.project_id,
        user_id=context.user_id,
        file_content=content,
        file_name=file.filename,
    )

    # Audit log
    audit = AuditService(db)
    action = AuditAction.UPLOAD_COMPLETED if result.status == UploadStatus.SUCCESS else AuditAction.UPLOAD_FAILED
    audit.log(
        action=action,
        resource_type="upload",
        resource_id=str(result.upload_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Attendance upload: {result.successful_rows}/{result.total_rows} rows successful",
        metadata={
            "file_name": file.filename,
            "status": result.status.value,
            "successful_rows": result.successful_rows,
            "failed_rows": result.failed_rows,
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    # Notify on failure
    if result.status == UploadStatus.FAILED:
        notify_upload_failed(
            db,
            context.project_id,
            context.user_id,
            "attendance",
            file.filename,
            result.failed_rows,
        )

    return result


@router.post("/exams", response_model=UploadResult)
def upload_exams(
    context: Annotated[ProjectContext, Depends(require_permission("exam:upload"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
    file: UploadFile = File(...),
):
    """
    Upload exam data from Excel file.
    
    STRICT VALIDATION:
    - Any invalid row triggers FULL ROLLBACK
    - marks_obtained must not exceed max_marks
    - All rows are validated before any insertion
    - Requires exam:upload permission
    
    Expected columns: student_id, student_name, exam_name, subject, exam_date, 
                     max_marks, marks_obtained, grade (optional), remarks (optional)
    """
    # Validate file
    if not file.filename:
        raise UploadError("No file provided")

    if not file.filename.endswith(".xlsx"):
        raise UploadError("Only .xlsx files are allowed")

    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise UploadError(f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    service = UploadService(db)
    result = service.process_exam_upload(
        project_id=context.project_id,
        user_id=context.user_id,
        file_content=content,
        file_name=file.filename,
    )

    # Audit log
    audit = AuditService(db)
    action = AuditAction.UPLOAD_COMPLETED if result.status == UploadStatus.SUCCESS else AuditAction.UPLOAD_FAILED
    audit.log(
        action=action,
        resource_type="upload",
        resource_id=str(result.upload_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Exam upload: {result.status.value}",
        metadata={
            "file_name": file.filename,
            "status": result.status.value,
            "successful_rows": result.successful_rows,
            "failed_rows": result.failed_rows,
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    # Notify on failure
    if result.status == UploadStatus.FAILED:
        notify_upload_failed(
            db,
            context.project_id,
            context.user_id,
            "exam",
            file.filename,
            result.failed_rows,
        )

    return result


@router.get("", response_model=PaginatedResponse[UploadWithDetails])
def list_uploads(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
    upload_type: UploadType | None = None,
    status: UploadStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List upload history with filtering and pagination.
    """
    from sqlalchemy import func

    query = (
        select(Upload)
        .options(selectinload(Upload.uploaded_by), selectinload(Upload.errors))
        .where(Upload.project_id == context.project_id)
    )

    if upload_type:
        query = query.where(Upload.upload_type == upload_type)
    if status:
        query = query.where(Upload.status == status)

    # Count total
    count_result = db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Apply pagination
    query = (
        query
        .order_by(Upload.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = db.execute(query)
    uploads = result.scalars().all()

    items = [
        UploadWithDetails(
            id=u.id,
            project_id=u.project_id,
            upload_type=u.upload_type,
            file_name=u.file_name,
            file_size=u.file_size,
            status=u.status,
            total_rows=u.total_rows,
            successful_rows=u.successful_rows,
            failed_rows=u.failed_rows,
            error_message=u.error_message,
            uploaded_by_id=u.uploaded_by_id,
            processing_started_at=u.processing_started_at,
            processing_completed_at=u.processing_completed_at,
            created_at=u.created_at,
            updated_at=u.updated_at,
            uploaded_by_name=u.uploaded_by.name if u.uploaded_by else None,
            errors=[
                UploadErrorResponse(
                    id=e.id,
                    upload_id=e.upload_id,
                    row_number=e.row_number,
                    column_name=e.column_name,
                    error_type=e.error_type,
                    error_message=e.error_message,
                    raw_value=e.raw_value,
                )
                for e in u.errors
            ],
        )
        for u in uploads
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{upload_id}", response_model=UploadWithDetails)
def get_upload(
    upload_id: UUID,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get upload details by ID with error information.
    """
    from app.core.exceptions import NotFoundError

    result = db.execute(
        select(Upload)
        .options(selectinload(Upload.uploaded_by), selectinload(Upload.errors))
        .where(
            Upload.id == upload_id,
            Upload.project_id == context.project_id,
        )
    )
    upload = result.scalar_one_or_none()

    if not upload:
        raise NotFoundError("Upload", str(upload_id))

    return UploadWithDetails(
        id=upload.id,
        project_id=upload.project_id,
        upload_type=upload.upload_type,
        file_name=upload.file_name,
        file_size=upload.file_size,
        status=upload.status,
        total_rows=upload.total_rows,
        successful_rows=upload.successful_rows,
        failed_rows=upload.failed_rows,
        error_message=upload.error_message,
        uploaded_by_id=upload.uploaded_by_id,
        processing_started_at=upload.processing_started_at,
        processing_completed_at=upload.processing_completed_at,
        created_at=upload.created_at,
        updated_at=upload.updated_at,
        uploaded_by_name=upload.uploaded_by.name if upload.uploaded_by else None,
        errors=[
            UploadErrorResponse(
                id=e.id,
                upload_id=e.upload_id,
                row_number=e.row_number,
                column_name=e.column_name,
                error_type=e.error_type,
                error_message=e.error_message,
                raw_value=e.raw_value,
            )
            for e in upload.errors
        ],
    )
