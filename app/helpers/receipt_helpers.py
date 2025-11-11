"""Gemeinsame Helfer für Formatierungen & Bilddarstellung, ausgelagert für bessere Wiederverwendbarkeit."""

from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO
from typing import Any

from PIL import Image

# Diese Mapping-Tabellen werden von mehreren Seiten genutzt, daher ziehen wir sie in ein eigenes Modul.
IMAGE_MIME_MAP = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
    "WEBP": "image/webp",
    "HEIF": "image/heif",
    "HEIC": "image/heic",
}

STATUS_STYLE_MAP = {
    "pending": {"label": "Ausstehend", "classes": "bg-amber-100 text-amber-700"},
    "processed": {"label": "Bestätigt", "classes": "bg-emerald-100 text-emerald-600"},
    "error": {"label": "Fehler", "classes": "bg-red-100 text-red-600"},
}
DEFAULT_STATUS_STYLE = {"label": "Unbekannt", "classes": "bg-grey-200 text-grey-600"}

CATEGORY_STYLE_MAP = {
    "Restaurant": "bg-blue-100 text-blue-700",
    "Lebensmittel": "bg-emerald-100 text-emerald-600",
    "Transport": "bg-amber-100 text-amber-700",
    "Kleidung": "bg-purple-100 text-purple-600",
}
DEFAULT_CATEGORY_STYLE = "bg-grey-200 text-grey-700"
STATUS_BADGE_BASE = "text-caption font-medium px-3 py-1 rounded-full"
CATEGORY_BADGE_BASE = "text-caption font-medium px-3 py-1 rounded-full"

_PLACEHOLDER_SVG = """
<svg xmlns='http://www.w3.org/2000/svg' width='400' height='300' viewBox='0 0 400 300'>
  <defs>
    <linearGradient id='grad' x1='0%' y1='0%' x2='100%' y2='100%'>
      <stop offset='0%' stop-color='#f4f6fb'/>
      <stop offset='100%' stop-color='#e9edf7'/>
    </linearGradient>
  </defs>
  <rect fill='url(#grad)' width='400' height='300'/>
  <g fill='#b0b8d1'>
    <path d='M160 90h80a10 10 0 0 1 10 10v140H150V100a10 10 0 0 1 10-10z' opacity='0.25'/>
    <path d='M170 110h60v100h-60z' opacity='0.3'/>
    <circle cx='200' cy='140' r='12' opacity='0.4'/>
    <rect x='175' y='170' width='50' height='12' rx='6' opacity='0.35'/>
  </g>
</svg>
""".strip()

PLACEHOLDER_IMAGE_DATA_URL = (
    "data:image/svg+xml;base64," + base64.b64encode(_PLACEHOLDER_SVG.encode("utf-8")).decode("ascii")
)


def _guess_image_media_type(image_bytes: bytes | None) -> str:
    """Bestimmt den MIME-Typ eines Bildes anhand der Bytes und liefert einen sinnvollen Standard."""
    if not image_bytes:
        return "application/octet-stream"
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            fmt = (img.format or "").upper()
    except Exception:
        fmt = ""
    return IMAGE_MIME_MAP.get(fmt, "image/jpeg")


def _format_date(date_value: str | None) -> str:
    """Formatiert ISO-Daten in ein deutschsprachiges Datum (z.B. '30. Sept. 2024')."""
    if not date_value:
        return "-"
    try:
        parsed = datetime.fromisoformat(date_value)
        return parsed.strftime("%d. %b %Y")
    except ValueError:
        return date_value


def _format_amount(amount: float | None, currency: str | None = None) -> str:
    """Formatiert Beträge mit zwei Nachkommastellen und optionaler Währung."""
    if amount is None:
        return "-"
    currency_code = (currency or "CHF").upper()
    formatted = f"{amount:,.2f}".replace(",", "'")
    return f"{currency_code} {formatted}"


def _image_to_data_url(image_bytes: bytes | None) -> str | None:
    """Wandelt Rohbytes eines Bildes in eine base64-Data-URL um."""
    if not image_bytes:
        return None
    encoded = base64.b64encode(image_bytes).decode("ascii")
    mime = _guess_image_media_type(image_bytes)
    return f"data:{mime};base64,{encoded}"
