"""Service for managing project holidays."""
from datetime import date, datetime
from sqlalchemy import select, cast, Date as SQLDate
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holiday import ProjectHoliday
from app.models.task import Task, TaskStatus
from app.core.exceptions import DuplicateResourceError


class HolidayService:
    """Service for managing project holidays."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def is_holiday(self, project_id: int, check_date: date) -> bool:
        """
        Check if a specific date is marked as a holiday for the project.
        
        Args:
            project_id: The project ID
            check_date: The date to check
            
        Returns:
            True if the date is a holiday, False otherwise
        """
        result = await self.db.execute(
            select(ProjectHoliday)
            .where(
                ProjectHoliday.project_id == project_id,
                ProjectHoliday.holiday_date == check_date,
            )
        )
        holiday = result.scalar_one_or_none()
        return holiday is not None
    
    async def cancel_recurring_tasks_for_date(
        self, project_id: int, target_date: date
    ) -> int:
        """
        Cancel all pending recurring tasks for a specific date.
        
        Args:
            project_id: The project ID
            target_date: The date to cancel tasks for
            
        Returns:
            Number of tasks cancelled
        """
        # Find pending recurring tasks created on target_date
        result = await self.db.execute(
            select(Task)
            .where(
                Task.project_id == project_id,
                Task.status == TaskStatus.PENDING,
                Task.recurring_template_id.isnot(None),
                cast(Task.created_at, SQLDate) == target_date,
            )
        )
        tasks = result.scalars().all()
        
        # Cancel them
        count = 0
        for task in tasks:
            task.status = TaskStatus.CANCELLED
            count += 1
        
        if count > 0:
            await self.db.commit()
        
        return count
