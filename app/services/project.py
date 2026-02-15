"""Project management service."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.models.menu_screen import MenuScreen, ProjectMenuScreen
from app.models.project import Project, ProjectStatus
from app.models.rbac import Permission, Role, RolePermission, UserRoleProject
from app.schemas.project import ProjectCreate, ProjectListItem, ProjectResponse, ProjectUpdate


# Default permissions for School Admin role (all except project:delete)
SCHOOL_ADMIN_EXCLUDED_PERMISSIONS = ["project:delete", "project:create"]

# Default permissions for Staff role (limited access for teachers)
STAFF_DEFAULT_PERMISSIONS = [
    # Attendance permissions
    "attendance:view",
    "attendance:create",
    "attendance:update",
    # Exam permissions
    "exam:view",
    "exam:create",
    "exam:update",
    # Student permissions (view only)
    "student:view",
    # Task permissions
    "task:view",
    "task:create",
    "task:update",
    # Task category permissions (view only)
    "task_category:view",
    # Upload permissions
    "upload:view",
    "upload:create",
    # Notification permissions
    "notification:view",
]


class ProjectService:
    """Project management service."""

    def __init__(self, db: Session):
        self.db = db

    def create_project(
        self,
        request: ProjectCreate,
        created_by_id: int,
    ) -> ProjectResponse:
        """Create a new project (school/tenant)."""
        project = Project(
            name=request.name,
            slug=request.slug,
            description=request.description,
            theme_color=request.theme_color,
            logo_url=request.logo_url,
            status=ProjectStatus.ACTIVE,
        )

        self.db.add(project)
        self.db.flush()

        # Allocate all menus to the new project by default
        menu_result = self.db.execute(select(MenuScreen.id))
        for (menu_id,) in menu_result:
            project_menu = ProjectMenuScreen(
                project_id=project.id,
                menu_screen_id=menu_id,
            )
            self.db.add(project_menu)
        self.db.flush()

        admin_role_id = None

        # Create default roles if requested
        if request.add_default_roles:
            # Get all permissions from the database
            perm_result = self.db.execute(select(Permission))
            all_permissions = {p.permission_key: p.id for p in perm_result.scalars().all()}

            # Create School Admin role
            school_admin_role = Role(
                project_id=project.id,
                name="School Admin",
                description="School administrator with full access to manage the school",
                is_project_admin=True,
                is_role_admin=True,
            )
            self.db.add(school_admin_role)
            self.db.flush()
            admin_role_id = school_admin_role.id

            # Assign all permissions to School Admin except excluded ones
            for perm_key, perm_id in all_permissions.items():
                if perm_key not in SCHOOL_ADMIN_EXCLUDED_PERMISSIONS:
                    role_perm = RolePermission(
                        project_id=project.id,
                        role_id=school_admin_role.id,
                        permission_id=perm_id,
                    )
                    self.db.add(role_perm)

            # Create Staff role
            staff_role = Role(
                project_id=project.id,
                name="Staff",
                description="Staff member with limited access",
                is_project_admin=False,
                is_role_admin=False,
            )
            self.db.add(staff_role)
            self.db.flush()

            # Assign limited permissions to Staff role
            for perm_key in STAFF_DEFAULT_PERMISSIONS:
                if perm_key in all_permissions:
                    role_perm = RolePermission(
                        project_id=project.id,
                        role_id=staff_role.id,
                        permission_id=all_permissions[perm_key],
                    )
                    self.db.add(role_perm)

            self.db.flush()

        # Assign creator as School Admin if default roles were created
        if admin_role_id:
            user_role = UserRoleProject(
                user_id=created_by_id,
                role_id=admin_role_id,
                project_id=project.id,
            )
            self.db.add(user_role)
            self.db.flush()

        self.db.refresh(project)

        return ProjectResponse.model_validate(project)

    def get_project(self, project_id: int) -> Project:
        """Get project by ID."""
        result = self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()

        if not project:
            raise NotFoundError("Project", str(project_id))

        return project

    def update_project(
        self,
        project_id: int,
        request: ProjectUpdate,
    ) -> ProjectResponse:
        """Update project metadata."""
        project = self.get_project(project_id)

        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)

        self.db.flush()
        self.db.refresh(project)

        return ProjectResponse.model_validate(project)

    def list_all_projects(self) -> list[ProjectResponse]:
        """List all projects (for super admin use).
        
        Returns all projects in the system without deduplication issues.
        """
        result = self.db.execute(
            select(Project).order_by(Project.name)
        )
        projects = result.scalars().all()
        return [ProjectResponse.model_validate(p) for p in projects]

    def list_user_projects(self, user_id: int) -> list[ProjectListItem]:
        """List all project-role combinations for a user.
        
        Returns all roles the user has across all projects.
        A user with multiple roles in the same project will have multiple entries.
        """
        result = self.db.execute(
            select(Project, Role)
            .join(UserRoleProject, Project.id == UserRoleProject.project_id)
            .join(Role, UserRoleProject.role_id == Role.id)
            .where(UserRoleProject.user_id == user_id)
            .order_by(Project.name, Role.name)
        )
        rows = result.all()

        # Return all project-role combinations (no deduplication)
        # This allows the frontend to show all roles a user can switch between
        project_roles: list[ProjectListItem] = []
        for project, role in rows:
            project_roles.append(ProjectListItem(
                id=project.id,
                name=project.name,
                slug=project.slug,
                description=project.description,
                theme_color=project.theme_color,
                logo_url=project.logo_url,
                status=project.status,
                role_id=role.id,
                role_name=role.name,
                is_project_admin=role.is_project_admin,
                is_role_admin=role.is_role_admin,
            ))

        return project_roles

    def suspend_project(self, project_id: int) -> ProjectResponse:
        """Suspend a project (block all mutations)."""
        project = self.get_project(project_id)
        project.status = ProjectStatus.SUSPENDED
        self.db.flush()
        self.db.refresh(project)
        return ProjectResponse.model_validate(project)

    def activate_project(self, project_id: int) -> ProjectResponse:
        """Activate a suspended project."""
        project = self.get_project(project_id)
        project.status = ProjectStatus.ACTIVE
        self.db.flush()
        self.db.refresh(project)
        return ProjectResponse.model_validate(project)

    def delete_project(self, project_id: int) -> None:
        """Delete a project and all its related data.
        
        This is a destructive operation that cannot be undone.
        All related data (roles, user assignments, etc.) will be cascade deleted
        by the database due to ON DELETE CASCADE foreign key constraints.
        """
        # Verify project exists first
        self.get_project(project_id)
        
        # Use direct SQL DELETE to avoid ORM loading relationships
        # and trying to set foreign keys to NULL
        self.db.execute(
            delete(Project).where(Project.id == project_id)
        )
        self.db.flush()

