# -*- coding: utf-8 -*-
"""
Einfaches FastAPI + NiceGUI Frontend zum Hochladen und Analysieren von Belegen.

Diese Datei ist der Haupteinstiegspunkt der Anwendung.
Sie verwendet das FastAPI-Framework für die API-Endpunkte und NiceGUI für die Benutzeroberfläche.
"""

import asyncio
import os

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from nicegui import storage as ng_storage, ui

from app.db import delete_receipt, load_receipt_image
from app.helpers.auth_helpers import _ensure_authenticated  # noqa: F401  # Für spätere Programmlogik verfügbar halten
from app.helpers.receipt_helpers import _guess_image_media_type
from app.receipt_analysis import analyze_receipt
from app.services.receipt_upload_service import process_receipt_upload
from app.ui_layout import nav  # noqa: F401  # Wird von den ausgelagerten Seiten genutzt

# 1. Erstellen der FastAPI-App
# Dies ist die Hauptanwendung, die von einem ASGI-Server wie uvicorn ausgeführt wird.
app = FastAPI(title="Smart Expense Tracker")

# NiceGUI-Storage aktivieren (für Benutzerzustand über Seitenwechsel hinweg)
ng_storage.set_storage_secret(os.getenv("NICEGUI_STORAGE_SECRET", "smart-expense-secret"))

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), user_id: int = Form(...)):
    """
    Nimmt eine Datei per REST-API entgegen, speichert sie und startet die Analyse.
    Dieser Endpunkt kann von anderen Programmen oder über die API-Dokumentation (Swagger) genutzt werden.
    """
    try:
        content = await file.read()
        result = await asyncio.to_thread(
            process_receipt_upload, user_id, content, file.filename
        )
        analysis = await analyze_receipt(result["receipt_id"], user_id)
        result["analysis"] = analysis
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/receipts/{receipt_id}/analyze")
async def api_analyze_receipt(receipt_id: int, user_id: int | None = None):
    """
    Analysiert einen bereits in der Datenbank gespeicherten Beleg.
    Kann z.B. aufgerufen werden, wenn eine Analyse erneut durchgeführt werden soll.
    """
    try:
        analysis = await analyze_receipt(receipt_id, user_id)
        return {"receipt_id": receipt_id, "analysis": analysis}
    except ValueError as e:
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/receipts/{receipt_id}/image")
async def api_receipt_image(receipt_id: int):
    """Gibt das gespeicherte Belegbild als HTTP-Response zurück."""
    try:
        record = await asyncio.to_thread(load_receipt_image, receipt_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    image_bytes = record.get("receipt_image")
    if not image_bytes:
        raise HTTPException(
            status_code=404, detail="Kein Bild für diesen Beleg gespeichert."
        )

    media_type = _guess_image_media_type(image_bytes)
    return Response(content=image_bytes, media_type=media_type)


@app.delete("/api/receipts/{receipt_id}")
async def api_delete_receipt(receipt_id: int, user_id: int | None = None):
    """Löscht einen bestehenden Beleg endgültig."""
    try:
        await asyncio.to_thread(delete_receipt, receipt_id, user_id=user_id)
    except ValueError as exc:
        message = str(exc)
        status = 404 if "nicht gefunden" in message.lower() else 400
        raise HTTPException(status_code=status, detail=message) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "receipt_id": receipt_id}


# 2. NiceGUI an die FastAPI-App anbinden (nach den API-Routen, damit Catch-All-Routen nicht dazwischenfunken)
ui.run_with(app)

# Das Theme-Modul kapselt Farben und globale Styles, damit main.py aufgeräumt bleibt.
from app.ui_theme import set_colors, set_global_styles

# Diese Aufrufe stellen sicher, dass Farben und CSS direkt zum Start gesetzt werden.
set_colors()
set_global_styles()

# Durch das Importieren der Page-Module werden die @ui.page-Routen registriert.
from app.ui_pages import (  # noqa: F401
    dashboard_extended_page,
    home_page,
    login_page,
    receipts_page,
    settings_page,
    upload_page,
)


# 5. Wichtiger Hinweis zum Ausführen der Anwendung:
# Die Funktion ui.run() wird normalerweise nicht direkt aufgerufen, wenn man `uvicorn` vom Terminal startet.
# Für das Deployment wird der Server jedoch programmatisch gestartet (siehe unten).

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
