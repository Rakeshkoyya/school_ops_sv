"""Recurring task template schemas."""

from datetime import date, datetime, time

from pydantic import Field, field_validator

from app.models.task import RecurrenceType
from app.schemas.common import BaseSchema


class RecurringTaskTemplateCreate(BaseSchema):
    """Schema for creating a recurring task template."""

    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    category_id: int | None = None
    
    # Recurrence settings
    recurrence_type: RecurrenceType
    days_of_week: str | None = Field(
        None, 
        pattern=r"^[0-6](,[0-6])*$",
        description="Comma-separated weekday numbers (0=Mon, 6=Sun). E.g., '0,1,2,3,4' for Mon-Fri"
    )
    scheduled_date: date | None = None  # For "once" recurrence type
    
    # Time settings
    created_on_time: time | None = None  # When task becomes visible
    start_time: time | None = None  # When work should start
    due_time: time | None = None  # Deadline time
    
    # Assignment
    assigned_to_user_id: int | None = None
    
    # Control whether to create a task for today as well
    create_task_today: bool = False

    @field_validator('scheduled_date')
    @classmethod
    def validate_scheduled_date(cls, v, info):
        """Scheduled date is required for 'once' recurrence type."""
        if info.data.get('recurrence_type') == RecurrenceType.ONCE and v is None:
            raise ValueError("scheduled_date is required for 'once' recurrence type")
        return v


class RecurringTaskTemplateUpdate(BaseSchema):
    """Schema for updating a recurring task template."""

    title: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    category_id: int | None = None
    
    # Recurrence settings
    recurrence_type: RecurrenceType | None = None
    days_of_week: str | None = Field(
        None,
        pattern=r"^[0-6](,[0-6])*$"
    )
    scheduled_date: date | None = None
    
    # Time settings
    created_on_time: time | None = None
    start_time: time | None = None
    due_time: time | None = None
    
    # Assignment
    assigned_to_user_id: int | None = None
    
    # Control
    is_active: bool | None = None


class RecurringTaskTemplateResponse(BaseSchema):
    """Response schema for recurring task template."""

    id: int
    project_id: int
    title: str
    description: str | None
    category_id: int | None
    recurrence_type: RecurrenceType
    days_of_week: str | None
    scheduled_date: date | None
    created_on_time: time | None
    start_time: time | None
    due_time: time | None
    assigned_to_user_id: int | None
    is_active: bool
    last_generated_date: date | None
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class RecurringTaskTemplateWithDetails(RecurringTaskTemplateResponse):
    """Response with related details."""

    category_name: str | None = None
    assigned_user_name: str | None = None
    created_by_name: str | None = None
    # Human-readable recurrence description
    recurrence_description: str | None = None
