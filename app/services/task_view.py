"""Task View Style management service."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.project import Project
from app.models.task_view import TaskViewStyle, UserTaskViewPreference, TASK_COLUMNS, get_default_column_config
from app.models.user import User
from app.schemas.task_view import (
    AvailableColumnsResponse,
    ColumnConfig,
    ColumnMetadata,
    EffectiveViewResponse,
    TaskViewStyleCreate,
    TaskViewStyleListResponse,
    TaskViewStyleResponse,
    TaskViewStyleUpdate,
    UserViewPreferenceResponse,
)


class TaskViewService:
    """Task view style management service."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== View Style CRUD ====================

    def create_view_style(
        self,
        project_id: int,
        user_id: int,
        request: TaskViewStyleCreate,
    ) -> TaskViewStyleResponse:
        """Create a new task view style."""
        # Convert column_config to dict list for storage
        column_config = [col.model_dump() for col in request.column_config]
        
        view_style = TaskViewStyle(
            project_id=project_id,
            name=request.name,
            description=request.description,
            column_config=column_config,
            is_system_default=False,
            created_by_id=user_id,
        )
        self.db.add(view_style)
        self.db.flush()
        self.db.refresh(view_style)
        
        return self._to_response(view_style)

    def get_view_style(
        self,
        view_id: int,
        project_id: int,
    ) -> TaskViewStyle:
        """Get view style by ID (returns model for internal use)."""
        result = self.db.execute(
            select(TaskViewStyle).where(
                TaskViewStyle.id == view_id,
                TaskViewStyle.project_id == project_id,
            )
        )
        view_style = result.scalar_one_or_none()
        if not view_style:
            raise NotFoundError("Task view style", str(view_id))
        return view_style

    def get_view_style_response(
        self,
        view_id: int,
        project_id: int,
    ) -> TaskViewStyleResponse:
        """Get view style as response schema."""
        view_style = self.get_view_style(view_id, project_id)
        return self._to_response(view_style)

    def list_view_styles(
        self,
        project_id: int,
    ) -> TaskViewStyleListResponse:
        """List all view styles for a project."""
        result = self.db.execute(
            select(TaskViewStyle)
            .where(TaskViewStyle.project_id == project_id)
            .order_by(TaskViewStyle.is_system_default.desc(), TaskViewStyle.name)
        )
        view_styles = result.scalars().all()
        
        # Get project default
        project = self.db.execute(
            select(Project).where(Project.id == project_id)
        ).scalar_one_or_none()
        
        return TaskViewStyleListResponse(
            views=[self._to_response(vs) for vs in view_styles],
            project_default_id=project.default_task_view_style_id if project else None,
        )

    def update_view_style(
        self,
        view_id: int,
        project_id: int,
        user_id: int,
        request: TaskViewStyleUpdate,
        is_admin: bool = False,
    ) -> TaskViewStyleResponse:
        """Update a view style."""
        view_style = self.get_view_style(view_id, project_id)
        
        # Check permission: creator or admin can update
        if not is_admin and view_style.created_by_id != user_id:
            raise ForbiddenError("You can only update your own view styles")
        
        # System default views can only be updated by admin
        if view_style.is_system_default and not is_admin:
            raise ForbiddenError("System default views can only be updated by administrators")
        
        update_data = request.model_dump(exclude_unset=True)
        
        # Convert column_config if present
        if "column_config" in update_data and update_data["column_config"]:
            update_data["column_config"] = [col.model_dump() for col in request.column_config]
        
        for field, value in update_data.items():
            setattr(view_style, field, value)
        
        self.db.flush()
        self.db.refresh(view_style)
        return self._to_response(view_style)

    def delete_view_style(
        self,
        view_id: int,
        project_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> None:
        """Delete a view style."""
        view_style = self.get_view_style(view_id, project_id)
        
        # Cannot delete system default
        if view_style.is_system_default:
            raise ValidationError("Cannot delete the system default view style")
        
        # Check permission: creator or admin can delete
        if not is_admin and view_style.created_by_id != user_id:
            raise ForbiddenError("You can only delete your own view styles")
        
        # Check if this is the project default - if so, reset to system default
        project = self.db.execute(
            select(Project).where(Project.id == project_id)
        ).scalar_one_or_none()
        
        if project and project.default_task_view_style_id == view_id:
            # Find system default and set it
            system_default = self.db.execute(
                select(TaskViewStyle).where(
                    TaskViewStyle.project_id == project_id,
                    TaskViewStyle.is_system_default == True,
                )
            ).scalar_one_or_none()
            project.default_task_view_style_id = system_default.id if system_default else None
        
        self.db.delete(view_style)
        self.db.flush()

    # ==================== Project Default Management ====================

    def set_project_default(
        self,
        project_id: int,
        view_id: int,
    ) -> TaskViewStyleResponse:
        """Set a view style as the project default."""
        # Verify view exists and belongs to project
        view_style = self.get_view_style(view_id, project_id)
        
        # Update project
        result = self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", str(project_id))
        
        project.default_task_view_style_id = view_id
        self.db.flush()
        
        return self._to_response(view_style)

    def get_project_default(
        self,
        project_id: int,
    ) -> TaskViewStyleResponse | None:
        """Get the project's default view style."""
        result = self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        
        if not project or not project.default_task_view_style_id:
            return None
        
        view_style = self.db.execute(
            select(TaskViewStyle).where(TaskViewStyle.id == project.default_task_view_style_id)
        ).scalar_one_or_none()
        
        return self._to_response(view_style) if view_style else None

    # ==================== User Preference Management ====================

    def get_user_preference(
        self,
        user_id: int,
        project_id: int,
    ) -> UserViewPreferenceResponse | None:
        """Get user's view style preference for a project."""
        result = self.db.execute(
            select(UserTaskViewPreference).where(
                UserTaskViewPreference.user_id == user_id,
                UserTaskViewPreference.project_id == project_id,
            )
        )
        preference = result.scalar_one_or_none()
        
        if not preference:
            return None
        
        return UserViewPreferenceResponse(
            user_id=preference.user_id,
            project_id=preference.project_id,
            view_style_id=preference.view_style_id,
            view_style=self._to_response(preference.view_style),
        )

    def set_user_preference(
        self,
        user_id: int,
        project_id: int,
        view_id: int,
    ) -> UserViewPreferenceResponse:
        """Set user's view style preference for a project."""
        # Verify view exists and belongs to project
        view_style = self.get_view_style(view_id, project_id)
        
        # Check if preference already exists
        result = self.db.execute(
            select(UserTaskViewPreference).where(
                UserTaskViewPreference.user_id == user_id,
                UserTaskViewPreference.project_id == project_id,
            )
        )
        preference = result.scalar_one_or_none()
        
        if preference:
            # Update existing
            preference.view_style_id = view_id
        else:
            # Create new
            preference = UserTaskViewPreference(
                user_id=user_id,
                project_id=project_id,
                view_style_id=view_id,
            )
            self.db.add(preference)
        
        self.db.flush()
        self.db.refresh(preference)
        
        return UserViewPreferenceResponse(
            user_id=preference.user_id,
            project_id=preference.project_id,
            view_style_id=preference.view_style_id,
            view_style=self._to_response(view_style),
        )

    def clear_user_preference(
        self,
        user_id: int,
        project_id: int,
    ) -> None:
        """Clear user's view style preference (fall back to project default)."""
        result = self.db.execute(
            select(UserTaskViewPreference).where(
                UserTaskViewPreference.user_id == user_id,
                UserTaskViewPreference.project_id == project_id,
            )
        )
        preference = result.scalar_one_or_none()
        
        if preference:
            self.db.delete(preference)
            self.db.flush()

    def get_effective_view(
        self,
        user_id: int,
        project_id: int,
    ) -> EffectiveViewResponse:
        """Get the effective view for a user in a project.
        
        Priority:
        1. User's personal preference
        2. Project's default view
        3. System default view
        """
        # Check user preference first
        user_pref = self.get_user_preference(user_id, project_id)
        if user_pref:
            return EffectiveViewResponse(
                view=user_pref.view_style,
                source="user_preference",
            )
        
        # Check project default
        project_default = self.get_project_default(project_id)
        if project_default:
            return EffectiveViewResponse(
                view=project_default,
                source="project_default",
            )
        
        # Fall back to system default
        result = self.db.execute(
            select(TaskViewStyle).where(
                TaskViewStyle.project_id == project_id,
                TaskViewStyle.is_system_default == True,
            )
        )
        system_default = result.scalar_one_or_none()
        
        if system_default:
            return EffectiveViewResponse(
                view=self._to_response(system_default),
                source="system_default",
            )
        
        # If no system default exists (shouldn't happen), create one on the fly
        # This handles edge case where migration wasn't run
        raise NotFoundError("Task view style", "system_default")

    # ==================== Utility Methods ====================

    def get_available_columns(self) -> AvailableColumnsResponse:
        """Get list of all available columns for view configuration."""
        columns = [
            ColumnMetadata(
                field=col["field"],
                label=col["label"],
                default_visible=col["default_visible"],
                default_order=col["default_order"],
            )
            for col in TASK_COLUMNS
        ]
        return AvailableColumnsResponse(columns=columns)

    def _to_response(self, view_style: TaskViewStyle) -> TaskViewStyleResponse:
        """Convert model to response schema."""
        # Get creator name
        created_by_name = None
        if view_style.created_by_id:
            user = self.db.execute(
                select(User).where(User.id == view_style.created_by_id)
            ).scalar_one_or_none()
            created_by_name = user.name if user else None
        
        # Convert column_config dicts to ColumnConfig objects
        column_config = [
            ColumnConfig(**col) for col in view_style.column_config
        ]
        
        return TaskViewStyleResponse(
            id=view_style.id,
            project_id=view_style.project_id,
            name=view_style.name,
            description=view_style.description,
            column_config=column_config,
            is_system_default=view_style.is_system_default,
            created_by_id=view_style.created_by_id,
            created_by_name=created_by_name,
            created_at=view_style.created_at,
            updated_at=view_style.updated_at,
        )
