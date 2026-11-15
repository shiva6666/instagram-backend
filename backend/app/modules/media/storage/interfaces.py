from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    size_bytes: int
    content_type: str | None


class ObjectNotFoundError(LookupError):
    pass


class ObjectStorageError(RuntimeError):
    pass


class ObjectStorage(Protocol):
    def presign_put_url(self, object_key: str, *, expires_in: int) -> str: ...

    def presign_get_url(self, object_key: str, *, expires_in: int) -> str: ...

    async def ensure_bucket(self) -> None: ...

    async def head_object(self, object_key: str) -> StoredObject: ...

    async def get_object(self, object_key: str, *, max_bytes: int) -> bytes: ...

    async def put_object(
        self, object_key: str, data: bytes, *, content_type: str
    ) -> None: ...

    async def delete_object(self, object_key: str) -> None: ...
