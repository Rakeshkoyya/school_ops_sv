"""RBAC endpoints for roles and permissions."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, ProjectContext, require_role_admin
from app.core.exceptions import PermissionDeniedError
from app.models.audit import AuditAction
from app.schemas.common import MessageResponse
from app.schemas.rbac import (
    BulkUserRoleAssign,
    PermissionResponse,
    RoleCreate,
    RolePermissionAssign,
    RoleResponse,
    RoleUpdate,
    RoleWithPermissions,
    RoleWithPermissionsAndProject,
    UserRoleAssign,
    UserRoleResponse,
    UserWithRoles,
)
from app.services.audit import AuditService
from app.services.rbac import RBACService

router = APIRouter()


# Permission endpoints
@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    List all available permissions.
    """
    service = RBACService(db)
    return await service.list_permissions()


# Role endpoints
@router.post("", response_model=RoleWithPermissions)
async def create_role(
    request: RoleCreate,
    context: Annotated[ProjectContext, Depends(require_role_admin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Create a new role for the project.
    Requires role admin access.
    """
    service = RBACService(db)
    role = await service.create_role(context.project_id, request)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ROLE_CREATED,
        resource_type="role",
        resource_id=str(role.id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Role '{role.name}' created",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return role


@router.post("/admin", response_model=RoleWithPermissions)
async def create_role_admin(
    request: RoleCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Create a new role for any project (super admin only).
    Requires super admin access and project_id in request body.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Super admin access required")
    
    if not request.project_id:
        raise PermissionDeniedError("project_id is required for super admin role creation")
    
    service = RBACService(db)
    role = await service.create_role(request.project_id, request)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ROLE_CREATED,
        resource_type="role",
        resource_id=str(role.id),
        project_id=request.project_id,
        user_id=user.id,
        description=f"Role '{role.name}' created by super admin",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return role


@router.get("/all", response_model=list[RoleWithPermissionsAndProject])
async def list_all_roles(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    List all roles across all projects.
    Super admin only.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Super admin access required")
    
    service = RBACService(db)
    roles = await service.list_all_roles()
    return roles


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    List all roles for the project.
    """
    service = RBACService(db)
    return await service.list_roles(context.project_id)


@router.get("/{role_id}", response_model=RoleWithPermissions)
async def get_role(
    role_id: UUID,
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get role details with permissions.
    """
    service = RBACService(db)
    return await service.get_role_with_permissions(role_id, context.project_id)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    request: RoleUpdate,
    context: Annotated[ProjectContext, Depends(require_role_admin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Update a role.
    Requires role admin access.
    """
    service = RBACService(db)
    role = await service.update_role(role_id, context.project_id, request)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ROLE_UPDATED,
        resource_type="role",
        resource_id=str(role_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Role '{role.name}' updated",
        metadata={"changes": request.model_dump(exclude_unset=True)},
        ip_address=http_request.client.host if http_request.client else None,
    )

    return role


@router.patch("/admin/{role_id}", response_model=RoleResponse)
async def update_role_admin(
    role_id: int,
    request: RoleUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Update a role (super admin only).
    Requires super admin access and project_id in request body.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Super admin access required")
    
    if not request.project_id:
        raise PermissionDeniedError("project_id is required for super admin role update")
    
    service = RBACService(db)
    role = await service.update_role(role_id, request.project_id, request)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ROLE_UPDATED,
        resource_type="role",
        resource_id=str(role_id),
        project_id=request.project_id,
        user_id=user.id,
        description=f"Role '{role.name}' updated by super admin",
        metadata={"changes": request.model_dump(exclude_unset=True)},
        ip_address=http_request.client.host if http_request.client else None,
    )

    return role


@router.delete("/{role_id}", response_model=MessageResponse)
async def delete_role(
    role_id: UUID,
    context: Annotated[ProjectContext, Depends(require_role_admin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Delete a role.
    Cannot delete roles with assigned users.
    Requires role admin access.
    """
    service = RBACService(db)
    await service.delete_role(role_id, context.project_id)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ROLE_DELETED,
        resource_type="role",
        resource_id=str(role_id),
        project_id=context.project_id,
        user_id=context.user_id,
        ip_address=http_request.client.host if http_request.client else None,
    )

    return MessageResponse(message="Role deleted successfully")


@router.delete("/admin/{role_id}", response_model=MessageResponse)
async def delete_role_admin(
    role_id: int,
    project_id: int,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Delete a role (super admin only).
    Cannot delete roles with assigned users.
    Requires super admin access.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Super admin access required")
    
    service = RBACService(db)
    await service.delete_role(role_id, project_id)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ROLE_DELETED,
        resource_type="role",
        resource_id=str(role_id),
        project_id=project_id,
        user_id=user.id,
        ip_address=http_request.client.host if http_request.client else None,
    )

    return MessageResponse(message="Role deleted successfully")


@router.put("/{role_id}/permissions", response_model=RoleWithPermissions)
async def assign_permissions_to_role(
    role_id: UUID,
    request: RolePermissionAssign,
    context: Annotated[ProjectContext, Depends(require_role_admin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Assign permissions to a role (replaces existing permissions).
    Requires role admin access.
    """
    service = RBACService(db)
    role = await service.assign_permissions_to_role(
        role_id,
        context.project_id,
        request.permission_ids,
    )

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.PERMISSION_GRANTED,
        resource_type="role",
        resource_id=str(role_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Permissions updated for role '{role.name}'",
        metadata={"permission_ids": [str(p) for p in request.permission_ids]},
        ip_address=http_request.client.host if http_request.client else None,
    )

    return role


# User-Role assignment endpoints
@router.post("/users/bulk-assign", response_model=MessageResponse)
async def bulk_assign_user_roles(
    request: BulkUserRoleAssign,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Bulk assign roles to a user across multiple projects.
    Super admin only - replaces all existing role assignments for the user.
    """
    if not user.is_super_admin:
        raise PermissionDeniedError("Super admin access required")

    service = RBACService(db)
    result = await service.bulk_assign_user_roles(request)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ROLE_ASSIGNED,
        resource_type="user_role_bulk",
        user_id=user.id,
        description=f"Bulk role assignment for user {request.user_id}",
        metadata={
            "target_user_id": request.user_id,
            "projects_updated": result["projects_updated"],
            "assignments_created": result["assignments_created"],
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    return MessageResponse(
        message=f"Successfully updated {result['assignments_created']} role assignments across {result['projects_updated']} projects"
    )


@router.get("/users", response_model=list[UserWithRoles])
async def list_project_users(
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    List all users in the project with their roles.
    """
    service = RBACService(db)
    return await service.list_project_users(context.project_id)


@router.post("/users", response_model=UserRoleResponse)
async def assign_user_to_role(
    request: UserRoleAssign,
    context: Annotated[ProjectContext, Depends(require_role_admin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Assign a user to a role in the project.
    Requires role admin access.
    """
    service = RBACService(db)
    assignment = await service.assign_user_to_role(context.project_id, request)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ROLE_ASSIGNED,
        resource_type="user_role",
        resource_id=str(assignment.id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"User assigned to role",
        metadata={
            "assigned_user_id": str(request.user_id),
            "role_id": str(request.role_id),
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    return assignment


@router.delete("/users/{user_id}/roles/{role_id}", response_model=MessageResponse)
async def revoke_user_role(
    user_id: UUID,
    role_id: UUID,
    context: Annotated[ProjectContext, Depends(require_role_admin())],
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Remove a user from a role in the project.
    Requires role admin access.
    """
    service = RBACService(db)
    await service.revoke_user_role(context.project_id, user_id, role_id)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ROLE_REVOKED,
        resource_type="user_role",
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"User role revoked",
        metadata={
            "revoked_user_id": str(user_id),
            "role_id": str(role_id),
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    return MessageResponse(message="User role revoked successfully")
