"""add_holidays_menu_screen_and_permissions

Revision ID: 27a5a6729455
Revises: 67c099db1ca1
Create Date: 2026-05-21 07:19:51.872901

This migration adds:
- Holiday and leave management permissions
- "Holidays & Leaves" menu screen
- Links menu screen to permissions
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision: str = '27a5a6729455'
down_revision: Union[str, None] = '67c099db1ca1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Holiday permissions
HOLIDAY_PERMISSIONS = [
    ("holiday:view", "View holidays and leaves"),
    ("holiday:create", "Create holidays and leaves"),
    ("holiday:delete", "Delete holidays and leaves"),
]


def upgrade() -> None:
    """Add holidays menu screen and permissions."""
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    print("📅 Adding holidays menu screen and permissions...")

    # 1. Add holiday permissions
    print("   Creating holiday permissions...")
    for perm_key, perm_desc in HOLIDAY_PERMISSIONS:
        conn.execute(text("""
            INSERT INTO permissions (permission_key, description)
            VALUES (:key, :desc)
            ON CONFLICT (permission_key) DO NOTHING
        """), {"key": perm_key, "desc": perm_desc})

    # 2. Add "Holidays & Leaves" menu screen
    print("   Creating Holidays & Leaves menu screen...")
    conn.execute(text("""
        INSERT INTO menu_screens (name, route, display_order, description, created_at, updated_at)
        VALUES (:name, :route, :display_order, :description, :now, :now)
        ON CONFLICT (name) DO NOTHING
    """), {
        "name": "Holidays & Leaves",
        "route": "/holidays",
        "display_order": 75,  # Between Fee Management (70) and Notifications (80)
        "description": "Manage project holidays and user leaves",
        "now": now,
    })

    # 3. Get menu screen ID
    menu_result = conn.execute(text("""
        SELECT id FROM menu_screens WHERE name = 'Holidays & Leaves'
    """))
    menu_row = menu_result.fetchone()
    if not menu_row:
        print("   ⚠️  Failed to find Holidays & Leaves menu screen")
        return
    
    menu_id = menu_row[0]

    # 4. Get permission IDs
    perm_result = conn.execute(text("""
        SELECT id, permission_key FROM permissions 
        WHERE permission_key LIKE 'holiday:%'
    """))
    permission_map = {row[1]: row[0] for row in perm_result}

    # 5. Link menu screen to permissions
    print("   Linking menu screen to permissions...")
    for perm_key in ["holiday:view", "holiday:create", "holiday:delete"]:
        perm_id = permission_map.get(perm_key)
        if perm_id:
            conn.execute(text("""
                INSERT INTO menu_screen_permissions (menu_screen_id, permission_id)
                VALUES (:menu_id, :perm_id)
                ON CONFLICT DO NOTHING
            """), {"menu_id": menu_id, "perm_id": perm_id})

    # 6. Allocate menu to all existing projects
    print("   Allocating Holidays & Leaves menu to all existing projects...")
    conn.execute(text("""
        INSERT INTO project_menu_screens (project_id, menu_screen_id, created_at)
        SELECT p.id, :menu_id, :now
        FROM projects p
        WHERE NOT EXISTS (
            SELECT 1 FROM project_menu_screens pms 
            WHERE pms.project_id = p.id AND pms.menu_screen_id = :menu_id
        )
    """), {"menu_id": menu_id, "now": now})

    print("✅ Holidays menu screen setup complete!")
    print("   Menu has been automatically allocated to all existing projects.")


def downgrade() -> None:
    """Remove holidays menu screen and permissions."""
    conn = op.get_bind()

    # Remove menu screen (cascade will handle permissions mapping)
    conn.execute(text("""
        DELETE FROM menu_screens WHERE name = 'Holidays & Leaves'
    """))

    # Remove permissions
    conn.execute(text("""
        DELETE FROM permissions WHERE permission_key LIKE 'holiday:%'
    """))
