"""Recurring task template service."""

from datetime import date, datetime, time, timezone, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.sql import cast
from sqlalchemy import Date as SQLDate

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.task import (
    EvoReductionType,
    RecurrenceType,
    RecurringTaskTemplate,
    Task,
    TaskCategory,
    TaskStatus,
)
from app.models.user import User
from app.schemas.recurring_task import (
    RecurringTaskTemplateCreate,
    RecurringTaskTemplateUpdate,
    RecurringTaskTemplateWithDetails,
)


WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class RecurringTaskService:
    """Service for managing recurring task templates and generation."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Template CRUD ====================

    def create_template(
        self,
        project_id: int,
        user_id: int,
        request: RecurringTaskTemplateCreate,
    ) -> RecurringTaskTemplateWithDetails:
        """Create a recurring task template."""
        # Validate category if provided
        if request.category_id:
            self._verify_category(request.category_id, project_id)
        
        # Validate assigned user if provided
        if request.assigned_to_user_id:
            self._verify_user_in_project(request.assigned_to_user_id, project_id)
        
        # Validate recurrence type requirements
        if request.recurrence_type == RecurrenceType.ONCE and not request.scheduled_date:
            raise ValidationError("scheduled_date is required for 'once' recurrence type")

        template = RecurringTaskTemplate(
            project_id=project_id,
            title=request.title,
            description=request.description,
            category_id=request.category_id,
            recurrence_type=request.recurrence_type.value,  # Use .value for DB enum
            days_of_week=request.days_of_week,
            scheduled_date=request.scheduled_date,
            created_on_time=request.created_on_time,
            start_time=request.start_time,
            due_time=request.due_time,
            assigned_to_user_id=request.assigned_to_user_id or user_id,
            is_active=True,
            created_by_id=user_id,
            # Evo Points settings
            evo_points=request.evo_points,
            evo_reduction_type=request.evo_reduction_type,
            evo_extension_time=request.evo_extension_time,
            evo_fixed_reduction_points=request.evo_fixed_reduction_points,
        )
        self.db.add(template)
        self.db.flush()
        
        # Handle immediate task creation based on recurrence type and flag
        today = date.today()
        should_create_today = False
        
        if request.recurrence_type == RecurrenceType.ONCE:
            # For "once" - create task on the scheduled date if it's today
            if request.scheduled_date == today:
                should_create_today = True
        elif request.create_task_today:
            # For daily/weekly - create today only if explicitly requested
            if request.recurrence_type == RecurrenceType.DAILY:
                should_create_today = True
            elif request.recurrence_type == RecurrenceType.WEEKLY:
                # Only create if today is one of the selected days
                weekday = today.weekday()
                if request.days_of_week and str(weekday) in request.days_of_week.split(","):
                    should_create_today = True
        
        if should_create_today:
            self._generate_task_from_template(template, today)
            template.last_generated_date = today
            self.db.flush()
        
        self.db.refresh(template)
        return self._enrich_template(template)

    def get_template(
        self,
        template_id: int,
        project_id: int,
    ) -> RecurringTaskTemplate:
        """Get a recurring task template by ID."""
        result = self.db.execute(
            select(RecurringTaskTemplate)
            .options(
                selectinload(RecurringTaskTemplate.category),
                selectinload(RecurringTaskTemplate.assigned_user),
                selectinload(RecurringTaskTemplate.created_by),
            )
            .where(
                RecurringTaskTemplate.id == template_id,
                RecurringTaskTemplate.project_id == project_id,
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError("RecurringTaskTemplate", str(template_id))
        return template

    def list_templates(
        self,
        project_id: int,
        include_inactive: bool = False,
        created_by_user_id: int | None = None,
        assigned_to_user_id: int | None = None,
        is_active: bool | None = None,
    ) -> list[RecurringTaskTemplateWithDetails]:
        """List all recurring task templates for a project with optional filters."""
        query = (
            select(RecurringTaskTemplate)
            .options(
                selectinload(RecurringTaskTemplate.category),
                selectinload(RecurringTaskTemplate.assigned_user),
                selectinload(RecurringTaskTemplate.created_by),
            )
            .where(RecurringTaskTemplate.project_id == project_id)
        )
        
        # Filter by active status - is_active param takes precedence over include_inactive
        if is_active is not None:
            query = query.where(RecurringTaskTemplate.is_active == is_active)
        elif not include_inactive:
            query = query.where(RecurringTaskTemplate.is_active == True)
        
        # Filter by creator
        if created_by_user_id is not None:
            query = query.where(RecurringTaskTemplate.created_by_id == created_by_user_id)
        
        # Filter by assigned user
        if assigned_to_user_id is not None:
            query = query.where(RecurringTaskTemplate.assigned_to_user_id == assigned_to_user_id)
        
        query = query.order_by(RecurringTaskTemplate.created_at.desc())
        
        result = self.db.execute(query)
        templates = result.scalars().all()
        return [self._enrich_template(t) for t in templates]

    def update_template(
        self,
        template_id: int,
        project_id: int,
        request: RecurringTaskTemplateUpdate,
    ) -> RecurringTaskTemplateWithDetails:
        """Update a recurring task template."""
        template = self.get_template(template_id, project_id)
        
        update_data = request.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(template, field, value)
        
        self.db.flush()
        self.db.refresh(template)
        return self._enrich_template(template)

    def delete_template(
        self,
        template_id: int,
        project_id: int,
    ) -> None:
        """Delete a recurring task template."""
        template = self.get_template(template_id, project_id)
        self.db.delete(template)
        self.db.flush()

    def toggle_template(
        self,
        template_id: int,
        project_id: int,
    ) -> RecurringTaskTemplateWithDetails:
        """Toggle a template's active status."""
        template = self.get_template(template_id, project_id)
        template.is_active = not template.is_active
        self.db.flush()
        self.db.refresh(template)
        return self._enrich_template(template)

    # ==================== Task Generation ====================

    def generate_tasks_for_date(self, target_date: date | None = None) -> int:
        """
        Generate all recurring tasks for a given date.
        Called by scheduler at midnight.
        """
        target_date = target_date or date.today()
        generated_count = 0

        # Get all active templates that haven't been generated for this date
        query = (
            select(RecurringTaskTemplate)
            .options(
                selectinload(RecurringTaskTemplate.category),
                selectinload(RecurringTaskTemplate.assigned_user),
            )
            .where(
                RecurringTaskTemplate.is_active == True,
                or_(
                    RecurringTaskTemplate.last_generated_date.is_(None),
                    RecurringTaskTemplate.last_generated_date < target_date,
                ),
            )
        )

        result = self.db.execute(query)
        templates = result.scalars().all()

        for template in templates:
            if self._should_generate_for_date(template, target_date):
                task = self._generate_task_from_template(template, target_date)
                if task:  # Only count if task was actually created (not duplicate)
                    template.last_generated_date = target_date
                    generated_count += 1
                    
                    # Deactivate "once" templates after generation
                    if template.recurrence_type == RecurrenceType.ONCE.value:
                        template.is_active = False

        self.db.commit()
        return generated_count

    def _should_generate_for_date(
        self,
        template: RecurringTaskTemplate,
        target_date: date,
    ) -> bool:
        """Check if a task should be generated based on recurrence rules."""
        weekday = target_date.weekday()  # 0 = Monday, 6 = Sunday

        if template.recurrence_type == RecurrenceType.ONCE.value:
            return template.scheduled_date == target_date

        elif template.recurrence_type == RecurrenceType.DAILY.value:
            if template.days_of_week:
                return str(weekday) in template.days_of_week.split(",")
            return True  # Every day if no days specified

        elif template.recurrence_type == RecurrenceType.WEEKLY.value:
            if template.days_of_week:
                return str(weekday) in template.days_of_week.split(",")
            return weekday == 0  # Default to Monday if no days specified

        return False

    def _generate_task_from_template(
        self,
        template: RecurringTaskTemplate,
        target_date: date,
    ) -> Task | None:
        """
        Create a task from a template for the given date.
        Returns None if a task already exists for this template on the target date.
        """
        # Check if task already exists for this template on this date (prevents duplicates)
        existing_task = self.db.execute(
            select(Task).where(
                Task.recurring_template_id == template.id,
                cast(Task.created_at, SQLDate) == target_date,
            )
        ).scalar_one_or_none()
        
        if existing_task:
            return None  # Task already exists, skip creation
        
        # Combine date with time fields and add IST timezone
        created_at = None
        if template.created_on_time:
            created_at = datetime.combine(
                target_date, template.created_on_time
            ).replace(tzinfo=IST)
        
        start_time = None
        if template.start_time:
            start_time = datetime.combine(
                target_date, template.start_time
            ).replace(tzinfo=IST)
        
        due_datetime = None
        if template.due_time:
            due_datetime = datetime.combine(
                target_date, template.due_time
            ).replace(tzinfo=IST)
        
        # Evo extension end (combine time with date)
        evo_extension_end = None
        if template.evo_extension_time:
            evo_extension_end = datetime.combine(
                target_date, template.evo_extension_time
            ).replace(tzinfo=IST)

        task = Task(
            project_id=template.project_id,
            title=template.title,
            description=template.description,
            category_id=template.category_id,
            status=TaskStatus.PENDING,
            due_datetime=due_datetime,
            start_time=start_time,
            assigned_to_user_id=template.assigned_to_user_id,
            assigned_to_role_id=None,
            recurring_template_id=template.id,
            created_by_id=template.created_by_id,
            # Evo Points settings from template
            evo_points=template.evo_points,
            evo_reduction_type=template.evo_reduction_type,
            evo_extension_end=evo_extension_end,
            evo_fixed_reduction_points=template.evo_fixed_reduction_points,
        )
        
        # Override created_at if specified
        if created_at:
            task.created_at = created_at
        
        self.db.add(task)
        self.db.flush()
        return task

    # ==================== Helpers ====================

    def _verify_category(self, category_id: int, project_id: int) -> None:
        """Verify category exists in project."""
        result = self.db.execute(
            select(TaskCategory).where(
                TaskCategory.id == category_id,
                TaskCategory.project_id == project_id,
            )
        )
        if not result.scalar_one_or_none():
            raise NotFoundError("TaskCategory", str(category_id))

    def _verify_user_in_project(self, user_id: int, project_id: int) -> None:
        """Verify user is part of the project."""
        from app.models.rbac import UserRoleProject
        
        result = self.db.execute(
            select(UserRoleProject).where(
                UserRoleProject.user_id == user_id,
                UserRoleProject.project_id == project_id,
            )
        )
        if not result.scalar_one_or_none():
            raise ValidationError(f"User {user_id} is not in this project")

    def _enrich_template(
        self,
        template: RecurringTaskTemplate,
    ) -> RecurringTaskTemplateWithDetails:
        """Enrich template with related names and human-readable description."""
        recurrence_description = self._build_recurrence_description(template)
        
        return RecurringTaskTemplateWithDetails(
            id=template.id,
            project_id=template.project_id,
            title=template.title,
            description=template.description,
            category_id=template.category_id,
            recurrence_type=template.recurrence_type,
            days_of_week=template.days_of_week,
            scheduled_date=template.scheduled_date,
            created_on_time=template.created_on_time,
            start_time=template.start_time,
            due_time=template.due_time,
            assigned_to_user_id=template.assigned_to_user_id,
            is_active=template.is_active,
            last_generated_date=template.last_generated_date,
            created_by_id=template.created_by_id,
            created_at=template.created_at,
            updated_at=template.updated_at,
            category_name=template.category.name if template.category else None,
            assigned_user_name=template.assigned_user.name if template.assigned_user else None,
            created_by_name=template.created_by.name if template.created_by else None,
            recurrence_description=recurrence_description,
        )

    def _build_recurrence_description(
        self,
        template: RecurringTaskTemplate,
    ) -> str:
        """Build human-readable recurrence description."""
        if template.recurrence_type == RecurrenceType.ONCE.value:
            return f"Once on {template.scheduled_date.strftime('%b %d, %Y')}" if template.scheduled_date else "Once"
        
        if template.recurrence_type == RecurrenceType.DAILY.value:
            if template.days_of_week:
                days = [WEEKDAY_NAMES[int(d)] for d in template.days_of_week.split(",")]
                return f"Every {', '.join(days)}"
            return "Every day"
        
        if template.recurrence_type == RecurrenceType.WEEKLY.value:
            if template.days_of_week:
                days = [WEEKDAY_NAMES[int(d)] for d in template.days_of_week.split(",")]
                return f"Weekly on {', '.join(days)}"
            return "Weekly on Monday"
        
        return str(template.recurrence_type)
