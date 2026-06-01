"""add_blocked_at_to_platform_identities

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-05-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = '6f7a8b9c0d1e'
down_revision: Union[str, Sequence[str], None] = '5e6f7a8b9c0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add blocked_at to platform_identities for broadcast filtering."""
    op.add_column('platform_identities', sa.Column(
        'blocked_at',
        sa.DateTime(timezone=True),
        nullable=True,
    ))
    # Partial index: only rows that are NOT blocked need to be scanned
    # during broadcast queries (WHERE blocked_at IS NULL).
    op.create_index(
        'ix_platform_identities_active',
        'platform_identities',
        ['platform'],
        postgresql_where=sa.text('blocked_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_platform_identities_active', table_name='platform_identities')
    op.drop_column('platform_identities', 'blocked_at')
