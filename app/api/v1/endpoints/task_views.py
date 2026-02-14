"""Task view style management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import ProjectContext, require_permission
from app.schemas.common import MessageResponse
from app.schemas.task_view import (
    AvailableColumnsResponse,
    EffectiveViewResponse,
    TaskViewStyleCreate,
    TaskViewStyleListResponse,
    TaskViewStyleResponse,
    TaskViewStyleUpdate,
    UserViewPreferenceResponse,
    UserViewPreferenceUpdate,
)
from app.services.task_view import TaskViewService

router = APIRouter()


# ==================== View Style CRUD Endpoints ====================

@router.get("", response_model=TaskViewStyleListResponse)
def list_view_styles(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """List all task view styles for the project.
    
    Returns all view styles available in the project, including:
    - System default view (always present)
    - Project-created views (by any user)
    
    Also returns the project's default view style ID for reference.
    """
    service = TaskViewService(db)
    return service.list_view_styles(context.project_id)


@router.post("", response_model=TaskViewStyleResponse)
def create_view_style(
    request: TaskViewStyleCreate,
    context: Annotated[ProjectContext, Depends(require_permission("task_view:create"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new task view style.
    
    Any user with task_view:create permission can create views.
    Views are visible to all project members.
    """
    service = TaskViewService(db)
    return service.create_view_style(context.project_id, context.user_id, request)


@router.get("/columns", response_model=AvailableColumnsResponse)
def get_available_columns(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """Get list of all available columns for view configuration.
    
    Returns metadata about each column including:
    - field: Column identifier
    - label: Display name
    - default_visible: Whether it's visible in the default view
    - default_order: Default display order
    """
    service = TaskViewService(db)
    return service.get_available_columns()


@router.get("/me/effective", response_model=EffectiveViewResponse)
def get_effective_view(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """Get the effective view style for the current user.
    
    Returns the view the user should see based on priority:
    1. User's personal preference (if set)
    2. Project's default view (if set)
    3. System default view
    
    Also indicates the source of the view (user_preference, project_default, or system_default).
    """
    service = TaskViewService(db)
    return service.get_effective_view(context.user_id, context.project_id)


@router.get("/me/preference", response_model=UserViewPreferenceResponse | None)
def get_user_preference(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """Get current user's view style preference for this project.
    
    Returns null if the user has no personal preference set
    (in which case they see the project default).
    """
    service = TaskViewService(db)
    return service.get_user_preference(context.user_id, context.project_id)


@router.put("/me/preference", response_model=UserViewPreferenceResponse)
def set_user_preference(
    request: UserViewPreferenceUpdate,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """Set current user's preferred view style for this project.
    
    This overrides the project default for this user only.
    Other users are not affected.
    """
    service = TaskViewService(db)
    return service.set_user_preference(
        context.user_id,
        context.project_id,
        request.view_style_id,
    )


@router.delete("/me/preference", response_model=MessageResponse)
def clear_user_preference(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """Clear current user's view style preference.
    
    After clearing, the user will see the project's default view.
    """
    service = TaskViewService(db)
    service.clear_user_preference(context.user_id, context.project_id)
    return MessageResponse(message="View preference cleared successfully")


@router.get("/{view_id}", response_model=TaskViewStyleResponse)
def get_view_style(
    view_id: int,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """Get a specific task view style by ID."""
    service = TaskViewService(db)
    return service.get_view_style_response(view_id, context.project_id)


@router.patch("/{view_id}", response_model=TaskViewStyleResponse)
def update_view_style(
    view_id: int,
    request: TaskViewStyleUpdate,
    context: Annotated[ProjectContext, Depends(require_permission("task_view:update"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update a task view style.
    
    Users can update their own views.
    Admins can update any view.
    System default views can only be updated by admins.
    """
    service = TaskViewService(db)
    return service.update_view_style(
        view_id,
        context.project_id,
        context.user_id,
        request,
        is_admin=context.is_project_admin,
    )


@router.delete("/{view_id}", response_model=MessageResponse)
def delete_view_style(
    view_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("task_view:delete"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a task view style.
    
    Users can delete their own views.
    Admins can delete any view except system defaults.
    System default views cannot be deleted.
    """
    service = TaskViewService(db)
    service.delete_view_style(
        view_id,
        context.project_id,
        context.user_id,
        is_admin=context.is_project_admin,
    )
    return MessageResponse(message="View style deleted successfully")


@router.post("/{view_id}/set-project-default", response_model=TaskViewStyleResponse)
def set_project_default(
    view_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("task_view:set_default"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Set a view style as the project's default.
    
    Requires task_view:set_default permission (admin only).
    
    The default view is used for all project members who don't have
    a personal preference set.
    """
    service = TaskViewService(db)
    return service.set_project_default(context.project_id, view_id)
