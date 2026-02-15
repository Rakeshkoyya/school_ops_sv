"""Menu screen schemas for sidebar menu management."""

from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema
from app.schemas.rbac import PermissionResponse


# Menu Screen base schemas
class MenuScreenBase(BaseSchema):
    """Base menu screen schema."""

    name: str = Field(..., min_length=2, max_length=100)
    route: str = Field(..., min_length=1, max_length=255)
    display_order: int = 0
    description: str | None = None


class MenuScreenCreate(MenuScreenBase):
    """Menu screen creation schema (admin only)."""

    permission_keys: list[str] = []  # Permission keys to link (e.g., ['task:view', 'task:create'])


class MenuScreenUpdate(BaseSchema):
    """Menu screen update schema."""

    name: str | None = Field(None, min_length=2, max_length=100)
    route: str | None = Field(None, min_length=1, max_length=255)
    display_order: int | None = None
    description: str | None = None
    permission_keys: list[str] | None = None


class MenuScreenResponse(BaseSchema):
    """Menu screen response schema."""

    id: int
    name: str
    route: str
    display_order: int
    description: str | None
    created_at: datetime
    updated_at: datetime


class MenuScreenWithPermissions(MenuScreenResponse):
    """Menu screen with its linked permissions."""

    permissions: list[PermissionResponse] = []


# Project Menu Allocation schemas
class ProjectMenuScreenResponse(BaseSchema):
    """Project menu allocation response."""

    id: int
    project_id: int
    menu_screen_id: int
    created_at: datetime
    menu_screen: MenuScreenResponse | None = None


class ProjectMenuAllocationRequest(BaseSchema):
    """Request to allocate/deallocate menus to a project."""

    menu_screen_ids: list[int] = Field(..., description="List of menu screen IDs to allocate")


class ProjectMenuAllocationResponse(BaseSchema):
    """Response showing allocated menus for a project."""

    project_id: int
    project_name: str | None = None
    allocated_menus: list[MenuScreenWithPermissions] = []


# For grouping permissions by menu in role management UI
class MenuPermissionGroup(BaseSchema):
    """Permissions grouped by menu screen for UI display."""

    menu_id: int
    menu_name: str
    is_allocated: bool = True  # Whether this menu is allocated to the project
    permissions: list[PermissionResponse] = []


class AvailablePermissionsResponse(BaseSchema):
    """Available permissions grouped by menu for a project."""

    project_id: int
    menu_groups: list[MenuPermissionGroup] = []
