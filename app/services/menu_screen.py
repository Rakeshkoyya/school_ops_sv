"""Menu Screen service for sidebar menu management."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.menu_screen import MenuScreen, MenuScreenPermission, ProjectMenuScreen
from app.models.project import Project
from app.models.rbac import Permission, RolePermission
from app.schemas.menu_screen import (
    AvailablePermissionsResponse,
    MenuPermissionGroup,
    MenuScreenCreate,
    MenuScreenResponse,
    MenuScreenUpdate,
    MenuScreenWithPermissions,
    ProjectMenuAllocationRequest,
    ProjectMenuAllocationResponse,
)
from app.schemas.rbac import PermissionResponse


class MenuScreenService:
    """Service for managing menu screens and project allocations."""

    def __init__(self, db: Session):
        self.db = db

    # Menu Screen CRUD
    def list_menu_screens(self) -> list[MenuScreenWithPermissions]:
        """List all menu screens with their permissions."""
        result = self.db.execute(
            select(MenuScreen)
            .options(selectinload(MenuScreen.permission_mappings).selectinload(MenuScreenPermission.permission))
            .order_by(MenuScreen.display_order)
        )
        menus = result.scalars().all()
        
        return [
            MenuScreenWithPermissions(
                id=menu.id,
                name=menu.name,
                route=menu.route,
                display_order=menu.display_order,
                description=menu.description,
                created_at=menu.created_at,
                updated_at=menu.updated_at,
                permissions=[
                    PermissionResponse.model_validate(mp.permission)
                    for mp in menu.permission_mappings
                ],
            )
            for menu in menus
        ]

    def get_menu_screen(self, menu_id: int) -> MenuScreen:
        """Get a menu screen by ID."""
        result = self.db.execute(
            select(MenuScreen)
            .options(selectinload(MenuScreen.permission_mappings).selectinload(MenuScreenPermission.permission))
            .where(MenuScreen.id == menu_id)
        )
        menu = result.scalar_one_or_none()
        if not menu:
            raise NotFoundError("MenuScreen", str(menu_id))
        return menu

    def create_menu_screen(self, request: MenuScreenCreate) -> MenuScreenWithPermissions:
        """Create a new menu screen (super admin only)."""
        # Check if name exists
        result = self.db.execute(
            select(MenuScreen).where(MenuScreen.name == request.name)
        )
        if result.scalar_one_or_none():
            raise ValidationError(f"Menu screen '{request.name}' already exists")

        menu = MenuScreen(
            name=request.name,
            route=request.route,
            display_order=request.display_order,
            description=request.description,
        )
        self.db.add(menu)
        self.db.flush()

        # Link permissions
        permissions = []
        for perm_key in request.permission_keys:
            perm_result = self.db.execute(
                select(Permission).where(Permission.permission_key == perm_key)
            )
            perm = perm_result.scalar_one_or_none()
            if perm:
                mapping = MenuScreenPermission(
                    menu_screen_id=menu.id,
                    permission_id=perm.id,
                )
                self.db.add(mapping)
                permissions.append(PermissionResponse.model_validate(perm))

        self.db.flush()
        self.db.refresh(menu)

        return MenuScreenWithPermissions(
            id=menu.id,
            name=menu.name,
            route=menu.route,
            display_order=menu.display_order,
            description=menu.description,
            created_at=menu.created_at,
            updated_at=menu.updated_at,
            permissions=permissions,
        )

    def update_menu_screen(
        self,
        menu_id: int,
        request: MenuScreenUpdate,
    ) -> MenuScreenWithPermissions:
        """Update a menu screen (super admin only)."""
        menu = self.get_menu_screen(menu_id)

        # Update fields
        if request.name is not None:
            # Check for duplicate name
            result = self.db.execute(
                select(MenuScreen).where(
                    MenuScreen.name == request.name,
                    MenuScreen.id != menu_id,
                )
            )
            if result.scalar_one_or_none():
                raise ValidationError(f"Menu screen '{request.name}' already exists")
            menu.name = request.name

        if request.route is not None:
            menu.route = request.route
        if request.display_order is not None:
            menu.display_order = request.display_order
        if request.description is not None:
            menu.description = request.description

        # Update permission links if provided
        if request.permission_keys is not None:
            # Remove existing mappings
            self.db.execute(
                delete(MenuScreenPermission).where(
                    MenuScreenPermission.menu_screen_id == menu_id
                )
            )
            # Add new mappings
            for perm_key in request.permission_keys:
                perm_result = self.db.execute(
                    select(Permission).where(Permission.permission_key == perm_key)
                )
                perm = perm_result.scalar_one_or_none()
                if perm:
                    mapping = MenuScreenPermission(
                        menu_screen_id=menu.id,
                        permission_id=perm.id,
                    )
                    self.db.add(mapping)

        self.db.flush()
        self.db.refresh(menu)

        # Reload with permissions
        return self._menu_to_response(menu)

    def delete_menu_screen(self, menu_id: int) -> None:
        """Delete a menu screen (super admin only)."""
        menu = self.get_menu_screen(menu_id)
        self.db.delete(menu)
        self.db.flush()

    # Project Menu Allocation
    def get_project_menus(self, project_id: int) -> ProjectMenuAllocationResponse:
        """Get all menus allocated to a project."""
        # Verify project exists
        project = self.db.execute(
            select(Project).where(Project.id == project_id)
        ).scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", str(project_id))

        # Get allocated menus
        result = self.db.execute(
            select(ProjectMenuScreen)
            .options(
                selectinload(ProjectMenuScreen.menu_screen)
                .selectinload(MenuScreen.permission_mappings)
                .selectinload(MenuScreenPermission.permission)
            )
            .where(ProjectMenuScreen.project_id == project_id)
            .order_by(ProjectMenuScreen.menu_screen_id)
        )
        allocations = result.scalars().all()

        allocated_menus = []
        for alloc in allocations:
            menu = alloc.menu_screen
            allocated_menus.append(
                MenuScreenWithPermissions(
                    id=menu.id,
                    name=menu.name,
                    route=menu.route,
                    display_order=menu.display_order,
                    description=menu.description,
                    created_at=menu.created_at,
                    updated_at=menu.updated_at,
                    permissions=[
                        PermissionResponse.model_validate(mp.permission)
                        for mp in menu.permission_mappings
                    ],
                )
            )

        # Sort by display_order
        allocated_menus.sort(key=lambda m: m.display_order)

        return ProjectMenuAllocationResponse(
            project_id=project_id,
            project_name=project.name,
            allocated_menus=allocated_menus,
        )

    def allocate_menus_to_project(
        self,
        project_id: int,
        request: ProjectMenuAllocationRequest,
    ) -> ProjectMenuAllocationResponse:
        """
        Allocate menus to a project.
        
        This replaces the current allocation - menus not in the list will be deallocated,
        and their permissions will be removed from all roles in the project.
        """
        # Verify project exists
        project = self.db.execute(
            select(Project).where(Project.id == project_id)
        ).scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", str(project_id))

        # Get current allocations
        current_result = self.db.execute(
            select(ProjectMenuScreen.menu_screen_id)
            .where(ProjectMenuScreen.project_id == project_id)
        )
        current_menu_ids = set(row[0] for row in current_result)
        new_menu_ids = set(request.menu_screen_ids)

        # Find menus being removed
        menus_to_remove = current_menu_ids - new_menu_ids
        
        # Find menus being added
        menus_to_add = new_menu_ids - current_menu_ids

        # Remove deallocated menus and cascade permissions
        if menus_to_remove:
            self._remove_menu_allocations(project_id, list(menus_to_remove))

        # Add new allocations
        for menu_id in menus_to_add:
            # Verify menu exists
            menu_exists = self.db.execute(
                select(MenuScreen.id).where(MenuScreen.id == menu_id)
            ).scalar_one_or_none()
            if menu_exists:
                allocation = ProjectMenuScreen(
                    project_id=project_id,
                    menu_screen_id=menu_id,
                )
                self.db.add(allocation)

        self.db.flush()

        return self.get_project_menus(project_id)

    def _remove_menu_allocations(
        self,
        project_id: int,
        menu_ids: list[int],
    ) -> None:
        """
        Remove menu allocations and cascade permission removal.
        
        When a menu is deallocated from a project, all permissions linked
        to that menu are removed from all roles in the project.
        """
        if not menu_ids:
            return

        # Get permission IDs linked to these menus
        perm_result = self.db.execute(
            select(MenuScreenPermission.permission_id)
            .where(MenuScreenPermission.menu_screen_id.in_(menu_ids))
        )
        permission_ids = [row[0] for row in perm_result]

        # Remove these permissions from all roles in the project
        if permission_ids:
            self.db.execute(
                delete(RolePermission).where(
                    RolePermission.project_id == project_id,
                    RolePermission.permission_id.in_(permission_ids),
                )
            )

        # Remove the menu allocations
        self.db.execute(
            delete(ProjectMenuScreen).where(
                ProjectMenuScreen.project_id == project_id,
                ProjectMenuScreen.menu_screen_id.in_(menu_ids),
            )
        )

    def get_available_permissions_for_project(
        self,
        project_id: int,
    ) -> AvailablePermissionsResponse:
        """
        Get permissions available for a project, grouped by menu screen.
        
        Only permissions from allocated menus are available.
        """
        # Get all menus with permissions
        all_menus = self.list_menu_screens()

        # Get allocated menu IDs
        allocated_result = self.db.execute(
            select(ProjectMenuScreen.menu_screen_id)
            .where(ProjectMenuScreen.project_id == project_id)
        )
        allocated_menu_ids = set(row[0] for row in allocated_result)

        # Build menu groups
        menu_groups = []
        for menu in all_menus:
            is_allocated = menu.id in allocated_menu_ids
            menu_groups.append(
                MenuPermissionGroup(
                    menu_id=menu.id,
                    menu_name=menu.name,
                    is_allocated=is_allocated,
                    permissions=menu.permissions if is_allocated else [],
                )
            )

        return AvailablePermissionsResponse(
            project_id=project_id,
            menu_groups=menu_groups,
        )

    def get_available_permission_ids_for_project(
        self,
        project_id: int,
    ) -> set[int]:
        """Get set of permission IDs available for a project."""
        # Get allocated menu IDs
        allocated_result = self.db.execute(
            select(ProjectMenuScreen.menu_screen_id)
            .where(ProjectMenuScreen.project_id == project_id)
        )
        allocated_menu_ids = [row[0] for row in allocated_result]
        
        if not allocated_menu_ids:
            return set()

        # Get permission IDs from those menus
        perm_result = self.db.execute(
            select(MenuScreenPermission.permission_id)
            .where(MenuScreenPermission.menu_screen_id.in_(allocated_menu_ids))
        )
        return set(row[0] for row in perm_result)

    def _menu_to_response(self, menu: MenuScreen) -> MenuScreenWithPermissions:
        """Convert a menu model to response with permissions."""
        return MenuScreenWithPermissions(
            id=menu.id,
            name=menu.name,
            route=menu.route,
            display_order=menu.display_order,
            description=menu.description,
            created_at=menu.created_at,
            updated_at=menu.updated_at,
            permissions=[
                PermissionResponse.model_validate(mp.permission)
                for mp in menu.permission_mappings
            ],
        )
