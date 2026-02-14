"""Add task:create_recurring permission.

Revision ID: add_recurring_task_permission
Revises: add_recurring_tasks_support
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_recurring_task_permission'
down_revision: Union[str, None] = 'add_recurring_tasks_support'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add task:create_recurring permission."""
    conn = op.get_bind()
    
    # Insert the new permission
    conn.execute(
        sa.text("""
            INSERT INTO permissions (permission_key, description)
            VALUES ('task:create_recurring', 'Create and manage recurring task templates')
            ON CONFLICT (permission_key) DO NOTHING
        """)
    )
    
    # Get the permission ID
    result = conn.execute(
        sa.text("SELECT id FROM permissions WHERE permission_key = 'task:create_recurring'")
    )
    permission_row = result.fetchone()
    if permission_row:
        permission_id = permission_row[0]
        
        # Assign this permission to Platform Admin and School Admin roles for ALL existing projects
        # This ensures existing admins get the new permission
        conn.execute(
            sa.text("""
                INSERT INTO role_permissions (project_id, role_id, permission_id, created_at)
                SELECT DISTINCT urp.project_id, r.id, :permission_id, NOW()
                FROM roles r
                CROSS JOIN user_role_projects urp
                WHERE r.name IN ('Platform Admin', 'School Admin')
                ON CONFLICT (project_id, role_id, permission_id) DO NOTHING
            """),
            {"permission_id": permission_id}
        )


def downgrade() -> None:
    """Remove task:create_recurring permission."""
    conn = op.get_bind()
    
    # Remove role_permissions entries
    conn.execute(
        sa.text("""
            DELETE FROM role_permissions 
            WHERE permission_id = (SELECT id FROM permissions WHERE permission_key = 'task:create_recurring')
        """)
    )
    
    # Remove the permission
    conn.execute(
        sa.text("DELETE FROM permissions WHERE permission_key = 'task:create_recurring'")
    )
