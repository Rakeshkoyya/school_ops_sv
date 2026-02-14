"""Add evo points gamification support.

Revision ID: add_evo_points_gamification
Revises: add_task_view_styles
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_evo_points_gamification'
down_revision: Union[str, None] = 'add_task_view_styles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define the enum types
evoreductiontype = postgresql.ENUM('none', 'gradual', 'fixed', name='evoreductiontype', create_type=False)
evotransactiontype = postgresql.ENUM('task_reward', 'admin_credit', 'admin_debit', name='evotransactiontype', create_type=False)


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


def enum_exists(enum_name: str) -> bool:
    """Check if an enum type exists."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = '{enum_name}'
        );
    """))
    return result.scalar()


def upgrade() -> None:
    """Add evo points gamification support."""
    conn = op.get_bind()
    
    # Create evoreductiontype enum
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE evoreductiontype AS ENUM ('NONE', 'GRADUAL', 'FIXED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))
    
    # Create evotransactiontype enum
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE evotransactiontype AS ENUM ('task_reward', 'admin_credit', 'admin_debit');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    # Add evo fields to tasks table
    if not column_exists('tasks', 'evo_points'):
        op.add_column('tasks', sa.Column('evo_points', sa.Integer(), nullable=True))
    
    if not column_exists('tasks', 'evo_reduction_type'):
        op.add_column('tasks', sa.Column(
            'evo_reduction_type',
            evoreductiontype,
            nullable=False,
            server_default='NONE'
        ))
    
    if not column_exists('tasks', 'evo_extension_end'):
        op.add_column('tasks', sa.Column('evo_extension_end', sa.DateTime(timezone=True), nullable=True))
    
    if not column_exists('tasks', 'evo_fixed_reduction_points'):
        op.add_column('tasks', sa.Column('evo_fixed_reduction_points', sa.Integer(), nullable=True))

    # Add default_evo_points to projects table
    if not column_exists('projects', 'default_evo_points'):
        op.add_column('projects', sa.Column('default_evo_points', sa.Integer(), nullable=False, server_default='0'))

    # Create evo_point_transactions table
    if not table_exists('evo_point_transactions'):
        op.create_table(
            'evo_point_transactions',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('project_id', sa.BigInteger(), nullable=True),
            sa.Column('transaction_type', evotransactiontype, nullable=False),
            sa.Column('amount', sa.Integer(), nullable=False),
            sa.Column('balance_after', sa.BigInteger(), nullable=False),
            sa.Column('reason', sa.Text(), nullable=False),
            sa.Column('task_id', sa.BigInteger(), nullable=True),
            sa.Column('performed_by_id', sa.BigInteger(), nullable=True),
            sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['performed_by_id'], ['users.id'], ondelete='SET NULL'),
        )
        
        # Create indexes
        op.create_index('ix_evo_point_transactions_user_id', 'evo_point_transactions', ['user_id'])
        op.create_index('ix_evo_point_transactions_project_id', 'evo_point_transactions', ['project_id'])
        op.create_index('ix_evo_point_transactions_transaction_type', 'evo_point_transactions', ['transaction_type'])
        op.create_index('ix_evo_point_transactions_task_id', 'evo_point_transactions', ['task_id'])

    # Add evo_points:manage permission
    conn.execute(sa.text("""
        INSERT INTO permissions (permission_key, description)
        VALUES ('evo_points:manage', 'Manage evo points - credit, debit, and view all transactions')
        ON CONFLICT (permission_key) DO NOTHING;
    """))


def downgrade() -> None:
    """Remove evo points gamification support."""
    conn = op.get_bind()
    
    # Remove permission
    conn.execute(sa.text("""
        DELETE FROM permissions WHERE permission_key = 'evo_points:manage';
    """))
    
    # Drop indexes
    if index_exists('ix_evo_point_transactions_task_id'):
        op.drop_index('ix_evo_point_transactions_task_id', table_name='evo_point_transactions')
    if index_exists('ix_evo_point_transactions_transaction_type'):
        op.drop_index('ix_evo_point_transactions_transaction_type', table_name='evo_point_transactions')
    if index_exists('ix_evo_point_transactions_project_id'):
        op.drop_index('ix_evo_point_transactions_project_id', table_name='evo_point_transactions')
    if index_exists('ix_evo_point_transactions_user_id'):
        op.drop_index('ix_evo_point_transactions_user_id', table_name='evo_point_transactions')
    
    # Drop table
    if table_exists('evo_point_transactions'):
        op.drop_table('evo_point_transactions')
    
    # Remove columns from projects
    if column_exists('projects', 'default_evo_points'):
        op.drop_column('projects', 'default_evo_points')
    
    # Remove columns from tasks
    if column_exists('tasks', 'evo_fixed_reduction_points'):
        op.drop_column('tasks', 'evo_fixed_reduction_points')
    if column_exists('tasks', 'evo_extension_end'):
        op.drop_column('tasks', 'evo_extension_end')
    if column_exists('tasks', 'evo_reduction_type'):
        op.drop_column('tasks', 'evo_reduction_type')
    if column_exists('tasks', 'evo_points'):
        op.drop_column('tasks', 'evo_points')
    
    # Drop enum types
    if enum_exists('evotransactiontype'):
        conn.execute(sa.text("DROP TYPE IF EXISTS evotransactiontype;"))
    if enum_exists('evoreductiontype'):
        conn.execute(sa.text("DROP TYPE IF EXISTS evoreductiontype;"))
