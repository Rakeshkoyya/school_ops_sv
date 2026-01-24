"""Authentication schemas."""

from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


class LoginRequest(BaseSchema):
    """Login request schema."""

    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6)


class TokenResponse(BaseSchema):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseSchema):
    """Refresh token request schema."""

    refresh_token: str


class UserCreate(BaseSchema):
    """User creation schema."""

    name: str = Field(..., min_length=2, max_length=255)
    username: str = Field(..., min_length=3, max_length=255)
    phone: str | None = None
    password: str = Field(..., min_length=8)


class UserResponse(BaseSchema):
    """User response schema."""

    id: int
    name: str
    username: str
    phone: str | None
    is_active: bool
    is_super_admin: bool
    evo_points: int = 0
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseSchema):
    """User update schema."""

    name: str | None = Field(None, min_length=2, max_length=255)
    phone: str | None = None


class PasswordChange(BaseSchema):
    """Password change schema."""

    current_password: str
    new_password: str = Field(..., min_length=8)


class ProjectInfo(BaseSchema):
    """Basic project info."""

    id: int
    name: str
    slug: str
    description: str | None = None
    theme_color: str | None = None
    logo_url: str | None = None
    status: str


class UserRoleInfo(BaseSchema):
    """User's role assignment in a project with permissions."""

    role_id: int
    role_name: str
    project_id: int
    project_name: str
    project_slug: str
    is_project_admin: bool = False
    is_role_admin: bool = False
    permissions: list[str] = []


class ProjectWithRole(BaseSchema):
    """Project info with user's role and its permissions (legacy compatibility)."""

    id: int
    name: str
    slug: str
    description: str | None = None
    theme_color: str | None = None
    logo_url: str | None = None
    status: str
    role_id: int
    role_name: str
    is_project_admin: bool = False
    is_role_admin: bool = False
    permissions: list[str] = []  # Permissions for this specific role


class CurrentUserResponse(BaseSchema):
    """Current user with projects and role assignments."""

    user: UserResponse
    projects: list[ProjectInfo] = []  # Unique projects
    user_roles: list[UserRoleInfo] = []  # All role assignments
    permissions: list[str] = []  # Aggregated permissions


class RoleInfo(BaseSchema):
    """Role info for user listing."""

    id: int
    name: str


class ProjectRoleMapping(BaseSchema):
    """Project with assigned roles for a user."""

    project_id: int
    project_name: str
    roles: list[RoleInfo] = []


class UserWithProjectRoles(UserResponse):
    """User with their project-role mappings."""

    project_roles: list[ProjectRoleMapping] = []


class AdminUserUpdate(BaseSchema):
    """Admin user update schema - allows more fields."""

    name: str | None = Field(None, min_length=2, max_length=255)
    phone: str | None = None
    is_active: bool | None = None
    is_super_admin: bool | None = None


class ProjectUserUpdate(BaseSchema):
    """Project-scoped user update schema - limited fields for school admin."""

    name: str | None = Field(None, min_length=2, max_length=255)
    phone: str | None = None
    is_active: bool | None = None


class UserBulkUploadResult(BaseSchema):
    """Result of bulk user upload."""

    total_rows: int
    successful_rows: int
    failed_rows: int
    errors: list[dict] = []
    message: str


class UserWithRoleAssignment(BaseSchema):
    """User creation with role assignment for bulk upload."""

    name: str = Field(..., min_length=2, max_length=255)
    username: str = Field(..., min_length=3, max_length=255)
    phone: str | None = None
    password: str = Field(..., min_length=8)
    role_id: int | None = None  # Optional role to assign in project
