from __future__ import annotations

import pytest

from app.modules.media.processing import (
    InvalidImageError,
    detect_image_content_type,
)


def test_detects_supported_image_signatures() -> None:
    assert detect_image_content_type(b"\xff\xd8\xff" + b"payload") == "image/jpeg"
    assert (
        detect_image_content_type(b"\x89PNG\r\n\x1a\n" + b"payload")
        == "image/png"
    )
    assert (
        detect_image_content_type(b"RIFFxxxxWEBP" + b"payload") == "image/webp"
    )


def test_rejects_unknown_or_non_image_payload() -> None:
    with pytest.raises(InvalidImageError):
        detect_image_content_type(b"<svg><script>alert(1)</script></svg>")
