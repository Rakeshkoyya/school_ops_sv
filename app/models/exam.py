"""Exam record model."""

from datetime import date
from decimal import Decimal

from sqlalchemy import DECIMAL, BigInteger, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, ProjectScopedMixin, TimestampMixin


class ExamRecord(Base, IDMixin, TimestampMixin, ProjectScopedMixin):
    """Exam record model with strict validation."""

    __tablename__ = "exam_records"

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exam_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(100), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    max_marks: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    marks_obtained: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Upload tracking
    upload_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("uploads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="exam_records",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "student_id", "exam_name", "subject",
            name="uq_exam_student_subject",
        ),
    )

    def __repr__(self) -> str:
        return f"<ExamRecord(student_id={self.student_id}, exam={self.exam_name})>"
