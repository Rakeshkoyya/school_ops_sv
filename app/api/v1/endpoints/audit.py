"""Audit log endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ProjectContext, require_permission
from app.models.audit import AuditAction
from app.schemas.audit import AuditLogFilter, AuditLogWithUser
from app.schemas.common import PaginatedResponse
from app.services.audit import AuditService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AuditLogWithUser])
async def list_audit_logs(
    context: Annotated[ProjectContext, Depends(require_permission("audit:view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    action: AuditAction | None = None,
    user_id: UUID | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    List audit logs for the project with filtering.
    Audit logs are append-only and cannot be modified.
    Requires audit:view permission.
    """
    service = AuditService(db)
    filters = AuditLogFilter(
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
    )
    logs, total = await service.list_logs(
        project_id=context.project_id,
        filters=filters,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=logs,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/actions", response_model=list[str])
async def list_audit_actions(
    context: ProjectContext,
):
    """
    List all available audit action types.
    """
    return [action.value for action in AuditAction]


@router.get("/resource-types", response_model=list[str])
async def list_resource_types(
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    List distinct resource types in the audit log.
    """
    from sqlalchemy import distinct, select
    from app.models.audit import AuditLog

    result = await db.execute(
        select(distinct(AuditLog.resource_type))
        .where(AuditLog.project_id == context.project_id)
        .order_by(AuditLog.resource_type)
    )
    return list(result.scalars().all())
