"""Exam service for CRUD operations."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.exam import ExamRecord
from app.schemas.exam import (
    ExamFilter,
    ExamRecordCreate,
    ExamRecordResponse,
    ExamRecordUpdate,
    ExamSummary,
)


class ExamService:
    """Exam record management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_record(
        self,
        project_id: UUID,
        request: ExamRecordCreate,
    ) -> ExamRecordResponse:
        """Create a single exam record."""
        # Validate marks
        if request.marks_obtained > request.max_marks:
            raise ValidationError(
                f"marks_obtained ({request.marks_obtained}) exceeds max_marks ({request.max_marks})"
            )

        record = ExamRecord(
            project_id=project_id,
            student_id=request.student_id,
            student_name=request.student_name,
            exam_name=request.exam_name,
            subject=request.subject,
            exam_date=request.exam_date,
            max_marks=request.max_marks,
            marks_obtained=request.marks_obtained,
            grade=request.grade,
            remarks=request.remarks,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)

        return ExamRecordResponse.model_validate(record)

    async def get_record(
        self,
        record_id: UUID,
        project_id: UUID,
    ) -> ExamRecord:
        """Get exam record by ID."""
        result = await self.db.execute(
            select(ExamRecord).where(
                ExamRecord.id == record_id,
                ExamRecord.project_id == project_id,
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            raise NotFoundError("Exam record", str(record_id))
        return record

    async def list_records(
        self,
        project_id: UUID,
        filters: ExamFilter | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ExamRecordResponse], int]:
        """List exam records with filtering."""
        query = select(ExamRecord).where(ExamRecord.project_id == project_id)

        if filters:
            if filters.student_id:
                query = query.where(ExamRecord.student_id == filters.student_id)
            if filters.exam_name:
                query = query.where(ExamRecord.exam_name == filters.exam_name)
            if filters.subject:
                query = query.where(ExamRecord.subject == filters.subject)
            if filters.date_from:
                query = query.where(ExamRecord.exam_date >= filters.date_from)
            if filters.date_to:
                query = query.where(ExamRecord.exam_date <= filters.date_to)

        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Apply pagination and ordering
        query = (
            query
            .order_by(ExamRecord.exam_date.desc(), ExamRecord.student_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        records = result.scalars().all()

        return [ExamRecordResponse.model_validate(r) for r in records], total

    async def update_record(
        self,
        record_id: UUID,
        project_id: UUID,
        request: ExamRecordUpdate,
    ) -> ExamRecordResponse:
        """Update an exam record."""
        record = await self.get_record(record_id, project_id)

        # Validate marks if updating
        if request.marks_obtained is not None:
            if request.marks_obtained > record.max_marks:
                raise ValidationError(
                    f"marks_obtained ({request.marks_obtained}) exceeds max_marks ({record.max_marks})"
                )

        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(record, field, value)

        await self.db.flush()
        await self.db.refresh(record)

        return ExamRecordResponse.model_validate(record)

    async def delete_record(
        self,
        record_id: UUID,
        project_id: UUID,
    ) -> None:
        """Delete an exam record."""
        record = await self.get_record(record_id, project_id)
        await self.db.delete(record)
        await self.db.flush()

    async def get_exam_summary(
        self,
        project_id: UUID,
        exam_name: str,
        subject: str,
    ) -> ExamSummary:
        """Get summary statistics for an exam."""
        # Assuming 40% is pass mark
        pass_percentage = Decimal("0.4")

        query = select(
            func.count().label("total"),
            func.avg(ExamRecord.marks_obtained).label("avg"),
            func.max(ExamRecord.marks_obtained).label("highest"),
            func.min(ExamRecord.marks_obtained).label("lowest"),
        ).where(
            ExamRecord.project_id == project_id,
            ExamRecord.exam_name == exam_name,
            ExamRecord.subject == subject,
        )

        result = await self.db.execute(query)
        row = result.one()

        # Count pass/fail
        pass_count_result = await self.db.execute(
            select(func.count()).where(
                ExamRecord.project_id == project_id,
                ExamRecord.exam_name == exam_name,
                ExamRecord.subject == subject,
                ExamRecord.marks_obtained >= ExamRecord.max_marks * pass_percentage,
            )
        )
        pass_count = pass_count_result.scalar() or 0

        total = row.total or 0
        fail_count = total - pass_count

        return ExamSummary(
            exam_name=exam_name,
            subject=subject,
            total_students=total,
            average_marks=Decimal(str(row.avg or 0)).quantize(Decimal("0.01")),
            highest_marks=row.highest or Decimal("0"),
            lowest_marks=row.lowest or Decimal("0"),
            pass_count=pass_count,
            fail_count=fail_count,
        )
