"""Attendance schemas."""

from datetime import date, datetime

from pydantic import Field

from app.models.attendance import AttendanceStatus
from app.schemas.common import BaseSchema


class AttendanceRecordCreate(BaseSchema):
    """Single attendance record creation schema."""

    student_id: str = Field(..., min_length=1, max_length=100)
    student_name: str = Field(..., min_length=1, max_length=255)
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
    student_id: str
    student_name: str
    attendance_date: date
    status: AttendanceStatus
    remarks: str | None
    upload_id: int | None
    created_at: datetime
    updated_at: datetime


class AttendanceFilter(BaseSchema):
    """Attendance filtering options."""

    student_id: str | None = None
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

    student_id: str
    student_name: str
    attendance_date: str  # Will be parsed as date
    status: str  # present, absent, late, excused
    remarks: str | None = None
