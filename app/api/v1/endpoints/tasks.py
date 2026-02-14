"""Task management endpoints with timer support."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import ProjectContext, require_permission
from app.models.audit import AuditAction
from app.models.task import TaskStatus
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.recurring_task import (
    RecurringTaskTemplateCreate,
    RecurringTaskTemplateUpdate,
    RecurringTaskTemplateWithDetails,
)
from app.schemas.task import (
    StaffTasksSummary,
    TaskCategoryCreate,
    TaskCategoryResponse,
    TaskCategoryUpdate,
    TaskCompletionResponse,
    TaskCreate,
    TaskFilter,
    TasksGroupedByCategory,
    TaskStatusUpdate,
    TaskUpdate,
    TaskWithDetails,
)
from app.services.audit import AuditService
from app.services.evo_point import EvoPointService
from app.services.notification import notify_task_assigned
from app.services.recurring_task import RecurringTaskService
from app.services.task import TaskService

router = APIRouter()


# ==================== Task Category Endpoints ====================

@router.get("/categories", response_model=list[TaskCategoryResponse])
def list_categories(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """List all task categories for the project."""
    service = TaskService(db)
    return service.list_categories(context.project_id)


@router.post("/categories", response_model=TaskCategoryResponse)
def create_category(
    request: TaskCategoryCreate,
    context: Annotated[ProjectContext, Depends(require_permission("task_category:create"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new task category. Requires task_category:create permission."""
    service = TaskService(db)
    return service.create_category(context.project_id, request)


@router.patch("/categories/{category_id}", response_model=TaskCategoryResponse)
def update_category(
    category_id: int,
    request: TaskCategoryUpdate,
    context: Annotated[ProjectContext, Depends(require_permission("task_category:update"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update a task category. Requires task_category:update permission."""
    service = TaskService(db)
    return service.update_category(category_id, context.project_id, request)


@router.delete("/categories/{category_id}", response_model=MessageResponse)
def delete_category(
    category_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("task_category:delete"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a task category. Requires task_category:delete permission."""
    service = TaskService(db)
    service.delete_category(category_id, context.project_id)
    return MessageResponse(message="Category deleted successfully")


# ==================== Task Endpoints ====================

@router.post("", response_model=TaskWithDetails)
def create_task(
    request: TaskCreate,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Create a new task.
    Any authenticated user can create tasks. If assigned_to_user_id is not specified,
    the task is assigned to the creator.
    """
    service = TaskService(db)
    task = service.create_task(context.project_id, context.user_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.TASK_CREATED,
        resource_type="task",
        resource_id=str(task.id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Task '{task.title}' created",
        ip_address=http_request.client.host if http_request.client else None,
    )

    # Notify assigned user if different from creator
    if task.assigned_to_user_id and task.assigned_to_user_id != context.user_id:
        notify_task_assigned(
            db,
            context.project_id,
            task.assigned_to_user_id,
            task.title,
            context.user.name,
        )

    return task


@router.get("/my-tasks", response_model=list[TaskWithDetails])
def get_my_tasks(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """Get all active tasks assigned to the current user."""
    service = TaskService(db)
    return service.get_my_tasks(context.project_id, context.user_id)


@router.get("/my-tasks/grouped", response_model=list[TasksGroupedByCategory])
def get_my_tasks_grouped(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """Get current user's tasks grouped by category for display."""
    service = TaskService(db)
    return service.get_my_tasks_grouped_by_category(context.project_id, context.user_id)


# ==================== Admin Endpoints ====================

@router.get("/admin/staff", response_model=list[dict])
def get_project_staff(
    context: Annotated[ProjectContext, Depends(require_permission("task:assign"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get list of staff members in the project for task assignment.
    Requires task:assign permission (School Admin only).
    """
    service = TaskService(db)
    return service.get_project_staff(context.project_id)


@router.get("/admin/staff/{user_id}/tasks", response_model=StaffTasksSummary)
def get_staff_tasks(
    user_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("task:assign"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get tasks for a specific staff member.
    Requires task:assign permission (School Admin only).
    """
    service = TaskService(db)
    return service.get_staff_tasks(context.project_id, user_id)


# ==================== Task List & Detail Endpoints ====================

@router.get("", response_model=PaginatedResponse[TaskWithDetails])
def list_tasks(
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
    status: TaskStatus | None = None,
    category_id: int | None = None,
    assigned_to_user_id: int | None = None,
    assigned_to_role_id: int | None = None,
    is_overdue: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List tasks with optional filtering and pagination."""
    service = TaskService(db)
    filters = TaskFilter(
        status=status,
        category_id=category_id,
        assigned_to_user_id=assigned_to_user_id,
        assigned_to_role_id=assigned_to_role_id,
        is_overdue=is_overdue,
    )
    tasks, total = service.list_tasks(
        context.project_id,
        filters=filters,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=tasks,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{task_id}", response_model=TaskWithDetails)
def get_task(
    task_id: int,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """Get task details by ID."""
    service = TaskService(db)
    task = service.get_task(task_id, context.project_id)
    return service._enrich_task(task)


@router.patch("/{task_id}", response_model=TaskWithDetails)
def update_task(
    task_id: int,
    request: TaskUpdate,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Update a task.
    Users can update tasks they created or are assigned to.
    Admins can update any task.
    """
    # Check if user is admin
    is_admin = context.is_project_admin

    service = TaskService(db)
    task = service.update_task(
        task_id, context.project_id, context.user_id, request, is_admin
    )

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.TASK_UPDATED,
        resource_type="task",
        resource_id=str(task_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Task '{task.title}' updated",
        metadata={"changes": request.model_dump(exclude_unset=True)},
        ip_address=http_request.client.host if http_request.client else None,
    )

    return task


@router.post("/{task_id}/start", response_model=TaskWithDetails)
def start_task(
    task_id: int,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """Start working on a task (sets start_time and status to in_progress)."""
    service = TaskService(db)
    return service.start_task(task_id, context.project_id, context.user_id)


@router.post("/{task_id}/complete", response_model=TaskCompletionResponse)
def complete_task(
    task_id: int,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """Mark a task as complete and award evo points if applicable."""
    task_service = TaskService(db)
    evo_service = EvoPointService(db)
    
    # Get task before completion to check evo points
    task_before = task_service.get_task(task_id, context.project_id)
    
    # Complete the task
    task = task_service.complete_task(task_id, context.project_id, context.user_id)
    
    # Award evo points if applicable
    evo_result = evo_service.award_task_points(
        task=task_before,
        user_id=context.user_id,
        project_id=context.project_id,
    )

    # Audit log with evo points metadata
    audit = AuditService(db)
    audit.log(
        action=AuditAction.TASK_COMPLETED,
        resource_type="task",
        resource_id=str(task_id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Task '{task.title}' completed",
        metadata={
            "evo_points_earned": evo_result.points_earned,
            "was_late": evo_result.was_late,
        } if evo_result.points_earned is not None else None,
        ip_address=http_request.client.host if http_request.client else None,
    )

    return TaskCompletionResponse(
        task=task,
        points_earned=evo_result.points_earned,
        new_balance=evo_result.new_balance,
        was_late=evo_result.was_late,
        original_points=evo_result.original_points,
        reduction_applied=evo_result.reduction_applied,
    )


@router.patch("/{task_id}/status", response_model=TaskWithDetails)
def update_task_status(
    task_id: int,
    request: TaskStatusUpdate,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """Quick status update for a task."""
    service = TaskService(db)
    task = service.update_task_status(
        task_id, context.project_id, context.user_id, request.status
    )

    # Audit log for completion
    if request.status == TaskStatus.DONE:
        audit = AuditService(db)
        audit.log(
            action=AuditAction.TASK_COMPLETED,
            resource_type="task",
            resource_id=str(task_id),
            project_id=context.project_id,
            user_id=context.user_id,
            description=f"Task '{task.title}' completed",
            ip_address=http_request.client.host if http_request.client else None,
        )

    return task


@router.delete("/{task_id}", response_model=MessageResponse)
def delete_task(
    task_id: int,
    context: ProjectContext,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Delete a task.
    Users can only delete tasks they created.
    Admins can delete any task.
    """
    is_admin = context.is_project_admin

    service = TaskService(db)
    service.delete_task(task_id, context.project_id, context.user_id, is_admin)
    return MessageResponse(message="Task deleted successfully")


# ==================== Recurring Task Template Endpoints ====================

@router.get("/recurring-templates", response_model=list[RecurringTaskTemplateWithDetails])
def list_recurring_templates(
    context: Annotated[ProjectContext, Depends(require_permission("task:create_recurring"))],
    db: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(False, description="Include inactive templates"),
):
    """List all recurring task templates. Requires task:create_recurring permission."""
    service = RecurringTaskService(db)
    return service.list_templates(context.project_id, include_inactive)


@router.post("/recurring-templates", response_model=RecurringTaskTemplateWithDetails)
def create_recurring_template(
    request: RecurringTaskTemplateCreate,
    context: Annotated[ProjectContext, Depends(require_permission("task:create_recurring"))],
    db: Annotated[Session, Depends(get_db)],
    http_request: Request,
):
    """
    Create a recurring task template.
    Tasks will be auto-generated based on the recurrence schedule.
    Requires task:create_recurring permission.
    """
    service = RecurringTaskService(db)
    template = service.create_template(context.project_id, context.user_id, request)

    # Audit log
    audit = AuditService(db)
    audit.log(
        action=AuditAction.TASK_CREATED,
        resource_type="recurring_task_template",
        resource_id=str(template.id),
        project_id=context.project_id,
        user_id=context.user_id,
        description=f"Recurring task template '{template.title}' created ({template.recurrence_type.value})",
        ip_address=http_request.client.host if http_request.client else None,
    )

    return template


@router.get("/recurring-templates/{template_id}", response_model=RecurringTaskTemplateWithDetails)
def get_recurring_template(
    template_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("task:create_recurring"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Get a recurring task template by ID."""
    service = RecurringTaskService(db)
    template = service.get_template(template_id, context.project_id)
    return service._enrich_template(template)


@router.patch("/recurring-templates/{template_id}", response_model=RecurringTaskTemplateWithDetails)
def update_recurring_template(
    template_id: int,
    request: RecurringTaskTemplateUpdate,
    context: Annotated[ProjectContext, Depends(require_permission("task:create_recurring"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update a recurring task template."""
    service = RecurringTaskService(db)
    return service.update_template(template_id, context.project_id, request)


@router.post("/recurring-templates/{template_id}/toggle", response_model=RecurringTaskTemplateWithDetails)
def toggle_recurring_template(
    template_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("task:create_recurring"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Toggle a recurring task template's active status."""
    service = RecurringTaskService(db)
    return service.toggle_template(template_id, context.project_id)


@router.delete("/recurring-templates/{template_id}", response_model=MessageResponse)
def delete_recurring_template(
    template_id: int,
    context: Annotated[ProjectContext, Depends(require_permission("task:create_recurring"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a recurring task template."""
    service = RecurringTaskService(db)
    service.delete_template(template_id, context.project_id)
    return MessageResponse(message="Recurring task template deleted successfully")


@router.post("/recurring-templates/trigger-generation", response_model=MessageResponse)
def trigger_task_generation(
    context: Annotated[ProjectContext, Depends(require_permission("task:create_recurring"))],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Manually trigger recurring task generation for today.
    Useful for testing or catching up missed generations.
    """
    from app.core.scheduler import trigger_recurring_task_generation
    
    trigger_recurring_task_generation()
    return MessageResponse(message="Recurring task generation triggered")
