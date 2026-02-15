"""Add evo points fields to recurring task templates.

Revision ID: add_evo_to_templates
Revises: add_evo_points_gamification
Create Date: 2026-02-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_evo_to_templates'
down_revision: str | None = 'add_evo_points_gamification'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add evo points columns to recurring_task_templates
    op.add_column(
        'recurring_task_templates',
        sa.Column('evo_points', sa.Integer(), nullable=True)
    )
    op.add_column(
        'recurring_task_templates',
        sa.Column(
            'evo_reduction_type',
            sa.Enum('NONE', 'GRADUAL', 'FIXED', name='evoreductiontype', create_type=False),
            nullable=False,
            server_default='NONE'
        )
    )
    op.add_column(
        'recurring_task_templates',
        sa.Column('evo_extension_time', sa.Time(), nullable=True)
    )
    op.add_column(
        'recurring_task_templates',
        sa.Column('evo_fixed_reduction_points', sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('recurring_task_templates', 'evo_fixed_reduction_points')
    op.drop_column('recurring_task_templates', 'evo_extension_time')
    op.drop_column('recurring_task_templates', 'evo_reduction_type')
    op.drop_column('recurring_task_templates', 'evo_points')
