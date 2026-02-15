"""Link orphaned permissions to menu screens.

Revision ID: link_orphan_perms
Revises: fix_missing_menu_alloc
Create Date: 2026-02-15

"""

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "link_orphan_perms"
down_revision = "fix_missing_menu_alloc"
branch_labels = None
depends_on = None


# Permissions that need to be linked to menu screens
PERMISSION_MENU_MAPPINGS = {
    # task_view permissions -> Tasks menu
    "task_view:create": "Tasks",
    "task_view:update": "Tasks",
    "task_view:delete": "Tasks",
    "task_view:set_default": "Tasks",
    # upload permissions -> relevant menus (Students can have uploads)
    "upload:view": "Students",
    "upload:create": "Students",
    # evo_points -> Tasks menu (gamification for tasks)
    "evo_points:manage": "Tasks",
}


def upgrade() -> None:
    """Link orphaned permissions to appropriate menu screens."""
    conn = op.get_bind()
    
    print("🔗 Linking orphaned permissions to menu screens...")
    
    # Get menu IDs by name
    menu_result = conn.execute(text("SELECT id, name FROM menu_screens"))
    menu_map = {row[1]: row[0] for row in menu_result}
    
    # Get permission IDs by key
    perm_result = conn.execute(text("SELECT id, permission_key FROM permissions"))
    perm_map = {row[1]: row[0] for row in perm_result}
    
    linked_count = 0
    for perm_key, menu_name in PERMISSION_MENU_MAPPINGS.items():
        perm_id = perm_map.get(perm_key)
        menu_id = menu_map.get(menu_name)
        
        if perm_id and menu_id:
            conn.execute(text("""
                INSERT INTO menu_screen_permissions (menu_screen_id, permission_id)
                VALUES (:menu_id, :perm_id)
                ON CONFLICT DO NOTHING
            """), {"menu_id": menu_id, "perm_id": perm_id})
            print(f"  Linked {perm_key} -> {menu_name}")
            linked_count += 1
        else:
            if not perm_id:
                print(f"  Warning: Permission '{perm_key}' not found")
            if not menu_id:
                print(f"  Warning: Menu '{menu_name}' not found")
    
    print(f"✅ Linked {linked_count} permissions to menus!")


def downgrade() -> None:
    """Remove the permission-menu links."""
    conn = op.get_bind()
    
    perm_keys = list(PERMISSION_MENU_MAPPINGS.keys())
    
    conn.execute(text("""
        DELETE FROM menu_screen_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE permission_key = ANY(:keys)
        )
    """), {"keys": perm_keys})
