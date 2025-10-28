# -*- coding: utf-8 -*-
"""
Einfaches FastAPI + NiceGUI Frontend zum Hochladen und Analysieren von Belegen.

Diese Datei ist der Haupteinstiegspunkt der Anwendung.
Sie verwendet das FastAPI-Framework für die API-Endpunkte und NiceGUI für die Benutzeroberfläche.
"""

# Importieren der notwendigen Bibliotheken
import asyncio
import os
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from nicegui import ui
from app.db import insert_receipt  # DB-Helfer
from app.receipt_analysis import analyze_receipt  # Funktion zur Analyse der Belege

# 1. Erstellen der FastAPI-App
# Dies ist die Hauptanwendung, die von einem ASGI-Server wie uvicorn ausgeführt wird.
app = FastAPI(title="Smart Expense Tracker")

# Maximale Dateigröße für den Upload festlegen (hier 20 Megabyte)
MAX_BYTES = 20 * 1024 * 1024


def process_receipt_upload(user_id: int, content: bytes, filename: str | None) -> dict:
    """
    Überprüft die hochgeladene Datei und speichert sie in der Datenbank.

    Args:
        user_id: Die ID des Benutzers, der den Beleg hochlädt.
        content: Der Inhalt der Datei als Bytes.
        filename: Der ursprüngliche Dateiname.

    Returns:
        Ein Dictionary mit dem Ergebnis des Speichervorgangs.

    Raises:
        ValueError: Wenn die Datei leer ist oder die maximale Größe überschreitet.
    """
    # Überprüfen, ob die Datei leer ist
    if not content:
        raise ValueError("Die hochgeladene Datei ist leer.")

    # Überprüfen, ob die Datei zu groß ist
    if len(content) > MAX_BYTES:
        raise ValueError("Die Datei ist zu groß (maximal 20 MB).")

    # Beleg in der Datenbank speichern
    db_result = insert_receipt(user_id, content)

    # Ergebnis-Dictionary erstellen und zurückgeben
    result = {
        "ok": True,
        "filename": filename or "upload.bin",
        "size_bytes": len(content),
    }
    # Die Ergebnisse aus der Datenbank zum Dictionary hinzufügen
    result.update(db_result)

    return result


# 3. FastAPI Endpunkte (für API-Aufrufe, z.B. über Swagger UI)


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), user_id: int = Form(...)):
    """
    Nimmt eine Datei per REST-API entgegen, speichert sie und startet die Analyse.
    Dieser Endpunkt kann von anderen Programmen oder über die API-Dokumentation (Swagger) genutzt werden.
    """
    try:
        # Inhalt der hochgeladenen Datei lesen
        content = await file.read()

        # Datei verarbeiten und speichern (blockierenden DB-Zugriff in Thread auslagern)
        result = await asyncio.to_thread(
            process_receipt_upload, user_id, content, file.filename
        )

        # Analyse des gespeicherten Belegs anstoßen
        analysis = await analyze_receipt(result["receipt_id"], user_id)

        # Analyseergebnis zum Ergebnis-Dictionary hinzufügen
        result["analysis"] = analysis

        return result
    except Exception as e:
        # Bei Fehlern eine HTTP-Fehlermeldung zurückgeben
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/receipts/{receipt_id}/analyze")
async def api_analyze_receipt(receipt_id: int, user_id: int | None = None):
    """
    Analysiert einen bereits in der Datenbank gespeicherten Beleg.
    Kann z.B. aufgerufen werden, wenn eine Analyse erneut durchgeführt werden soll.
    """
    try:
        # Analyse für den gegebenen Beleg durchführen
        analysis = await analyze_receipt(receipt_id, user_id)
        return {"receipt_id": receipt_id, "analysis": analysis}
    except ValueError as e:
        # Spezifische Fehlerbehandlung für "nicht gefunden"
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except Exception as e:
        # Allgemeine Fehlerbehandlung
        raise HTTPException(status_code=500, detail=str(e))


# 2. NiceGUI an die FastAPI-App anbinden (nach den API-Routen, damit Catch-All-Routen nicht dazwischenfunken)
ui.run_with(app)

# Navigation extrahieren, damit sie auf jeder Seite erscheint
def nav_item(label: str, icon: str, path: str, active: bool = False):
    color = 'text-primary' if active else 'text-grey-7'
    with ui.row().classes(f'items-center gap-1 cursor-pointer {color}') \
                 .on('click', lambda: ui.navigate.to(path)):
        ui.icon(icon)
        ui.link(label, path).classes('no-underline')

def current_path() -> str:
    try:
        return ui.get_client().content.path
    except:
        return '/'

def nav():
    with ui.header().classes('justify-center bg-white/70 backdrop-blur-md'):
        with ui.row().classes('items-center gap-2'):
            p = current_path()
            nav_item('Home',      'home',           '/',         active=(p == '/'))
            nav_item('Upload',    'upload',         '/upload',   active=(p == '/upload'))
            nav_item('Receipts',  'receipt_long',   '/receipts', active=(p == '/receipts'))
            nav_item('Dashboard', 'dashboard',      '/dashboard',active=(p == '/dashboard'))

# Navigation / Menüleiste
@ui.page('/')
def home_page():
    nav()
    with ui.column().classes('items-center justify-center h-screen text-center gap-4 q-px-xl'
                             ):
        ui.icon('emoji_objects').classes('text-6xl text-primary')
        ui.label('Willkommen beim Smart Expense Tracker!').classes('text-h4 font-semibold')
        
        ui.markdown(
            """
            Mit dem **Smart Expense Tracker** kannst du deine Ausgaben ganz einfach digital verwalten:  
            📸 **Belege hochladen**,  
            🧾 **automatisch analysieren lassen**  
            und 📊 übersichtlich im **Dashboard auswerten**.  
            """
        ).classes('text-body1 text-grey-7 max-w-2xl')

        ui.label('Wähle oben einen Menüpunkt aus, um zu starten.').classes('text-body2 text-grey-7')

# 4. Drei Hauptregister

@ui.page('/upload')
def upload_page():
    nav()
    with ui.column().classes('items-center justify-start q-mt-xl gap-3 q-pa-md'):
        ui.markdown("## Beleg hochladen")

    # Eingabefeld für die Benutzer-ID
    user_input = ui.number(label="Benutzer-ID", value=1, min=1)
    user_input.props('dense outlined style="max-width:200px"')
    user_input.classes("mb-2")

    ui.markdown(
        "Wähle ein Bild von deinem Computer aus **oder** mache ein Foto mit deiner Kamera."
    )

    # Ein Label, um den Status anzuzeigen (z.B. "Upload erfolgreich")
    status_label = ui.markdown("-").classes("mt-4")

    # Ein Dictionary, um die zuletzt ausgewählte Datei zu speichern.
    # Wir brauchen das, weil wir zwei Upload-Möglichkeiten haben (Datei und Kamera)
    # und wir uns merken müssen, welche Datei der Benutzer zuletzt ausgewählt hat.
    selected_files: dict[str, dict | None] = {"upload": None, "camera": None}

    async def remember_file(kind: str, event) -> None:
        """
        Speichert die Informationen der hochgeladenen Datei im `selected_files` Dictionary.
        Wird aufgerufen, wenn eine Datei über das Upload- oder Kamera-Element ausgewählt wird.
        """
        file_info = {
            "name": event.file.name or "receipt.bin",
            "content": await event.file.read(),
        }
        selected_files[kind] = file_info
        status_label.set_content(f'{kind.title()} bereit: {file_info["name"]}')

    # Upload-Element für Dateien vom Computer
    upload_widget = ui.upload(
        label="Datei auswählen oder hierher ziehen", auto_upload=True, multiple=False
    )
    upload_widget.props('accept=".heic,.heif,.jpg,.jpeg,.png,.webp,image/*"')
    upload_widget.classes("max-w-xl")
    # Wenn eine Datei hochgeladen wird, rufe `remember_file` auf
    upload_widget.on_upload(lambda event: remember_file("upload", event))

    # Upload-Element für die Kamera (besonders für Mobilgeräte)
    camera_widget = ui.upload(
        label="Foto aufnehmen (mobil)", auto_upload=True, multiple=False
    )
    camera_widget.props('accept="image/*" capture=environment')
    camera_widget.classes("max-w-xl")
    # Wenn ein Foto gemacht wird, rufe `remember_file` auf
    camera_widget.on_upload(lambda event: remember_file("camera", event))

    async def run_full_flow(selected: dict | None) -> None:
        """
        Führt den gesamten Prozess aus: Eingaben validieren, Beleg speichern, analysieren und Ergebnis anzeigen.
        """
        # Prüfen, ob eine Datei ausgewählt wurde
        if not selected:
            status_label.set_content("Bitte wähle zuerst eine Datei aus.")
            return

        try:
            # Benutzer-ID aus dem Eingabefeld holen und validieren
            user_id = int(user_input.value or 0)
            if user_id < 1:
                status_label.set_content(
                    "Bitte gib eine gültige Benutzer-ID (>= 1) ein."
                )
                return

            # Schritt 1: Datei verarbeiten und in der Datenbank speichern
            status_label.set_content("Beleg wird hochgeladen und gespeichert...")
            upload_result = await asyncio.to_thread(
                process_receipt_upload,
                user_id,
                selected["content"],
                selected["name"],
            )

            # Schritt 2: Beleg analysieren
            status_label.set_content("Analyse wird durchgeführt...")
            analysis = await analyze_receipt(upload_result["receipt_id"], user_id)

            # Analyseergebnis zum Ergebnis hinzufügen
            upload_result["analysis"] = analysis

            # Schritt 3: Endergebnis anzeigen
            status_label.set_content(f"Upload & Analyse erfolgreich:\n{upload_result}")

        except Exception as error:
            # Bei Fehlern eine einfache Fehlermeldung anzeigen
            status_label.set_content(f"Fehler: {error!s}")

    # Button, um den Upload vom Computer zu starten
    ui.button(
        "Vom Computer hochladen",
        on_click=lambda: run_full_flow(selected_files["upload"]),
    )
    # Button, um den Upload von der Kamera zu starten
    ui.button(
        "Von der Kamera hochladen",
        on_click=lambda: run_full_flow(selected_files["camera"]),
    )

@ui.page('/receipts')
def receipts_page():
    nav()
    with ui.column().classes('items-center justify-start min-h-screen gap-4 q-pa-md'):
        ui.label('📄 Gespeicherte Belege')
        ui.markdown('Hier könnte eine Tabelle mit allen Belegen angezeigt werden.')

@ui.page('/dashboard')
def dashboard_page():
    nav()
    with ui.column().classes('items-center justify-start min-h-screen gap-4 q-pa-md'):
        ui.label('📊 Dashboard')
        ui.markdown('Hier kannst du Auswertungen und Diagramme anzeigen.')

# 5. Wichtiger Hinweis zum Ausführen der Anwendung:
# Die Funktion ui.run() wird normalerweise nicht direkt aufgerufen, wenn man `uvicorn` vom Terminal startet.
# Für das Deployment wird der Server jedoch programmatisch gestartet (siehe unten).

if __name__ == "__main__":
    # Dieser Block wird nur ausgeführt, wenn die Datei direkt mit `python app/main.py` gestartet wird.
    # Er ist entscheidend für das Deployment auf Plattformen wie Google Cloud Run.
    # Liest den PORT aus den Umgebungsvariablen, mit 8000 als Standard für die lokale Entwicklung.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
