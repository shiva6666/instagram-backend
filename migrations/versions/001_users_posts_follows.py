"""Create users, posts, and follows.

Revision ID: 001
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL 16 does not provide a built-in UUIDv7 generator.  UUIDv7 can
    # be supplied by the application later without changing these column
    # types; gen_random_uuid() keeps database-created rows valid in the
    # meantime.
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("username", CITEXT(), nullable=False),
        sa.Column("email", CITEXT(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_key", sa.String(length=512), nullable=True),
        sa.Column(
            "is_private",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
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
        sa.UniqueConstraint("username", name="users_username_key"),
        sa.UniqueConstraint("email", name="users_email_key"),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'pending_deletion')",
            name="users_status_check",
        ),
    )

    op.create_table(
        "posts",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="posts_user_id_fkey",
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "follows",
        sa.Column("follower_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("following_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'accepted'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "follower_id",
            "following_id",
            name="follows_pkey",
        ),
        sa.ForeignKeyConstraint(
            ["follower_id"],
            ["users.id"],
            name="follows_follower_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["following_id"],
            ["users.id"],
            name="follows_following_id_fkey",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "follower_id <> following_id",
            name="follows_no_self_follow_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted')",
            name="follows_status_check",
        ),
    )

    op.create_index(
        "ix_posts_user_id_created_at_id",
        "posts",
        ["user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_posts_created_at_id",
        "posts",
        ["created_at", "id"],
    )
    op.create_index(
        "ix_follows_follower_id_created_at",
        "follows",
        ["follower_id", "created_at"],
    )
    op.create_index(
        "ix_follows_following_id_created_at",
        "follows",
        ["following_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_follows_following_id_created_at", table_name="follows")
    op.drop_index("ix_follows_follower_id_created_at", table_name="follows")
    op.drop_index("ix_posts_created_at_id", table_name="posts")
    op.drop_index("ix_posts_user_id_created_at_id", table_name="posts")
    op.drop_table("follows")
    op.drop_table("posts")
    op.drop_table("users")
