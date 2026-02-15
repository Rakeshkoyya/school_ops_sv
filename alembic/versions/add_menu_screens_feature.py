"""add_menu_screens_and_allocations

Revision ID: add_menu_screens_feature
Revises: add_task_view_styles
Create Date: 2026-02-15 10:00:00.000000

This migration creates the menu screen management system:
- menu_screens: Defines available sidebar menu items
- menu_screen_permissions: Links menus to their related permissions
- project_menu_screens: Allocates menus to specific projects

When menus are removed from a project, the associated permissions
are automatically cleaned up via application logic (tightly coupled).
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision: str = 'add_menu_screens_feature'
down_revision: Union[str, None] = 'add_evo_to_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Menu screens with their routes
MENU_SCREENS = [
    # (name, route, display_order, description)
    ("Dashboard", "/dashboard", 0, "Main dashboard overview"),
    ("Users", "/users", 10, "User management within a project"),
    ("Students", "/students", 20, "Student records management"),
    ("Roles", "/roles", 30, "Role and permission management"),
    ("Tasks", "/tasks", 40, "Task management and tracking"),
    ("Attendance", "/attendance", 50, "Attendance tracking"),
    ("Exams", "/exams", 60, "Examination records"),
    ("Fee Management", "/fees", 70, "Fee and payment management"),
    ("Notifications", "/notifications", 80, "Notification center"),
    ("Audit Logs", "/audit", 90, "System audit logs"),
]

# Map each menu to its related permissions
# Dashboard has no permissions (always visible if allocated)
MENU_PERMISSION_MAPPING = {
    "Dashboard": [],  # Always visible
    "Users": ["user:view", "user:invite", "user:remove"],
    "Students": ["student:view", "student:create", "student:update", "student:delete", "student:upload"],
    "Roles": ["role:view", "role:create", "role:update", "role:delete", "role:assign"],
    "Tasks": [
        "task:view", "task:create", "task:update", "task:delete", "task:assign", "task:create_recurring",
        "task_category:view", "task_category:create", "task_category:update", "task_category:delete",
    ],
    "Attendance": ["attendance:view", "attendance:create", "attendance:update", "attendance:delete", "attendance:upload"],
    "Exams": ["exam:view", "exam:create", "exam:update", "exam:delete", "exam:upload"],
    "Fee Management": ["fee:view", "fee:create", "fee:update", "fee:delete", "fee:upload"],
    "Notifications": ["notification:view", "notification:create"],
    "Audit Logs": ["audit:view"],
}


def upgrade() -> None:
    """Create menu screen tables and seed default data."""
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    print("🖥️  Creating menu screen tables...")

    # 1. Create menu_screens table
    op.create_table(
        'menu_screens',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('route', sa.String(length=255), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_menu_screen_name'),
    )

    # 2. Create menu_screen_permissions table
    op.create_table(
        'menu_screen_permissions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('menu_screen_id', sa.BigInteger(), nullable=False),
        sa.Column('permission_id', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['menu_screen_id'], ['menu_screens.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('menu_screen_id', 'permission_id', name='uq_menu_screen_permission'),
    )
    op.create_index('ix_menu_screen_permissions_menu_screen_id', 'menu_screen_permissions', ['menu_screen_id'])
    op.create_index('ix_menu_screen_permissions_permission_id', 'menu_screen_permissions', ['permission_id'])

    # 3. Create project_menu_screens table
    op.create_table(
        'project_menu_screens',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('menu_screen_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['menu_screen_id'], ['menu_screens.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'menu_screen_id', name='uq_project_menu_screen'),
    )
    op.create_index('ix_project_menu_screens_project_id', 'project_menu_screens', ['project_id'])
    op.create_index('ix_project_menu_screens_menu_screen_id', 'project_menu_screens', ['menu_screen_id'])

    # 4. Seed menu screens
    print("   Seeding menu screens...")
    for name, route, display_order, description in MENU_SCREENS:
        conn.execute(text("""
            INSERT INTO menu_screens (name, route, display_order, description, created_at, updated_at)
            VALUES (:name, :route, :display_order, :description, :now, :now)
        """), {
            "name": name,
            "route": route,
            "display_order": display_order,
            "description": description,
            "now": now,
        })

    # 5. Get menu screen IDs
    menu_result = conn.execute(text("SELECT id, name FROM menu_screens"))
    menu_map = {row[1]: row[0] for row in menu_result}

    # 6. Get permission IDs
    perm_result = conn.execute(text("SELECT id, permission_key FROM permissions"))
    permission_map = {row[1]: row[0] for row in perm_result}

    # 7. Link menu screens to permissions
    print("   Linking menu screens to permissions...")
    for menu_name, perm_keys in MENU_PERMISSION_MAPPING.items():
        menu_id = menu_map.get(menu_name)
        if not menu_id:
            continue
        for perm_key in perm_keys:
            perm_id = permission_map.get(perm_key)
            if perm_id:
                conn.execute(text("""
                    INSERT INTO menu_screen_permissions (menu_screen_id, permission_id)
                    VALUES (:menu_id, :perm_id)
                    ON CONFLICT DO NOTHING
                """), {"menu_id": menu_id, "perm_id": perm_id})

    # 8. Allocate all menus to all existing projects (maintain current behavior)
    print("   Allocating all menus to existing projects...")
    conn.execute(text("""
        INSERT INTO project_menu_screens (project_id, menu_screen_id, created_at)
        SELECT p.id, m.id, :now
        FROM projects p
        CROSS JOIN menu_screens m
        ON CONFLICT DO NOTHING
    """), {"now": now})

    print("✅ Menu screens setup complete!")


def downgrade() -> None:
    """Remove menu screen tables."""
    op.drop_index('ix_project_menu_screens_menu_screen_id', table_name='project_menu_screens')
    op.drop_index('ix_project_menu_screens_project_id', table_name='project_menu_screens')
    op.drop_table('project_menu_screens')
    
    op.drop_index('ix_menu_screen_permissions_permission_id', table_name='menu_screen_permissions')
    op.drop_index('ix_menu_screen_permissions_menu_screen_id', table_name='menu_screen_permissions')
    op.drop_table('menu_screen_permissions')
    
    op.drop_table('menu_screens')
