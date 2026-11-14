"""Introduce media assets and one-post-per-media associations.

Revision ID: 005
Revises: 004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_key", sa.String(512), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ready"),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="media_status_check",
        ),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="media_size_nonnegative"),
        sa.CheckConstraint("width IS NULL OR width > 0", name="media_width_positive"),
        sa.CheckConstraint("height IS NULL OR height > 0", name="media_height_positive"),
    )
    op.create_index("ix_media_owner_created", "media", ["owner_id", "created_at"])
    op.create_index("ix_media_status_created", "media", ["status", "created_at"])

    # Preserve existing URL-backed post images as ready media assets.
    op.add_column(
        "post_images",
        sa.Column("media_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.execute("UPDATE post_images SET media_id = gen_random_uuid()")
    op.execute(
        """
        INSERT INTO media (id, owner_id, object_key, url, status)
        SELECT pi.media_id, p.user_id, NULL, pi.url, 'ready'
        FROM post_images AS pi
        JOIN posts AS p ON p.id = pi.post_id
        """
    )

    op.rename_table("post_images", "post_media")
    op.alter_column("post_media", "media_id", nullable=False)
    op.create_foreign_key(
        "fk_post_media_media_id",
        "post_media",
        "media",
        ["media_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint("uq_post_media_media_id", "post_media", ["media_id"])
    op.create_index("ix_post_media_media_id", "post_media", ["media_id"])


def downgrade() -> None:
    op.drop_index("ix_post_media_media_id", table_name="post_media")
    op.drop_constraint("uq_post_media_media_id", "post_media", type_="unique")
    op.drop_constraint("fk_post_media_media_id", "post_media", type_="foreignkey")
    op.alter_column("post_media", "media_id", nullable=True)
    op.rename_table("post_media", "post_images")
    op.drop_column("post_images", "media_id")
    op.drop_index("ix_media_status_created", table_name="media")
    op.drop_index("ix_media_owner_created", table_name="media")
    op.drop_table("media")
