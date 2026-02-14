"""Add recurring tasks support - due_datetime and recurring_task_templates.

Revision ID: add_recurring_tasks_support
Revises: add_color_to_task_categories
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_recurring_tasks_support'
down_revision: Union[str, None] = 'add_color_to_task_categories'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define the enum type that already exists or will be created
recurrencetype = postgresql.ENUM('daily', 'weekly', 'once', name='recurrencetype', create_type=False)


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
    """Add recurring tasks support."""
    conn = op.get_bind()
    
    # Create recurrence_type enum (check if exists first for PostgreSQL)
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE recurrencetype AS ENUM ('daily', 'weekly', 'once');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    # Create recurring_task_templates table first (before adding FK in tasks)
    if not table_exists('recurring_task_templates'):
        op.create_table(
            'recurring_task_templates',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('project_id', sa.BigInteger(), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('category_id', sa.BigInteger(), nullable=True),
            sa.Column('recurrence_type', recurrencetype, nullable=False),
            sa.Column('days_of_week', sa.String(20), nullable=True),
            sa.Column('scheduled_date', sa.Date(), nullable=True),
            sa.Column('created_on_time', sa.Time(), nullable=True),
            sa.Column('start_time', sa.Time(), nullable=True),
            sa.Column('due_time', sa.Time(), nullable=True),
            sa.Column('assigned_to_user_id', sa.BigInteger(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('last_generated_date', sa.Date(), nullable=True),
            sa.Column('created_by_id', sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['category_id'], ['task_categories.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        )
    
    if not index_exists('ix_recurring_task_templates_project_id'):
        op.create_index('ix_recurring_task_templates_project_id', 'recurring_task_templates', ['project_id'])
    if not index_exists('ix_recurring_task_templates_category_id'):
        op.create_index('ix_recurring_task_templates_category_id', 'recurring_task_templates', ['category_id'])
    if not index_exists('ix_recurring_task_templates_assigned_to_user_id'):
        op.create_index('ix_recurring_task_templates_assigned_to_user_id', 'recurring_task_templates', ['assigned_to_user_id'])

    # Change due_date to due_datetime in tasks table
    if not column_exists('tasks', 'due_datetime'):
        op.add_column('tasks', sa.Column('due_datetime', sa.DateTime(timezone=True), nullable=True))
    
    # Migrate existing data: convert date to datetime (end of day)
    if column_exists('tasks', 'due_date'):
        op.execute("""
            UPDATE tasks 
            SET due_datetime = due_date::timestamp + interval '23 hours 59 minutes 59 seconds'
            WHERE due_date IS NOT NULL AND due_datetime IS NULL
        """)
        # Drop the old column
        op.drop_column('tasks', 'due_date')

    # Add recurring_template_id to tasks
    if not column_exists('tasks', 'recurring_template_id'):
        op.add_column('tasks', sa.Column('recurring_template_id', sa.BigInteger(), nullable=True))
    
    if not constraint_exists('fk_tasks_recurring_template_id'):
        op.create_foreign_key(
            'fk_tasks_recurring_template_id',
            'tasks',
            'recurring_task_templates',
            ['recurring_template_id'],
            ['id'],
            ondelete='SET NULL'
        )
    
    if not index_exists('ix_tasks_recurring_template_id'):
        op.create_index('ix_tasks_recurring_template_id', 'tasks', ['recurring_template_id'])


def downgrade() -> None:
    """Remove recurring tasks support."""
    # Remove recurring_template_id from tasks
    if index_exists('ix_tasks_recurring_template_id'):
        op.drop_index('ix_tasks_recurring_template_id', table_name='tasks')
    if constraint_exists('fk_tasks_recurring_template_id'):
        op.drop_constraint('fk_tasks_recurring_template_id', 'tasks', type_='foreignkey')
    if column_exists('tasks', 'recurring_template_id'):
        op.drop_column('tasks', 'recurring_template_id')

    # Convert due_datetime back to due_date
    if not column_exists('tasks', 'due_date'):
        op.add_column('tasks', sa.Column('due_date', sa.Date(), nullable=True))
    if column_exists('tasks', 'due_datetime'):
        op.execute("""
            UPDATE tasks 
            SET due_date = due_datetime::date
            WHERE due_datetime IS NOT NULL
        """)
        op.drop_column('tasks', 'due_datetime')

    # Drop recurring_task_templates table
    if table_exists('recurring_task_templates'):
        if index_exists('ix_recurring_task_templates_assigned_to_user_id'):
            op.drop_index('ix_recurring_task_templates_assigned_to_user_id', table_name='recurring_task_templates')
        if index_exists('ix_recurring_task_templates_category_id'):
            op.drop_index('ix_recurring_task_templates_category_id', table_name='recurring_task_templates')
        if index_exists('ix_recurring_task_templates_project_id'):
            op.drop_index('ix_recurring_task_templates_project_id', table_name='recurring_task_templates')
        op.drop_table('recurring_task_templates')

    # Drop recurrence_type enum
    conn = op.get_bind()
    conn.execute(sa.text("DROP TYPE IF EXISTS recurrencetype;"))
