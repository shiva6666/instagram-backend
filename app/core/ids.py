from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime


def new_uuid7() -> uuid.UUID:
    """Generate a UUIDv7 for application-created entities."""
    timestamp_ms = int(datetime.now(UTC).timestamp() * 1_000) & ((1 << 48) - 1)
    value = timestamp_ms << 80
    value |= 0x7 << 76
    value |= secrets.randbits(12) << 64
    value |= 0x2 << 62
    value |= secrets.randbits(62)
    return uuid.UUID(int=value)
