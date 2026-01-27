"""Add color column to task_categories table.

Revision ID: add_color_to_task_categories
Revises: add_project_deleted
Create Date: 2026-01-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_color_to_task_categories'
down_revision: Union[str, None] = 'add_exam_date_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add color column to task_categories table."""
    op.add_column('task_categories', sa.Column('color', sa.String(20), nullable=True))


def downgrade() -> None:
    """Remove color column from task_categories table."""
    op.drop_column('task_categories', 'color')
