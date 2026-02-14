"""Task schemas with timer support."""

from datetime import datetime

from pydantic import Field, model_validator

from app.models.task import EvoReductionType, TaskStatus
from app.schemas.common import BaseSchema


# Task Category schemas
class TaskCategoryCreate(BaseSchema):
    """Task category creation schema."""

    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = None
    color: str | None = Field(None, max_length=20)  # Hex color like #FF5733


class TaskCategoryUpdate(BaseSchema):
    """Task category update schema."""

    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = None
    color: str | None = Field(None, max_length=20)


class TaskCategoryResponse(BaseSchema):
    """Task category response schema."""

    id: int
    project_id: int
    name: str
    description: str | None
    color: str | None
    created_at: datetime
    updated_at: datetime


# Task schemas
class TaskCreate(BaseSchema):
    """Task creation schema."""

    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    category_id: int | None = None
    due_datetime: datetime | None = None
    assigned_to_user_id: int | None = None  # Optional - for assigning to another user
    assigned_to_role_id: int | None = None  # Optional - for assigning to a role
    
    # Evo Points - Gamification fields
    evo_points: int | None = Field(None, ge=0, description="Points awarded on completion (null = use project default)")
    evo_reduction_type: EvoReductionType | None = Field(None, description="How points reduce after due time")
    evo_extension_end: datetime | None = Field(None, description="GRADUAL: when points hit zero; FIXED: grace period end")
    evo_fixed_reduction_points: int | None = Field(None, ge=0, description="FIXED: the reduced point value after due time")

    @model_validator(mode='after')
    def validate_evo_fields(self):
        """Validate evo point reduction fields."""
        if self.evo_reduction_type == EvoReductionType.GRADUAL:
            if self.evo_extension_end is None:
                raise ValueError("evo_extension_end is required when evo_reduction_type is GRADUAL")
        elif self.evo_reduction_type == EvoReductionType.FIXED:
            # Only evo_fixed_reduction_points is required for FIXED; extension_end is optional
            if self.evo_fixed_reduction_points is None:
                raise ValueError("evo_fixed_reduction_points is required when evo_reduction_type is FIXED")
        return self


class TaskUpdate(BaseSchema):
    """Task update schema."""

    title: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    category_id: int | None = None
    status: TaskStatus | None = None
    due_datetime: datetime | None = None
    assigned_to_user_id: int | None = None
    assigned_to_role_id: int | None = None
    
    # Evo Points - Gamification fields
    evo_points: int | None = Field(None, ge=0)
    evo_reduction_type: EvoReductionType | None = None
    evo_extension_end: datetime | None = None
    evo_fixed_reduction_points: int | None = Field(None, ge=0)

    @model_validator(mode='after')
    def validate_evo_fields(self):
        """Validate evo point reduction fields."""
        if self.evo_reduction_type == EvoReductionType.GRADUAL:
            if self.evo_extension_end is None:
                raise ValueError("evo_extension_end is required when evo_reduction_type is GRADUAL")
        elif self.evo_reduction_type == EvoReductionType.FIXED:
            # Only evo_fixed_reduction_points is required for FIXED; extension_end is optional
            if self.evo_fixed_reduction_points is None:
                raise ValueError("evo_fixed_reduction_points is required when evo_reduction_type is FIXED")
        return self


class TaskStartStop(BaseSchema):
    """Schema for starting/stopping task timer."""

    action: str = Field(..., pattern="^(start|stop)$")


class TaskResponse(BaseSchema):
    """Task response schema."""

    id: int
    project_id: int
    category_id: int | None
    title: str
    description: str | None
    status: TaskStatus
    start_time: datetime | None
    end_time: datetime | None
    due_datetime: datetime | None
    assigned_to_user_id: int | None
    assigned_to_role_id: int | None
    auto_rule_key: str | None
    recurring_template_id: int | None = None
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    
    # Evo Points fields
    evo_points: int | None = None
    evo_reduction_type: EvoReductionType = EvoReductionType.NONE
    evo_extension_end: datetime | None = None
    evo_fixed_reduction_points: int | None = None


class TaskWithDetails(TaskResponse):
    """Task response with related details and computed fields."""

    category_name: str | None = None
    assigned_user_name: str | None = None
    assigned_role_name: str | None = None
    created_by_name: str | None = None
    is_overdue: bool = False
    time_remaining_seconds: int | None = None  # Seconds until due_datetime (negative if overdue)
    elapsed_seconds: int | None = None  # Time elapsed since start_time
    
    # Evo Points computed fields
    effective_evo_points: int = 0  # Actual points considering project default
    current_reward_points: int | None = None  # Points user would get if completed now (with reductions)
    earned_evo_points: int | None = None  # Points actually earned on completion (for done tasks)


class TaskStatusUpdate(BaseSchema):
    """Quick status update schema."""

    status: TaskStatus


class TaskFilter(BaseSchema):
    """Task filtering options."""

    status: TaskStatus | None = None
    category_id: int | None = None
    assigned_to_user_id: int | None = None
    assigned_to_role_id: int | None = None
    is_overdue: bool | None = None
    due_before: datetime | None = None
    due_after: datetime | None = None


class TasksGroupedByCategory(BaseSchema):
    """Tasks grouped by category for display."""

    category_id: int | None
    category_name: str | None
    tasks: list[TaskWithDetails]


class StaffTasksSummary(BaseSchema):
    """Summary of tasks for a staff member."""

    user_id: int
    user_name: str
    pending_count: int
    in_progress_count: int
    overdue_count: int
    completed_today_count: int
    tasks: list[TaskWithDetails]


class TaskCompletionResponse(BaseSchema):
    """Response for task completion with evo points info."""

    task: TaskWithDetails
    points_earned: int | None = None
    new_balance: int | None = None
    was_late: bool = False
    original_points: int | None = None
    reduction_applied: int | None = None
