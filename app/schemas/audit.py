"""Audit log schemas."""

from datetime import datetime
from typing import Any

from app.models.audit import AuditAction
from app.schemas.common import BaseSchema


class AuditLogResponse(BaseSchema):
    """Audit log response schema."""

    id: int
    project_id: int | None
    user_id: int | None
    action: AuditAction
    resource_type: str
    resource_id: str | None
    description: str | None
    metadata: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AuditLogWithUser(AuditLogResponse):
    """Audit log with user details."""

    user_name: str | None = None
    user_username: str | None = None


class AuditLogFilter(BaseSchema):
    """Audit log filtering options."""

    action: AuditAction | None = None
    user_id: int | None = None
    resource_type: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class AuditLogCreate(BaseSchema):
    """Internal schema for creating audit logs."""

    project_id: int | None = None
    user_id: int | None = None
    action: AuditAction
    resource_type: str
    resource_id: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
