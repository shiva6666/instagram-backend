"""Add post image metadata, post privacy, and block relationships.

Revision ID: 003
Revises: 002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column(
            "is_private",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "post_images",
        sa.Column(
            "post_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.CheckConstraint("position >= 0", name="post_images_position_nonnegative"),
    )

    op.create_table(
        "user_blocks",
        sa.Column(
            "blocker_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "blocked_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.CheckConstraint(
            "blocker_id <> blocked_id",
            name="user_blocks_no_self_block",
        ),
    )
    op.create_index("ix_user_blocks_blocked", "user_blocks", ["blocked_id"])


def downgrade() -> None:
    op.drop_index("ix_user_blocks_blocked", table_name="user_blocks")
    op.drop_table("user_blocks")
    op.drop_table("post_images")
    op.drop_column("posts", "is_private")
