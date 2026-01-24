"""RBAC schemas for roles and permissions."""

from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


# Permission schemas
class PermissionResponse(BaseSchema):
    """Permission response schema."""

    id: int
    permission_key: str
    description: str | None


class PermissionCreate(BaseSchema):
    """Permission creation schema (admin only)."""

    permission_key: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-z]+\.[a-z_]+$")
    description: str | None = None


# Role schemas
class RoleCreate(BaseSchema):
    """Role creation schema."""

    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    is_project_admin: bool = False
    is_role_admin: bool = False
    permission_ids: list[int] = []
    permissions: list[str] = []  # Alternative: permission keys (e.g., 'task:view')
    project_id: int | None = None  # For super admin to specify project


class RoleUpdate(BaseSchema):
    """Role update schema."""

    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = None
    is_project_admin: bool | None = None
    is_role_admin: bool | None = None
    permissions: list[str] | None = None  # Permission keys (e.g., 'task:view')
    project_id: int | None = None  # For super admin to specify project


class RoleResponse(BaseSchema):
    """Role response schema."""

    id: int
    project_id: int
    name: str
    description: str | None
    is_project_admin: bool
    is_role_admin: bool
    created_at: datetime
    updated_at: datetime


class RoleWithPermissions(RoleResponse):
    """Role response with permissions."""

    permissions: list[PermissionResponse] = []


class RoleWithPermissionsAndProject(RoleWithPermissions):
    """Role response with permissions and project name (for super admin)."""

    project_name: str | None = None


# Role-Permission assignment
class RolePermissionAssign(BaseSchema):
    """Assign permissions to a role."""

    permission_ids: list[int]


# User-Role assignment
class UserRoleAssign(BaseSchema):
    """Assign a user to a role."""

    user_id: int
    role_id: int


class UserRoleResponse(BaseSchema):
    """User role assignment response."""

    id: int
    user_id: int
    role_id: int
    project_id: int
    created_at: datetime
    user_name: str | None = None
    user_username: str | None = None
    role_name: str | None = None


class UserWithRoles(BaseSchema):
    """User with their roles in a project."""

    user_id: int
    user_name: str
    user_username: str
    roles: list[RoleResponse] = []


# Bulk assignment schemas
class ProjectRoleMapping(BaseSchema):
    """A single project with its role assignments."""

    project_id: int
    role_ids: list[int]


class BulkUserRoleAssign(BaseSchema):
    """Bulk assign roles to a user across multiple projects."""

    user_id: int
    mappings: list[ProjectRoleMapping]
