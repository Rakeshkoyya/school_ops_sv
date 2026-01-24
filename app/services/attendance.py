"""Attendance service for CRUD operations."""

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.attendance import AttendanceRecord, AttendanceStatus
from app.schemas.attendance import (
    AttendanceFilter,
    AttendanceRecordCreate,
    AttendanceRecordResponse,
    AttendanceRecordUpdate,
    AttendanceSummary,
)


class AttendanceService:
    """Attendance management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_record(
        self,
        project_id: UUID,
        request: AttendanceRecordCreate,
    ) -> AttendanceRecordResponse:
        """Create a single attendance record."""
        record = AttendanceRecord(
            project_id=project_id,
            student_id=request.student_id,
            student_name=request.student_name,
            attendance_date=request.attendance_date,
            status=request.status,
            remarks=request.remarks,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)

        return AttendanceRecordResponse.model_validate(record)

    async def get_record(
        self,
        record_id: UUID,
        project_id: UUID,
    ) -> AttendanceRecord:
        """Get attendance record by ID."""
        result = await self.db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.id == record_id,
                AttendanceRecord.project_id == project_id,
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            raise NotFoundError("Attendance record", str(record_id))
        return record

    async def list_records(
        self,
        project_id: UUID,
        filters: AttendanceFilter | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AttendanceRecordResponse], int]:
        """List attendance records with filtering."""
        query = select(AttendanceRecord).where(
            AttendanceRecord.project_id == project_id
        )

        if filters:
            if filters.student_id:
                query = query.where(AttendanceRecord.student_id == filters.student_id)
            if filters.status:
                query = query.where(AttendanceRecord.status == filters.status)
            if filters.date_from:
                query = query.where(AttendanceRecord.attendance_date >= filters.date_from)
            if filters.date_to:
                query = query.where(AttendanceRecord.attendance_date <= filters.date_to)

        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Apply pagination and ordering
        query = (
            query
            .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.student_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        records = result.scalars().all()

        return [AttendanceRecordResponse.model_validate(r) for r in records], total

    async def update_record(
        self,
        record_id: UUID,
        project_id: UUID,
        request: AttendanceRecordUpdate,
    ) -> AttendanceRecordResponse:
        """Update an attendance record."""
        record = await self.get_record(record_id, project_id)

        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(record, field, value)

        await self.db.flush()
        await self.db.refresh(record)

        return AttendanceRecordResponse.model_validate(record)

    async def delete_record(
        self,
        record_id: UUID,
        project_id: UUID,
    ) -> None:
        """Delete an attendance record."""
        record = await self.get_record(record_id, project_id)
        await self.db.delete(record)
        await self.db.flush()

    async def get_summary(
        self,
        project_id: UUID,
        date_from: date,
        date_to: date,
        student_id: str | None = None,
    ) -> AttendanceSummary:
        """Get attendance summary for a date range."""
        query = select(
            func.count().label("total"),
            func.sum(func.cast(AttendanceRecord.status == AttendanceStatus.PRESENT, Integer)).label("present"),
            func.sum(func.cast(AttendanceRecord.status == AttendanceStatus.ABSENT, Integer)).label("absent"),
            func.sum(func.cast(AttendanceRecord.status == AttendanceStatus.LATE, Integer)).label("late"),
            func.sum(func.cast(AttendanceRecord.status == AttendanceStatus.EXCUSED, Integer)).label("excused"),
        ).where(
            AttendanceRecord.project_id == project_id,
            AttendanceRecord.attendance_date >= date_from,
            AttendanceRecord.attendance_date <= date_to,
        )

        if student_id:
            query = query.where(AttendanceRecord.student_id == student_id)

        result = await self.db.execute(query)
        row = result.one()

        return AttendanceSummary(
            total_records=row.total or 0,
            present_count=row.present or 0,
            absent_count=row.absent or 0,
            late_count=row.late or 0,
            excused_count=row.excused or 0,
            date_from=date_from,
            date_to=date_to,
        )


# Import for type casting
from sqlalchemy import Integer
