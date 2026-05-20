"""Service for managing project holidays."""
from datetime import date, datetime
from sqlalchemy import select, cast, Date as SQLDate
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holiday import ProjectHoliday, UserLeave
from app.models.task import Task, TaskStatus
from app.core.exceptions import DuplicateResourceError
from app.schemas.holiday import (
    ProjectHolidayCreate,
    ProjectHolidayResponse,
    UserLeaveCreate,
    UserLeaveResponse,
)


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
    
    async def create_holiday(
        self,
        project_id: int,
        holiday_data: ProjectHolidayCreate,
        created_by_id: int,
    ) -> ProjectHolidayResponse:
        """
        Create a new project holiday.
        
        If the date is today or in the past, cancels pending recurring tasks.
        
        Args:
            project_id: The project ID
            holiday_data: Holiday creation data
            created_by_id: ID of user creating the holiday
            
        Returns:
            Created holiday with tasks_cancelled count
            
        Raises:
            DuplicateResourceError: If holiday already exists for this date
        """
        # Check for duplicate
        existing = await self.db.execute(
            select(ProjectHoliday)
            .where(
                ProjectHoliday.project_id == project_id,
                ProjectHoliday.holiday_date == holiday_data.holiday_date,
            )
        )
        if existing.scalar_one_or_none():
            raise DuplicateResourceError("Holiday already exists for this date")
        
        # Create holiday
        holiday = ProjectHoliday(
            project_id=project_id,
            holiday_date=holiday_data.holiday_date,
            name=holiday_data.name,
            description=holiday_data.description,
            created_by_id=created_by_id,
        )
        self.db.add(holiday)
        await self.db.commit()
        await self.db.refresh(holiday)
        
        # Cancel tasks if past or today
        tasks_cancelled = 0
        if holiday_data.holiday_date <= date.today():
            tasks_cancelled = await self.cancel_recurring_tasks_for_date(
                project_id, holiday_data.holiday_date
            )
        
        return ProjectHolidayResponse(
            id=holiday.id,
            project_id=holiday.project_id,
            holiday_date=holiday.holiday_date,
            name=holiday.name,
            description=holiday.description,
            created_by_id=holiday.created_by_id,
            created_at=holiday.created_at.date(),
            updated_at=holiday.updated_at.date(),
            tasks_cancelled=tasks_cancelled,
        )
    
    async def list_holidays(
        self,
        project_id: int,
        year: int | None = None,
        month: int | None = None,
    ) -> list[ProjectHolidayResponse]:
        """
        List holidays for a project with optional filters.
        
        Args:
            project_id: The project ID
            year: Optional year filter
            month: Optional month filter (1-12)
            
        Returns:
            List of holidays
        """
        query = select(ProjectHoliday).where(
            ProjectHoliday.project_id == project_id
        )
        
        if year and month:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
            query = query.where(
                ProjectHoliday.holiday_date >= start_date,
                ProjectHoliday.holiday_date < end_date,
            )
        elif year:
            query = query.where(
                ProjectHoliday.holiday_date >= date(year, 1, 1),
                ProjectHoliday.holiday_date < date(year + 1, 1, 1),
            )
        
        query = query.order_by(ProjectHoliday.holiday_date)
        
        result = await self.db.execute(query)
        holidays = result.scalars().all()
        
        return [
            ProjectHolidayResponse(
                id=h.id,
                project_id=h.project_id,
                holiday_date=h.holiday_date,
                name=h.name,
                description=h.description,
                created_by_id=h.created_by_id,
                created_at=h.created_at.date(),
                updated_at=h.updated_at.date(),
                tasks_cancelled=None,
            )
            for h in holidays
        ]
    
    async def delete_holiday(self, project_id: int, holiday_id: int) -> bool:
        """
        Delete a holiday.
        
        Note: Does not restore cancelled tasks.
        
        Args:
            project_id: The project ID
            holiday_id: The holiday ID
            
        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(
            select(ProjectHoliday)
            .where(
                ProjectHoliday.id == holiday_id,
                ProjectHoliday.project_id == project_id,
            )
        )
        holiday = result.scalar_one_or_none()
        
        if not holiday:
            return False
        
        await self.db.delete(holiday)
        await self.db.commit()
        return True


class UserLeaveService:
    """Service for managing user leaves."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def is_user_on_leave(
        self, project_id: int, user_id: int, check_date: date
    ) -> bool:
        """
        Check if a user is on leave on a specific date.
        
        Args:
            project_id: The project ID
            user_id: The user ID
            check_date: The date to check
            
        Returns:
            True if user is on leave, False otherwise
        """
        result = await self.db.execute(
            select(UserLeave)
            .where(
                UserLeave.project_id == project_id,
                UserLeave.user_id == user_id,
                UserLeave.leave_date == check_date,
            )
        )
        leave = result.scalar_one_or_none()
        return leave is not None
    
    async def cancel_user_tasks_for_date(
        self, project_id: int, user_id: int, target_date: date
    ) -> int:
        """
        Cancel pending recurring tasks for a specific user on a date.
        
        Args:
            project_id: The project ID
            user_id: The user ID
            target_date: The date to cancel tasks for
            
        Returns:
            Number of tasks cancelled
        """
        # Find user's pending recurring tasks for target_date
        result = await self.db.execute(
            select(Task)
            .where(
                Task.project_id == project_id,
                Task.assigned_to_user_id == user_id,
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
    
    async def create_leave(
        self,
        project_id: int,
        leave_data: UserLeaveCreate,
        created_by_id: int,
    ) -> UserLeaveResponse:
        """
        Create a new user leave.
        
        If the date is today or in the past, cancels user's pending recurring tasks.
        
        Args:
            project_id: The project ID
            leave_data: Leave creation data
            created_by_id: ID of user creating the leave
            
        Returns:
            Created leave with tasks_cancelled count
            
        Raises:
            DuplicateResourceError: If leave already exists for this user/date
        """
        # Check for duplicate
        existing = await self.db.execute(
            select(UserLeave)
            .where(
                UserLeave.project_id == project_id,
                UserLeave.user_id == leave_data.user_id,
                UserLeave.leave_date == leave_data.leave_date,
            )
        )
        if existing.scalar_one_or_none():
            raise DuplicateResourceError("Leave already exists for this user and date")
        
        # Create leave
        leave = UserLeave(
            project_id=project_id,
            user_id=leave_data.user_id,
            leave_date=leave_data.leave_date,
            reason=leave_data.reason,
            notes=leave_data.notes,
            created_by_id=created_by_id,
        )
        self.db.add(leave)
        await self.db.commit()
        await self.db.refresh(leave)
        
        # Cancel user's tasks if past or today
        tasks_cancelled = 0
        if leave_data.leave_date <= date.today():
            tasks_cancelled = await self.cancel_user_tasks_for_date(
                project_id, leave_data.user_id, leave_data.leave_date
            )
        
        return UserLeaveResponse(
            id=leave.id,
            project_id=leave.project_id,
            user_id=leave.user_id,
            leave_date=leave.leave_date,
            reason=leave.reason,
            notes=leave.notes,
            created_by_id=leave.created_by_id,
            created_at=leave.created_at.date(),
            updated_at=leave.updated_at.date(),
            tasks_cancelled=tasks_cancelled,
        )
    
    async def list_leaves(
        self,
        project_id: int,
        user_id: int | None = None,
        year: int | None = None,
        month: int | None = None,
    ) -> list[UserLeaveResponse]:
        """
        List user leaves with optional filters.
        
        Args:
            project_id: The project ID
            user_id: Optional user filter
            year: Optional year filter
            month: Optional month filter (1-12)
            
        Returns:
            List of user leaves
        """
        query = select(UserLeave).where(
            UserLeave.project_id == project_id
        )
        
        if user_id:
            query = query.where(UserLeave.user_id == user_id)
        
        if year and month:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
            query = query.where(
                UserLeave.leave_date >= start_date,
                UserLeave.leave_date < end_date,
            )
        elif year:
            query = query.where(
                UserLeave.leave_date >= date(year, 1, 1),
                UserLeave.leave_date < date(year + 1, 1, 1),
            )
        
        query = query.order_by(UserLeave.leave_date)
        
        result = await self.db.execute(query)
        leaves = result.scalars().all()
        
        return [
            UserLeaveResponse(
                id=l.id,
                project_id=l.project_id,
                user_id=l.user_id,
                leave_date=l.leave_date,
                reason=l.reason,
                notes=l.notes,
                created_by_id=l.created_by_id,
                created_at=l.created_at.date(),
                updated_at=l.updated_at.date(),
                tasks_cancelled=None,
            )
            for l in leaves
        ]
    
    async def delete_leave(self, project_id: int, leave_id: int) -> bool:
        """
        Delete a user leave.
        
        Note: Does not restore cancelled tasks.
        
        Args:
            project_id: The project ID
            leave_id: The leave ID
            
        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(
            select(UserLeave)
            .where(
                UserLeave.id == leave_id,
                UserLeave.project_id == project_id,
            )
        )
        leave = result.scalar_one_or_none()
        
        if not leave:
            return False
        
        await self.db.delete(leave)
        await self.db.commit()
        return True
