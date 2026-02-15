"""Add fee permissions and update menu mapping.

Revision ID: add_fee_permissions
Revises: remove_menu_icon_name
Create Date: 2026-02-15

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'add_fee_permissions'
down_revision: Union[str, None] = 'remove_menu_icon_name'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fee permissions to add
FEE_PERMISSIONS = [
    ("fee:view", "View fee records"),
    ("fee:create", "Create fee records"),
    ("fee:update", "Update fee records"),
    ("fee:delete", "Delete fee records"),
    ("fee:upload", "Upload fees via Excel"),
]


def upgrade() -> None:
    """Add fee permissions and link them to Fee Management menu."""
    conn = op.get_bind()

    print("💰 Adding fee permissions...")

    # 1. Insert fee permissions
    for perm_key, description in FEE_PERMISSIONS:
        conn.execute(text("""
            INSERT INTO permissions (permission_key, description)
            VALUES (:key, :desc)
            ON CONFLICT (permission_key) DO NOTHING
        """), {"key": perm_key, "desc": description})

    # 2. Get Fee Management menu screen ID
    menu_result = conn.execute(text(
        "SELECT id FROM menu_screens WHERE name = 'Fee Management'"
    ))
    menu_row = menu_result.fetchone()

    if menu_row:
        menu_id = menu_row[0]
        print(f"   Found Fee Management menu with ID: {menu_id}")

        # 3. Get fee permission IDs and link them to the menu
        for perm_key, _ in FEE_PERMISSIONS:
            perm_result = conn.execute(text(
                "SELECT id FROM permissions WHERE permission_key = :key"
            ), {"key": perm_key})
            perm_row = perm_result.fetchone()

            if perm_row:
                perm_id = perm_row[0]
                conn.execute(text("""
                    INSERT INTO menu_screen_permissions (menu_screen_id, permission_id)
                    VALUES (:menu_id, :perm_id)
                    ON CONFLICT (menu_screen_id, permission_id) DO NOTHING
                """), {"menu_id": menu_id, "perm_id": perm_id})
                print(f"   Linked permission '{perm_key}' to Fee Management menu")
    else:
        print("   Fee Management menu not found - skipping permission links")

    print("✅ Fee permissions added successfully")


def downgrade() -> None:
    """Remove fee permissions."""
    conn = op.get_bind()

    # Remove menu screen permission links
    conn.execute(text("""
        DELETE FROM menu_screen_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE permission_key LIKE 'fee:%'
        )
    """))

    # Remove permissions
    for perm_key, _ in FEE_PERMISSIONS:
        conn.execute(text(
            "DELETE FROM permissions WHERE permission_key = :key"
        ), {"key": perm_key})
