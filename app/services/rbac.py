"""RBAC (Role-Based Access Control) service."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.models.menu_screen import MenuScreenPermission, ProjectMenuScreen
from app.models.rbac import Permission, Role, RolePermission, UserRoleProject
from app.models.user import User
from app.schemas.rbac import (
    PermissionCreate,
    PermissionResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    RoleWithPermissions,
    RoleWithPermissionsAndProject,
    UserRoleAssign,
    UserRoleResponse,
    UserWithRoles,
    BulkUserRoleAssign,
)


class RBACService:
    """Role-Based Access Control service."""

    def __init__(self, db: Session):
        self.db = db

    def _get_available_permission_ids_for_project(self, project_id: int) -> set[int]:
        """Get permission IDs available for a project based on allocated menus."""
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

    def _validate_permissions_for_project(
        self,
        project_id: int,
        permission_ids: list[int],
        skip_validation: bool = False,
    ) -> list[int]:
        """
        Validate that permissions are available for the project.
        
        Returns filtered list of valid permission IDs.
        If skip_validation is True, returns all permission IDs (for super admin override).
        """
        if skip_validation:
            return permission_ids
        
        available_ids = self._get_available_permission_ids_for_project(project_id)
        
        valid_ids = []
        invalid_ids = []
        for perm_id in permission_ids:
            if perm_id in available_ids:
                valid_ids.append(perm_id)
            else:
                invalid_ids.append(perm_id)
        
        if invalid_ids:
            # Get permission keys for error message
            perm_result = self.db.execute(
                select(Permission.permission_key)
                .where(Permission.id.in_(invalid_ids))
            )
            invalid_keys = [row[0] for row in perm_result]
            raise ValidationError(
                f"Permissions not available for this project (not in allocated menus): {', '.join(invalid_keys)}"
            )
        
        return valid_ids

    # Permission methods
    def list_permissions(self) -> list[PermissionResponse]:
        """List all available permissions."""
        result = self.db.execute(
            select(Permission).order_by(Permission.permission_key)
        )
        permissions = result.scalars().all()
        return [PermissionResponse.model_validate(p) for p in permissions]

    def create_permission(
        self,
        request: PermissionCreate,
    ) -> PermissionResponse:
        """Create a new permission (system admin only)."""
        # Check if permission key exists
        result = self.db.execute(
            select(Permission).where(Permission.permission_key == request.permission_key)
        )
        if result.scalar_one_or_none():
            raise ValidationError(f"Permission key '{request.permission_key}' already exists")

        permission = Permission(
            permission_key=request.permission_key,
            description=request.description,
        )
        self.db.add(permission)
        self.db.flush()
        self.db.refresh(permission)

        return PermissionResponse.model_validate(permission)

    def get_permission(self, permission_id: int) -> Permission:
        """Get permission by ID."""
        result = self.db.execute(
            select(Permission).where(Permission.id == permission_id)
        )
        permission = result.scalar_one_or_none()
        if not permission:
            raise NotFoundError("Permission", str(permission_id))
        return permission

    # Role methods
    def create_role(
        self,
        project_id: int,
        request: RoleCreate,
    ) -> RoleWithPermissions:
        """Create a new role for a project."""
        # Check if role name exists in project
        result = self.db.execute(
            select(Role).where(
                Role.project_id == project_id,
                Role.name == request.name,
            )
        )
        if result.scalar_one_or_none():
            raise ValidationError(f"Role '{request.name}' already exists in this project")

        role = Role(
            project_id=project_id,
            name=request.name,
            description=request.description,
            is_project_admin=request.is_project_admin,
            is_role_admin=request.is_role_admin,
        )
        self.db.add(role)
        self.db.flush()

        # Collect permission IDs - support both permission_ids and permissions (keys)
        permission_ids_to_assign = list(request.permission_ids)
        
        # If permission keys are provided, resolve them to IDs
        if request.permissions:
            for perm_key in request.permissions:
                perm_result = self.db.execute(
                    select(Permission).where(Permission.permission_key == perm_key)
                )
                perm = perm_result.scalar_one_or_none()
                if perm and perm.id not in permission_ids_to_assign:
                    permission_ids_to_assign.append(perm.id)

        # Validate permissions are available for this project's allocated menus
        if permission_ids_to_assign:
            permission_ids_to_assign = self._validate_permissions_for_project(
                project_id, permission_ids_to_assign
            )

        # Assign permissions
        permissions = []
        for permission_id in permission_ids_to_assign:
            permission = self.get_permission(permission_id)
            role_permission = RolePermission(
                project_id=project_id,
                role_id=role.id,
                permission_id=permission_id,
            )
            self.db.add(role_permission)
            permissions.append(PermissionResponse.model_validate(permission))

        self.db.flush()
        self.db.refresh(role)

        return RoleWithPermissions(
            **RoleResponse.model_validate(role).model_dump(),
            permissions=permissions,
        )

    def get_role(self, role_id: int, project_id: int) -> Role:
        """Get role by ID and project."""
        result = self.db.execute(
            select(Role).where(
                Role.id == role_id,
                Role.project_id == project_id,
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise NotFoundError("Role", str(role_id))
        return role

    def list_roles(self, project_id: int) -> list[RoleWithPermissions]:
        """List all roles for a project with their permissions."""
        result = self.db.execute(
            select(Role)
            .where(Role.project_id == project_id)
            .order_by(Role.name)
        )
        roles = result.scalars().all()
        
        roles_with_permissions = []
        for role in roles:
            # Get permissions for this role
            perm_result = self.db.execute(
                select(Permission)
                .join(RolePermission, Permission.id == RolePermission.permission_id)
                .where(
                    RolePermission.role_id == role.id,
                    RolePermission.project_id == project_id,
                )
            )
            permissions = perm_result.scalars().all()
            
            roles_with_permissions.append(RoleWithPermissions(
                **RoleResponse.model_validate(role).model_dump(),
                permissions=[p.permission_key for p in permissions],
            ))
        
        return roles_with_permissions

    def list_all_roles(self) -> list[RoleWithPermissionsAndProject]:
        """List all roles across all projects (for super admin)."""
        result = self.db.execute(
            select(Role)
            .options(selectinload(Role.project))
            .order_by(Role.project_id, Role.name)
        )
        roles = result.scalars().all()
        
        # Get all role-permission mappings
        roles_with_permissions = []
        for role in roles:
            # Get permissions for this role
            perm_result = self.db.execute(
                select(Permission)
                .join(RolePermission, Permission.id == RolePermission.permission_id)
                .where(RolePermission.role_id == role.id)
            )
            permissions = perm_result.scalars().all()
            
            roles_with_permissions.append(RoleWithPermissionsAndProject(
                **RoleResponse.model_validate(role).model_dump(),
                permissions=[p.permission_key for p in permissions],
                project_name=role.project.name if role.project else None,
            ))
        
        return roles_with_permissions

    def get_role_with_permissions(
        self,
        role_id: int,
        project_id: int,
    ) -> RoleWithPermissions:
        """Get role with its permissions."""
        role = self.get_role(role_id, project_id)

        # Get permissions for role
        result = self.db.execute(
            select(Permission)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .where(
                RolePermission.role_id == role_id,
                RolePermission.project_id == project_id,
            )
        )
        permissions = result.scalars().all()

        return RoleWithPermissions(
            **RoleResponse.model_validate(role).model_dump(),
            permissions=[p.permission_key for p in permissions],
        )

    def update_role(
        self,
        role_id: int,
        project_id: int,
        request: RoleUpdate,
    ) -> RoleResponse:
        """Update a role."""
        role = self.get_role(role_id, project_id)

        update_data = request.model_dump(exclude_unset=True)
        
        # Handle permissions update if provided
        permissions_to_update = update_data.pop('permissions', None)

        # Check for name conflict
        if "name" in update_data:
            result = self.db.execute(
                select(Role).where(
                    Role.project_id == project_id,
                    Role.name == update_data["name"],
                    Role.id != role_id,
                )
            )
            if result.scalar_one_or_none():
                raise ValidationError(f"Role '{update_data['name']}' already exists")

        for field, value in update_data.items():
            setattr(role, field, value)
        
        # Update permissions if provided
        if permissions_to_update is not None:
            # Resolve permission keys to IDs
            permission_ids = []
            for perm_key in permissions_to_update:
                perm_result = self.db.execute(
                    select(Permission).where(Permission.permission_key == perm_key)
                )
                perm = perm_result.scalar_one_or_none()
                if perm:
                    permission_ids.append(perm.id)
            
            # Validate permissions are available for this project's allocated menus
            if permission_ids:
                permission_ids = self._validate_permissions_for_project(
                    project_id, permission_ids
                )
            
            # Remove existing permissions
            self.db.execute(
                delete(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.project_id == project_id,
                )
            )
            
            # Add new permissions
            for perm_id in permission_ids:
                role_permission = RolePermission(
                    project_id=project_id,
                    role_id=role_id,
                    permission_id=perm_id,
                )
                self.db.add(role_permission)

        self.db.flush()
        self.db.refresh(role)

        return RoleResponse.model_validate(role)

    def delete_role(self, role_id: int, project_id: int) -> None:
        """Delete a role."""
        role = self.get_role(role_id, project_id)

        # Check if any users are assigned to this role
        result = self.db.execute(
            select(UserRoleProject).where(UserRoleProject.role_id == role_id)
        )
        if result.scalar_one_or_none():
            raise ValidationError("Cannot delete role with assigned users")

        # Delete related role_permissions first to avoid ORM trying to set FK to NULL
        self.db.execute(
            delete(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.project_id == project_id,
            )
        )

        self.db.delete(role)
        self.db.flush()

    def assign_permissions_to_role(
        self,
        role_id: int,
        project_id: int,
        permission_ids: list[int],
        skip_validation: bool = False,
    ) -> RoleWithPermissions:
        """
        Assign permissions to a role (replaces existing).
        
        Args:
            role_id: Role ID to assign permissions to
            project_id: Project ID
            permission_ids: List of permission IDs to assign
            skip_validation: If True, skip menu allocation validation (for super admin)
        """
        role = self.get_role(role_id, project_id)

        # Validate permissions are available for this project's allocated menus
        if permission_ids and not skip_validation:
            permission_ids = self._validate_permissions_for_project(
                project_id, permission_ids
            )

        # Remove existing permissions
        self.db.execute(
            delete(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.project_id == project_id,
            )
        )

        # Add new permissions
        permissions = []
        for permission_id in permission_ids:
            permission = self.get_permission(permission_id)
            role_permission = RolePermission(
                project_id=project_id,
                role_id=role_id,
                permission_id=permission_id,
            )
            self.db.add(role_permission)
            permissions.append(PermissionResponse.model_validate(permission))

        self.db.flush()

        return RoleWithPermissions(
            **RoleResponse.model_validate(role).model_dump(),
            permissions=permissions,
        )

    # User-Role assignment methods
    def assign_user_to_role(
        self,
        project_id: int,
        request: UserRoleAssign,
    ) -> UserRoleResponse:
        """Assign a user to a role in a project."""
        # Verify role exists
        role = self.get_role(request.role_id, project_id)

        # Verify user exists
        result = self.db.execute(
            select(User).where(User.id == request.user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(request.user_id))

        # Check if assignment exists
        result = self.db.execute(
            select(UserRoleProject).where(
                UserRoleProject.user_id == request.user_id,
                UserRoleProject.role_id == request.role_id,
                UserRoleProject.project_id == project_id,
            )
        )
        if result.scalar_one_or_none():
            raise ValidationError("User is already assigned to this role")

        assignment = UserRoleProject(
            user_id=request.user_id,
            role_id=request.role_id,
            project_id=project_id,
        )
        self.db.add(assignment)
        self.db.flush()
        self.db.refresh(assignment)

        return UserRoleResponse(
            id=assignment.id,
            user_id=assignment.user_id,
            role_id=assignment.role_id,
            project_id=assignment.project_id,
            created_at=assignment.created_at,
            user_name=user.name,
            user_username=user.username,
            role_name=role.name,
        )

    def revoke_user_role(
        self,
        project_id: int,
        user_id: int,
        role_id: int,
    ) -> None:
        """Remove a user from a role in a project."""
        result = self.db.execute(
            select(UserRoleProject).where(
                UserRoleProject.user_id == user_id,
                UserRoleProject.role_id == role_id,
                UserRoleProject.project_id == project_id,
            )
        )
        assignment = result.scalar_one_or_none()

        if not assignment:
            raise NotFoundError("User role assignment")

        self.db.delete(assignment)
        self.db.flush()

    def update_user_roles(
        self,
        project_id: int,
        user_id: int,
        role_ids: list[int],
    ) -> list[RoleResponse]:
        """Replace all roles for a user in a project."""
        # Verify user exists
        result = self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(user_id))

        # Verify all roles exist and belong to this project
        roles = []
        for role_id in role_ids:
            role = self.get_role(role_id, project_id)
            roles.append(role)

        # Delete existing role assignments for this user in this project
        self.db.execute(
            delete(UserRoleProject).where(
                UserRoleProject.user_id == user_id,
                UserRoleProject.project_id == project_id,
            )
        )

        # Create new assignments
        for role_id in role_ids:
            assignment = UserRoleProject(
                user_id=user_id,
                role_id=role_id,
                project_id=project_id,
            )
            self.db.add(assignment)

        self.db.flush()

        return [RoleResponse.model_validate(role) for role in roles]

    def list_project_users(
        self,
        project_id: int,
    ) -> list[UserWithRoles]:
        """List all users in a project with their roles."""
        result = self.db.execute(
            select(User, Role)
            .join(UserRoleProject, User.id == UserRoleProject.user_id)
            .join(Role, UserRoleProject.role_id == Role.id)
            .where(UserRoleProject.project_id == project_id)
            .order_by(User.name)
        )
        rows = result.all()

        # Group by user
        users_dict: dict[int, UserWithRoles] = {}
        for user, role in rows:
            if user.id not in users_dict:
                users_dict[user.id] = UserWithRoles(
                    user_id=user.id,
                    user_name=user.name,
                    user_username=user.username,
                    roles=[],
                )
            users_dict[user.id].roles.append(RoleResponse.model_validate(role))

        return list(users_dict.values())

    def get_user_permissions(
        self,
        user_id: int,
        project_id: int,
    ) -> set[str]:
        """Get all permissions for a user in a project."""
        result = self.db.execute(
            select(Permission.permission_key)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .join(UserRoleProject, RolePermission.role_id == UserRoleProject.role_id)
            .where(
                UserRoleProject.user_id == user_id,
                UserRoleProject.project_id == project_id,
            )
        )
        return set(result.scalars().all())

    def get_role_permissions(
        self,
        role_id: int,
    ) -> set[str]:
        """Get all permissions for a specific role."""
        result = self.db.execute(
            select(Permission.permission_key)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .where(RolePermission.role_id == role_id)
        )
        return set(result.scalars().all())

    def bulk_assign_user_roles(
        self,
        request: BulkUserRoleAssign,
    ) -> dict:
        """
        Bulk assign roles to a user across multiple projects.
        This replaces all existing role assignments for the user in the specified projects.
        """
        # Verify user exists
        result = self.db.execute(
            select(User).where(User.id == request.user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(request.user_id))

        # Get all project IDs from the request
        project_ids = [m.project_id for m in request.mappings]

        # Remove existing role assignments for this user in these projects
        if project_ids:
            self.db.execute(
                delete(UserRoleProject).where(
                    UserRoleProject.user_id == request.user_id,
                    UserRoleProject.project_id.in_(project_ids),
                )
            )

        # Also remove assignments for projects not in the mappings (user was removed from those)
        # Get all current project assignments for this user
        result = self.db.execute(
            select(UserRoleProject.project_id)
            .where(UserRoleProject.user_id == request.user_id)
            .distinct()
        )
        current_project_ids = set(result.scalars().all())
        
        # Remove from projects that are no longer in mappings
        projects_to_remove = current_project_ids - set(project_ids)
        if projects_to_remove:
            self.db.execute(
                delete(UserRoleProject).where(
                    UserRoleProject.user_id == request.user_id,
                    UserRoleProject.project_id.in_(projects_to_remove),
                )
            )

        # Add new assignments
        assignments_created = 0
        for mapping in request.mappings:
            for role_id in mapping.role_ids:
                # Verify role exists and belongs to the project
                role_result = self.db.execute(
                    select(Role).where(
                        Role.id == role_id,
                        Role.project_id == mapping.project_id,
                    )
                )
                role = role_result.scalar_one_or_none()
                if not role:
                    raise ValidationError(f"Role {role_id} not found in project {mapping.project_id}")

                assignment = UserRoleProject(
                    user_id=request.user_id,
                    role_id=role_id,
                    project_id=mapping.project_id,
                )
                self.db.add(assignment)
                assignments_created += 1

        self.db.flush()

        return {
            "user_id": request.user_id,
            "assignments_created": assignments_created,
            "projects_updated": len(project_ids),
        }
