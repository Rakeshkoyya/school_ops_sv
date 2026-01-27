"""FastAPI dependency injection utilities."""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    ProjectSuspendedError,
)
from app.core.security import verify_access_token
from app.models.project import Project, ProjectStatus
from app.models.rbac import Permission, Role, RolePermission, UserRoleProject
from app.models.user import User


class CurrentUserContext:
    """Context object containing current user, project, and permissions."""

    def __init__(
        self,
        user: User,
        project: Project | None = None,
        roles: list[Role] | None = None,
        permissions: set[str] | None = None,
    ):
        self.user = user
        self.project = project
        self.roles = roles or []
        self.permissions = permissions or set()

    @property
    def user_id(self) -> int:
        return self.user.id

    @property
    def project_id(self) -> int | None:
        return self.project.id if self.project else None

    def has_permission(self, permission_key: str) -> bool:
        """Check if user has a specific permission."""
        return permission_key in self.permissions

    def is_project_admin(self) -> bool:
        """Check if user is a project admin."""
        return any(role.is_project_admin for role in self.roles)

    def is_role_admin(self) -> bool:
        """Check if user can manage roles."""
        return any(role.is_role_admin for role in self.roles)
    
    def is_super_admin(self) -> bool:
        """Check if user is a super admin."""
        return self.user.is_super_admin


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: str = Header(..., description="Bearer token"),
) -> User:
    """Extract and validate the current user from JWT token."""
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid authorization header format")

    token = authorization[7:]  # Remove "Bearer " prefix
    payload = verify_access_token(token)

    if not payload:
        raise AuthenticationError("Invalid or expired token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Invalid token payload")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise AuthenticationError("Invalid user ID in token")

    result = db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("User account is deactivated")

    return user


def get_project_context(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    x_project_id: str = Header(..., description="Project ID"),
) -> CurrentUserContext:
    """Get the full user context including project and permissions."""
    try:
        project_id = int(x_project_id)
    except ValueError:
        raise NotFoundError("Project", x_project_id)

    # Get project
    result = db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise NotFoundError("Project", x_project_id)

    # Get user's roles for this project
    roles_result = db.execute(
        select(Role)
        .join(UserRoleProject, Role.id == UserRoleProject.role_id)
        .where(
            UserRoleProject.user_id == user.id,
            UserRoleProject.project_id == project_id,
        )
    )
    roles = list(roles_result.scalars().all())

    # Super admins have access to all projects
    if not roles and not user.is_super_admin:
        raise PermissionDeniedError("You don't have access to this project")

    # Get permissions for all roles
    permissions: set[str] = set()
    if roles:
        role_ids = [role.id for role in roles]
        permissions_result = db.execute(
            select(Permission.permission_key)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .where(
                RolePermission.role_id.in_(role_ids),
                RolePermission.project_id == project_id,
            )
        )
        permissions = set(permissions_result.scalars().all())

    return CurrentUserContext(
        user=user,
        project=project,
        roles=roles,
        permissions=permissions,
    )


def require_permission(permission_key: str):
    """Dependency factory that requires a specific permission."""

    def check_permission(
        context: Annotated[CurrentUserContext, Depends(get_project_context)],
    ) -> CurrentUserContext:
        if not context.has_permission(permission_key) and not context.is_project_admin():
            raise PermissionDeniedError(
                f"Permission '{permission_key}' required",
                required_permission=permission_key,
            )
        return context

    return check_permission


def require_project_active():
    """Dependency that ensures project is not suspended."""

    def check_project_status(
        context: Annotated[CurrentUserContext, Depends(get_project_context)],
    ) -> CurrentUserContext:
        if context.project and context.project.status == ProjectStatus.SUSPENDED:
            raise ProjectSuspendedError(str(context.project_id))
        return context

    return check_permission


def require_project_admin():
    """Dependency that requires project admin role."""

    def check_admin(
        context: Annotated[CurrentUserContext, Depends(get_project_context)],
    ) -> CurrentUserContext:
        if not context.is_project_admin():
            raise PermissionDeniedError("Project admin access required")
        return context

    return check_admin


def require_role_admin():
    """Dependency that requires role admin capability."""

    def check_role_admin(
        context: Annotated[CurrentUserContext, Depends(get_project_context)],
    ) -> CurrentUserContext:
        if not context.is_role_admin() and not context.is_project_admin():
            raise PermissionDeniedError("Role admin access required")
        return context

    return check_role_admin


# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
ProjectContext = Annotated[CurrentUserContext, Depends(get_project_context)]
