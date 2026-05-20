"""add_holiday_and_leave_management

Revision ID: 67c099db1ca1
Revises: add_oauth_support
Create Date: 2026-05-21 02:25:12.122969

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67c099db1ca1'
down_revision: Union[str, None] = 'add_oauth_support'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create project_holidays table
    op.create_table(
        'project_holidays',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('holiday_date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'holiday_date', name='uq_project_holiday_date')
    )
    op.create_index('ix_project_holidays_project_id', 'project_holidays', ['project_id'])
    op.create_index('ix_project_holidays_holiday_date', 'project_holidays', ['holiday_date'])

    # Create user_leaves table
    op.create_table(
        'user_leaves',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('leave_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'user_id', 'leave_date', name='uq_project_user_leave_date')
    )
    op.create_index('ix_user_leaves_project_id', 'user_leaves', ['project_id'])
    op.create_index('ix_user_leaves_user_id', 'user_leaves', ['user_id'])
    op.create_index('ix_user_leaves_leave_date', 'user_leaves', ['leave_date'])
    op.create_index('ix_user_leaves_project_user_date', 'user_leaves', ['project_id', 'user_id', 'leave_date'])


def downgrade() -> None:
    op.drop_index('ix_user_leaves_project_user_date', 'user_leaves')
    op.drop_index('ix_user_leaves_leave_date', 'user_leaves')
    op.drop_index('ix_user_leaves_user_id', 'user_leaves')
    op.drop_index('ix_user_leaves_project_id', 'user_leaves')
    op.drop_table('user_leaves')
    
    op.drop_index('ix_project_holidays_holiday_date', 'project_holidays')
    op.drop_index('ix_project_holidays_project_id', 'project_holidays')
    op.drop_table('project_holidays')
