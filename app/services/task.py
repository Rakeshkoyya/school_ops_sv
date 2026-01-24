"""Task management service with timer support."""

from datetime import date, datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.rbac import Role, UserRoleProject
from app.models.task import Task, TaskCategory, TaskStatus
from app.models.user import User
from app.schemas.task import (
    StaffTasksSummary,
    TaskCategoryCreate,
    TaskCategoryResponse,
    TaskCategoryUpdate,
    TaskCreate,
    TaskFilter,
    TasksGroupedByCategory,
    TaskUpdate,
    TaskWithDetails,
)


class TaskService:
    """Task management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Category Methods ====================

    async def create_category(
        self,
        project_id: int,
        request: TaskCategoryCreate,
    ) -> TaskCategoryResponse:
        """Create a task category."""
        category = TaskCategory(
            project_id=project_id,
            name=request.name,
            description=request.description,
        )
        self.db.add(category)
        await self.db.flush()
        await self.db.refresh(category)
        return TaskCategoryResponse.model_validate(category)

    async def get_category(
        self,
        category_id: int,
        project_id: int,
    ) -> TaskCategory:
        """Get category by ID."""
        result = await self.db.execute(
            select(TaskCategory).where(
                TaskCategory.id == category_id,
                TaskCategory.project_id == project_id,
            )
        )
        category = result.scalar_one_or_none()
        if not category:
            raise NotFoundError("Task category", str(category_id))
        return category

    async def list_categories(
        self,
        project_id: int,
    ) -> list[TaskCategoryResponse]:
        """List all categories for a project."""
        result = await self.db.execute(
            select(TaskCategory)
            .where(TaskCategory.project_id == project_id)
            .order_by(TaskCategory.name)
        )
        categories = result.scalars().all()
        return [TaskCategoryResponse.model_validate(c) for c in categories]

    async def update_category(
        self,
        category_id: int,
        project_id: int,
        request: TaskCategoryUpdate,
    ) -> TaskCategoryResponse:
        """Update a category."""
        category = await self.get_category(category_id, project_id)
        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(category, field, value)
        await self.db.flush()
        await self.db.refresh(category)
        return TaskCategoryResponse.model_validate(category)

    async def delete_category(
        self,
        category_id: int,
        project_id: int,
    ) -> None:
        """Delete a category (tasks will have null category)."""
        category = await self.get_category(category_id, project_id)
        await self.db.delete(category)
        await self.db.flush()

    # ==================== Task Creation Methods ====================

    async def create_task(
        self,
        project_id: int,
        user_id: int,
        request: TaskCreate,
    ) -> TaskWithDetails:
        """Create a new task."""
        if request.category_id:
            await self.get_category(request.category_id, project_id)

        # Determine assigned user - default to creator if not specified
        assigned_user_id = request.assigned_to_user_id or user_id
        if request.assigned_to_user_id:
            await self._verify_user_in_project(request.assigned_to_user_id, project_id)
        
        # If assigning to a role, verify the role exists in the project
        if request.assigned_to_role_id:
            await self._verify_role_in_project(request.assigned_to_role_id, project_id)

        task = Task(
            project_id=project_id,
            category_id=request.category_id,
            title=request.title,
            description=request.description,
            status=TaskStatus.PENDING,
            due_date=request.due_date,
            assigned_to_user_id=assigned_user_id,
            assigned_to_role_id=request.assigned_to_role_id,
            created_by_id=user_id,
        )
        self.db.add(task)
        await self.db.flush()
        
        # Reload task with relationships
        task = await self.get_task(task.id, project_id)
        return await self._enrich_task(task)

    # ==================== Task Query Methods ====================

    async def get_task(
        self,
        task_id: int,
        project_id: int,
    ) -> Task:
        """Get task by ID."""
        result = await self.db.execute(
            select(Task)
            .options(
                selectinload(Task.category),
                selectinload(Task.assigned_user),
                selectinload(Task.assigned_role),
                selectinload(Task.created_by),
            )
            .where(
                Task.id == task_id,
                Task.project_id == project_id,
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            raise NotFoundError("Task", str(task_id))
        return task

    async def get_my_tasks(
        self,
        project_id: int,
        user_id: int,
        include_role_tasks: bool = True,
    ) -> list[TaskWithDetails]:
        """Get tasks assigned to the current user (directly or via role)."""
        conditions = [Task.assigned_to_user_id == user_id]

        if include_role_tasks:
            role_result = await self.db.execute(
                select(UserRoleProject.role_id).where(
                    UserRoleProject.user_id == user_id,
                    UserRoleProject.project_id == project_id,
                )
            )
            role_ids = list(role_result.scalars().all())
            if role_ids:
                conditions.append(Task.assigned_to_role_id.in_(role_ids))

        query = (
            select(Task)
            .options(
                selectinload(Task.category),
                selectinload(Task.assigned_user),
                selectinload(Task.assigned_role),
                selectinload(Task.created_by),
            )
            .where(
                Task.project_id == project_id,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE]),
                or_(*conditions),
            )
            .order_by(Task.due_date.asc().nullslast(), Task.created_at.desc())
        )

        result = await self.db.execute(query)
        tasks = result.scalars().all()
        return [await self._enrich_task(t) for t in tasks]

    async def get_my_tasks_grouped_by_category(
        self,
        project_id: int,
        user_id: int,
    ) -> list[TasksGroupedByCategory]:
        """Get user's tasks grouped by category."""
        tasks = await self.get_my_tasks(project_id, user_id)

        # Group by category
        groups: dict[int | None, TasksGroupedByCategory] = {}
        for task in tasks:
            cat_id = task.category_id
            if cat_id not in groups:
                groups[cat_id] = TasksGroupedByCategory(
                    category_id=cat_id,
                    category_name=task.category_name,
                    tasks=[],
                )
            groups[cat_id].tasks.append(task)

        # Sort: categories with tasks first, then uncategorized
        sorted_groups = sorted(
            groups.values(),
            key=lambda g: (g.category_id is None, g.category_name or ""),
        )
        return sorted_groups

    async def get_staff_tasks(
        self,
        project_id: int,
        staff_user_id: int,
    ) -> StaffTasksSummary:
        """Get tasks for a specific staff member (admin view)."""
        # Get user info
        user_result = await self.db.execute(
            select(User).where(User.id == staff_user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User", str(staff_user_id))

        # Get all tasks for the user
        query = (
            select(Task)
            .options(
                selectinload(Task.category),
                selectinload(Task.assigned_user),
                selectinload(Task.assigned_role),
                selectinload(Task.created_by),
            )
            .where(
                Task.project_id == project_id,
                Task.assigned_to_user_id == staff_user_id,
            )
            .order_by(Task.due_date.asc().nullslast(), Task.created_at.desc())
        )

        result = await self.db.execute(query)
        tasks = result.scalars().all()
        enriched_tasks = [await self._enrich_task(t) for t in tasks]

        # Calculate counts
        today = date.today()
        pending_count = sum(1 for t in enriched_tasks if t.status == TaskStatus.PENDING)
        in_progress_count = sum(1 for t in enriched_tasks if t.status == TaskStatus.IN_PROGRESS)
        overdue_count = sum(1 for t in enriched_tasks if t.is_overdue)
        completed_today_count = sum(
            1 for t in enriched_tasks
            if t.status == TaskStatus.DONE and t.end_time and t.end_time.date() == today
        )

        return StaffTasksSummary(
            user_id=staff_user_id,
            user_name=user.name,
            pending_count=pending_count,
            in_progress_count=in_progress_count,
            overdue_count=overdue_count,
            completed_today_count=completed_today_count,
            tasks=enriched_tasks,
        )

    async def list_tasks(
        self,
        project_id: int,
        filters: TaskFilter | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TaskWithDetails], int]:
        """List tasks with optional filtering."""
        query = select(Task).where(Task.project_id == project_id)

        if filters:
            if filters.status:
                query = query.where(Task.status == filters.status)
            if filters.category_id:
                query = query.where(Task.category_id == filters.category_id)
            if filters.assigned_to_user_id:
                query = query.where(Task.assigned_to_user_id == filters.assigned_to_user_id)
            if filters.assigned_to_role_id:
                query = query.where(Task.assigned_to_role_id == filters.assigned_to_role_id)
            if filters.due_before:
                query = query.where(Task.due_date <= filters.due_before)
            if filters.due_after:
                query = query.where(Task.due_date >= filters.due_after)
            if filters.is_overdue:
                today = date.today()
                query = query.where(
                    and_(
                        Task.due_date < today,
                        Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                    )
                )

        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Apply pagination
        query = (
            query
            .options(
                selectinload(Task.category),
                selectinload(Task.assigned_user),
                selectinload(Task.assigned_role),
                selectinload(Task.created_by),
            )
            .order_by(Task.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        tasks = result.scalars().all()
        enriched = [await self._enrich_task(t) for t in tasks]
        return enriched, total

    # ==================== Task Update Methods ====================

    async def update_task(
        self,
        task_id: int,
        project_id: int,
        user_id: int,
        request: TaskUpdate,
        is_admin: bool = False,
    ) -> TaskWithDetails:
        """Update a task."""
        task = await self.get_task(task_id, project_id)

        # Check permissions: admin can update any task, user can update tasks they created or are assigned to
        if not is_admin:
            if task.created_by_id != user_id and task.assigned_to_user_id != user_id:
                raise ForbiddenError("You can only update tasks you created or are assigned to")

        update_data = request.model_dump(exclude_unset=True)

        if "category_id" in update_data and update_data["category_id"]:
            await self.get_category(update_data["category_id"], project_id)

        for field, value in update_data.items():
            setattr(task, field, value)

        await self.db.flush()
        await self.db.refresh(task)
        return await self._enrich_task(task)

    async def start_task(
        self,
        task_id: int,
        project_id: int,
        user_id: int,
    ) -> TaskWithDetails:
        """Start working on a task (sets start_time and status to in_progress)."""
        task = await self.get_task(task_id, project_id)

        # Verify user is assigned to this task
        if task.assigned_to_user_id != user_id:
            raise ForbiddenError("You can only start tasks assigned to you")

        if task.status == TaskStatus.DONE:
            raise ValidationError("Cannot start a completed task")

        task.start_time = datetime.now(timezone.utc)
        task.status = TaskStatus.IN_PROGRESS
        await self.db.flush()
        await self.db.refresh(task)
        return await self._enrich_task(task)

    async def complete_task(
        self,
        task_id: int,
        project_id: int,
        user_id: int,
    ) -> TaskWithDetails:
        """Mark a task as complete."""
        task = await self.get_task(task_id, project_id)

        # Verify user is assigned to this task
        if task.assigned_to_user_id != user_id:
            raise ForbiddenError("You can only complete tasks assigned to you")

        task.end_time = datetime.now(timezone.utc)
        task.status = TaskStatus.DONE
        await self.db.flush()
        await self.db.refresh(task)
        return await self._enrich_task(task)

    async def update_task_status(
        self,
        task_id: int,
        project_id: int,
        user_id: int,
        status: TaskStatus,
    ) -> TaskWithDetails:
        """Quick status update for a task."""
        task = await self.get_task(task_id, project_id)

        # Verify user is assigned to this task
        if task.assigned_to_user_id != user_id:
            raise ForbiddenError("You can only update status of tasks assigned to you")

        task.status = status
        if status == TaskStatus.IN_PROGRESS and not task.start_time:
            task.start_time = datetime.now(timezone.utc)
        elif status == TaskStatus.DONE:
            task.end_time = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(task)
        return await self._enrich_task(task)

    async def delete_task(
        self,
        task_id: int,
        project_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> None:
        """Delete a task."""
        task = await self.get_task(task_id, project_id)

        # Check permissions
        if not is_admin:
            if task.created_by_id != user_id:
                raise ForbiddenError("You can only delete tasks you created")

        await self.db.delete(task)
        await self.db.flush()

    # ==================== Helper Methods ====================

    async def _verify_user_in_project(self, user_id: int, project_id: int) -> None:
        """Verify a user exists and has access to the project."""
        result = await self.db.execute(
            select(UserRoleProject).where(
                UserRoleProject.user_id == user_id,
                UserRoleProject.project_id == project_id,
            )
        )
        if not result.scalar_one_or_none():
            raise ValidationError(f"User {user_id} is not a member of this project")

    async def _verify_role_in_project(self, role_id: int, project_id: int) -> None:
        """Verify a role exists in the project."""
        result = await self.db.execute(
            select(Role).where(
                Role.id == role_id,
                Role.project_id == project_id,
            )
        )
        if not result.scalar_one_or_none():
            raise ValidationError(f"Role {role_id} is not in this project")

    async def _enrich_task(self, task: Task) -> TaskWithDetails:
        """Enrich task with related names and computed fields."""
        today = date.today()
        now = datetime.now(timezone.utc)
        
        is_overdue = (
            task.due_date is not None
            and task.due_date < today
            and task.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        )

        # Calculate elapsed time if task is in progress
        elapsed_seconds = None
        if task.start_time and task.status == TaskStatus.IN_PROGRESS:
            elapsed = now - task.start_time
            elapsed_seconds = int(elapsed.total_seconds())

        # Calculate time remaining until due_date (in seconds)
        time_remaining_seconds = None
        if task.due_date and task.status not in [TaskStatus.DONE, TaskStatus.CANCELLED]:
            # Due date is end of day
            due_datetime = datetime.combine(task.due_date, datetime.max.time()).replace(tzinfo=timezone.utc)
            remaining = due_datetime - now
            time_remaining_seconds = int(remaining.total_seconds())

        return TaskWithDetails(
            id=task.id,
            project_id=task.project_id,
            category_id=task.category_id,
            title=task.title,
            description=task.description,
            status=task.status,
            start_time=task.start_time,
            end_time=task.end_time,
            due_date=task.due_date,
            assigned_to_user_id=task.assigned_to_user_id,
            assigned_to_role_id=task.assigned_to_role_id,
            auto_rule_key=task.auto_rule_key,
            created_by_id=task.created_by_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
            category_name=task.category.name if task.category else None,
            assigned_user_name=task.assigned_user.name if task.assigned_user else None,
            assigned_role_name=task.assigned_role.name if task.assigned_role else None,
            created_by_name=task.created_by.name if task.created_by else None,
            is_overdue=is_overdue,
            time_remaining_seconds=time_remaining_seconds,
            elapsed_seconds=elapsed_seconds,
        )

    async def get_project_staff(self, project_id: int) -> list[dict]:
        """Get list of staff members in the project for admin selection."""
        result = await self.db.execute(
            select(User, Role.name.label("role_name"))
            .join(UserRoleProject, UserRoleProject.user_id == User.id)
            .join(Role, Role.id == UserRoleProject.role_id)
            .where(
                UserRoleProject.project_id == project_id,
                User.is_active == True,
            )
            .order_by(User.name)
        )
        rows = result.all()

        # Group by user
        staff_map = {}
        for user, role_name in rows:
            if user.id not in staff_map:
                staff_map[user.id] = {
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "roles": [],
                }
            staff_map[user.id]["roles"].append(role_name)

        return list(staff_map.values())
