"""Task View Style schemas."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


# Available column fields for task views
AVAILABLE_COLUMNS = [
    "checkbox",
    "title", 
    "description",
    "status",
    "category",
    "created_at",
    "created_by",
    "assignee",
    "due_datetime",
    "evo_points",
    "timer",
    "actions",
]


class ColumnConfig(BaseSchema):
    """Configuration for a single column in a view."""
    
    field: str = Field(..., description="Column field identifier")
    visible: bool = Field(True, description="Whether the column is visible")
    order: int = Field(..., ge=0, description="Display order (0-based)")
    width: str | None = Field(None, description="Column width (e.g., '150px', '10%', 'auto')")
    
    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        if v not in AVAILABLE_COLUMNS:
            raise ValueError(f"Invalid column field: {v}. Must be one of {AVAILABLE_COLUMNS}")
        return v


class TaskViewStyleCreate(BaseSchema):
    """Task view style creation schema."""
    
    name: str = Field(..., min_length=2, max_length=100, description="View name")
    description: str | None = Field(None, max_length=500, description="Optional description")
    column_config: list[ColumnConfig] = Field(..., min_length=1, description="Column configuration")
    
    @field_validator("column_config")
    @classmethod
    def validate_column_config(cls, v: list[ColumnConfig]) -> list[ColumnConfig]:
        # Check for duplicate fields
        fields = [col.field for col in v]
        if len(fields) != len(set(fields)):
            raise ValueError("Duplicate column fields are not allowed")
        
        # Check for duplicate orders
        orders = [col.order for col in v]
        if len(orders) != len(set(orders)):
            raise ValueError("Duplicate column orders are not allowed")
        
        return v


class TaskViewStyleUpdate(BaseSchema):
    """Task view style update schema."""
    
    name: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = Field(None, max_length=500)
    column_config: list[ColumnConfig] | None = Field(None, min_length=1)
    
    @field_validator("column_config")
    @classmethod
    def validate_column_config(cls, v: list[ColumnConfig] | None) -> list[ColumnConfig] | None:
        if v is None:
            return v
        
        # Check for duplicate fields
        fields = [col.field for col in v]
        if len(fields) != len(set(fields)):
            raise ValueError("Duplicate column fields are not allowed")
        
        # Check for duplicate orders
        orders = [col.order for col in v]
        if len(orders) != len(set(orders)):
            raise ValueError("Duplicate column orders are not allowed")
        
        return v


class TaskViewStyleResponse(BaseSchema):
    """Task view style response schema."""
    
    id: int
    project_id: int
    name: str
    description: str | None
    column_config: list[ColumnConfig]
    is_system_default: bool
    created_by_id: int | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskViewStyleListResponse(BaseSchema):
    """List of task view styles with metadata."""
    
    views: list[TaskViewStyleResponse]
    project_default_id: int | None = Field(None, description="ID of the project's default view")


class UserViewPreferenceUpdate(BaseSchema):
    """User view preference update schema."""
    
    view_style_id: int = Field(..., description="ID of the view style to set as preference")


class UserViewPreferenceResponse(BaseSchema):
    """User view preference response schema."""
    
    user_id: int
    project_id: int
    view_style_id: int
    view_style: TaskViewStyleResponse


class EffectiveViewResponse(BaseSchema):
    """Response containing the effective view for the user."""
    
    view: TaskViewStyleResponse
    source: Literal["user_preference", "project_default", "system_default"] = Field(
        ..., description="How this view was determined"
    )


class ColumnMetadata(BaseSchema):
    """Metadata about an available column."""
    
    field: str
    label: str
    default_visible: bool
    default_order: int
    default_width: str | None = None


class AvailableColumnsResponse(BaseSchema):
    """Response containing all available columns for configuration."""
    
    columns: list[ColumnMetadata]
