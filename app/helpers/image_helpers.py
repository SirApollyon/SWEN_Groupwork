"""Helper utilities for normalizing uploaded receipt images."""

from __future__ import annotations

from io import BytesIO
from typing import Tuple

from PIL import Image

try:  # Pillow >= 9
    _RESAMPLING = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - fallback for older Pillow
    _RESAMPLING = Image.LANCZOS  # type: ignore[attr-defined]

try:  # pragma: no cover - import side effect only
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover - gracefully degrade if optional dep missing
    pillow_heif = None  # type: ignore

_HEIF_BRANDS = {
    b"heic",
    b"heix",
    b"hevc",
    b"hevx",
    b"mif1",
    b"msf1",
    b"heif",
}


def _is_probably_heif(payload: bytes) -> bool:
    """Lightweight detection of HEIC/HEIF containers via ftyp brand."""
    return (
        len(payload) > 12
        and payload[4:8] == b"ftyp"
        and payload[8:12].lower() in _HEIF_BRANDS
    )


def _resize_if_needed(image: Image.Image, max_edge: int = 3200) -> Image.Image:
    """Downscale very large photos to keep uploads lightweight."""
    width, height = image.size
    longest = max(width, height)
    if longest <= max_edge:
        return image
    scale = max_edge / float(longest)
    new_size = (int(width * scale), int(height * scale))
    return image.resize(new_size, _RESAMPLING)


def normalize_upload_image(data: bytes) -> Tuple[bytes, str | None]:
    """
    Ensure uploaded images are browser- and model-friendly.

    Converts HEIC/HEIF files to JPEG (RGB) so they render in browsers and can be
    processed by downstream libraries. Returns the potentially converted bytes
    plus the resulting MIME type (None if unchanged).
    """
    if _is_probably_heif(data):
        if pillow_heif is None:
            raise ValueError(
                "HEIC/HEIF-Unterstützung ist nicht verfügbar. Bitte installiere 'pillow-heif'."
            )
        with Image.open(BytesIO(data)) as src:
            prepared = _resize_if_needed(src)
            rgb_image = prepared.convert("RGB")
            buffer = BytesIO()
            rgb_image.save(buffer, format="JPEG", quality=90, optimize=True)
            return buffer.getvalue(), "image/jpeg"
    return data, None


__all__ = ["normalize_upload_image"]
