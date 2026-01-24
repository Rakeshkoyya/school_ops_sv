"""Project management endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, ProjectContext, require_project_admin
from app.models.audit import AuditAction
from app.schemas.common import MessageResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.audit import AuditService
from app.services.project import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ProjectResponse)
async def create_project(
    request: ProjectCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Create a new project (school/tenant).
    The creator becomes the project admin.
    """
    logger.info(f"Creating project with data: {request}")
    service = ProjectService(db)
    project = await service.create_project(request, current_user.id)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.PROJECT_CREATED,
        resource_type="project",
        resource_id=str(project.id),
        project_id=project.id,
        user_id=current_user.id,
        description=f"Project '{project.name}' created",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return project


@router.get("", response_model=list[ProjectListItem])
async def list_user_projects(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    List all projects the current user belongs to.
    """
    service = ProjectService(db)
    return await service.list_user_projects(current_user.id)


@router.get("/current", response_model=ProjectResponse)
async def get_current_project(
    context: ProjectContext,
):
    """
    Get the current project (from X-Project-Id header).
    """
    return ProjectResponse.model_validate(context.project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get project details by ID.
    User must have access to the project.
    """
    service = ProjectService(db)
    project = await service.get_project(project_id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    request: ProjectUpdate,
    context: Annotated[ProjectContext, Depends(require_project_admin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Update project metadata.
    Requires project admin role.
    """
    service = ProjectService(db)
    project = await service.update_project(project_id, request)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.PROJECT_UPDATED,
        resource_type="project",
        resource_id=str(project_id),
        project_id=project_id,
        user_id=context.user_id,
        description=f"Project '{project.name}' updated",
        metadata={"changes": request.model_dump(exclude_unset=True)},
        ip_address=http_request.client.host if http_request.client else None,
    )

    return project


@router.post("/{project_id}/suspend", response_model=ProjectResponse)
async def suspend_project(
    project_id: int,
    context: Annotated[ProjectContext, Depends(require_project_admin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Suspend a project (blocks all mutations).
    Requires project admin role.
    """
    service = ProjectService(db)
    project = await service.suspend_project(project_id)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.PROJECT_SUSPENDED,
        resource_type="project",
        resource_id=str(project_id),
        project_id=project_id,
        user_id=context.user_id,
        description=f"Project '{project.name}' suspended",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return project


@router.post("/{project_id}/activate", response_model=ProjectResponse)
async def activate_project(
    project_id: int,
    context: Annotated[ProjectContext, Depends(require_project_admin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Activate a suspended project.
    Requires project admin role.
    """
    service = ProjectService(db)
    project = await service.activate_project(project_id)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.PROJECT_ACTIVATED,
        resource_type="project",
        resource_id=str(project_id),
        project_id=project_id,
        user_id=context.user_id,
        description=f"Project '{project.name}' activated",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return project


@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Delete a project and all its data.
    Super admin only - this is a destructive operation.
    """
    if not current_user.is_super_admin:
        from app.core.exceptions import PermissionDeniedError
        raise PermissionDeniedError("Super admin access required")
    
    service = ProjectService(db)
    project = await service.get_project(project_id)
    project_name = project.name
    
    await service.delete_project(project_id)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.PROJECT_DELETED,
        resource_type="project",
        resource_id=str(project_id),
        user_id=current_user.id,
        description=f"Project '{project_name}' deleted by super admin",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return MessageResponse(message=f"Project '{project_name}' deleted successfully")
