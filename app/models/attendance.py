"""Attendance record model."""

import enum
from datetime import date

from sqlalchemy import BigInteger, Date, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, ProjectScopedMixin, TimestampMixin


class AttendanceStatus(str, enum.Enum):
    """Attendance status enumeration."""

    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"

    @classmethod
    def from_string(cls, value: str) -> "AttendanceStatus":
        """Convert string to AttendanceStatus, handling common variations."""
        value = value.strip().upper()
        mapping = {
            "P": cls.PRESENT,
            "PRESENT": cls.PRESENT,
            "A": cls.ABSENT,
            "ABSENT": cls.ABSENT,
            "L": cls.LATE,
            "LATE": cls.LATE,
            "E": cls.EXCUSED,
            "EXCUSED": cls.EXCUSED,
        }
        if value in mapping:
            return mapping[value]
        raise ValueError(f"Invalid attendance status: {value}")


class AttendanceRecord(Base, IDMixin, TimestampMixin, ProjectScopedMixin):
    """Attendance record model."""

    __tablename__ = "attendance_records"

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
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus),
        nullable=False,
    )
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
        back_populates="attendance_records",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "student_id", "attendance_date",
            name="uq_attendance_student_date",
        ),
    )

    @property
    def student_name(self) -> str:
        """Get student name from relationship."""
        return self.student.student_name if self.student else ""

    @property
    def class_name(self) -> str:
        """Get class name from student relationship."""
        return self.student.class_name if self.student else ""

    @property
    def section(self) -> str | None:
        """Get section from student relationship."""
        return self.student.section if self.student else None

    @property
    def class_section(self) -> str:
        """Get combined class-section."""
        if self.student:
            section = self.student.section or ""
            return f"{self.student.class_name}-{section}" if section else self.student.class_name
        return ""

    def __repr__(self) -> str:
        return f"<AttendanceRecord(student_id={self.student_id}, date={self.attendance_date})>"
