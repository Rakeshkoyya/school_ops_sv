"""Add task view styles support.

Revision ID: add_task_view_styles
Revises: add_recurring_task_permission
Create Date: 2026-02-14

"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_task_view_styles'
down_revision: Union[str, None] = 'add_recurring_task_permission'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default column configuration for the standard view
DEFAULT_COLUMN_CONFIG = [
    {"field": "checkbox", "visible": True, "order": 0},
    {"field": "title", "visible": True, "order": 1},
    {"field": "description", "visible": True, "order": 2},
    {"field": "status", "visible": True, "order": 3},
    {"field": "category", "visible": True, "order": 4},
    {"field": "created_at", "visible": True, "order": 5},
    {"field": "created_by", "visible": True, "order": 6},
    {"field": "assignee", "visible": True, "order": 7},
    {"field": "due_datetime", "visible": True, "order": 8},
    {"field": "timer", "visible": True, "order": 9},
    {"field": "actions", "visible": True, "order": 10},
]


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = '{table_name}' AND column_name = '{column_name}'
        );
    """))
    return result.scalar()


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = '{table_name}'
        );
    """))
    return result.scalar()


def index_exists(index_name: str) -> bool:
    """Check if an index exists."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"""
        SELECT EXISTS (
            SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}'
        );
    """))
    return result.scalar()


def constraint_exists(constraint_name: str) -> bool:
    """Check if a constraint exists."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.table_constraints 
            WHERE constraint_name = '{constraint_name}'
        );
    """))
    return result.scalar()


def upgrade() -> None:
    """Add task view styles tables and seed data."""
    conn = op.get_bind()
    
    # Create task_view_styles table
    if not table_exists('task_view_styles'):
        op.create_table(
            'task_view_styles',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('project_id', sa.BigInteger(), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('column_config', sa.JSON(), nullable=False),
            sa.Column('is_system_default', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_by_id', sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        )
    
    if not index_exists('ix_task_view_styles_project_id'):
        op.create_index('ix_task_view_styles_project_id', 'task_view_styles', ['project_id'])
    if not index_exists('ix_task_view_styles_created_by_id'):
        op.create_index('ix_task_view_styles_created_by_id', 'task_view_styles', ['created_by_id'])
    
    # Create user_task_view_preferences table
    if not table_exists('user_task_view_preferences'):
        op.create_table(
            'user_task_view_preferences',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('project_id', sa.BigInteger(), nullable=False),
            sa.Column('view_style_id', sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['view_style_id'], ['task_view_styles.id'], ondelete='CASCADE'),
            sa.UniqueConstraint('user_id', 'project_id', name='uq_user_project_view_preference'),
        )
    
    if not index_exists('ix_user_task_view_preferences_user_id'):
        op.create_index('ix_user_task_view_preferences_user_id', 'user_task_view_preferences', ['user_id'])
    if not index_exists('ix_user_task_view_preferences_project_id'):
        op.create_index('ix_user_task_view_preferences_project_id', 'user_task_view_preferences', ['project_id'])
    if not index_exists('ix_user_task_view_preferences_view_style_id'):
        op.create_index('ix_user_task_view_preferences_view_style_id', 'user_task_view_preferences', ['view_style_id'])
    
    # Add default_task_view_style_id column to projects table
    if not column_exists('projects', 'default_task_view_style_id'):
        op.add_column('projects', sa.Column('default_task_view_style_id', sa.BigInteger(), nullable=True))
    
    if not index_exists('ix_projects_default_task_view_style_id'):
        op.create_index('ix_projects_default_task_view_style_id', 'projects', ['default_task_view_style_id'])
    
    # Add FK constraint (need to add after task_view_styles table exists)
    if not constraint_exists('fk_projects_default_task_view_style'):
        op.create_foreign_key(
            'fk_projects_default_task_view_style',
            'projects',
            'task_view_styles',
            ['default_task_view_style_id'],
            ['id'],
            ondelete='SET NULL'
        )
    
    # Seed "Standard View" for each existing project
    conn.execute(sa.text("""
        INSERT INTO task_view_styles (project_id, name, description, column_config, is_system_default, created_at, updated_at)
        SELECT 
            p.id,
            'Standard View',
            'Default view showing all task columns',
            :column_config,
            true,
            NOW(),
            NOW()
        FROM projects p
        WHERE NOT EXISTS (
            SELECT 1 FROM task_view_styles tvs 
            WHERE tvs.project_id = p.id AND tvs.is_system_default = true
        )
    """), {"column_config": json.dumps(DEFAULT_COLUMN_CONFIG)})
    
    # Set the default_task_view_style_id for each project to point to its system default view
    conn.execute(sa.text("""
        UPDATE projects p
        SET default_task_view_style_id = tvs.id
        FROM task_view_styles tvs
        WHERE tvs.project_id = p.id 
        AND tvs.is_system_default = true
        AND p.default_task_view_style_id IS NULL
    """))
    
    # Add task view permissions
    permissions = [
        ('task_view:create', 'Create task view styles'),
        ('task_view:update', 'Update task view styles'),
        ('task_view:delete', 'Delete task view styles'),
        ('task_view:set_default', 'Set project default task view style'),
    ]
    
    for perm_key, perm_desc in permissions:
        conn.execute(
            sa.text("""
                INSERT INTO permissions (permission_key, description)
                VALUES (:perm_key, :perm_desc)
                ON CONFLICT (permission_key) DO NOTHING
            """),
            {"perm_key": perm_key, "perm_desc": perm_desc}
        )
    
    # Assign task_view:create, task_view:update, task_view:delete to all users (via Staff role)
    # Assign task_view:set_default only to admin roles
    
    # Get all permission IDs
    for perm_key in ['task_view:create', 'task_view:update', 'task_view:delete']:
        result = conn.execute(
            sa.text("SELECT id FROM permissions WHERE permission_key = :perm_key"),
            {"perm_key": perm_key}
        )
        permission_row = result.fetchone()
        if permission_row:
            permission_id = permission_row[0]
            # Assign to all roles (everyone can create/edit their own views)
            conn.execute(
                sa.text("""
                    INSERT INTO role_permissions (project_id, role_id, permission_id, created_at)
                    SELECT DISTINCT urp.project_id, urp.role_id, :permission_id, NOW()
                    FROM user_role_projects urp
                    ON CONFLICT (project_id, role_id, permission_id) DO NOTHING
                """),
                {"permission_id": permission_id}
            )
    
    # Assign task_view:set_default only to admin roles
    result = conn.execute(
        sa.text("SELECT id FROM permissions WHERE permission_key = 'task_view:set_default'")
    )
    permission_row = result.fetchone()
    if permission_row:
        permission_id = permission_row[0]
        conn.execute(
            sa.text("""
                INSERT INTO role_permissions (project_id, role_id, permission_id, created_at)
                SELECT DISTINCT urp.project_id, r.id, :permission_id, NOW()
                FROM roles r
                INNER JOIN user_role_projects urp ON urp.role_id = r.id
                WHERE r.is_project_admin = true OR r.name IN ('Platform Admin', 'School Admin', 'Super Admin')
                ON CONFLICT (project_id, role_id, permission_id) DO NOTHING
            """),
            {"permission_id": permission_id}
        )


def downgrade() -> None:
    """Remove task view styles tables and permissions."""
    conn = op.get_bind()
    
    # Remove role_permissions entries for task_view permissions
    conn.execute(
        sa.text("""
            DELETE FROM role_permissions 
            WHERE permission_id IN (
                SELECT id FROM permissions 
                WHERE permission_key IN ('task_view:create', 'task_view:update', 'task_view:delete', 'task_view:set_default')
            )
        """)
    )
    
    # Remove permissions
    conn.execute(
        sa.text("""
            DELETE FROM permissions 
            WHERE permission_key IN ('task_view:create', 'task_view:update', 'task_view:delete', 'task_view:set_default')
        """)
    )
    
    # Remove FK constraint from projects
    if constraint_exists('fk_projects_default_task_view_style'):
        op.drop_constraint('fk_projects_default_task_view_style', 'projects', type_='foreignkey')
    
    # Remove column from projects
    if column_exists('projects', 'default_task_view_style_id'):
        op.drop_column('projects', 'default_task_view_style_id')
    
    # Drop user_task_view_preferences table
    if table_exists('user_task_view_preferences'):
        op.drop_table('user_task_view_preferences')
    
    # Drop task_view_styles table
    if table_exists('task_view_styles'):
        op.drop_table('task_view_styles')
