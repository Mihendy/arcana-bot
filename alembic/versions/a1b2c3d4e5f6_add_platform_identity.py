"""add_platform_identity

Decouple users from Telegram: remove tg_id/username/full_name from the users
table and introduce a generic platform_identities table. Existing rows are
backfilled so no data is lost.

Revision ID: a1b2c3d4e5f6
Revises: 7a1b2c3d4e5f
Create Date: 2026-05-22 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create platform_identities table
    # ------------------------------------------------------------------
    op.create_table(
        "platform_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "external_id", name="uq_platform_external_id"),
    )
    op.create_index("ix_platform_identities_user_id", "platform_identities", ["user_id"])

    # ------------------------------------------------------------------
    # 2. Backfill: migrate existing Telegram users → platform_identities
    #    (tg_id still exists on users at this point)
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO platform_identities (user_id, platform, external_id, display_name)
        SELECT id, 'telegram', CAST(tg_id AS TEXT), full_name
        FROM users
        WHERE tg_id IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 3. llm_usage_events: swap user_tg_id (BigInt, no FK) → user_id (Int, FK)
    # ------------------------------------------------------------------
    op.add_column(
        "llm_usage_events",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    # Backfill via tg_id join (still present in users)
    op.execute(
        """
        UPDATE llm_usage_events lue
        SET user_id = u.id
        FROM users u
        WHERE CAST(u.tg_id AS TEXT) = CAST(lue.user_tg_id AS TEXT)
        """
    )
    # Rows whose tg_id no longer matches a user get user_id = NULL — keep them
    # nullable rather than deleting analytics history.
    op.create_foreign_key(
        "fk_llm_usage_events_user_id",
        "llm_usage_events",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_llm_usage_events_user_id", "llm_usage_events", ["user_id"])
    op.drop_index("ix_llm_usage_events_user_tg_id", table_name="llm_usage_events")
    op.drop_column("llm_usage_events", "user_tg_id")

    # ------------------------------------------------------------------
    # 4. Clean up legacy columns on users
    #    (must happen AFTER backfill steps above)
    # ------------------------------------------------------------------
    op.drop_index("ix_users_tg_id", table_name="users")
    op.drop_constraint("users_tg_id_key", "users", type_="unique")
    op.drop_column("users", "tg_id")
    op.drop_column("users", "username")
    op.drop_column("users", "full_name")

    # ------------------------------------------------------------------
    # 5. readings: drop legacy scalar image_url; fix image_urls NOT NULL
    # ------------------------------------------------------------------
    op.drop_column("readings", "image_url")
    op.execute("UPDATE readings SET image_urls = '[]' WHERE image_urls IS NULL")
    op.alter_column("readings", "image_urls", nullable=False)


def downgrade() -> None:
    # ------------------------------------------------------------------
    # 5r. Restore readings columns
    # ------------------------------------------------------------------
    op.alter_column("readings", "image_urls", nullable=True)
    op.add_column("readings", sa.Column("image_url", sa.Text(), nullable=True))

    # ------------------------------------------------------------------
    # 4r. Restore users columns (data is gone — restored as NULL)
    # ------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("username", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("tg_id", sa.BigInteger(), nullable=True),
    )
    # Restore tg_id from platform_identities where possible
    op.execute(
        """
        UPDATE users u
        SET tg_id    = CAST(pi.external_id AS BIGINT),
            full_name = pi.display_name
        FROM platform_identities pi
        WHERE pi.user_id = u.id AND pi.platform = 'telegram'
        """
    )
    op.create_unique_constraint("users_tg_id_key", "users", ["tg_id"])
    op.create_index("ix_users_tg_id", "users", ["tg_id"], unique=True)

    # ------------------------------------------------------------------
    # 3r. Restore llm_usage_events.user_tg_id
    # ------------------------------------------------------------------
    op.add_column(
        "llm_usage_events",
        sa.Column("user_tg_id", sa.BigInteger(), nullable=True),
    )
    op.execute(
        """
        UPDATE llm_usage_events lue
        SET user_tg_id = CAST(pi.external_id AS BIGINT)
        FROM users u
        JOIN platform_identities pi ON pi.user_id = u.id AND pi.platform = 'telegram'
        WHERE u.id = lue.user_id
        """
    )
    op.drop_index("ix_llm_usage_events_user_id", table_name="llm_usage_events")
    op.drop_constraint("fk_llm_usage_events_user_id", "llm_usage_events", type_="foreignkey")
    op.drop_column("llm_usage_events", "user_id")
    op.create_index(
        "ix_llm_usage_events_user_tg_id", "llm_usage_events", ["user_tg_id"], unique=False
    )

    # ------------------------------------------------------------------
    # 2r + 1r. Drop platform_identities table
    # ------------------------------------------------------------------
    op.drop_index("ix_platform_identities_user_id", table_name="platform_identities")
    op.drop_table("platform_identities")
