"""Add OAuth support with email and oauth_accounts table.

Revision ID: add_oauth_support
Revises: 
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'add_oauth_support'
down_revision: Union[str, None] = 'link_orphan_perms'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # Add email column to users table (if not exists)
    if not column_exists('users', 'email'):
        op.add_column(
            'users',
            sa.Column('email', sa.String(320), nullable=True)
        )
        op.create_index('ix_users_email', 'users', ['email'], unique=True)
    
    # Make password_hash nullable for OAuth-only users
    op.alter_column(
        'users',
        'password_hash',
        existing_type=sa.Text(),
        nullable=True
    )
    
    # Create oauth_accounts table (if not exists)
    if not table_exists('oauth_accounts'):
        op.create_table(
            'oauth_accounts',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.BigInteger(), nullable=False),
            sa.Column('provider', sa.String(50), nullable=False),
            sa.Column('provider_user_id', sa.String(255), nullable=False),
            sa.Column('provider_email', sa.String(320), nullable=True),
            sa.Column('access_token', sa.Text(), nullable=True),
            sa.Column('refresh_token', sa.Text(), nullable=True),
            sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('provider', 'provider_user_id', name='uq_oauth_provider_user'),
        )
        op.create_index('ix_oauth_accounts_user_id', 'oauth_accounts', ['user_id'])
        op.create_index('ix_oauth_accounts_provider', 'oauth_accounts', ['provider'])


def downgrade() -> None:
    # Drop oauth_accounts table
    op.drop_index('ix_oauth_accounts_provider', table_name='oauth_accounts')
    op.drop_index('ix_oauth_accounts_user_id', table_name='oauth_accounts')
    op.drop_table('oauth_accounts')
    
    # Make password_hash required again (only if no OAuth-only users exist)
    op.alter_column(
        'users',
        'password_hash',
        existing_type=sa.Text(),
        nullable=False
    )
    
    # Remove email column
    op.drop_index('ix_users_email', table_name='users')
    op.drop_column('users', 'email')
