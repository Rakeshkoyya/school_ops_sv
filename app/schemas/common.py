"""Common schema utilities and base classes."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields."""

    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class PaginatedResponse(BaseSchema, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class SuccessResponse(BaseSchema):
    """Standard success response."""

    success: bool = True
    message: str | None = None
    data: Any = None


class ErrorDetail(BaseSchema):
    """Error detail structure."""

    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(BaseSchema):
    """Standard error response."""

    success: bool = False
    error: ErrorDetail


class MessageResponse(BaseSchema):
    """Simple message response."""

    message: str
