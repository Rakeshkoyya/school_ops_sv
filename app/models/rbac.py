"""RBAC (Role-Based Access Control) models."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin


class Role(Base, IDMixin, TimestampMixin):
    """Project-scoped role model."""

    __tablename__ = "roles"

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_project_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_role_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="roles")
    # passive_deletes=True tells SQLAlchemy to let the database handle CASCADE deletes
    permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        lazy="selectin",
        passive_deletes=True,
    )
    user_assignments: Mapped[list["UserRoleProject"]] = relationship(
        "UserRoleProject",
        back_populates="role",
        lazy="selectin",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_role_project_name"),
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name}, project_id={self.project_id})>"


class Permission(Base, IDMixin):
    """Global permission model."""

    __tablename__ = "permissions"

    permission_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="permission",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Permission(key={self.permission_key})>"


class RolePermission(Base, IDMixin):
    """Junction table linking roles to permissions within a project."""

    __tablename__ = "role_permissions"

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="permissions")
    permission: Mapped["Permission"] = relationship("Permission", back_populates="role_permissions")

    __table_args__ = (
        UniqueConstraint(
            "project_id", "role_id", "permission_id",
            name="uq_role_permission_project",
        ),
    )

    def __repr__(self) -> str:
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id})>"


class UserRoleProject(Base, IDMixin):
    """Junction table assigning users to roles within projects."""

    __tablename__ = "user_role_projects"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="role_assignments")
    role: Mapped["Role"] = relationship("Role", back_populates="user_assignments")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "role_id", "project_id",
            name="uq_user_role_project",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserRoleProject(user_id={self.user_id}, role_id={self.role_id})>"


# Import here to avoid circular imports
from app.models.project import Project
from app.models.user import User
