"""Notification schemas."""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import BaseSchema


class NotificationCreate(BaseSchema):
    """Notification creation schema (internal use)."""

    user_id: int
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    notification_type: str = Field(..., min_length=1, max_length=50)
    action_url: str | None = None
    action_data: dict[str, Any] | None = None


class NotificationResponse(BaseSchema):
    """Notification response schema."""

    id: int
    project_id: int
    user_id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    read_at: datetime | None
    action_url: str | None
    action_data: dict[str, Any] | None
    created_at: datetime


class NotificationFilter(BaseSchema):
    """Notification filtering options."""

    is_read: bool | None = None
    notification_type: str | None = None


class NotificationMarkRead(BaseSchema):
    """Mark notifications as read."""

    notification_ids: list[int]


class NotificationStats(BaseSchema):
    """Notification statistics."""

    total: int
    unread: int
    read: int
