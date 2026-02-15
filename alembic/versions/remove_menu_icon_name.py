"""Remove icon_name from menu_screens table.

Revision ID: remove_menu_icon_name
Revises: add_menu_screens_feature
Create Date: 2026-02-15

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'remove_menu_icon_name'
down_revision: Union[str, None] = 'add_menu_screens_feature'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove icon_name column from menu_screens."""
    op.drop_column('menu_screens', 'icon_name')


def downgrade() -> None:
    """Add icon_name column back to menu_screens."""
    op.add_column(
        'menu_screens',
        sa.Column('icon_name', sa.String(length=50), nullable=False, server_default='LayoutDashboard')
    )
