"""Menu Screen models for dynamic sidebar management."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin


class MenuScreen(Base, IDMixin, TimestampMixin):
    """
    Menu screen definition.
    
    Represents a sidebar menu item that can be allocated to projects.
    Each menu screen maps to one or more permissions.
    """

    __tablename__ = "menu_screens"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    permission_mappings: Mapped[list["MenuScreenPermission"]] = relationship(
        "MenuScreenPermission",
        back_populates="menu_screen",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    project_allocations: Mapped[list["ProjectMenuScreen"]] = relationship(
        "ProjectMenuScreen",
        back_populates="menu_screen",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MenuScreen(id={self.id}, name={self.name}, route={self.route})>"


class MenuScreenPermission(Base, IDMixin):
    """
    Junction table linking menu screens to their required permissions.
    
    When a menu is allocated to a project, these are the permissions
    that become available for roles in that project.
    """

    __tablename__ = "menu_screen_permissions"

    menu_screen_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("menu_screens.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    menu_screen: Mapped["MenuScreen"] = relationship(
        "MenuScreen",
        back_populates="permission_mappings",
    )
    permission: Mapped["Permission"] = relationship("Permission")

    __table_args__ = (
        UniqueConstraint(
            "menu_screen_id",
            "permission_id",
            name="uq_menu_screen_permission",
        ),
    )

    def __repr__(self) -> str:
        return f"<MenuScreenPermission(menu_screen_id={self.menu_screen_id}, permission_id={self.permission_id})>"


class ProjectMenuScreen(Base, IDMixin):
    """
    Junction table for menus allocated to projects.
    
    Super admins control which menu screens are available for each project.
    When a menu is deallocated, related permissions are cascaded/removed
    from all roles in that project.
    """

    __tablename__ = "project_menu_screens"

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    menu_screen_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("menu_screens.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="menu_allocations")
    menu_screen: Mapped["MenuScreen"] = relationship(
        "MenuScreen",
        back_populates="project_allocations",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "menu_screen_id",
            name="uq_project_menu_screen",
        ),
    )

    def __repr__(self) -> str:
        return f"<ProjectMenuScreen(project_id={self.project_id}, menu_screen_id={self.menu_screen_id})>"
