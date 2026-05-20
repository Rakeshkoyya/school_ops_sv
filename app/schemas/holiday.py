"""Schemas for holiday and user leave management."""
from datetime import date
from pydantic import BaseModel, Field


# Project Holiday Schemas
class ProjectHolidayBase(BaseModel):
    """Base schema for project holidays."""
    holiday_date: date = Field(..., description="The holiday date")
    name: str | None = Field(None, max_length=255, description="Holiday name (e.g., Christmas)")
    description: str | None = Field(None, description="Additional details about the holiday")


class ProjectHolidayCreate(ProjectHolidayBase):
    """Schema for creating a project holiday."""
    pass


class ProjectHolidayUpdate(BaseModel):
    """Schema for updating a project holiday."""
    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None)


class ProjectHolidayResponse(ProjectHolidayBase):
    """Schema for project holiday response."""
    id: int
    project_id: int
    created_by_id: int
    created_at: date
    updated_at: date
    tasks_cancelled: int | None = Field(None, description="Number of tasks cancelled (only for past/today dates)")

    class Config:
        from_attributes = True


# User Leave Schemas
class UserLeaveBase(BaseModel):
    """Base schema for user leaves."""
    user_id: int = Field(..., description="User ID who is on leave")
    leave_date: date = Field(..., description="The leave date")
    reason: str | None = Field(None, max_length=255, description="Reason for leave")
    notes: str | None = Field(None, description="Additional notes about the leave")


class UserLeaveCreate(UserLeaveBase):
    """Schema for creating a user leave."""
    pass


class UserLeaveUpdate(BaseModel):
    """Schema for updating a user leave."""
    reason: str | None = Field(None, max_length=255)
    notes: str | None = Field(None)


class UserLeaveResponse(UserLeaveBase):
    """Schema for user leave response."""
    id: int
    project_id: int
    created_by_id: int
    created_at: date
    updated_at: date
    tasks_cancelled: int | None = Field(None, description="Number of tasks cancelled (only for past/today dates)")

    class Config:
        from_attributes = True
