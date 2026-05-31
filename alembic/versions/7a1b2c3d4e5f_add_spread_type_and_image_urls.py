"""add spread_type and image_urls to readings

Revision ID: 7a1b2c3d4e5f
Revises: 3c4d7a9b1e2f
Create Date: 2026-04-17 08:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "3c4d7a9b1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "readings",
        sa.Column("spread_type", sa.String(length=64), nullable=False, server_default="3_cards"),
    )
    op.add_column(
        "readings",
        sa.Column("image_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("readings", "image_urls")
    op.drop_column("readings", "spread_type")
