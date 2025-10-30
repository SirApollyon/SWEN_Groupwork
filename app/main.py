# -*- coding: utf-8 -*-
"""
Einfaches FastAPI + NiceGUI Frontend zum Hochladen und Analysieren von Belegen.

Diese Datei ist der Haupteinstiegspunkt der Anwendung.
Sie verwendet das FastAPI-Framework für die API-Endpunkte und NiceGUI für die Benutzeroberfläche.
"""

# Importieren der notwendigen Bibliotheken
import asyncio
import base64
import os
from datetime import datetime
from io import BytesIO
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from nicegui import ui
from app.db import (
    get_receipt_detail,
    insert_receipt,
    list_receipts_overview,
    load_receipt_image,
)  # DB-Helfer
from app.receipt_analysis import analyze_receipt  # Funktion zur Analyse der Belege
from PIL import Image

# 1. Erstellen der FastAPI-App
# Dies ist die Hauptanwendung, die von einem ASGI-Server wie uvicorn ausgeführt wird.
app = FastAPI(title="Smart Expense Tracker")

# Maximale Dateigröße für den Upload festlegen (hier 20 Megabyte)
MAX_BYTES = 20 * 1024 * 1024

IMAGE_MIME_MAP = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "BMP": "image/bmp",
    "TIFF": "image/tiff",
    "WEBP": "image/webp",
}


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


@app.get("/api/receipts/{receipt_id}/image")
async def api_receipt_image(receipt_id: int):
    """Gibt das gespeicherte Belegbild als HTTP-Response zurǬck."""
    try:
        record = await asyncio.to_thread(load_receipt_image, receipt_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    image_bytes = record.get("receipt_image")
    if not image_bytes:
        raise HTTPException(
            status_code=404, detail="Kein Bild fǬr diesen Beleg gespeichert."
        )

    media_type = _guess_image_media_type(image_bytes)
    return Response(content=image_bytes, media_type=media_type)


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
        return ui.context.client.content.path
    except Exception:
        return '/'

def nav():
    with ui.header().classes('justify-center bg-white/70 backdrop-blur-md'):
        with ui.row().classes('items-center gap-2'):
            p = current_path()
            nav_item('Home',      'home',           '/',         active=(p == '/'))
            nav_item('Upload',    'upload',         '/upload',   active=(p == '/upload'))
            nav_item('Receipts',  'receipt_long',   '/receipts', active=(p == '/receipts'))
            nav_item('Dashboard', 'dashboard',      '/dashboard',active=(p == '/dashboard'))
            nav_item('Settings', 'settings',      '/settings',active=(p == '/settings'))

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
             **Belege hochladen**,  
             **automatisch analysieren lassen**  
            und  übersichtlich im **Dashboard auswerten**.  
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

    receipts: list[dict] = []
    filtered: list[dict] = []
    category_options: list[str] = ["Alle Kategorien"]

    with ui.column().classes(
        "w-full items-center min-h-screen gap-6 q-pa-xl bg-gradient-to-b from-blue-50 to-white"
    ):
        header_row = ui.row().classes("w-full max-w-6xl items-end justify-between")
        with header_row:
            ui.label("Belegübersicht").classes("text-h5 font-semibold text-grey-9")
            total_count_label = ui.label("0 Belege").classes("text-caption text-grey-6")

        search_input = ui.input(label="").props(
            'dense filled rounded clearable placeholder="Belege suchen..."'
        )
        search_input.classes("w-full max-w-6xl bg-white/90 shadow-sm")
        with search_input.add_slot("prepend"):
            ui.icon("search").classes("text-grey-5")

        filter_card = ui.card().classes(
            "w-full max-w-6xl bg-white/90 backdrop-blur rounded-2xl border border-white/70 shadow-sm"
        )
        with filter_card:
            with ui.row().classes("w-full items-center justify-between gap-4"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("style").classes(
                        "text-primary text-2xl bg-primary/10 rounded-full p-2"
                    )
                    with ui.column().classes("gap-0"):
                        category_title = ui.label("Alle Kategorien").classes(
                            "text-body1 font-medium text-grey-9"
                        )
                        category_hint = ui.label("Kein Filter aktiv").classes(
                            "text-caption text-grey-6"
                        )
                category_select = ui.select(
                    options=category_options,
                    value="Alle Kategorien",
                    label="",
                ).props('dense outlined rounded clearable clear-icon="close"')
                category_select.classes("min-w-[220px]")

        loading_container = ui.row().classes(
            "w-full max-w-6xl justify-center items-center gap-2 text-grey-6"
        )
        with loading_container:
            ui.spinner("dots").classes("text-primary")
            ui.label("Belege werden geladen ...")

        cards_container = ui.row().classes(
            "w-full max-w-6xl gap-4 flex-wrap justify-start items-stretch"
        )

    detail_dialog = ui.dialog()
    with detail_dialog, ui.card().classes(
        "max-w-4xl w-[760px] bg-white/95 backdrop-blur border border-white/80 shadow-xl p-6"
    ):
        with ui.row().classes("w-full gap-6"):
            with ui.column().classes("w-5/12 gap-3"):
                ui.label("Beleg-Vorschau").classes("text-body1 font-semibold text-grey-8")
                detail_image = ui.image(PLACEHOLDER_IMAGE_DATA_URL).classes(
                    "w-full h-72 object-cover rounded-xl bg-grey-2"
                )
                detail_image.props("fit=cover")
                detail_caption = ui.label("").classes("text-caption text-grey-6")
            with ui.column().classes("w-7/12 gap-3"):
                with ui.row().classes("items-center justify-between gap-2"):
                    ui.label("Extrahierte Informationen").classes(
                        "text-body1 font-semibold text-grey-8"
                    )
                    detail_status_badge = ui.label("Unbekannt").classes(
                        f"{STATUS_BADGE_BASE} bg-grey-200 text-grey-600"
                    )
                detail_info_label = ui.label("").classes("text-caption text-primary")
                with ui.row().classes("gap-3 w-full"):
                    date_field = ui.input("Datum").props(
                        "readonly dense filled rounded"
                    )
                    with date_field.add_slot("prepend"):
                        ui.icon("event").classes("text-primary")
                    amount_field = ui.input("Betrag").props(
                        "readonly dense filled rounded"
                    )
                    with amount_field.add_slot("prepend"):
                        ui.icon("payments").classes("text-primary")
                with ui.row().classes("gap-3 w-full"):
                    merchant_field = ui.input("Händler").props(
                        "readonly dense filled rounded"
                    )
                    with merchant_field.add_slot("prepend"):
                        ui.icon("storefront").classes("text-primary")
                    category_field = ui.input("Kategorie").props(
                        "readonly dense filled rounded"
                    )
                    with category_field.add_slot("prepend"):
                        ui.icon("local_offer").classes("text-primary")
                ui.label("Vom System vorgeschlagen").classes("text-caption text-grey-5")
        with ui.row().classes("justify-end gap-3 w-full mt-4"):
            ui.button("Bestätigen", on_click=detail_dialog.close).classes(
                "bg-emerald-500 text-white px-6 rounded-full"
            )
            ui.button("Abbrechen", on_click=detail_dialog.close).classes(
                "bg-white text-grey-7 border border-grey-4 px-6 rounded-full"
            )

    def update_header() -> None:
        if not receipts:
            total_count_label.set_text("Keine Belege vorhanden")
        else:
            total_count_label.set_text(
                f"{len(filtered)} von {len(receipts)} Belegen angezeigt"
            )

    def apply_filters() -> None:
        nonlocal filtered, category_options

        term = (search_input.value or "").strip().lower()
        selected = category_select.value or "Alle Kategorien"
        if selected not in category_options:
            selected = "Alle Kategorien"
            category_select.value = selected

        if selected == "Alle Kategorien":
            category_title.set_text("Alle Kategorien")
            category_hint.set_text("Kein Filter aktiv")
        else:
            category_title.set_text(selected)
            category_hint.set_text("Filter aktiv")

        filtered = []
        for receipt in receipts:
            category_name = receipt.get("category_name") or "Ohne Kategorie"
            if selected != "Alle Kategorien" and category_name != selected:
                continue
            haystack = " ".join(
                filter(
                    None,
                    [
                        receipt.get("issuer_name"),
                        receipt.get("issuer_city"),
                        receipt.get("description"),
                        category_name,
                    ],
                )
            ).lower()
            if term and term not in haystack:
                continue
            filtered.append(receipt)

        render_cards()

    def render_cards() -> None:
        cards_container.clear()
        update_header()

        if not filtered:
            with cards_container:
                empty_card = ui.card().classes(
                    "w-full bg-white/85 border border-dashed border-grey-3 rounded-2xl p-8 text-grey-6 items-center gap-2"
                )
                with empty_card:
                    ui.icon("receipt_long").classes("text-3xl text-grey-5")
                    ui.label("Keine Belege gefunden.").classes("text-body2 text-grey-6")
                    ui.label("Passe Suche oder Filter an.").classes(
                        "text-caption text-grey-5"
                    )
            return

        for receipt in filtered:
            receipt_id = receipt.get("receipt_id")
            title = (
                receipt.get("issuer_name")
                or receipt.get("description")
                or f"Beleg #{receipt_id}"
            )
            city = receipt.get("issuer_city")
            date_value = receipt.get("transaction_date") or receipt.get("upload_date")
            formatted_date = _format_date(date_value)
            amount_value = _format_amount(receipt.get("amount"), receipt.get("currency"))
            category_name = receipt.get("category_name") or "Ohne Kategorie"
            category_classes = CATEGORY_STYLE_MAP.get(
                category_name, DEFAULT_CATEGORY_STYLE
            )
            status_key = (receipt.get("status_name") or "").lower()
            status_style = STATUS_STYLE_MAP.get(status_key, DEFAULT_STATUS_STYLE)
            image_source = (
                f"/api/receipts/{receipt_id}/image"
                if receipt.get("has_image")
                else PLACEHOLDER_IMAGE_DATA_URL
            )

            with cards_container:
                card = ui.card().classes(
                    "receipt-card w-full max-w-[320px] min-w-[260px] bg-white/85 backdrop-blur "
                    "border border-white/70 rounded-2xl overflow-hidden shadow-lg transition-all "
                    "cursor-pointer hover:-translate-y-1 hover:shadow-xl"
                )
                card.on(
                    "click",
                    lambda e, rid=receipt_id: asyncio.create_task(
                        show_receipt_detail(rid)
                    ),
                )
                with card:
                    ui.image(image_source).classes("w-full h-40 object-cover").props(
                        "fit=cover"
                    )
                    with ui.column().classes("p-4 gap-3"):
                        with ui.column().classes("gap-1"):
                            ui.label(title).classes(
                                "text-body1 font-semibold text-grey-9 truncate"
                            )
                            with ui.row().classes(
                                "items-center gap-1 text-caption text-grey-6"
                            ):
                                ui.icon("event").classes("text-sm text-grey-5")
                                ui.label(formatted_date)
                            if city:
                                with ui.row().classes(
                                    "items-center gap-1 text-caption text-grey-5"
                                ):
                                    ui.icon("location_on").classes("text-sm")
                                    ui.label(city)
                        ui.label(amount_value).classes(
                            "text-subtitle1 font-semibold text-grey-8"
                        )
                        with ui.row().classes("justify-between items-center"):
                            ui.label(category_name).classes(
                                f"{CATEGORY_BADGE_BASE} {category_classes}"
                            )
                            ui.label(status_style["label"]).classes(
                                f"{STATUS_BADGE_BASE} {status_style['classes']}"
                            )

    async def show_receipt_detail(receipt_id: int) -> None:
        detail_dialog.open()
        detail_caption.set_text(f"Beleg #{receipt_id}")
        detail_status_badge.set_text("Lade ...")
        detail_status_badge.classes(
            f"{STATUS_BADGE_BASE} bg-blue-100 text-blue-600"
        )
        detail_info_label.set_text("Beleg wird geladen ...")
        detail_info_label.classes("text-caption text-primary")
        detail_image.set_source(PLACEHOLDER_IMAGE_DATA_URL)
        date_field.value = ""
        amount_field.value = ""
        merchant_field.value = ""
        category_field.value = ""

        try:
            payload = await asyncio.to_thread(get_receipt_detail, receipt_id)
        except Exception as exc:
            detail_info_label.set_text(f"Fehler beim Laden: {exc}")
            detail_info_label.classes("text-caption text-red-600")
            ui.notify(f"Beleg konnte nicht geöffnet werden: {exc}", color="negative")
            return

        detail_info_label.set_text("")
        receipt_title = (
            payload.get("issuer", {}).get("name")
            or payload.get("transaction", {}).get("description")
            or f"Beleg #{receipt_id}"
        )
        detail_caption.set_text(receipt_title)
        detail_image.set_source(
            _image_to_data_url(payload.get("receipt_image"))
            or PLACEHOLDER_IMAGE_DATA_URL
        )

        txn = payload.get("transaction") or {}
        date_field.value = _format_date(
            txn.get("date") or payload.get("upload_date")
        )
        amount_field.value = _format_amount(
            txn.get("amount"), txn.get("currency")
        )
        merchant_field.value = (
            payload.get("issuer", {}).get("name")
            or txn.get("description")
            or "-"
        )
        category_field.value = txn.get("category_name") or "Ohne Kategorie"

        status_key = (payload.get("status_name") or "").lower()
        status_style = STATUS_STYLE_MAP.get(status_key, DEFAULT_STATUS_STYLE)
        detail_status_badge.set_text(status_style["label"])
        detail_status_badge.classes(
            f"{STATUS_BADGE_BASE} {status_style['classes']}"
        )

        if payload.get("error_message"):
            detail_info_label.set_text(payload["error_message"])
            detail_info_label.classes("text-caption text-red-600")
        elif status_key == "pending":
            detail_info_label.set_text("Die Analyse ist noch ausstehend.")
            detail_info_label.classes("text-caption text-amber-600")
        else:
            detail_info_label.set_text("Analyse erfolgreich abgeschlossen.")
            detail_info_label.classes("text-caption text-emerald-600")

    async def load_data() -> None:
        nonlocal receipts, filtered, category_options
        try:
            data = await asyncio.to_thread(list_receipts_overview, None)
        except Exception as exc:
            loading_container.clear()
            with cards_container:
                error_card = ui.card().classes(
                    "w-full bg-red-50 border border-red-100 text-red-600 p-6 rounded-2xl gap-2"
                )
                with error_card:
                    ui.icon("error").classes("text-red-500")
                    ui.label("Belege konnten nicht geladen werden.").classes(
                        "text-body2"
                    )
                    ui.label(str(exc)).classes("text-caption")
            ui.notify(f"Fehler beim Laden der Belege: {exc}", color="negative")
            return

        receipts = data
        filtered = receipts.copy()
        categories = sorted(
            {r.get("category_name") or "Ohne Kategorie" for r in receipts}
        )
        category_options = ["Alle Kategorien"] + categories
        category_select.options = category_options
        category_select.value = "Alle Kategorien"
        search_input.value = ""

        loading_container.clear()
        apply_filters()

    search_input.on("update:model-value", lambda e: apply_filters())
    category_select.on("update:model-value", lambda e: apply_filters())
    ui.timer(0.1, lambda: asyncio.create_task(load_data()), once=True)
@ui.page('/dashboard')
def dashboard_page():
    nav()
    with ui.column().classes('items-center justify-start min-h-screen gap-4 q-pa-md'):
        ui.label('Dashboard')
        ui.markdown('Hier kannst du Auswertungen und Diagramme anzeigen.')

@ui.page('/settings')
def receipts_page():
    nav()
    with ui.column().classes('items-center justify-start min-h-screen gap-4 q-pa-md'):
        ui.label('Settings')
        ui.markdown('Nutzerangaben wie (Name / Vorname) Budgetanpassung Account (Bank-Kontoverbindung) und Logout Button.')

# 5. Wichtiger Hinweis zum Ausführen der Anwendung:
# Die Funktion ui.run() wird normalerweise nicht direkt aufgerufen, wenn man `uvicorn` vom Terminal startet.
# Für das Deployment wird der Server jedoch programmatisch gestartet (siehe unten).

if __name__ == "__main__":
    # Dieser Block wird nur ausgeführt, wenn die Datei direkt mit `python app/main.py` gestartet wird.
    # Er ist entscheidend für das Deployment auf Plattformen wie Google Cloud Run.
    # Liest den PORT aus den Umgebungsvariablen, mit 8000 als Standard für die lokale Entwicklung.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
