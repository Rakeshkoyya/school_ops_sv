"""Add PROJECT_DELETED audit action

Revision ID: add_project_deleted
Revises: 113e87aef32d
Create Date: 2026-01-24

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_project_deleted'
down_revision: Union[str, None] = '113e87aef32d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the PROJECT_DELETED value to the auditaction enum
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'PROJECT_DELETED'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values easily
    # This would require recreating the enum type
    pass
