"""Project schemas."""

from datetime import datetime

from pydantic import Field

from app.models.project import ProjectStatus
from app.schemas.common import BaseSchema


class ProjectCreate(BaseSchema):
    """Project creation schema."""

    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    theme_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_url: str | None = None
    add_default_roles: bool = Field(default=True, description="Create default School Admin and Staff roles")


class ProjectUpdate(BaseSchema):
    """Project update schema."""

    name: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    theme_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_url: str | None = None
    status: ProjectStatus | None = None


class ProjectResponse(BaseSchema):
    """Project response schema."""

    id: int
    name: str
    slug: str
    description: str | None
    theme_color: str | None
    logo_url: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class ProjectListItem(BaseSchema):
    """Project list item with user's role info."""

    id: int
    name: str
    slug: str
    description: str | None
    theme_color: str | None
    logo_url: str | None
    status: ProjectStatus
    role_id: int | None = None  # The specific role ID for this assignment
    role_name: str | None = None
    is_project_admin: bool = False
    is_role_admin: bool = False
