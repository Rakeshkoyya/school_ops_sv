"""Project management endpoints."""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

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
from app.schemas.project_transfer import ProjectImportResult
from app.services.audit import AuditService
from app.services.project import ProjectService
from app.services.project_transfer import ProjectTransferService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ProjectResponse)
def create_project(
    request: ProjectCreate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Create a new project (school/tenant).
    The creator becomes the project admin.
    """
    logger.info(f"Creating project with data: {request}")
    service = ProjectService(db)
    project = service.create_project(request, current_user.id)

    # Audit log
    audit = AuditService(db)
    audit.log(
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
def list_user_projects(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    """
    List all projects the current user belongs to.
    """
    service = ProjectService(db)
    return service.list_user_projects(current_user.id)


@router.get("/all", response_model=list[ProjectResponse])
def list_all_projects(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    """
    List all projects in the system (super admin only).
    """
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can access all projects"
        )
    service = ProjectService(db)
    return service.list_all_projects()


@router.get("/current", response_model=ProjectResponse)
def get_current_project(
    context: ProjectContext,
):
    """
    Get the current project (from X-Project-Id header).
    """
    return ProjectResponse.model_validate(context.project)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get project details by ID.
    User must have access to the project.
    """
    service = ProjectService(db)
    project = service.get_project(project_id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    request: ProjectUpdate,
    context: Annotated[ProjectContext, Depends(require_project_admin())],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Update project metadata.
    Requires project admin role.
    """
    service = ProjectService(db)
    project = service.update_project(project_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
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
def suspend_project(
    project_id: int,
    context: Annotated[ProjectContext, Depends(require_project_admin())],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Suspend a project (blocks all mutations).
    Requires project admin role.
    """
    service = ProjectService(db)
    project = service.suspend_project(project_id)

    # Audit log
    audit = AuditService(db)
    audit.log(
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
def activate_project(
    project_id: int,
    context: Annotated[ProjectContext, Depends(require_project_admin())],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Activate a suspended project.
    Requires project admin role.
    """
    service = ProjectService(db)
    project = service.activate_project(project_id)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.PROJECT_ACTIVATED,
        resource_type="project",
        resource_id=str(project_id),
        project_id=project_id,
        user_id=context.user_id,
        description=f"Project '{project.name}' activated",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return project


@router.get("/{project_id}/export")
def export_project(
    project_id: int,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Export all project data as a JSON file.
    Super admin only.
    """
    if not current_user.is_super_admin:
        from app.core.exceptions import PermissionDeniedError
        raise PermissionDeniedError("Super admin access required")

    service = ProjectTransferService(db)
    export_data = service.export_project(project_id)

    slug = export_data.get("project", {}).get("slug", "project")
    content = json.dumps(export_data, indent=2, default=str)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.PROJECT_UPDATED,
        resource_type="project",
        resource_id=str(project_id),
        user_id=current_user.id,
        description=f"Project '{slug}' exported",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{slug}_export.json"'
        },
    )


@router.post("/import", response_model=ProjectImportResult)
def import_project(
    file: UploadFile,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Import a project from an exported JSON file.
    Super admin only. Creates a new project with all associated data.
    """
    if not current_user.is_super_admin:
        from app.core.exceptions import PermissionDeniedError
        raise PermissionDeniedError("Super admin access required")

    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .json files are accepted",
        )

    try:
        raw = file.file.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON file: {exc}",
        )

    service = ProjectTransferService(db)
    result = service.import_project(data)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.PROJECT_CREATED,
        resource_type="project",
        resource_id=str(result.project_id),
        project_id=result.project_id,
        user_id=current_user.id,
        description=f"Project '{result.project_name}' imported from file",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return result


@router.delete("/{project_id}", response_model=MessageResponse)
def delete_project(
    project_id: int,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
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
    project = service.get_project(project_id)
    project_name = project.name
    
    service.delete_project(project_id)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.PROJECT_DELETED,
        resource_type="project",
        resource_id=str(project_id),
        user_id=current_user.id,
        description=f"Project '{project_name}' deleted by super admin",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return MessageResponse(message=f"Project '{project_name}' deleted successfully")
