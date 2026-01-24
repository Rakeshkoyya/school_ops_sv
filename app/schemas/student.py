"""Student schemas."""

from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema, PaginatedResponse


class StudentBase(BaseSchema):
    """Base student schema."""

    student_name: str = Field(..., min_length=2, max_length=255)
    class_name: str = Field(..., min_length=1, max_length=50)
    section: str | None = Field(None, max_length=50)
    parent_name: str | None = Field(None, max_length=255)
    parent_phone_no: str | None = Field(None, max_length=50)


class StudentCreate(StudentBase):
    """Student creation schema."""

    pass


class StudentUpdate(BaseSchema):
    """Student update schema."""

    student_name: str | None = Field(None, min_length=2, max_length=255)
    class_name: str | None = Field(None, min_length=1, max_length=50)
    section: str | None = Field(None, max_length=50)
    parent_name: str | None = Field(None, max_length=255)
    parent_phone_no: str | None = Field(None, max_length=50)


class StudentResponse(StudentBase):
    """Student response schema."""

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime


class StudentBulkCreate(BaseSchema):
    """Bulk student creation from Excel."""

    students: list[StudentCreate]


class StudentBulkUploadResult(BaseSchema):
    """Result of bulk student upload."""

    total_rows: int
    successful_rows: int
    failed_rows: int
    errors: list[dict] = []
    message: str


class StudentFilter(BaseSchema):
    """Student filter options."""

    class_name: str | None = None
    section: str | None = None
    search: str | None = None  # Search by name


class PaginatedStudentResponse(PaginatedResponse):
    """Paginated student list."""

    items: list[StudentResponse]
