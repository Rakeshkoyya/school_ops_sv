"""Notification endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ProjectContext
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.notification import (
    NotificationFilter,
    NotificationMarkRead,
    NotificationResponse,
    NotificationStats,
)
from app.services.notification import NotificationService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
    is_read: bool | None = None,
    notification_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List notifications for the current user.
    """
    service = NotificationService(db)
    filters = NotificationFilter(
        is_read=is_read,
        notification_type=notification_type,
    )
    notifications, total = await service.list_notifications(
        project_id=context.project_id,
        user_id=context.user_id,
        filters=filters,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=notifications,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get notification statistics (total, read, unread counts).
    """
    service = NotificationService(db)
    return await service.get_stats(context.project_id, context.user_id)


@router.post("/mark-read", response_model=MessageResponse)
async def mark_notifications_read(
    request: NotificationMarkRead,
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Mark specific notifications as read.
    """
    service = NotificationService(db)
    count = await service.mark_as_read(request.notification_ids, context.user_id)
    return MessageResponse(message=f"Marked {count} notifications as read")


@router.post("/mark-all-read", response_model=MessageResponse)
async def mark_all_notifications_read(
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Mark all notifications as read.
    """
    service = NotificationService(db)
    count = await service.mark_all_as_read(context.project_id, context.user_id)
    return MessageResponse(message=f"Marked {count} notifications as read")


@router.delete("/{notification_id}", response_model=MessageResponse)
async def delete_notification(
    notification_id: UUID,
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Delete a notification.
    """
    service = NotificationService(db)
    await service.delete_notification(notification_id, context.user_id)
    return MessageResponse(message="Notification deleted successfully")
