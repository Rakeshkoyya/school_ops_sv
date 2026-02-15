"""Menu screen endpoints for sidebar management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, ProjectContext
from app.core.exceptions import PermissionDeniedError
from app.models.audit import AuditAction
from app.schemas.common import MessageResponse
from app.schemas.menu_screen import (
    AvailablePermissionsResponse,
    MenuScreenCreate,
    MenuScreenUpdate,
    MenuScreenWithPermissions,
    ProjectMenuAllocationRequest,
    ProjectMenuAllocationResponse,
)
from app.services.audit import AuditService
from app.services.menu_screen import MenuScreenService

router = APIRouter()


# Super Admin endpoints
@router.get("", response_model=list[MenuScreenWithPermissions])
def list_menu_screens(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    """
    List all available menu screens with their permissions.
    Requires super admin access.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Only super admins can list all menu screens")
    
    service = MenuScreenService(db)
    return service.list_menu_screens()


@router.post("", response_model=MenuScreenWithPermissions)
def create_menu_screen(
    request: MenuScreenCreate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Create a new menu screen.
    Requires super admin access.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Only super admins can create menu screens")
    
    service = MenuScreenService(db)
    menu = service.create_menu_screen(request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.PROJECT_UPDATED,  # Reuse or add MENU_CREATED
        resource_type="menu_screen",
        resource_id=str(menu.id),
        project_id=None,
        user_id=user.id,
        description=f"Menu screen '{menu.name}' created",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return menu


# Project-scoped endpoints (for current project context)
@router.get("/current", response_model=ProjectMenuAllocationResponse)
def get_current_project_menus(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get menus allocated to the current project.
    Uses X-Project-Id header.
    """
    service = MenuScreenService(db)
    return service.get_project_menus(context.project_id)


@router.get("/current/permissions", response_model=AvailablePermissionsResponse)
def get_current_project_available_permissions(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get available permissions for the current project, grouped by menu.
    
    Only permissions from allocated menus are returned.
    Used by role management UI to show permission checkboxes.
    """
    service = MenuScreenService(db)
    return service.get_available_permissions_for_project(context.project_id)


# Super Admin menu screen management
@router.get("/{menu_id}", response_model=MenuScreenWithPermissions)
def get_menu_screen(
    menu_id: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get a specific menu screen.
    Requires super admin access.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Only super admins can view menu screen details")
    
    service = MenuScreenService(db)
    menu = service.get_menu_screen(menu_id)
    return service._menu_to_response(menu)


@router.patch("/{menu_id}", response_model=MenuScreenWithPermissions)
def update_menu_screen(
    menu_id: int,
    request: MenuScreenUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Update a menu screen.
    Requires super admin access.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Only super admins can update menu screens")
    
    service = MenuScreenService(db)
    menu = service.update_menu_screen(menu_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.PROJECT_UPDATED,
        resource_type="menu_screen",
        resource_id=str(menu.id),
        project_id=None,
        user_id=user.id,
        description=f"Menu screen '{menu.name}' updated",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return menu


@router.delete("/{menu_id}", response_model=MessageResponse)
def delete_menu_screen(
    menu_id: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Delete a menu screen.
    Requires super admin access.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Only super admins can delete menu screens")
    
    service = MenuScreenService(db)
    menu = service.get_menu_screen(menu_id)
    menu_name = menu.name
    service.delete_menu_screen(menu_id)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.PROJECT_DELETED,
        resource_type="menu_screen",
        resource_id=str(menu_id),
        project_id=None,
        user_id=user.id,
        description=f"Menu screen '{menu_name}' deleted",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return MessageResponse(message=f"Menu screen '{menu_name}' deleted successfully")


# Project allocation endpoints
@router.get("/project/{project_id}", response_model=ProjectMenuAllocationResponse)
def get_project_menus(
    project_id: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get menus allocated to a specific project.
    Requires super admin access.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Only super admins can view project menu allocations")
    
    service = MenuScreenService(db)
    return service.get_project_menus(project_id)


@router.put("/project/{project_id}", response_model=ProjectMenuAllocationResponse)
def allocate_menus_to_project(
    project_id: int,
    request: ProjectMenuAllocationRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Allocate menus to a project.
    
    This replaces current allocations. Menus not in the list will be deallocated.
    When a menu is deallocated, its permissions are removed from all roles in the project.
    Requires super admin access.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Only super admins can allocate menus to projects")
    
    service = MenuScreenService(db)
    result = service.allocate_menus_to_project(project_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.PROJECT_UPDATED,
        resource_type="project",
        resource_id=str(project_id),
        project_id=project_id,
        user_id=user.id,
        description=f"Menu allocations updated for project",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return result


@router.get("/project/{project_id}/permissions", response_model=AvailablePermissionsResponse)
def get_project_available_permissions(
    project_id: int,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get available permissions for a specific project, grouped by menu.
    Requires super admin access.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Only super admins can view other project permissions")
    
    service = MenuScreenService(db)
    return service.get_available_permissions_for_project(project_id)
