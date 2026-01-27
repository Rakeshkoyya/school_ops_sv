"""Notification service."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.notification import Notification
from app.schemas.notification import (
    NotificationCreate,
    NotificationFilter,
    NotificationResponse,
    NotificationStats,
)


class NotificationService:
    """In-app notification service."""

    def __init__(self, db: Session):
        self.db = db

    def create_notification(
        self,
        project_id: UUID,
        request: NotificationCreate,
    ) -> NotificationResponse:
        """Create a new notification."""
        notification = Notification(
            project_id=project_id,
            user_id=request.user_id,
            title=request.title,
            message=request.message,
            notification_type=request.notification_type,
            action_url=request.action_url,
            action_data=request.action_data,
        )
        self.db.add(notification)
        self.db.flush()
        self.db.refresh(notification)

        return NotificationResponse.model_validate(notification)

    def get_notification(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> Notification:
        """Get notification by ID (must belong to user)."""
        result = self.db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        notification = result.scalar_one_or_none()
        if not notification:
            raise NotFoundError("Notification", str(notification_id))
        return notification

    def list_notifications(
        self,
        project_id: UUID,
        user_id: UUID,
        filters: NotificationFilter | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[NotificationResponse], int]:
        """List notifications for a user."""
        query = select(Notification).where(
            Notification.project_id == project_id,
            Notification.user_id == user_id,
        )

        if filters:
            if filters.is_read is not None:
                query = query.where(Notification.is_read == filters.is_read)
            if filters.notification_type:
                query = query.where(Notification.notification_type == filters.notification_type)

        # Count total
        count_result = self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Apply pagination and ordering
        query = (
            query
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = self.db.execute(query)
        notifications = result.scalars().all()

        return [NotificationResponse.model_validate(n) for n in notifications], total

    def mark_as_read(
        self,
        notification_ids: list[UUID],
        user_id: UUID,
    ) -> int:
        """Mark notifications as read. Returns count of updated."""
        result = self.db.execute(
            update(Notification)
            .where(
                Notification.id.in_(notification_ids),
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
            .values(
                is_read=True,
                read_at=datetime.now(timezone.utc),
            )
        )
        self.db.flush()
        return result.rowcount

    def mark_all_as_read(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> int:
        """Mark all notifications as read for a user."""
        result = self.db.execute(
            update(Notification)
            .where(
                Notification.project_id == project_id,
                Notification.user_id == user_id,
                Notification.is_read == False,
            )
            .values(
                is_read=True,
                read_at=datetime.now(timezone.utc),
            )
        )
        self.db.flush()
        return result.rowcount

    def get_stats(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> NotificationStats:
        """Get notification statistics for a user."""
        result = self.db.execute(
            select(
                func.count().label("total"),
                func.sum(func.cast(Notification.is_read == False, Integer)).label("unread"),
            )
            .where(
                Notification.project_id == project_id,
                Notification.user_id == user_id,
            )
        )
        row = result.one()

        total = row.total or 0
        unread = row.unread or 0

        return NotificationStats(
            total=total,
            unread=unread,
            read=total - unread,
        )

    def delete_notification(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> None:
        """Delete a notification."""
        notification = self.get_notification(notification_id, user_id)
        self.db.delete(notification)
        self.db.flush()


# Convenience functions for creating common notifications
def notify_upload_failed(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    upload_type: str,
    file_name: str,
    error_count: int,
) -> None:
    """Send notification for failed upload."""
    service = NotificationService(db)
    service.create_notification(
        project_id=project_id,
        request=NotificationCreate(
            user_id=user_id,
            title="Upload Failed",
            message=f"Your {upload_type} upload '{file_name}' failed with {error_count} errors.",
            notification_type="upload_failed",
        ),
    )


def notify_task_assigned(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    task_title: str,
    assigned_by: str,
) -> None:
    """Send notification for task assignment."""
    service = NotificationService(db)
    service.create_notification(
        project_id=project_id,
        request=NotificationCreate(
            user_id=user_id,
            title="New Task Assigned",
            message=f"You have been assigned a new task: '{task_title}' by {assigned_by}.",
            notification_type="task_assigned",
        ),
    )


def notify_permission_changed(
    db: Session,
    project_id: UUID,
    user_id: UUID,
    role_name: str,
    action: str,
) -> None:
    """Send notification for permission change."""
    service = NotificationService(db)
    service.create_notification(
        project_id=project_id,
        request=NotificationCreate(
            user_id=user_id,
            title="Permissions Updated",
            message=f"Your role '{role_name}' has been {action}.",
            notification_type="permission_changed",
        ),
    )


# Import for type hint
from sqlalchemy import Integer
