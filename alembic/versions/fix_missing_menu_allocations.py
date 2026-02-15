"""Fix missing menu allocations for projects.

Revision ID: fix_missing_menu_alloc
Revises: add_fee_permissions
Create Date: 2026-02-15

"""

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "fix_missing_menu_alloc"
down_revision = "add_fee_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allocate all menus to any projects that don't have them."""
    conn = op.get_bind()
    
    print("🔧 Fixing missing menu allocations...")
    
    # Allocate all menus to all projects that don't have them
    result = conn.execute(text("""
        INSERT INTO project_menu_screens (project_id, menu_screen_id, created_at)
        SELECT p.id, m.id, NOW()
        FROM projects p
        CROSS JOIN menu_screens m
        WHERE NOT EXISTS (
            SELECT 1 FROM project_menu_screens pms
            WHERE pms.project_id = p.id AND pms.menu_screen_id = m.id
        )
    """))
    
    # Get count of new allocations
    count_result = conn.execute(text("""
        SELECT COUNT(*) FROM project_menu_screens
    """))
    total = count_result.scalar()
    
    print(f"✅ Menu allocations fixed! Total allocations: {total}")


def downgrade() -> None:
    """No downgrade - menu allocations should persist."""
    pass
