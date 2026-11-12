"""Add covering indexes for cursor-paginated follow lists.

Revision ID: 004
Revises: 003
"""

from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_follows_followers_cursor",
        "follows",
        ["following_id", "created_at", "follower_id"],
    )
    op.create_index(
        "ix_follows_following_cursor",
        "follows",
        ["follower_id", "created_at", "following_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_follows_following_cursor", table_name="follows")
    op.drop_index("ix_follows_followers_cursor", table_name="follows")
