"""add image_url to readings

Revision ID: 9d2f3b7e1a1c
Revises: c8f17ac51a4d
Create Date: 2026-04-17 03:12:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d2f3b7e1a1c"
down_revision: Union[str, Sequence[str], None] = "c8f17ac51a4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("readings", sa.Column("image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("readings", "image_url")
