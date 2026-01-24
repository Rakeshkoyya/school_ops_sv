"""Upload tracking models."""

import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, ProjectScopedMixin, TimestampMixin


class UploadStatus(str, enum.Enum):
    """Upload status enumeration."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    PROCESSING = "processing"


class UploadType(str, enum.Enum):
    """Upload type enumeration."""

    ATTENDANCE = "attendance"
    EXAM = "exam"


class Upload(Base, IDMixin, TimestampMixin, ProjectScopedMixin):
    """Upload tracking model."""

    __tablename__ = "uploads"

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    upload_type: Mapped[UploadType] = mapped_column(
        Enum(UploadType),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus),
        default=UploadStatus.PROCESSING,
        nullable=False,
    )
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    successful_rows: Mapped[int] = mapped_column(Integer, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # User who uploaded
    uploaded_by_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Processing timestamps
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    errors: Mapped[list["UploadError"]] = relationship(
        "UploadError",
        back_populates="upload",
        lazy="selectin",
    )
    uploaded_by: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Upload(id={self.id}, type={self.upload_type}, status={self.status})>"


class UploadError(Base, IDMixin):
    """Row-level upload error model."""

    __tablename__ = "upload_errors"

    upload_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    column_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    upload: Mapped["Upload"] = relationship("Upload", back_populates="errors")

    def __repr__(self) -> str:
        return f"<UploadError(upload_id={self.upload_id}, row={self.row_number})>"


# Import to avoid circular imports
from app.models.user import User
