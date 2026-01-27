"""Attendance management endpoints."""

from datetime import date
from typing import Annotated
from io import BytesIO

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import ProjectContext, require_permission
from app.core.exceptions import UploadError
from app.models.attendance import AttendanceStatus
from app.models.audit import AuditAction
from app.schemas.attendance import (
    AttendanceByClassResponse,
    AttendanceFilter,
    AttendanceRecordCreate,
    AttendanceRecordResponse,
    AttendanceRecordUpdate,
    AttendanceSummary,
    AttendanceUploadResult,
    BulkAttendanceCreate,
    BulkAttendanceResponse,
    TemplateRequest,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.attendance import AttendanceService
from app.services.audit import AuditService

router = APIRouter()


@router.post("", response_model=AttendanceRecordResponse)
def create_attendance_record(
    request: AttendanceRecordCreate,
    context: Annotated[ProjectContext, Depends(require_permission("attendance:create"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Create a single attendance record.
    Requires attendance:create permission.
    """
    service = AttendanceService(db)
    record = service.create_record(context.project_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.DATA_CREATED,
        resource_type="attendance",
        resource_id=str(record.id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Attendance record created for student {record.student_id}",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return record


@router.get("", response_model=PaginatedResponse[AttendanceRecordResponse])
def list_attendance_records(
    context: Annotated[ProjectContext, Depends(require_permission("attendance:view"))],
    db: Annotated[Session, Depends(get_db)],
    student_id: int | None = None,
    class_section: str | None = None,
    class_name: str | None = None,
    section: str | None = None,
    status: AttendanceStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=2000),
):
    """
    List attendance records with filtering and pagination.
    Requires attendance:view permission.
    """
    service = AttendanceService(db)
    filters = AttendanceFilter(
        student_id=student_id,
        class_section=class_section,
        class_name=class_name,
        section=section,
        status=status,
        date_from=date_from,
        date_to=date_to,
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


@router.get("/summary", response_model=AttendanceSummary)
def get_attendance_summary(
    context: Annotated[ProjectContext, Depends(require_permission("attendance:view"))],
    db: Annotated[Session, Depends(get_db)],
    date_from: date = Query(...),
    date_to: date = Query(...),
    student_id: int | None = None,
    class_section: str | None = None,
):
    """
    Get attendance summary statistics for a date range.
    Requires attendance:view permission.
    """
    service = AttendanceService(db)
    return service.get_summary(
        context.project_id,
        date_from=date_from,
        date_to=date_to,
        student_id=student_id,
        class_section=class_section,
    )


@router.get("/class-sections")
def get_class_sections(
    context: Annotated[ProjectContext, Depends(require_permission("attendance:view"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get distinct class-section combinations with student counts.
    Requires attendance:view permission.
    """
    service = AttendanceService(db)
    return service.get_class_sections(context.project_id)


@router.get("/by-class", response_model=AttendanceByClassResponse)
def get_attendance_by_class(
    context: Annotated[ProjectContext, Depends(require_permission("attendance:view"))],
    db: Annotated[Session, Depends(get_db)],
    class_section: str = Query(..., description="Class-section like '3-A'"),
    attendance_date: date = Query(..., description="Date for attendance"),
):
    """
    Get all student attendance for a specific class on a specific date.
    Returns all students in the class with their attendance status.
    Requires attendance:view permission.
    """
    service = AttendanceService(db)
    return service.get_attendance_by_class_date(
        context.project_id,
        class_section=class_section,
        attendance_date=attendance_date,
    )


@router.get("/template")
def download_attendance_template(
    context: Annotated[ProjectContext, Depends(require_permission("attendance:create"))],
    db: Annotated[Session, Depends(get_db)],
    class_section: str | None = Query(None, description="Class-section like '3-A'. If empty, generic template."),
    month: int | None = Query(None, ge=1, le=12, description="Month (1-12). Defaults to current month."),
    year: int | None = Query(None, description="Year. Defaults to current year."),
):
    """
    Download Excel template for attendance upload.
    If class_section is provided, template includes students from that class.
    Requires attendance:create permission.
    """
    service = AttendanceService(db)
    content = service.generate_template(
        project_id=context.project_id,
        class_section=class_section,
        month=month,
        year=year,
    )

    # Generate filename
    today = date.today()
    month_val = month or today.month
    year_val = year or today.year
    filename = f"attendance_template_{year_val}_{month_val:02d}"
    if class_section:
        filename += f"_{class_section.replace('-', '_')}"
    filename += ".xlsx"

    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/bulk", response_model=BulkAttendanceResponse)
def bulk_create_attendance(
    request: BulkAttendanceCreate,
    context: Annotated[ProjectContext, Depends(require_permission("attendance:create"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Create or update attendance records in bulk for a class on a specific date.
    If attendance already exists for a student on the date, it will be updated.
    Requires attendance:create permission.
    """
    service = AttendanceService(db)
    result = service.bulk_create_or_update(context.project_id, request)

    # Audit log
    if result.successful > 0:
        audit = AuditService(db)
        audit.log(
            action=AuditAction.DATA_CREATED,
            resource_type="attendance_bulk",
            project_id=context.project_id,
            user_id=context.user_id,
            description=f"Bulk attendance: {result.successful} records for {request.class_section} on {request.attendance_date}",
            metadata={
                "class_section": request.class_section,
                "date": str(request.attendance_date),
                "successful": result.successful,
                "failed": result.failed,
            },
            ip_address=http_request.client.host if http_request.client else None,
        )

    return result


@router.post("/upload", response_model=AttendanceUploadResult)
def upload_attendance_excel(
    context: Annotated[ProjectContext, Depends(require_permission("attendance:create"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
    file: UploadFile = File(...),
):
    """
    Upload attendance data from Excel file.
    Download the template first to see the expected format.
    Validates all data before saving - if critical errors exist, no data is saved.
    Requires attendance:create permission.
    """
    # Validate file
    if not file.filename:
        raise UploadError("No file provided")

    if not file.filename.endswith(".xlsx"):
        raise UploadError("Only .xlsx files are allowed")

    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise UploadError(f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    service = AttendanceService(db)
    result = service.process_excel_upload(
        project_id=context.project_id,
        file_content=content,
    )

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.UPLOAD_COMPLETED,
        resource_type="attendance_upload",
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Attendance upload: {result.successful_rows}/{result.total_rows} rows",
        metadata={
            "file_name": file.filename,
            "successful_rows": result.successful_rows,
            "failed_rows": result.failed_rows,
            "skipped_rows": result.skipped_rows,
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    return result


@router.get("/{record_id}", response_model=AttendanceRecordResponse)
def get_attendance_record(
    record_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("attendance:view"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get attendance record by ID.
    Requires attendance:view permission.
    """
    service = AttendanceService(db)
    record = service.get_record(record_id, context.project_id)
    return AttendanceRecordResponse.model_validate(service._record_to_response(record))


@router.patch("/{record_id}", response_model=AttendanceRecordResponse)
def update_attendance_record(
    record_id: int,
    request: AttendanceRecordUpdate,
    context: Annotated[ProjectContext, Depends(require_permission("attendance:update"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Update an attendance record.
    Requires attendance:update permission.
    """
    service = AttendanceService(db)
    record = service.update_record(record_id, context.project_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.DATA_UPDATED,
        resource_type="attendance",
        resource_id=str(record_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Attendance record {record_id} updated",
        metadata=request.model_dump(exclude_unset=True),
        ip_address=http_request.client.host if http_request.client else None,
    )

    return record


@router.delete("/{record_id}", response_model=MessageResponse)
def delete_attendance_record(
    record_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("attendance:delete"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Delete an attendance record.
    Requires attendance:delete permission.
    """
    service = AttendanceService(db)
    service.delete_record(record_id, context.project_id)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.DATA_DELETED,
        resource_type="attendance",
        resource_id=str(record_id),
        project_id=context.project_id,
        user_id=context.user_id,
        ip_address=http_request.client.host if http_request.client else None,
    )

    return MessageResponse(message="Attendance record deleted successfully")
