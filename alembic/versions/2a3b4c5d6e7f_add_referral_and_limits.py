"""add_referral_and_limits

Revision ID: 2a3b4c5d6e7f
Revises: 156b17080a2e
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a3b4c5d6e7f'
down_revision: Union[str, Sequence[str], None] = '156b17080a2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add daily_limit, bonus_balance, and referrer_id to users."""
    # server_default fills existing rows immediately, satisfying NOT NULL.
    op.add_column('users', sa.Column(
        'daily_limit', sa.Integer(), nullable=False, server_default=sa.text('3')
    ))
    op.add_column('users', sa.Column(
        'bonus_balance', sa.Integer(), nullable=False, server_default=sa.text('0')
    ))
    op.add_column('users', sa.Column(
        'referrer_id', sa.Integer(), nullable=True
    ))
    op.create_foreign_key(
        op.f('fk_users_referrer_id'),
        'users', 'users',
        ['referrer_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Remove referral and limit columns from users."""
    op.drop_constraint(op.f('fk_users_referrer_id'), 'users', type_='foreignkey')
    op.drop_column('users', 'referrer_id')
    op.drop_column('users', 'bonus_balance')
    op.drop_column('users', 'daily_limit')
