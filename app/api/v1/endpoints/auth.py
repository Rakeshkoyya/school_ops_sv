"""Authentication endpoints."""

from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, ProjectContext
from app.core.exceptions import PermissionDeniedError, UploadError
from app.models.audit import AuditAction
from app.schemas.auth import (
    AdminUserUpdate,
    CurrentUserResponse,
    LoginRequest,
    PasswordChange,
    ProjectUserUpdate,
    RefreshTokenRequest,
    TokenResponse,
    UserBulkUploadResult,
    UserCreate,
    UserResponse,
    UserWithProjectRoles,
)
from app.schemas.common import MessageResponse
from app.services.audit import AuditService
from app.services.auth import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Authenticate user and return access/refresh tokens.
    """
    service = AuthService(db)
    response = await service.login(request)

    # Audit log
    audit = AuditService(db)
    # Get user ID from token for audit
    from app.core.security import verify_access_token
    payload = verify_access_token(response.access_token)
    if payload:
        user_id_str = payload.get("sub")
        user_id = int(user_id_str) if user_id_str else None
        await audit.log(
            action=AuditAction.USER_LOGIN,
            resource_type="user",
            resource_id=user_id_str,
            user_id=user_id,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent"),
        )

    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Refresh access token using a valid refresh token.
    """
    service = AuthService(db)
    return await service.refresh_tokens(request.refresh_token)


@router.post("/register", response_model=UserResponse)
async def register(
    request: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Register a new user account.
    """
    service = AuthService(db)
    user = await service.register_user(request)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.USER_CREATED,
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
        description=f"User {user.username} registered",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return user


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get current authenticated user with their projects and role assignments.
    Returns:
    - user: User info
    - projects: List of unique projects the user has access to
    - user_roles: List of all role assignments (a user can have multiple roles per project)
    - permissions: Aggregated permissions across all roles
    """
    from app.schemas.auth import ProjectInfo, UserRoleInfo
    from app.services.project import ProjectService
    from app.services.rbac import RBACService
    
    project_service = ProjectService(db)
    rbac_service = RBACService(db)
    
    # Get all project-role combinations for the user
    user_project_roles = await project_service.list_user_projects(current_user.id)
    
    # Build unique projects list
    projects_map: dict[int, ProjectInfo] = {}
    user_roles: list[UserRoleInfo] = []
    all_permissions: set[str] = set()
    
    for proj in user_project_roles:
        # Add to unique projects map
        if proj.id not in projects_map:
            projects_map[proj.id] = ProjectInfo(
                id=proj.id,
                name=proj.name,
                slug=proj.slug,
                description=proj.description,
                theme_color=proj.theme_color,
                logo_url=proj.logo_url,
                status=proj.status.value if hasattr(proj.status, 'value') else str(proj.status),
            )
        
        # Get permissions for this specific role
        role_permissions: set[str] = set()
        if proj.role_id:
            role_permissions = await rbac_service.get_role_permissions(proj.role_id)
        all_permissions.update(role_permissions)
        
        # Add role assignment
        user_roles.append(UserRoleInfo(
            role_id=proj.role_id,
            role_name=proj.role_name or "Member",
            project_id=proj.id,
            project_name=proj.name,
            project_slug=proj.slug,
            is_project_admin=proj.is_project_admin,
            is_role_admin=getattr(proj, 'is_role_admin', False),
            permissions=sorted(list(role_permissions)),
        ))
    
    return CurrentUserResponse(
        user=UserResponse.model_validate(current_user),
        projects=list(projects_map.values()),
        user_roles=user_roles,
        permissions=sorted(list(all_permissions)),
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: PasswordChange,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Change current user's password.
    """
    service = AuthService(db)
    await service.change_password(
        current_user.id,
        request.current_password,
        request.new_password,
    )
    return MessageResponse(message="Password changed successfully")


# Super Admin User Management Endpoints
@router.get("/users", response_model=list[UserWithProjectRoles])
async def list_all_users(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    unassigned_only: bool = Query(False, description="Only show users with no project assignments"),
):
    """
    List all users with their project-role mappings.
    Super admin only.
    Use unassigned_only=true to filter users without any project assignments.
    """
    if not current_user.is_super_admin:
        raise PermissionDeniedError("Super admin access required")
    
    service = AuthService(db)
    if unassigned_only:
        return await service.list_unassigned_users()
    return await service.list_all_users()


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_admin(
    user_id: int,
    request: AdminUserUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Update a user (super admin only).
    """
    if not current_user.is_super_admin:
        raise PermissionDeniedError("Super admin access required")
    
    service = AuthService(db)
    user = await service.update_user_admin(user_id, request)
    
    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.USER_UPDATED,
        resource_type="user",
        resource_id=str(user_id),
        user_id=current_user.id,
        description=f"User {user.username} updated by super admin",
        metadata=request.model_dump(exclude_unset=True),
        ip_address=http_request.client.host if http_request.client else None,
    )
    
    return user


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Delete a user (super admin only).
    """
    if not current_user.is_super_admin:
        raise PermissionDeniedError("Super admin access required")
    
    if user_id == current_user.id:
        raise PermissionDeniedError("Cannot delete your own account")
    
    service = AuthService(db)
    await service.delete_user(user_id)
    
    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.USER_DELETED,
        resource_type="user",
        resource_id=str(user_id),
        user_id=current_user.id,
        description=f"User deleted by super admin",
        ip_address=http_request.client.host if http_request.client else None,
    )
    
    return MessageResponse(message="User deleted successfully")


@router.get("/users/template")
async def download_user_template(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_role: bool = Query(False, description="Include Role ID column"),
):
    """
    Download Excel template for user bulk upload.
    Super admin only.
    """
    if not current_user.is_super_admin:
        raise PermissionDeniedError("Super admin access required")
    
    service = AuthService(db)
    content = service.generate_user_template(include_role_column=include_role)

    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=users_template.xlsx"},
    )


@router.post("/users/upload", response_model=UserBulkUploadResult)
async def bulk_upload_users(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
    file: UploadFile = File(...),
    project_id: int | None = Query(None, description="Project ID to assign users to"),
    default_role_id: int | None = Query(None, description="Default role ID if not specified in Excel"),
):
    """
    Bulk upload users from Excel file.
    Super admin only.
    
    Download the template first to see the expected format.
    Optionally assign users to a project with a default role.
    """
    if not current_user.is_super_admin:
        raise PermissionDeniedError("Super admin access required")
    
    # Validate file
    if not file.filename:
        raise UploadError("No file provided")

    if not file.filename.endswith(".xlsx"):
        raise UploadError("Only .xlsx files are allowed")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise UploadError(f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    service = AuthService(db)
    result = await service.bulk_upload_users(content, project_id, default_role_id)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.UPLOAD_COMPLETED,
        resource_type="user_upload",
        user_id=current_user.id,
        description=f"User bulk upload: {result.successful_rows}/{result.total_rows} rows",
        metadata={
            "file_name": file.filename,
            "successful_rows": result.successful_rows,
            "failed_rows": result.failed_rows,
            "project_id": project_id,
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    return result


# Project-scoped user management endpoints
@router.get("/project-users", response_model=list[UserWithProjectRoles])
async def list_project_users(
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    List all users in the current project with their roles.
    Requires user:view permission or project admin.
    """
    service = AuthService(db)
    return await service.list_project_users(context.project_id)


@router.get("/project-users/template")
async def download_project_user_template(
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Download Excel template for user bulk upload to project.
    """
    service = AuthService(db)
    content = service.generate_user_template(include_role_column=True)

    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=users_template.xlsx"},
    )


@router.post("/project-users/upload", response_model=UserBulkUploadResult)
async def bulk_upload_project_users(
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
    file: UploadFile = File(...),
    default_role_id: int | None = Query(None, description="Default role ID if not specified in Excel"),
):
    """
    Bulk upload users to the current project.
    Requires user:invite permission or project admin.
    
    Download the template first to see the expected format.
    """
    # Validate file
    if not file.filename:
        raise UploadError("No file provided")

    if not file.filename.endswith(".xlsx"):
        raise UploadError("Only .xlsx files are allowed")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise UploadError(f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    service = AuthService(db)
    result = await service.bulk_upload_users(content, context.project_id, default_role_id)

    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.UPLOAD_COMPLETED,
        resource_type="user_upload",
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"User bulk upload: {result.successful_rows}/{result.total_rows} rows",
        metadata={
            "file_name": file.filename,
            "successful_rows": result.successful_rows,
            "failed_rows": result.failed_rows,
        },
        ip_address=http_request.client.host if http_request.client else None,
    )

    return result


@router.patch("/project-users/{user_id}", response_model=UserResponse)
async def update_project_user(
    user_id: int,
    request: ProjectUserUpdate,
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Update a user within the current project.
    Requires user:invite permission or project admin.
    School admins can update name, phone, and is_active status.
    """
    # Check permission
    if not context.has_permission("user:invite") and not context.is_project_admin():
        raise PermissionDeniedError("Permission 'user:invite' required")
    
    # Cannot modify yourself
    if user_id == context.user_id:
        raise PermissionDeniedError("Cannot modify your own account through this endpoint")
    
    service = AuthService(db)
    user = await service.update_project_user(user_id, context.project_id, request)
    
    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.USER_UPDATED,
        resource_type="user",
        resource_id=str(user_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"User {user.username} updated",
        metadata=request.model_dump(exclude_unset=True),
        ip_address=http_request.client.host if http_request.client else None,
    )
    
    return user


@router.delete("/project-users/{user_id}", response_model=MessageResponse)
async def remove_user_from_project(
    user_id: int,
    context: ProjectContext,
    db: Annotated[AsyncSession, Depends(get_db)],
    http_request: Request,
):
    """
    Remove a user from the current project.
    Requires user:remove permission or project admin.
    This removes the user's role assignment in the project, not the user account itself.
    """
    # Check permission
    if not context.has_permission("user:remove") and not context.is_project_admin():
        raise PermissionDeniedError("Permission 'user:remove' required")
    
    # Cannot remove yourself
    if user_id == context.user_id:
        raise PermissionDeniedError("Cannot remove yourself from the project")
    
    service = AuthService(db)
    await service.remove_user_from_project(user_id, context.project_id)
    
    # Audit log
    audit = AuditService(db)
    await audit.log(
        action=AuditAction.ROLE_REVOKED,
        resource_type="user_project_assignment",
        resource_id=str(user_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"User removed from project",
        ip_address=http_request.client.host if http_request.client else None,
    )
    
    return MessageResponse(message="User removed from project successfully")
