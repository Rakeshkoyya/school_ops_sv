"""Task management service with timer support."""

from datetime import date, datetime, timezone, timedelta

from sqlalchemy import and_, func, or_, select

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.evo_point import EvoPointTransaction, EvoTransactionType
from app.models.project import Project
from app.models.rbac import Role, UserRoleProject
from app.models.task import EvoReductionType, Task, TaskCategory, TaskStatus
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

    def __init__(self, db: Session):
        self.db = db

    # ==================== Category Methods ====================

    def create_category(
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
        self.db.flush()
        self.db.refresh(category)
        return TaskCategoryResponse.model_validate(category)

    def get_category(
        self,
        category_id: int,
        project_id: int,
    ) -> TaskCategory:
        """Get category by ID."""
        result = self.db.execute(
            select(TaskCategory).where(
                TaskCategory.id == category_id,
                TaskCategory.project_id == project_id,
            )
        )
        category = result.scalar_one_or_none()
        if not category:
            raise NotFoundError("Task category", str(category_id))
        return category

    def list_categories(
        self,
        project_id: int,
    ) -> list[TaskCategoryResponse]:
        """List all categories for a project."""
        result = self.db.execute(
            select(TaskCategory)
            .where(TaskCategory.project_id == project_id)
            .order_by(TaskCategory.name)
        )
        categories = result.scalars().all()
        return [TaskCategoryResponse.model_validate(c) for c in categories]

    def update_category(
        self,
        category_id: int,
        project_id: int,
        request: TaskCategoryUpdate,
    ) -> TaskCategoryResponse:
        """Update a category."""
        category = self.get_category(category_id, project_id)
        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(category, field, value)
        self.db.flush()
        self.db.refresh(category)
        return TaskCategoryResponse.model_validate(category)

    def delete_category(
        self,
        category_id: int,
        project_id: int,
    ) -> None:
        """Delete a category (tasks will have null category)."""
        category = self.get_category(category_id, project_id)
        self.db.delete(category)
        self.db.flush()

    # ==================== Task Creation Methods ====================

    def create_task(
        self,
        project_id: int,
        user_id: int,
        request: TaskCreate,
    ) -> TaskWithDetails:
        """Create a new task."""
        if request.category_id:
            self.get_category(request.category_id, project_id)

        # Determine assigned user - default to creator if not specified
        assigned_user_id = request.assigned_to_user_id or user_id
        if request.assigned_to_user_id:
            self._verify_user_in_project(request.assigned_to_user_id, project_id)
        
        # If assigning to a role, verify the role exists in the project
        if request.assigned_to_role_id:
            self._verify_role_in_project(request.assigned_to_role_id, project_id)

        # Handle due_datetime - treat naive datetime as IST
        due_datetime = request.due_datetime
        if due_datetime and due_datetime.tzinfo is None:
            # Input is naive - treat as IST
            due_datetime = due_datetime.replace(tzinfo=IST)

        # Handle evo_extension_end - treat naive datetime as IST
        evo_extension_end = request.evo_extension_end
        if evo_extension_end and evo_extension_end.tzinfo is None:
            evo_extension_end = evo_extension_end.replace(tzinfo=IST)

        task = Task(
            project_id=project_id,
            category_id=request.category_id,
            title=request.title,
            description=request.description,
            status=TaskStatus.PENDING,
            due_datetime=due_datetime,
            assigned_to_user_id=assigned_user_id,
            assigned_to_role_id=request.assigned_to_role_id,
            created_by_id=user_id,
            # Evo Points fields
            evo_points=request.evo_points,
            evo_reduction_type=request.evo_reduction_type or EvoReductionType.NONE,
            evo_extension_end=evo_extension_end,
            evo_fixed_reduction_points=request.evo_fixed_reduction_points,
        )
        self.db.add(task)
        self.db.flush()
        
        # Reload task with relationships
        task = self.get_task(task.id, project_id)
        return self._enrich_task(task)

    # ==================== Task Query Methods ====================

    def get_task(
        self,
        task_id: int,
        project_id: int,
    ) -> Task:
        """Get task by ID."""
        result = self.db.execute(
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

    def get_my_tasks(
        self,
        project_id: int,
        user_id: int,
        include_role_tasks: bool = True,
    ) -> list[TaskWithDetails]:
        """Get tasks assigned to the current user (directly or via role).
        
        Includes:
        - All pending, in_progress, and overdue tasks
        - Tasks completed TODAY (so users can see recent accomplishments)
        """
        conditions = [Task.assigned_to_user_id == user_id]

        if include_role_tasks:
            role_result = self.db.execute(
                select(UserRoleProject.role_id).where(
                    UserRoleProject.user_id == user_id,
                    UserRoleProject.project_id == project_id,
                )
            )
            role_ids = list(role_result.scalars().all())
            if role_ids:
                conditions.append(Task.assigned_to_role_id.in_(role_ids))

        # Get today's start in IST
        today_start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)

        # Status conditions: pending/in_progress/overdue OR completed today
        status_conditions = or_(
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE]),
            and_(
                Task.status == TaskStatus.DONE,
                Task.end_time >= today_start,  # Completed today
            ),
        )

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
                status_conditions,
                or_(*conditions),
            )
            .order_by(
                # Sort: non-done first, then by due date
                Task.status == TaskStatus.DONE,  # Done tasks at bottom
                Task.due_datetime.asc().nullslast(),
                Task.created_at.desc(),
            )
        )

        result = self.db.execute(query)
        tasks = result.scalars().all()
        return [self._enrich_task(t) for t in tasks]

    def get_my_tasks_grouped_by_category(
        self,
        project_id: int,
        user_id: int,
    ) -> list[TasksGroupedByCategory]:
        """Get user's tasks grouped by category."""
        tasks = self.get_my_tasks(project_id, user_id)

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

    def get_staff_tasks(
        self,
        project_id: int,
        staff_user_id: int,
    ) -> StaffTasksSummary:
        """Get tasks for a specific staff member (admin view)."""
        # Get user info
        user_result = self.db.execute(
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
            .order_by(Task.due_datetime.asc().nullslast(), Task.created_at.desc())
        )

        result = self.db.execute(query)
        tasks = result.scalars().all()
        enriched_tasks = [self._enrich_task(t) for t in tasks]

        # Calculate counts
        today = datetime.now(IST).date()
        pending_count = sum(1 for t in enriched_tasks if t.status == TaskStatus.PENDING)
        in_progress_count = sum(1 for t in enriched_tasks if t.status == TaskStatus.IN_PROGRESS)
        overdue_count = sum(1 for t in enriched_tasks if t.is_overdue)
        completed_today_count = sum(
            1 for t in enriched_tasks
            if t.status == TaskStatus.DONE and t.end_time and (
                t.end_time.astimezone(IST).date() if t.end_time.tzinfo else t.end_time.date()
            ) == today
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

    def list_tasks(
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
                query = query.where(Task.due_datetime <= filters.due_before)
            if filters.due_after:
                query = query.where(Task.due_datetime >= filters.due_after)
            if filters.is_overdue:
                now_ist = datetime.now(IST)
                query = query.where(
                    and_(
                        Task.due_datetime < now_ist,  # Compare with IST datetime
                        Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                    )
                )

        # Count total
        count_result = self.db.execute(
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

        result = self.db.execute(query)
        tasks = result.scalars().all()
        enriched = [self._enrich_task(t) for t in tasks]
        return enriched, total

    # ==================== Task Update Methods ====================

    def update_task(
        self,
        task_id: int,
        project_id: int,
        user_id: int,
        request: TaskUpdate,
        is_admin: bool = False,
    ) -> TaskWithDetails:
        """Update a task."""
        task = self.get_task(task_id, project_id)

        # Check permissions: admin can update any task, user can update tasks they created or are assigned to
        if not is_admin:
            if task.created_by_id != user_id and task.assigned_to_user_id != user_id:
                raise ForbiddenError("You can only update tasks you created or are assigned to")

        update_data = request.model_dump(exclude_unset=True)

        if "category_id" in update_data and update_data["category_id"]:
            self.get_category(update_data["category_id"], project_id)

        # Handle due_datetime - treat naive datetime as IST
        if "due_datetime" in update_data and update_data["due_datetime"]:
            due_dt = update_data["due_datetime"]
            if isinstance(due_dt, datetime) and due_dt.tzinfo is None:
                update_data["due_datetime"] = due_dt.replace(tzinfo=IST)

        for field, value in update_data.items():
            setattr(task, field, value)

        self.db.flush()
        self.db.refresh(task)
        return self._enrich_task(task)

    def start_task(
        self,
        task_id: int,
        project_id: int,
        user_id: int,
    ) -> TaskWithDetails:
        """Start working on a task (sets start_time and status to in_progress)."""
        task = self.get_task(task_id, project_id)

        # Verify user is assigned to this task
        if task.assigned_to_user_id != user_id:
            raise ForbiddenError("You can only start tasks assigned to you")

        if task.status == TaskStatus.DONE:
            raise ValidationError("Cannot start a completed task")

        task.start_time = datetime.now(IST)  # Store with IST timezone
        task.status = TaskStatus.IN_PROGRESS
        self.db.flush()
        self.db.refresh(task)
        return self._enrich_task(task)

    def complete_task(
        self,
        task_id: int,
        project_id: int,
        user_id: int,
    ) -> TaskWithDetails:
        """Mark a task as complete."""
        task = self.get_task(task_id, project_id)

        # Verify user is assigned to this task
        if task.assigned_to_user_id != user_id:
            raise ForbiddenError("You can only complete tasks assigned to you")

        task.end_time = datetime.now(IST)  # Store with IST timezone
        task.status = TaskStatus.DONE
        self.db.flush()
        self.db.refresh(task)
        return self._enrich_task(task)

    def update_task_status(
        self,
        task_id: int,
        project_id: int,
        user_id: int,
        status: TaskStatus,
    ) -> TaskWithDetails:
        """Quick status update for a task."""
        task = self.get_task(task_id, project_id)

        # Verify user is assigned to this task
        if task.assigned_to_user_id != user_id:
            raise ForbiddenError("You can only update status of tasks assigned to you")

        task.status = status
        if status == TaskStatus.IN_PROGRESS and not task.start_time:
            task.start_time = datetime.now(IST)  # Store with IST timezone
        elif status == TaskStatus.DONE:
            task.end_time = datetime.now(IST)  # Store with IST timezone

        self.db.flush()
        self.db.refresh(task)
        return self._enrich_task(task)

    def delete_task(
        self,
        task_id: int,
        project_id: int,
        user_id: int,
        is_admin: bool = False,
    ) -> None:
        """Delete a task."""
        task = self.get_task(task_id, project_id)

        # Check permissions
        if not is_admin:
            if task.created_by_id != user_id:
                raise ForbiddenError("You can only delete tasks you created")

        self.db.delete(task)
        self.db.flush()

    # ==================== Helper Methods ====================

    def _verify_user_in_project(self, user_id: int, project_id: int) -> None:
        """Verify a user exists and has access to the project."""
        result = self.db.execute(
            select(UserRoleProject).where(
                UserRoleProject.user_id == user_id,
                UserRoleProject.project_id == project_id,
            )
        )
        if not result.scalar_one_or_none():
            raise ValidationError(f"User {user_id} is not a member of this project")

    def _verify_role_in_project(self, role_id: int, project_id: int) -> None:
        """Verify a role exists in the project."""
        result = self.db.execute(
            select(Role).where(
                Role.id == role_id,
                Role.project_id == project_id,
            )
        )
        if not result.scalar_one_or_none():
            raise ValidationError(f"Role {role_id} is not in this project")

    def _enrich_task(self, task: Task) -> TaskWithDetails:
        """Enrich task with related names and computed fields."""
        now = datetime.now(IST)
        
        # Helper to ensure datetime is timezone-aware (IST) for comparison
        def make_aware(dt: datetime | None) -> datetime | None:
            if dt is None:
                return None
            if dt.tzinfo is None:
                # Treat naive datetimes as IST (as they come from user input in IST)
                return dt.replace(tzinfo=IST)
            return dt
        
        due_dt = make_aware(task.due_datetime)
        start_dt = make_aware(task.start_time)
        
        is_overdue = (
            due_dt is not None
            and due_dt < now
            and task.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        )

        # Calculate elapsed time if task is in progress
        elapsed_seconds = None
        if start_dt and task.status == TaskStatus.IN_PROGRESS:
            elapsed = now - start_dt
            elapsed_seconds = int(elapsed.total_seconds())

        # Calculate time remaining until due_datetime (in seconds)
        time_remaining_seconds = None
        if due_dt and task.status not in [TaskStatus.DONE, TaskStatus.CANCELLED]:
            remaining = due_dt - now
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
            due_datetime=task.due_datetime,
            assigned_to_user_id=task.assigned_to_user_id,
            assigned_to_role_id=task.assigned_to_role_id,
            auto_rule_key=task.auto_rule_key,
            recurring_template_id=task.recurring_template_id,
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
            # Evo Points fields
            evo_points=task.evo_points,
            evo_reduction_type=task.evo_reduction_type,
            evo_extension_end=task.evo_extension_end,
            evo_fixed_reduction_points=task.evo_fixed_reduction_points,
            effective_evo_points=self._get_effective_evo_points(task),
            current_reward_points=self._calculate_current_reward_points(task, now) if task.status != TaskStatus.DONE else None,
            earned_evo_points=self._get_earned_evo_points(task) if task.status == TaskStatus.DONE else None,
        )

    def _get_earned_evo_points(self, task: Task) -> int | None:
        """Get the evo points earned for a completed task from transactions."""
        if task.assigned_to_user_id is None:
            return None
        
        # Look up the transaction for this task
        transaction = self.db.execute(
            select(EvoPointTransaction)
            .where(
                EvoPointTransaction.task_id == task.id,
                EvoPointTransaction.transaction_type == EvoTransactionType.TASK_REWARD,
            )
        ).scalar_one_or_none()
        
        if transaction:
            return transaction.amount
        return None

    def _get_effective_evo_points(self, task: Task) -> int:
        """Get effective evo points for a task (task value or project default)."""
        if task.evo_points is not None:
            return task.evo_points
        project = self.db.get(Project, task.project_id)
        if project:
            return project.default_evo_points
        return 0

    def _calculate_current_reward_points(self, task: Task, now: datetime) -> int | None:
        """Calculate current reward points if task were completed now."""
        # Only user-assigned tasks with evo points
        if task.assigned_to_user_id is None:
            return None
        
        effective_points = self._get_effective_evo_points(task)
        if effective_points <= 0:
            return 0
        
        # If no due datetime or no reduction, return full points
        if not task.due_datetime or task.evo_reduction_type == EvoReductionType.NONE:
            return effective_points
        
        due_dt = task.due_datetime
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=IST)
        
        # If not yet due, return full points
        if now <= due_dt:
            return effective_points
        
        # Apply reduction based on type
        if task.evo_reduction_type == EvoReductionType.GRADUAL:
            if not task.evo_extension_end:
                return 0
            ext_end = task.evo_extension_end
            if ext_end.tzinfo is None:
                ext_end = ext_end.replace(tzinfo=IST)
            if now >= ext_end:
                return 0
            total_decay = (ext_end - due_dt).total_seconds()
            elapsed = (now - due_dt).total_seconds()
            if total_decay <= 0:
                return 0
            remaining_ratio = 1 - (elapsed / total_decay)
            return max(0, int(effective_points * remaining_ratio))
        
        elif task.evo_reduction_type == EvoReductionType.FIXED:
            if not task.evo_extension_end:
                return task.evo_fixed_reduction_points or 0
            ext_end = task.evo_extension_end
            if ext_end.tzinfo is None:
                ext_end = ext_end.replace(tzinfo=IST)
            if now >= ext_end:
                return 0
            return task.evo_fixed_reduction_points or 0
        
        return effective_points

    def get_project_staff(self, project_id: int) -> list[dict]:
        """Get list of staff members in the project for admin selection."""
        result = self.db.execute(
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
