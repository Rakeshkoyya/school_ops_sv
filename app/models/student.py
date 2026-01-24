"""Student model."""

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, ProjectScopedMixin, TimestampMixin


class Student(Base, IDMixin, TimestampMixin, ProjectScopedMixin):
    """Student model for managing student records."""

    __tablename__ = "students"

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    class_name: Mapped[str] = mapped_column(String(50), nullable=False)  # 'class' is reserved keyword
    section: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_phone_no: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        "AttendanceRecord",
        back_populates="student",
        lazy="selectin",
    )
    exam_records: Mapped[list["ExamRecord"]] = relationship(
        "ExamRecord",
        back_populates="student",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Student(id={self.id}, name={self.student_name}, class={self.class_name})>"
