"""Geschäftslogik zum Validieren und Speichern hochgeladener Belegdateien."""

from __future__ import annotations

from app.db import insert_receipt
from app.helpers.image_helpers import normalize_upload_image

MAX_BYTES = 20 * 1024 * 1024  # 20 MB safety limit after normalization


def process_receipt_upload(user_id: int, content: bytes, filename: str | None) -> dict:
    """
    Prüft eine hochgeladene Datei und speichert sie über die Datenbankschicht.

    Parameter:
        user_id: Benutzer-ID, der der Beleg zugeordnet wird.
        content: Rohbytes der Datei.
        filename: Optionaler ursprünglicher Dateiname (nur für Metadaten).

    Rückgabe:
        dict mit den gespeicherten Metadaten zum Beleg.

    Ausnahmen:
        ValueError: Wenn die Datei leer ist oder das Größenlimit überschreitet.
    """
    if not content:
        raise ValueError("Die hochgeladene Datei ist leer.")

    normalized_content, mime_type = normalize_upload_image(content)
    if len(normalized_content) > MAX_BYTES:
        raise ValueError("Die Datei ist zu groß (maximal 20 MB).")

    db_result = insert_receipt(user_id, normalized_content)
    result = {
        "ok": True,
        "filename": filename or "upload.bin",
        "size_bytes": len(normalized_content),
    }
    if mime_type:
        result["mime_type"] = mime_type
    result.update(db_result)
    return result
