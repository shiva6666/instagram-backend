from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.feed.models import FeedItem
from app.modules.feed.repository import FeedRepository


class InvalidFeedCursorError(ValueError):
    """Raised when a home-feed cursor is malformed."""


@dataclass(frozen=True, slots=True)
class FeedPage:
    items: tuple[FeedItem, ...]
    next_cursor: str | None


def _encode_cursor(item: FeedItem) -> str:
    payload = {
        "created_at": item.post.created_at.isoformat(),
        "post_id": str(item.post.id),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[datetime, UUID] | None:
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        created_at = datetime.fromisoformat(payload["created_at"])
        post_id = UUID(payload["post_id"])
        if created_at.tzinfo is None:
            raise ValueError("cursor timestamp must include timezone")
        return created_at, post_id
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise InvalidFeedCursorError("invalid feed cursor") from error


class FeedService:
    def __init__(self, repository: FeedRepository) -> None:
        self._repository = repository

    async def get_feed(
        self, *, viewer_id: UUID, cursor: str | None, limit: int
    ) -> FeedPage:
        decoded_cursor = _decode_cursor(cursor)
        items = await self._repository.list_feed(
            viewer_id,
            cursor=decoded_cursor,
            limit=limit,
        )
        has_more = len(items) > limit
        page = tuple(items[:limit])
        next_cursor = _encode_cursor(page[-1]) if has_more and page else None
        return FeedPage(items=page, next_cursor=next_cursor)
