from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from typing import Protocol


class InvalidImageError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProcessedImage:
    content_type: str
    width: int
    height: int
    display_bytes: bytes
    thumbnail_bytes: bytes


class ImageProcessor(Protocol):
    async def process(
        self, image_bytes: bytes, *, declared_content_type: str
    ) -> ProcessedImage: ...


def detect_image_content_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if (
        len(image_bytes) >= 12
        and image_bytes[:4] == b"RIFF"
        and image_bytes[8:12] == b"WEBP"
    ):
        return "image/webp"
    raise InvalidImageError("only JPEG, PNG, and WebP images are accepted")


class ImageMagickProcessor:
    """Validate and produce metadata-stripped WebP display and thumbnail files."""

    MAX_WIDTH = 8000
    MAX_HEIGHT = 8000
    MAX_PIXELS = 40_000_000

    @staticmethod
    def _run(command: list[str], image_bytes: bytes) -> bytes:
        try:
            result = subprocess.run(
                command,
                input=image_bytes,
                capture_output=True,
                check=False,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise InvalidImageError("image processing failed") from error
        if result.returncode != 0 or not result.stdout:
            raise InvalidImageError("image is corrupt or could not be processed")
        return result.stdout

    async def process(
        self, image_bytes: bytes, *, declared_content_type: str
    ) -> ProcessedImage:
        return await asyncio.to_thread(
            self._process, image_bytes, declared_content_type
        )

    def _process(
        self, image_bytes: bytes, declared_content_type: str
    ) -> ProcessedImage:
        detected_type = detect_image_content_type(image_bytes)
        if detected_type != declared_content_type:
            raise InvalidImageError("file content does not match declared content type")

        limits = [
            "-limit",
            "memory",
            "128MiB",
            "-limit",
            "map",
            "256MiB",
            "-limit",
            "disk",
            "512MiB",
            "-limit",
            "time",
            "15",
            "-limit",
            "thread",
            "1",
        ]
        metadata = (
            self._run(
                ["identify", *limits, "-format", "%m|%w|%h|%n\n", "-"],
                image_bytes,
            )
            .decode("ascii", errors="strict")
            .strip()
            .splitlines()
        )
        if len(metadata) != 1:
            raise InvalidImageError("animated or multi-frame images are not supported")

        try:
            image_format, width_text, height_text, frame_text = metadata[0].split("|")
            width = int(width_text)
            height = int(height_text)
            frames = int(frame_text)
        except (ValueError, TypeError) as error:
            raise InvalidImageError("image metadata could not be read") from error

        expected_format = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
        }[detected_type]
        if image_format.upper() != expected_format:
            raise InvalidImageError("image signature and decoded format do not match")
        if frames != 1:
            raise InvalidImageError("animated images are not supported")
        if (
            width <= 0
            or height <= 0
            or width > self.MAX_WIDTH
            or height > self.MAX_HEIGHT
            or width * height > self.MAX_PIXELS
        ):
            raise InvalidImageError("image dimensions exceed the allowed limit")

        display = self._run(
            [
                "convert",
                *limits,
                "-",
                "-auto-orient",
                "-strip",
                "-resize",
                "1600x1600>",
                "-quality",
                "85",
                "webp:-",
            ],
            image_bytes,
        )
        thumbnail = self._run(
            [
                "convert",
                *limits,
                "-",
                "-auto-orient",
                "-strip",
                "-thumbnail",
                "320x320^",
                "-gravity",
                "center",
                "-extent",
                "320x320",
                "-quality",
                "80",
                "webp:-",
            ],
            image_bytes,
        )
        return ProcessedImage(
            content_type=detected_type,
            width=width,
            height=height,
            display_bytes=display,
            thumbnail_bytes=thumbnail,
        )
