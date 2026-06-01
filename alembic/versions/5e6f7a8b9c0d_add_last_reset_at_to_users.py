"""add_last_reset_at_to_users

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-05-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '5e6f7a8b9c0d'
down_revision: Union[str, Sequence[str], None] = '4d5e6f7a8b9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add last_reset_at to users for lazy daily-limit reset."""
    op.add_column('users', sa.Column(
        'last_reset_at',
        sa.DateTime(timezone=True),
        nullable=False,
        # Epoch default guarantees every existing user's first access triggers
        # a reset — their stored date will always be < today.
        server_default=sa.text("'2000-01-01 00:00:00+00'"),
    ))


def downgrade() -> None:
    op.drop_column('users', 'last_reset_at')
