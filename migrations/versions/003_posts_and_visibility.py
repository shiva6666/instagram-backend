"""Create posts, post images, and relationship edges used for visibility.

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
    op.create_table(
        "posts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("caption", sa.String(2200), nullable=True),
        sa.Column(
            "is_private",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_posts_user_created",
        "posts",
        ["user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_posts_active_user",
        "posts",
        ["user_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
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
        "user_follows",
        sa.Column(
            "follower_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "followee_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted')",
            name="user_follows_status_check",
        ),
        sa.CheckConstraint(
            "follower_id <> followee_id",
            name="user_follows_no_self_follow",
        ),
    )
    op.create_index(
        "ix_user_follows_followee", "user_follows", ["followee_id", "status"]
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
    op.drop_index("ix_user_follows_followee", table_name="user_follows")
    op.drop_table("user_follows")
    op.drop_table("post_images")
    op.drop_index("ix_posts_active_user", table_name="posts")
    op.drop_index("ix_posts_user_created", table_name="posts")
    op.drop_table("posts")
