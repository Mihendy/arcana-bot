"""add_premium_and_payments

Revision ID: 4d5e6f7a8b9c
Revises: 2a3b4c5d6e7f
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4d5e6f7a8b9c'
down_revision: Union[str, Sequence[str], None] = '2a3b4c5d6e7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add premium columns to users and create payments table."""
    # ── users: premium subscription fields ──────────────────────────────────
    op.add_column('users', sa.Column(
        'premium_expires_at', sa.DateTime(timezone=True), nullable=True
    ))
    op.add_column('users', sa.Column(
        'subscription_tier', sa.String(length=32), nullable=True
    ))

    # ── payments table ───────────────────────────────────────────────────────
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False,
                  server_default=sa.text("'pending'")),
        sa.Column('provider_payment_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name=op.f('fk_payments_user_id'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_payments')),
    )
    # provider_payment_id: webhook lookup key — must be fast
    op.create_index(
        op.f('ix_payments_provider_payment_id'),
        'payments', ['provider_payment_id'],
    )
    # user_id: list a user's payment history
    op.create_index(
        op.f('ix_payments_user_id'),
        'payments', ['user_id'],
    )


def downgrade() -> None:
    """Drop payments table and remove premium columns from users."""
    op.drop_index(op.f('ix_payments_user_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_provider_payment_id'), table_name='payments')
    op.drop_table('payments')
    op.drop_column('users', 'subscription_tier')
    op.drop_column('users', 'premium_expires_at')
