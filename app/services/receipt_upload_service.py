"""Business logic for validating and storing uploaded receipt files."""

from __future__ import annotations

from app.db import insert_receipt

MAX_BYTES = 20 * 1024 * 1024  # 20 MB safety limit for uploads


def process_receipt_upload(user_id: int, content: bytes, filename: str | None) -> dict:
    """
    Validates an uploaded file and persists it using the database layer.

    Args:
        user_id: ID of the user performing the upload.
        content: Raw file contents.
        filename: Optional original filename (used for metadata only).

    Returns:
        dict: database metadata about the stored receipt plus file info.

    Raises:
        ValueError: if the file is empty or exceeds the max size.
    """
    if not content:
        raise ValueError("Die hochgeladene Datei ist leer.")
    if len(content) > MAX_BYTES:
        raise ValueError("Die Datei ist zu groß (maximal 20 MB).")

    db_result = insert_receipt(user_id, content)
    result = {
        "ok": True,
        "filename": filename or "upload.bin",
        "size_bytes": len(content),
    }
    result.update(db_result)
    return result


__all__ = ["process_receipt_upload", "MAX_BYTES"]

