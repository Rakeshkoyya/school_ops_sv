"""Attendance schemas."""

from datetime import date, datetime
from typing import Optional

from pydantic import Field, field_validator

from app.models.attendance import AttendanceStatus
from app.schemas.common import BaseSchema


class AttendanceRecordCreate(BaseSchema):
    """Single attendance record creation schema."""

    student_id: int = Field(..., description="Student database ID")
    attendance_date: date
    status: AttendanceStatus
    remarks: str | None = None


class AttendanceRecordUpdate(BaseSchema):
    """Attendance record update schema."""

    status: AttendanceStatus | None = None
    remarks: str | None = None


class AttendanceRecordResponse(BaseSchema):
    """Attendance record response schema."""

    id: int
    project_id: int
    student_id: int
    student_name: str
    class_name: str
    section: str | None
    attendance_date: date
    status: AttendanceStatus
    remarks: str | None
    upload_id: int | None
    created_at: datetime
    updated_at: datetime


class AttendanceFilter(BaseSchema):
    """Attendance filtering options."""

    student_id: int | None = None
    class_name: str | None = None
    section: str | None = None
    class_section: str | None = None  # Combined filter like "3-A"
    status: AttendanceStatus | None = None
    date_from: date | None = None
    date_to: date | None = None


class AttendanceSummary(BaseSchema):
    """Attendance summary for a date range."""

    total_records: int
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int
    date_from: date
    date_to: date


class AttendanceUploadRow(BaseSchema):
    """Expected row format for attendance Excel upload."""

    student_id: int
    student_name: str
    attendance_date: str  # Will be parsed as date
    status: str  # present, absent, late, excused
    remarks: str | None = None


# ==========================================
# Bulk Attendance Operations
# ==========================================

class SingleAttendanceInput(BaseSchema):
    """Single student attendance entry for bulk operations."""

    student_id: int
    status: AttendanceStatus
    remarks: str | None = None


class BulkAttendanceCreate(BaseSchema):
    """Bulk attendance creation for a class on a specific date."""

    attendance_date: date
    class_section: str = Field(..., description="Class-section like '3-A'")
    records: list[SingleAttendanceInput]


class BulkAttendanceUpdate(BaseSchema):
    """Bulk attendance update request."""

    updates: list[dict]  # List of {id, status, remarks}


class BulkAttendanceResponse(BaseSchema):
    """Response for bulk attendance operations."""

    total_records: int
    successful: int
    failed: int
    errors: list[dict] = []
    message: str


# ==========================================
# Template Generation
# ==========================================

class TemplateRequest(BaseSchema):
    """Request for generating attendance template."""

    class_section: str | None = Field(None, description="Class-section like '3-A'. If empty, generic template.")
    month: int | None = Field(None, ge=1, le=12, description="Month (1-12). Defaults to current month.")
    year: int | None = Field(None, description="Year. Defaults to current year.")


# ==========================================
# Excel Upload
# ==========================================

class AttendanceUploadError(BaseSchema):
    """Error detail for attendance upload."""

    row: int
    student_name: str | None = None
    column: str | None = None
    message: str


class AttendanceUploadResult(BaseSchema):
    """Result of attendance Excel upload processing."""

    total_rows: int
    successful_rows: int
    failed_rows: int
    skipped_rows: int = 0
    errors: list[AttendanceUploadError] = []
    message: str


class AttendanceByClassResponse(BaseSchema):
    """Response for getting attendance by class and date."""

    class_section: str
    attendance_date: date
    students: list[dict]  # List of student with their attendance status
    total_students: int
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int
