"""Student management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import ProjectContext, require_permission
from app.core.exceptions import UploadError
from app.models.audit import AuditAction
from app.schemas.common import MessageResponse
from app.schemas.student import (
    PaginatedStudentResponse,
    StudentBulkUploadResult,
    StudentCreate,
    StudentFilter,
    StudentResponse,
    StudentUpdate,
)
from app.services.audit import AuditService
from app.services.student import StudentService

router = APIRouter()


@router.post("", response_model=StudentResponse)
def create_student(
    request: StudentCreate,
    context: Annotated[ProjectContext, Depends(require_permission("student:create"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """Create a new student."""
    service = StudentService(db)
    student = service.create_student(context.project_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.DATA_CREATED,
        resource_type="student",
        resource_id=str(student.id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Student '{student.student_name}' created",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return student


@router.get("", response_model=PaginatedStudentResponse)
def list_students(
    context: Annotated[ProjectContext, Depends(require_permission("student:view"))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    class_name: str | None = None,
    section: str | None = None,
    class_section: str | None = None,
    search: str | None = None,
):
    """List students with filtering and pagination.
    
    class_section parameter accepts format like "3-A" and parses into class_name and section.
    """
    service = StudentService(db)
    
    # Parse class_section if provided (e.g., "3-A" -> class_name="3", section="A")
    filter_class_name = class_name
    filter_section = section
    if class_section and "-" in class_section:
        parts = class_section.rsplit("-", 1)
        filter_class_name = parts[0]
        filter_section = parts[1]
    elif class_section:
        filter_class_name = class_section
    
    filters = StudentFilter(class_name=filter_class_name, section=filter_section, search=search)
    return service.list_students(context.project_id, filters, page, page_size)


@router.get("/template")
def download_student_template(
    context: Annotated[ProjectContext, Depends(require_permission("student:upload"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Download Excel template for student bulk upload."""
    service = StudentService(db)
    content = service.generate_template()

    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=students_template.xlsx"},
    )


@router.get("/classes")
def get_class_sections(
    context: Annotated[ProjectContext, Depends(require_permission("student:view"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get distinct class-section combinations for the project."""
    service = StudentService(db)
    return service.get_class_sections(context.project_id)


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("student:view"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get a student by ID."""
    service = StudentService(db)
    student = service.get_student(context.project_id, student_id)
    return StudentResponse.model_validate(student)


@router.patch("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: int,
    request: StudentUpdate,
    context: Annotated[ProjectContext, Depends(require_permission("student:update"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """Update a student."""
    service = StudentService(db)
    student = service.update_student(context.project_id, student_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.DATA_UPDATED,
        resource_type="student",
        resource_id=str(student_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Student '{student.student_name}' updated",
        metadata=request.model_dump(exclude_unset=True),
        ip_address=http_request.client.host if http_request.client else None,
    )

    return student


@router.delete("/{student_id}", response_model=MessageResponse)
def delete_student(
    student_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("student:delete"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """Delete a student."""
    service = StudentService(db)
    service.delete_student(context.project_id, student_id)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.DATA_DELETED,
        resource_type="student",
        resource_id=str(student_id),
        project_id=context.project_id,
        user_id=context.user_id,
        ip_address=http_request.client.host if http_request.client else None,
    )

    return MessageResponse(message="Student deleted successfully")


@router.post("/upload", response_model=StudentBulkUploadResult)
def bulk_upload_students(
    context: Annotated[ProjectContext, Depends(require_permission("student:upload"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
    file: UploadFile = File(...),
):
    """
    Bulk upload students from Excel file.
    
    Download the template first to see the expected format.
    Partial success is allowed - invalid rows will be skipped.
    """
    # Validate file
    if not file.filename:
        raise UploadError("No file provided")

    if not file.filename.endswith(".xlsx"):
        raise UploadError("Only .xlsx files are allowed")

    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise UploadError(f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    service = StudentService(db)
    result = service.bulk_upload(context.project_id, content)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.UPLOAD_COMPLETED,
        resource_type="student_upload",
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Student bulk upload: {result.successful_rows}/{result.total_rows} rows",
        metadata={
            "file_name": file.filename,
            "successful_rows": result.successful_rows,
            "failed_rows": result.failed_rows,
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    return result
