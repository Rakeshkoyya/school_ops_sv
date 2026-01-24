"""RBAC (Role-Based Access Control) service."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
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

    def __init__(self, db: AsyncSession):
        self.db = db

    # Permission methods
    async def list_permissions(self) -> list[PermissionResponse]:
        """List all available permissions."""
        result = await self.db.execute(
            select(Permission).order_by(Permission.permission_key)
        )
        permissions = result.scalars().all()
        return [PermissionResponse.model_validate(p) for p in permissions]

    async def create_permission(
        self,
        request: PermissionCreate,
    ) -> PermissionResponse:
        """Create a new permission (system admin only)."""
        # Check if permission key exists
        result = await self.db.execute(
            select(Permission).where(Permission.permission_key == request.permission_key)
        )
        if result.scalar_one_or_none():
            raise ValidationError(f"Permission key '{request.permission_key}' already exists")

        permission = Permission(
            permission_key=request.permission_key,
            description=request.description,
        )
        self.db.add(permission)
        await self.db.flush()
        await self.db.refresh(permission)

        return PermissionResponse.model_validate(permission)

    async def get_permission(self, permission_id: int) -> Permission:
        """Get permission by ID."""
        result = await self.db.execute(
            select(Permission).where(Permission.id == permission_id)
        )
        permission = result.scalar_one_or_none()
        if not permission:
            raise NotFoundError("Permission", str(permission_id))
        return permission

    # Role methods
    async def create_role(
        self,
        project_id: int,
        request: RoleCreate,
    ) -> RoleWithPermissions:
        """Create a new role for a project."""
        # Check if role name exists in project
        result = await self.db.execute(
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
        await self.db.flush()

        # Collect permission IDs - support both permission_ids and permissions (keys)
        permission_ids_to_assign = list(request.permission_ids)
        
        # If permission keys are provided, resolve them to IDs
        if request.permissions:
            for perm_key in request.permissions:
                perm_result = await self.db.execute(
                    select(Permission).where(Permission.permission_key == perm_key)
                )
                perm = perm_result.scalar_one_or_none()
                if perm and perm.id not in permission_ids_to_assign:
                    permission_ids_to_assign.append(perm.id)

        # Assign permissions
        permissions = []
        for permission_id in permission_ids_to_assign:
            permission = await self.get_permission(permission_id)
            role_permission = RolePermission(
                project_id=project_id,
                role_id=role.id,
                permission_id=permission_id,
            )
            self.db.add(role_permission)
            permissions.append(PermissionResponse.model_validate(permission))

        await self.db.flush()
        await self.db.refresh(role)

        return RoleWithPermissions(
            **RoleResponse.model_validate(role).model_dump(),
            permissions=permissions,
        )

    async def get_role(self, role_id: int, project_id: int) -> Role:
        """Get role by ID and project."""
        result = await self.db.execute(
            select(Role).where(
                Role.id == role_id,
                Role.project_id == project_id,
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise NotFoundError("Role", str(role_id))
        return role

    async def list_roles(self, project_id: int) -> list[RoleResponse]:
        """List all roles for a project."""
        result = await self.db.execute(
            select(Role)
            .where(Role.project_id == project_id)
            .order_by(Role.name)
        )
        roles = result.scalars().all()
        return [RoleResponse.model_validate(r) for r in roles]

    async def list_all_roles(self) -> list[RoleWithPermissionsAndProject]:
        """List all roles across all projects (for super admin)."""
        result = await self.db.execute(
            select(Role)
            .options(selectinload(Role.project))
            .order_by(Role.project_id, Role.name)
        )
        roles = result.scalars().all()
        
        # Get all role-permission mappings
        roles_with_permissions = []
        for role in roles:
            # Get permissions for this role
            perm_result = await self.db.execute(
                select(Permission)
                .join(RolePermission, Permission.id == RolePermission.permission_id)
                .where(RolePermission.role_id == role.id)
            )
            permissions = perm_result.scalars().all()
            
            roles_with_permissions.append(RoleWithPermissionsAndProject(
                **RoleResponse.model_validate(role).model_dump(),
                permissions=[PermissionResponse.model_validate(p) for p in permissions],
                project_name=role.project.name if role.project else None,
            ))
        
        return roles_with_permissions

    async def get_role_with_permissions(
        self,
        role_id: int,
        project_id: int,
    ) -> RoleWithPermissions:
        """Get role with its permissions."""
        role = await self.get_role(role_id, project_id)

        # Get permissions for role
        result = await self.db.execute(
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
            permissions=[PermissionResponse.model_validate(p) for p in permissions],
        )

    async def update_role(
        self,
        role_id: int,
        project_id: int,
        request: RoleUpdate,
    ) -> RoleResponse:
        """Update a role."""
        role = await self.get_role(role_id, project_id)

        update_data = request.model_dump(exclude_unset=True)
        
        # Handle permissions update if provided
        permissions_to_update = update_data.pop('permissions', None)

        # Check for name conflict
        if "name" in update_data:
            result = await self.db.execute(
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
            # Remove existing permissions
            await self.db.execute(
                delete(RolePermission).where(
                    RolePermission.role_id == role_id,
                    RolePermission.project_id == project_id,
                )
            )
            
            # Add new permissions
            for perm_key in permissions_to_update:
                perm_result = await self.db.execute(
                    select(Permission).where(Permission.permission_key == perm_key)
                )
                perm = perm_result.scalar_one_or_none()
                if perm:
                    role_permission = RolePermission(
                        project_id=project_id,
                        role_id=role_id,
                        permission_id=perm.id,
                    )
                    self.db.add(role_permission)

        await self.db.flush()
        await self.db.refresh(role)

        return RoleResponse.model_validate(role)

    async def delete_role(self, role_id: int, project_id: int) -> None:
        """Delete a role."""
        role = await self.get_role(role_id, project_id)

        # Check if any users are assigned to this role
        result = await self.db.execute(
            select(UserRoleProject).where(UserRoleProject.role_id == role_id)
        )
        if result.scalar_one_or_none():
            raise ValidationError("Cannot delete role with assigned users")

        # Delete related role_permissions first to avoid ORM trying to set FK to NULL
        await self.db.execute(
            delete(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.project_id == project_id,
            )
        )

        await self.db.delete(role)
        await self.db.flush()

    async def assign_permissions_to_role(
        self,
        role_id: int,
        project_id: int,
        permission_ids: list[int],
    ) -> RoleWithPermissions:
        """Assign permissions to a role (replaces existing)."""
        role = await self.get_role(role_id, project_id)

        # Remove existing permissions
        await self.db.execute(
            delete(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.project_id == project_id,
            )
        )

        # Add new permissions
        permissions = []
        for permission_id in permission_ids:
            permission = await self.get_permission(permission_id)
            role_permission = RolePermission(
                project_id=project_id,
                role_id=role_id,
                permission_id=permission_id,
            )
            self.db.add(role_permission)
            permissions.append(PermissionResponse.model_validate(permission))

        await self.db.flush()

        return RoleWithPermissions(
            **RoleResponse.model_validate(role).model_dump(),
            permissions=permissions,
        )

    # User-Role assignment methods
    async def assign_user_to_role(
        self,
        project_id: int,
        request: UserRoleAssign,
    ) -> UserRoleResponse:
        """Assign a user to a role in a project."""
        # Verify role exists
        role = await self.get_role(request.role_id, project_id)

        # Verify user exists
        result = await self.db.execute(
            select(User).where(User.id == request.user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(request.user_id))

        # Check if assignment exists
        result = await self.db.execute(
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
        await self.db.flush()
        await self.db.refresh(assignment)

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

    async def revoke_user_role(
        self,
        project_id: int,
        user_id: int,
        role_id: int,
    ) -> None:
        """Remove a user from a role in a project."""
        result = await self.db.execute(
            select(UserRoleProject).where(
                UserRoleProject.user_id == user_id,
                UserRoleProject.role_id == role_id,
                UserRoleProject.project_id == project_id,
            )
        )
        assignment = result.scalar_one_or_none()

        if not assignment:
            raise NotFoundError("User role assignment")

        await self.db.delete(assignment)
        await self.db.flush()

    async def list_project_users(
        self,
        project_id: int,
    ) -> list[UserWithRoles]:
        """List all users in a project with their roles."""
        result = await self.db.execute(
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

    async def get_user_permissions(
        self,
        user_id: int,
        project_id: int,
    ) -> set[str]:
        """Get all permissions for a user in a project."""
        result = await self.db.execute(
            select(Permission.permission_key)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .join(UserRoleProject, RolePermission.role_id == UserRoleProject.role_id)
            .where(
                UserRoleProject.user_id == user_id,
                UserRoleProject.project_id == project_id,
            )
        )
        return set(result.scalars().all())

    async def get_role_permissions(
        self,
        role_id: int,
    ) -> set[str]:
        """Get all permissions for a specific role."""
        result = await self.db.execute(
            select(Permission.permission_key)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .where(RolePermission.role_id == role_id)
        )
        return set(result.scalars().all())

    async def bulk_assign_user_roles(
        self,
        request: BulkUserRoleAssign,
    ) -> dict:
        """
        Bulk assign roles to a user across multiple projects.
        This replaces all existing role assignments for the user in the specified projects.
        """
        # Verify user exists
        result = await self.db.execute(
            select(User).where(User.id == request.user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(request.user_id))

        # Get all project IDs from the request
        project_ids = [m.project_id for m in request.mappings]

        # Remove existing role assignments for this user in these projects
        if project_ids:
            await self.db.execute(
                delete(UserRoleProject).where(
                    UserRoleProject.user_id == request.user_id,
                    UserRoleProject.project_id.in_(project_ids),
                )
            )

        # Also remove assignments for projects not in the mappings (user was removed from those)
        # Get all current project assignments for this user
        result = await self.db.execute(
            select(UserRoleProject.project_id)
            .where(UserRoleProject.user_id == request.user_id)
            .distinct()
        )
        current_project_ids = set(result.scalars().all())
        
        # Remove from projects that are no longer in mappings
        projects_to_remove = current_project_ids - set(project_ids)
        if projects_to_remove:
            await self.db.execute(
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
                role_result = await self.db.execute(
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

        await self.db.flush()

        return {
            "user_id": request.user_id,
            "assignments_created": assignments_created,
            "projects_updated": len(project_ids),
        }
