"""Exam management endpoints."""

from datetime import date
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import ProjectContext, require_permission
from app.core.exceptions import UploadError
from app.models.audit import AuditAction
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.exam import (
    BulkExamCreate,
    BulkExamResponse,
    ExamByClassResponse,
    ExamFilter,
    ExamRecordCreate,
    ExamRecordResponse,
    ExamRecordUpdate,
    ExamSummary,
    ExamUploadResult,
    SUBJECTS,
)
from app.services.audit import AuditService
from app.services.exam import ExamService

router = APIRouter()


@router.post("", response_model=ExamRecordResponse)
def create_exam_record(
    request: ExamRecordCreate,
    context: Annotated[ProjectContext, Depends(require_permission("exam:create"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Create a single exam record.
    Validates that marks_obtained <= max_marks.
    Requires exam:create permission.
    """
    service = ExamService(db)
    record = service.create_record(context.project_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.DATA_CREATED,
        resource_type="exam",
        resource_id=str(record.id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Exam record created for student {record.student_id}",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return record


@router.get("", response_model=PaginatedResponse[ExamRecordResponse])
def list_exam_records(
    context: Annotated[ProjectContext, Depends(require_permission("exam:view"))],
    db: Annotated[Session, Depends(get_db)],
    student_id: int | None = None,
    class_section: str | None = None,
    class_name: str | None = None,
    section: str | None = None,
    exam_name: str | None = None,
    subject: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """
    List exam records with filtering and pagination.
    Requires exam:view permission.
    """
    service = ExamService(db)
    filters = ExamFilter(
        student_id=student_id,
        class_section=class_section,
        class_name=class_name,
        section=section,
        exam_name=exam_name,
        subject=subject,
        date_from=date_from,
        date_to=date_to,
        month=month,
        year=year,
    )
    records, total = service.list_records(
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
def get_exam_summary(
    context: Annotated[ProjectContext, Depends(require_permission("exam:view"))],
    db: Annotated[Session, Depends(get_db)],
    exam_name: str = Query(...),
    subject: str = Query(...),
):
    """
    Get exam summary statistics (average, pass/fail counts, etc.).
    Requires exam:view permission.
    """
    service = ExamService(db)
    return service.get_exam_summary(
        context.project_id,
        exam_name=exam_name,
        subject=subject,
    )


@router.get("/class-sections")
def get_class_sections(
    context: Annotated[ProjectContext, Depends(require_permission("exam:view"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get distinct class-section combinations with student counts.
    Requires exam:view permission.
    """
    service = ExamService(db)
    return service.get_class_sections(context.project_id)


@router.get("/subjects")
def get_subjects(
    context: Annotated[ProjectContext, Depends(require_permission("exam:view"))],
):
    """
    Get list of available subjects.
    Requires exam:view permission.
    """
    return SUBJECTS


@router.get("/exam-names")
def get_exam_names(
    context: Annotated[ProjectContext, Depends(require_permission("exam:view"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get list of distinct exam names for the project.
    Requires exam:view permission.
    """
    service = ExamService(db)
    return service.get_exam_names(context.project_id)


@router.get("/by-class", response_model=ExamByClassResponse)
def get_exam_by_class(
    context: Annotated[ProjectContext, Depends(require_permission("exam:view"))],
    db: Annotated[Session, Depends(get_db)],
    class_section: str = Query(..., description="Class-section like '3-A'"),
    exam_name: str = Query(..., description="Exam name"),
    subject: str = Query(..., description="Subject"),
):
    """
    Get all student exam records for a specific class, exam, and subject.
    Returns all students in the class with their exam data.
    Requires exam:view permission.
    """
    service = ExamService(db)
    return service.get_exam_by_class(
        context.project_id,
        class_section=class_section,
        exam_name=exam_name,
        subject=subject,
    )


@router.get("/template")
def download_exam_template(
    context: Annotated[ProjectContext, Depends(require_permission("exam:create"))],
    db: Annotated[Session, Depends(get_db)],
    class_section: str | None = Query(None, description="Class-section like '3-A'. If empty, generic template."),
    subject: str | None = Query(None, description="Subject for the exam template."),
    month: int | None = Query(None, ge=1, le=12, description="Month (1-12). Defaults to current month."),
    year: int | None = Query(None, description="Year. Defaults to current year."),
):
    """
    Download Excel template for exam upload.
    If class_section and subject are provided, template includes students from that class.
    Requires exam:create permission.
    """
    service = ExamService(db)
    content = service.generate_template(
        project_id=context.project_id,
        class_section=class_section,
        subject=subject,
        month=month,
        year=year,
    )

    # Generate filename
    today = date.today()
    month_val = month or today.month
    year_val = year or today.year
    filename = f"exam_template_{year_val}_{month_val:02d}"
    if class_section:
        filename += f"_{class_section.replace('-', '_')}"
    if subject:
        filename += f"_{subject.replace(' ', '_')}"
    filename += ".xlsx"

    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/bulk", response_model=BulkExamResponse)
def bulk_create_exam(
    request: BulkExamCreate,
    context: Annotated[ProjectContext, Depends(require_permission("exam:create"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Create or update exam records in bulk for a class.
    If exam record already exists for a student on the exam/subject, it will be updated.
    Requires exam:create permission.
    """
    service = ExamService(db)
    result = service.bulk_create_or_update(context.project_id, request)

    # Audit log
    if result.successful > 0:
        audit = AuditService(db)
        audit.log(
            action=AuditAction.DATA_CREATED,
            resource_type="exam_bulk",
            project_id=context.project_id,
            user_id=context.user_id,
            description=f"Bulk exam: {result.successful} records for {request.class_section} - {request.exam_name} - {request.subject}",
            metadata={
                "class_section": request.class_section,
                "exam_name": request.exam_name,
                "subject": request.subject,
                "successful": result.successful,
                "failed": result.failed,
            },
            ip_address=http_request.client.host if http_request.client else None,
        )

    return result


@router.post("/upload", response_model=ExamUploadResult)
def upload_exam_excel(
    context: Annotated[ProjectContext, Depends(require_permission("exam:create"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
    file: UploadFile = File(...),
):
    """
    Upload exam data from Excel file.
    Download the template first to see the expected format.
    Requires exam:create permission.
    """
    # Validate file
    if not file.filename:
        raise UploadError("No file provided")

    if not file.filename.endswith(".xlsx"):
        raise UploadError("Only .xlsx files are allowed")

    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise UploadError(f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    service = ExamService(db)
    result = service.process_excel_upload(
        project_id=context.project_id,
        file_content=content,
    )

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.UPLOAD_COMPLETED,
        resource_type="exam_upload",
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Exam upload: {result.successful_rows}/{result.total_rows} rows",
        metadata={
            "file_name": file.filename,
            "successful_rows": result.successful_rows,
            "failed_rows": result.failed_rows,
            "skipped_rows": result.skipped_rows,
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    return result


@router.get("/{record_id}", response_model=ExamRecordResponse)
def get_exam_record(
    record_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("exam:view"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get exam record by ID.
    Requires exam:view permission.
    """
    service = ExamService(db)
    record = service.get_record(record_id, context.project_id)
    return ExamRecordResponse.model_validate(service._record_to_response(record))


@router.patch("/{record_id}", response_model=ExamRecordResponse)
def update_exam_record(
    record_id: int,
    request: ExamRecordUpdate,
    context: Annotated[ProjectContext, Depends(require_permission("exam:update"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Update an exam record.
    Validates that marks_obtained <= max_marks.
    Requires exam:update permission.
    """
    service = ExamService(db)
    record = service.update_record(record_id, context.project_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.DATA_UPDATED,
        resource_type="exam",
        resource_id=str(record_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Exam record {record_id} updated",
        metadata=request.model_dump(exclude_unset=True),
        ip_address=http_request.client.host if http_request.client else None,
    )

    return record


@router.delete("/{record_id}", response_model=MessageResponse)
def delete_exam_record(
    record_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("exam:delete"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Delete an exam record.
    Requires exam:delete permission.
    """
    service = ExamService(db)
    service.delete_record(record_id, context.project_id)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.DATA_DELETED,
        resource_type="exam",
        resource_id=str(record_id),
        project_id=context.project_id,
        user_id=context.user_id,
        ip_address=http_request.client.host if http_request.client else None,
    )

    return MessageResponse(message="Exam record deleted successfully")
