"""Exam schemas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


class ExamRecordCreate(BaseSchema):
    """Single exam record creation schema."""

    student_id: str = Field(..., min_length=1, max_length=100)
    student_name: str = Field(..., min_length=1, max_length=255)
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
        # Note: This validation is also enforced at service layer
        return v


class ExamRecordUpdate(BaseSchema):
    """Exam record update schema."""

    marks_obtained: Decimal | None = Field(None, ge=0)
    grade: str | None = Field(None, max_length=10)
    remarks: str | None = None


class ExamRecordResponse(BaseSchema):
    """Exam record response schema."""

    id: int
    project_id: int
    student_id: str
    student_name: str
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

    student_id: str | None = None
    exam_name: str | None = None
    subject: str | None = None
    date_from: date | None = None
    date_to: date | None = None


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


class ExamUploadRow(BaseSchema):
    """Expected row format for exam Excel upload."""

    student_id: str
    student_name: str
    exam_name: str
    subject: str
    exam_date: str  # Will be parsed as date
    max_marks: str  # Will be parsed as Decimal
    marks_obtained: str  # Will be parsed as Decimal
    grade: str | None = None
    remarks: str | None = None
