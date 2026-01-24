"""Audit logging service."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditAction, AuditLog
from app.schemas.audit import AuditLogFilter, AuditLogWithUser


class AuditService:
    """Audit logging service - append-only."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str | None = None,
        project_id: UUID | None = None,
        user_id: UUID | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry."""
        log = AuditLog(
            project_id=project_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_logs(
        self,
        project_id: UUID | None = None,
        filters: AuditLogFilter | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLogWithUser], int]:
        """List audit logs with filtering."""
        from sqlalchemy import func
        from sqlalchemy.orm import selectinload

        from app.models.user import User

        query = select(AuditLog).options(selectinload(AuditLog.user))

        if project_id:
            query = query.where(AuditLog.project_id == project_id)

        if filters:
            if filters.action:
                query = query.where(AuditLog.action == filters.action)
            if filters.user_id:
                query = query.where(AuditLog.user_id == filters.user_id)
            if filters.resource_type:
                query = query.where(AuditLog.resource_type == filters.resource_type)
            if filters.date_from:
                query = query.where(AuditLog.created_at >= filters.date_from)
            if filters.date_to:
                query = query.where(AuditLog.created_at <= filters.date_to)

        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Apply pagination and ordering
        query = (
            query
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        logs = result.scalars().all()

        return [
            AuditLogWithUser(
                id=log.id,
                project_id=log.project_id,
                user_id=log.user_id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                description=log.description,
                metadata=log.metadata,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                created_at=log.created_at,
                user_name=log.user.name if log.user else None,
                user_username=log.user.username if log.user else None,
            )
            for log in logs
        ], total


# Convenience functions for common audit actions
async def audit_user_created(
    db: AsyncSession,
    created_user_id: UUID,
    created_by_id: UUID,
    project_id: UUID | None = None,
    ip_address: str | None = None,
) -> None:
    """Log user creation."""
    service = AuditService(db)
    await service.log(
        action=AuditAction.USER_CREATED,
        resource_type="user",
        resource_id=str(created_user_id),
        project_id=project_id,
        user_id=created_by_id,
        description=f"User {created_user_id} was created",
        ip_address=ip_address,
    )


async def audit_role_updated(
    db: AsyncSession,
    role_id: UUID,
    project_id: UUID,
    user_id: UUID,
    changes: dict[str, Any],
    ip_address: str | None = None,
) -> None:
    """Log role update."""
    service = AuditService(db)
    await service.log(
        action=AuditAction.ROLE_UPDATED,
        resource_type="role",
        resource_id=str(role_id),
        project_id=project_id,
        user_id=user_id,
        description=f"Role {role_id} was updated",
        metadata={"changes": changes},
        ip_address=ip_address,
    )


async def audit_upload_failed(
    db: AsyncSession,
    upload_id: UUID,
    project_id: UUID,
    user_id: UUID,
    error_message: str,
    ip_address: str | None = None,
) -> None:
    """Log upload failure."""
    service = AuditService(db)
    await service.log(
        action=AuditAction.UPLOAD_FAILED,
        resource_type="upload",
        resource_id=str(upload_id),
        project_id=project_id,
        user_id=user_id,
        description=f"Upload {upload_id} failed: {error_message}",
        ip_address=ip_address,
    )
