"""add llm usage events table

Revision ID: 3c4d7a9b1e2f
Revises: 9d2f3b7e1a1c
Create Date: 2026-04-17 04:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c4d7a9b1e2f"
down_revision: Union[str, Sequence[str], None] = "9d2f3b7e1a1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_tg_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_llm_usage_events_user_tg_id"), "llm_usage_events", ["user_tg_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_llm_usage_events_user_tg_id"), table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
