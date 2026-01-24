"""Upload schemas."""

from datetime import datetime

from app.models.upload import UploadStatus, UploadType
from app.schemas.common import BaseSchema


class UploadResponse(BaseSchema):
    """Upload record response schema."""

    id: int
    project_id: int
    upload_type: UploadType
    file_name: str
    file_size: int
    status: UploadStatus
    total_rows: int
    successful_rows: int
    failed_rows: int
    error_message: str | None
    uploaded_by_id: int
    processing_started_at: datetime | None
    processing_completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UploadWithDetails(UploadResponse):
    """Upload response with additional details."""

    uploaded_by_name: str | None = None
    errors: list["UploadErrorResponse"] = []


class UploadErrorResponse(BaseSchema):
    """Upload error response schema."""

    id: int
    upload_id: int
    row_number: int
    column_name: str | None
    error_type: str
    error_message: str
    raw_value: str | None


class UploadFilter(BaseSchema):
    """Upload filtering options."""

    upload_type: UploadType | None = None
    status: UploadStatus | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class UploadResult(BaseSchema):
    """Result of an upload operation."""

    upload_id: int
    status: UploadStatus
    total_rows: int
    successful_rows: int
    failed_rows: int
    errors: list[UploadErrorResponse] = []
    message: str
