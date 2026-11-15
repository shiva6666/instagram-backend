"""Delete discarded or abandoned, unattached media assets.

Run periodically with `make cleanup-media`. The script is safe to retry:
object deletion is idempotent and rows are claimed with SKIP LOCKED.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.core.config import settings
from app.core.db import session_factory
from app.modules.media.storage.interfaces import ObjectStorageError
from app.modules.media.storage.s3 import S3CompatibleStorage


CLAIM_SQL = text(
    """
    WITH candidates AS (
        SELECT m.id
        FROM media AS m
        WHERE
            NOT EXISTS (
                SELECT 1 FROM post_media AS pm WHERE pm.media_id = m.id
            )
            AND (
                m.upload_expires_at IS NULL
                OR m.upload_expires_at <= :safe_before
            )
            AND (
                m.status = 'deleting'
                OR m.cleanup_requested_at <= :now
                OR (
                    m.created_at <= :expired_before
                    AND m.status IN ('pending', 'failed', 'ready')
                )
            )
        ORDER BY COALESCE(m.cleanup_requested_at, m.created_at), m.id
        LIMIT :batch_size
        FOR UPDATE SKIP LOCKED
    )
    UPDATE media AS m
    SET status = 'deleting', updated_at = :now
    FROM candidates
    WHERE m.id = candidates.id
    RETURNING
        m.id, m.owner_id, m.object_key,
        m.display_object_key, m.thumbnail_object_key
    """
)


async def cleanup_media(batch_size: int = 100) -> int:
    if session_factory is None:
        raise RuntimeError("DATABASE_URL must be configured")
    storage = S3CompatibleStorage.from_settings()
    await storage.ensure_bucket()

    now = datetime.now(UTC)
    expired_before = now - timedelta(hours=settings.media_cleanup_grace_hours)
    safe_before = now - timedelta(minutes=5)
    async with session_factory() as session:
        # A soft-deleted post keeps its media during the grace period. Once
        # that period expires, detach its media so the normal cleanup claim
        # can remove the object and metadata safely.
        await session.execute(
            text(
                """
                UPDATE media AS m
                SET cleanup_requested_at = COALESCE(m.cleanup_requested_at, :now),
                    updated_at = :now
                FROM post_media AS pm
                JOIN posts AS p ON p.id = pm.post_id
                WHERE m.id = pm.media_id
                  AND p.deleted_at IS NOT NULL
                  AND p.deleted_at <= :expired_before
                """
            ),
            {"now": now, "expired_before": expired_before},
        )
        await session.execute(
            text(
                """
                DELETE FROM post_media AS pm
                USING posts AS p
                WHERE p.id = pm.post_id
                  AND p.deleted_at IS NOT NULL
                  AND p.deleted_at <= :expired_before
                """
            ),
            {"expired_before": expired_before},
        )
        result = await session.execute(
            CLAIM_SQL,
            {
                "now": now,
                "expired_before": expired_before,
                "safe_before": safe_before,
                "batch_size": batch_size,
            },
        )
        candidates = result.mappings().all()
        await session.commit()

    deleted_count = 0
    for candidate in candidates:
        media_id = candidate["id"]
        owner_id = candidate["owner_id"]
        keys = {
            key
            for key in (
                candidate["object_key"],
                candidate["display_object_key"],
                candidate["thumbnail_object_key"],
                f"processed/{owner_id}/{media_id}/display.webp",
                f"processed/{owner_id}/{media_id}/thumbnail.webp",
            )
            if key
        }
        try:
            for object_key in keys:
                await storage.delete_object(object_key)
        except ObjectStorageError:
            # Keep the row in deleting state. The next run retries all keys.
            continue

        async with session_factory() as session:
            result = await session.execute(
                text(
                    """
                    DELETE FROM media
                    WHERE id = :media_id
                      AND status = 'deleting'
                      AND NOT EXISTS (
                          SELECT 1 FROM post_media
                          WHERE post_media.media_id = media.id
                      )
                    """
                ),
                {"media_id": media_id},
            )
            await session.commit()
            deleted_count += result.rowcount or 0

    return deleted_count


def main() -> None:
    deleted = asyncio.run(cleanup_media())
    print(f"Deleted {deleted} unattached media assets.")


if __name__ == "__main__":
    main()
