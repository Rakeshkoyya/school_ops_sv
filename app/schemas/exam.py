"""Exam schemas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


# ==========================================
# Constants
# ==========================================

# Hardcoded subjects list
SUBJECTS = [
    "Mathematics",
    "English",
    "Science",
    "Social Studies",
    "Hindi",
    "Computer Science",
    "Physics",
    "Chemistry",
    "Biology",
    "History",
    "Geography",
    "Economics",
    "Accountancy",
    "Business Studies",
    "Political Science",
    "Physical Education",
    "Art",
    "Music",
]


# ==========================================
# Exam Record Schemas
# ==========================================

class ExamRecordCreate(BaseSchema):
    """Single exam record creation schema."""

    student_id: int = Field(..., description="Student database ID")
    exam_name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=100)
    exam_date: date
    max_marks: Decimal = Field(..., gt=0)
    marks_obtained: Decimal = Field(..., ge=0)
    grade: str | None = Field(None, max_length=10)
    remarks: str | None = None

    @field_validator("marks_obtained")
    @classmethod
    def validate_marks(cls, v: Decimal, info) -> Decimal:
        """Validate marks_obtained doesn't exceed max_marks."""
        return v


class ExamRecordUpdate(BaseSchema):
    """Exam record update schema."""

    marks_obtained: Decimal | None = Field(None, ge=0)
    max_marks: Decimal | None = Field(None, gt=0)
    grade: str | None = Field(None, max_length=10)
    remarks: str | None = None


class ExamRecordResponse(BaseSchema):
    """Exam record response schema."""

    id: int
    project_id: int
    student_id: int
    student_name: str
    class_name: str
    section: str | None
    exam_name: str
    subject: str
    exam_date: date
    max_marks: Decimal
    marks_obtained: Decimal
    grade: str | None
    remarks: str | None
    upload_id: int | None
    created_at: datetime
    updated_at: datetime


class ExamFilter(BaseSchema):
    """Exam filtering options."""

    student_id: int | None = None
    class_section: str | None = None  # Combined filter like "3-A"
    class_name: str | None = None
    section: str | None = None
    exam_name: str | None = None
    subject: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    month: int | None = None  # 1-12
    year: int | None = None


class ExamSummary(BaseSchema):
    """Exam summary statistics."""

    exam_name: str
    subject: str
    total_students: int
    average_marks: Decimal
    highest_marks: Decimal
    lowest_marks: Decimal
    pass_count: int
    fail_count: int


# ==========================================
# Bulk Exam Operations
# ==========================================

class SingleExamInput(BaseSchema):
    """Single student exam entry for bulk operations."""

    student_id: int
    marks_obtained: Decimal = Field(..., ge=0)
    grade: str | None = None
    remarks: str | None = None


class BulkExamCreate(BaseSchema):
    """Bulk exam creation for a class on a specific date."""

    exam_name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=100)
    exam_date: date
    max_marks: Decimal = Field(..., gt=0)
    class_section: str = Field(..., description="Class-section like '3-A'")
    records: list[SingleExamInput]


class BulkExamResponse(BaseSchema):
    """Response for bulk exam operations."""

    total_records: int
    successful: int
    failed: int
    errors: list[dict] = []
    message: str


# ==========================================
# View/Edit Exam Data
# ==========================================

class StudentExamEntry(BaseSchema):
    """Student exam entry for view/edit."""

    student_id: int
    student_name: str
    class_name: str
    section: str | None
    marks_obtained: Decimal | None
    max_marks: Decimal | None
    grade: str | None
    remarks: str | None
    record_id: int | None


class ExamByClassResponse(BaseSchema):
    """Response for exam data by class."""

    class_section: str
    exam_name: str
    subject: str
    exam_date: date | None
    max_marks: Decimal | None
    students: list[StudentExamEntry]
    total_students: int
    average_marks: Decimal | None
    highest_marks: Decimal | None
    lowest_marks: Decimal | None


# ==========================================
# Template Generation
# ==========================================

class ExamTemplateRequest(BaseSchema):
    """Request for generating exam template."""

    class_section: str | None = Field(None, description="Class-section like '3-A'. If empty, generic template.")
    subject: str | None = Field(None, description="Subject for the exam template.")
    month: int | None = Field(None, ge=1, le=12, description="Month (1-12). Defaults to current month.")
    year: int | None = Field(None, description="Year. Defaults to current year.")


# ==========================================
# Excel Upload
# ==========================================

class ExamUploadError(BaseSchema):
    """Error detail for exam upload."""

    row: int
    student_name: str | None = None
    column: str | None = None
    message: str


class ExamUploadResult(BaseSchema):
    """Result of exam Excel upload processing."""

    total_rows: int
    successful_rows: int
    failed_rows: int
    skipped_rows: int = 0
    errors: list[ExamUploadError] = []
    message: str


class ExamUploadRow(BaseSchema):
    """Expected row format for exam Excel upload."""

    student_name: str
    class_section: str
    exam_name: str
    subject: str
    exam_date: str  # Will be parsed as date
    max_marks: str  # Will be parsed as Decimal
    marks_obtained: str  # Will be parsed as Decimal
    grade: str | None = None
    remarks: str | None = None
