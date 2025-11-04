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
from nicegui import ui, app as ng_app, storage as ng_storage
from app.db import (
    authenticate_user,
    create_user,
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

# NiceGUI-Storage aktivieren (für Benutzerzustand über Seitenwechsel hinweg)
ng_storage.set_storage_secret(os.getenv("NICEGUI_STORAGE_SECRET", "smart-expense-secret"))

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

# ------------------ Login-Helfer ------------------
def _get_user_store(create: bool = False) -> dict | None:
    """Liefert den benutzerspezifischen Storage (persistiert über Seitenwechsel)."""
    try:
        store = ng_app.storage.user
        if store is not None:
            return store
    except Exception:
        store = None

    client = getattr(ui.context, "client", None)
    if not client:
        return None
    root_storage = getattr(client, "storage", None)
    if not root_storage:
        return None

    contains_user_key = False
    try:
        contains_user_key = "user" in root_storage  # type: ignore[operator]
    except Exception:
        contains_user_key = False

    if not contains_user_key:
        if not create:
            return None
        try:
            root_storage["user"] = {}  # type: ignore[index]
        except Exception:
            try:
                setattr(root_storage, "user", {})
            except Exception:
                return None

    store = None
    getter = getattr(root_storage, "get", None)
    if callable(getter):
        try:
            store = getter("user")
        except Exception:
            store = None
    if store is None:
        try:
            store = getattr(root_storage, "user")
        except Exception:
            store = None

    if isinstance(store, dict):
        return store

    if store is None:
        if not create:
            return None
        normalized: dict = {}
    else:
        try:
            normalized = dict(store)
        except TypeError:
            normalized = {}

    stored_ok = False
    try:
        root_storage["user"] = normalized  # type: ignore[index]
        stored_ok = True
    except Exception:
        pass
    if not stored_ok:
        try:
            setattr(root_storage, "user", normalized)
            stored_ok = True
        except Exception:
            return None

    refreshed = None
    if stored_ok:
        getter = getattr(root_storage, "get", None)
        if callable(getter):
            try:
                refreshed = getter("user")
            except Exception:
                refreshed = None
        if refreshed is None:
            try:
                refreshed = getattr(root_storage, "user")
            except Exception:
                refreshed = None

    return refreshed if isinstance(refreshed, dict) else normalized


def _get_logged_in_user() -> dict | None:
    """Liest die gespeicherten Benutzerdaten aus dem Browser-Speicher."""
    storage = _get_user_store(create=False)
    if storage is None:
        return None

    guest_flag = storage.get("guest")
    if guest_flag:
        return {
            "user_id": None,
            "email": None,
            "name": "Gastmodus",
            "guest": True,
        }

    user_id = storage.get("user_id")
    if user_id is None:
        return None
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        return None
    return {
        "user_id": user_id_int,
        "email": storage.get("email"),
        "name": storage.get("name"),
        "guest": bool(storage.get("guest")),
    }


def _set_logged_in_user(user: dict) -> None:
    """Speichert Benutzerinformationen nach erfolgreicher Anmeldung."""
    store = _get_user_store(create=True)
    if store is None:
        return
    store.pop("guest", None)
    store["user_id"] = int(user.get("user_id"))
    store["email"] = user.get("email")
    store["name"] = user.get("name")


def _set_guest_user() -> None:
    """Aktiviert den Gastmodus ohne Anmeldung."""
    store = _get_user_store(create=True)
    if store is None:
        return
    store.clear()
    store["user_id"] = 1
    store["email"] = None
    store["name"] = "Demo-Konto"
    store["guest"] = False


def _clear_logged_in_user() -> None:
    """Löscht gespeicherte Anmeldedaten (z.B. beim Ausloggen)."""
    store = _get_user_store(create=False)
    if not store:
        return
    try:
        store.clear()
    except AttributeError:
        for key in list(store.keys()):
            del store[key]


def _redirect_to_login(message: str | None = None) -> None:
    """Zeigt einen kurzen Hinweis und leitet anschließend zur Login-Seite um."""
    ui.timer(0.1, lambda: ui.navigate.to("/login"), once=True)
    with ui.column().classes(
        "items-center justify-center h-screen gap-3 text-grey-6"
    ):
        ui.spinner("dots").classes("text-primary text-4xl")
        ui.label(message or "Weiterleitung zum Login ...").classes(
            "text-body2 text-grey-6"
        )


def _ensure_authenticated(message: str | None = None) -> dict | None:
    """Gibt den eingeloggten Benutzer zurück oder leitet andernfalls zum Login um."""
    user = _get_logged_in_user()
    if not user:
        _redirect_to_login(message)
        return None
    return user


def _logout_and_redirect() -> None:
    """Meldet den aktuellen Benutzer ab und führt zurück zur Login-Seite."""
    try:
        _clear_logged_in_user()
    finally:
        ui.navigate.to("/login")


# Navigation: linke Sidebar à la Figma
def _current_path() -> str:
    try:
        return ui.context.client.content.path
    except Exception:
        return '/'

def _side_nav_item(label: str, icon: str, path: str, active: bool = False) -> None:
    base = (
        'w-full items-center gap-2 px-3 py-2 rounded-xl cursor-pointer '
        'transition-all'
    )
    active_cls = (
        'bg-gradient-to-r from-indigo-500 to-indigo-600 text-white shadow-md'
    )
    inactive_cls = 'text-grey-7 hover:bg-indigo-50 hover:text-indigo-700'
    with ui.row().classes(f'{base} {active_cls if active else inactive_cls}')\
                 .on('click', lambda: ui.navigate.to(path)):
        ui.icon(icon).classes('text-[18px]')
        ui.label(label).classes('text-body2 font-medium')

def nav(user: dict):
    # Linke Sidebar mit Titel + Sprachchip und Haupt-Menüpunkten
    p = _current_path()
    display_name = user.get("name") or user.get("email") or "Gast"
    initials = "".join(part[0] for part in display_name.split() if part).upper()[:2]
    with ui.left_drawer(value=True).props('bordered').classes(
        'w-64 bg-white/80 backdrop-blur p-4'
    ):
        with ui.column().classes('gap-3'):
            # Header der App
            with ui.row().classes('items-center justify-between'):
                with ui.column().classes('gap-0'):
                    ui.label('Smart Expense Tracker').classes('text-subtitle1 font-semibold')
                    ui.label('Ihre persönliche Finanzübersicht').classes('text-caption text-grey-6')
                # Sprachchip (ohne Funktion, rein visuell)
                with ui.row().classes(
                    'items-center gap-1 px-2 py-1 rounded-full bg-grey-1 text-grey-7 border'
                ):
                    ui.icon('language').classes('text-grey-6')
                    ui.label('DE').classes('text-caption')

            ui.separator().classes('q-my-sm')

            # Menüeinträge wie im Figma: Übersicht, Belege, Hochladen
            _side_nav_item('Übersicht', 'dashboard', '/dashboard', active=(p == '/dashboard'))
            _side_nav_item('Belege', 'receipt_long', '/receipts', active=(p == '/receipts'))
            _side_nav_item('Hochladen', 'upload', '/upload', active=(p == '/upload'))
            _side_nav_item('Einstellungen', 'settings', '/settings', active=(p == '/settings'))

# ------------------ Monatsswitcher (Header rechts) ------------------
GERMAN_MONTHS = [
    'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
]

def _first_of_month(dt: datetime) -> datetime:
    return dt.replace(day=1)

def _shift_month(dt: datetime, delta: int) -> datetime:
    y, m = dt.year, dt.month
    m0 = (m - 1) + delta
    y += m0 // 12
    m = (m0 % 12) + 1
    return datetime(y, m, 1)

def _format_month_de(dt: datetime) -> str:
    return f"{GERMAN_MONTHS[dt.month - 1]} {dt.year}"

# Fallback-State für Fälle ohne UI-Kontext (Timer/Background)
GLOBAL_SELECTED_MONTH = _first_of_month(datetime.today())

def get_selected_month() -> datetime:
    try:
        client = ui.context.client
        if not hasattr(client, 'selected_month'):
            client.selected_month = _first_of_month(datetime.today())
        return client.selected_month
    except Exception:
        return GLOBAL_SELECTED_MONTH

def set_selected_month(value: datetime) -> None:
    value = _first_of_month(value)
    try:
        ui.context.client.selected_month = value
    except Exception:
        pass
    global GLOBAL_SELECTED_MONTH
    GLOBAL_SELECTED_MONTH = value

def month_bar(username: str = 'Giuliano', on_change=None) -> None:
    current = get_selected_month()
    def update(delta: int) -> None:
        nonlocal current
        current = _shift_month(current, delta)
        set_selected_month(current)
        month_label.set_text(_format_month_de(current))
        if on_change:
            on_change(current)

    with ui.row().classes('items-end gap-3'):
        with ui.column().classes('items-end'):
            ui.label('Aktueller Monat').classes('text-caption text-grey-6')
            month_label = ui.label(_format_month_de(current)).classes(
                'text-h5 text-indigo-600 font-medium'
            )
        with ui.row().classes('items-center gap-1 q-ml-sm'):
            ui.button(icon='chevron_left', on_click=lambda: update(-1)).props('flat round dense')
            ui.button(icon='chevron_right', on_click=lambda: update(1)).props('flat round dense')
        with ui.row().classes('items-center bg-white/90 backdrop-blur border rounded-full px-4 py-2 shadow-sm cursor-pointer hover:bg-blue-50 transition-all').on('click', _logout_and_redirect):
            ui.label('Logout').classes('text-body2 font-medium text-blue-600')

# Login-Seite im Look der gelieferten Vorlage
@ui.page('/login')
def login_page():
    # Wenn bereits angemeldet, direkt weiterleiten
    if _get_logged_in_user():
        ui.timer(0.1, lambda: ui.navigate.to('/dashboard'), once=True)
        with ui.column().classes(
            'items-center justify-center h-screen gap-3 text-white'
        ):
            ui.spinner('dots').classes('text-white text-4xl')
            ui.label('Du bist bereits eingeloggt – einen Moment...').classes(
                'text-body2 text-white/80'
            )
        return

    # -------- Formular-Handler (deutsch kommentiert) --------
    async def handle_login() -> None:
        """Prüft Eingaben und meldet den Benutzer an."""
        status_label.set_text('')
        email = (login_email.value or '').strip()
        password = login_password.value or ''
        if not email or not password:
            status_label.set_text('Bitte E-Mail und Passwort eingeben.')
            return
        try:
            user_data = await asyncio.to_thread(authenticate_user, email, password)
        except ValueError as exc:
            status_label.set_text(str(exc))
            ui.notify(str(exc), color='warning')
            return
        except Exception as exc:
            status_label.set_text('Anmeldung aktuell nicht möglich.')
            ui.notify(f'Fehler bei der Anmeldung: {exc}', color='negative')
            return

        _set_logged_in_user(user_data)
        welcome = user_data.get('name') or user_data.get('email')
        ui.notify(f'Willkommen zurück, {welcome}!', color='positive')
        ui.navigate.to('/dashboard')

    async def handle_signup() -> None:
        """Legt ein neues Konto in Azure SQL an."""
        signup_status.set_text('')
        name = (signup_name.value or '').strip()
        email = (signup_email.value or '').strip()
        password = signup_password.value or ''
        confirm = signup_password_confirm.value or ''

        if not email or not password:
            signup_status.set_text('E-Mail und Passwort sind Pflichtfelder.')
            return
        if password != confirm:
            signup_status.set_text('Die Passwörter stimmen nicht überein.')
            return
        if len(password) < 8:
            signup_status.set_text('Das Passwort sollte mindestens 8 Zeichen haben.')
            return

        try:
            user_data = await asyncio.to_thread(
                create_user, name or None, email, password
            )
        except ValueError as exc:
            signup_status.set_text(str(exc))
            return
        except Exception as exc:
            signup_status.set_text(f'Konto konnte nicht erstellt werden: {exc}')
            return

        _set_logged_in_user(user_data)
        ui.notify('Konto erfolgreich erstellt!', color='positive')
        signup_dialog.close()
        ui.navigate.to('/dashboard')

    def skip_login() -> None:
        """Lädt das Demo-Konto ohne Anmeldung."""
        _set_guest_user()
        ui.notify('Demo-Konto geladen (Benutzer 1).', color='info')
        ui.navigate.to('/dashboard')

    # -------- Layout: linke blaue Bildhälfte, rechte Formularhälfte --------
    signup_dialog = ui.dialog()
    with signup_dialog, ui.card().classes(
        'w-[380px] max-w-full bg-white rounded-[28px] p-6 shadow-2xl gap-4'
    ):
        ui.label('Konto erstellen').classes('text-h6 text-indigo-600 font-semibold')
        ui.label('Fülle die Felder aus, um dein Smart Expense Tracker Konto zu erstellen.')\
            .classes('text-caption text-grey-6')
        signup_name = ui.input('Name (optional)').props('dense outlined rounded')
        signup_email = ui.input('E-Mail').props(
            'dense outlined rounded type=email placeholder="name@example.com"'
        )
        with signup_email.add_slot('prepend'):
            ui.icon('mail').classes('text-indigo-500')
        signup_password = ui.input('Passwort', password=True, password_toggle_button=True)\
            .props('dense outlined rounded placeholder="Mindestens 8 Zeichen"')
        with signup_password.add_slot('prepend'):
            ui.icon('lock').classes('text-indigo-500')
        signup_password_confirm = ui.input('Passwort bestätigen', password=True, password_toggle_button=True)\
            .props('dense outlined rounded')
        with signup_password_confirm.add_slot('prepend'):
            ui.icon('lock_reset').classes('text-indigo-500')
        signup_status = ui.label('').classes('text-caption text-red-500 min-h-[18px]')
        ui.button('Registrieren', on_click=lambda: asyncio.create_task(handle_signup()))\
            .classes('w-full bg-indigo-500 text-white hover:bg-indigo-600 hover:-translate-y-0.5 transition-all shadow-lg rounded-xl')
        ui.button('Abbrechen', on_click=signup_dialog.close).props('flat')\
            .classes('w-full text-indigo-600 hover:text-indigo-700')

    with ui.element('div').classes(
        'min-h-screen w-full bg-[#0F4CFF] flex items-center justify-center px-4 py-10'
    ):
        with ui.element('div').classes(
            'w-full max-w-5xl flex flex-col md:flex-row rounded-[40px] overflow-hidden '
            'shadow-[0_44px_88px_-32px_rgba(15,76,255,0.55)]'
        ):
            with ui.column().classes(
                'w-full md:w-1/2 bg-[#0F4CFF] text-white items-center justify-center py-16 px-12 gap-4'
            ):
                ui.icon('credit_score').classes('text-4xl text-white bg-white/10 rounded-full p-3')
                ui.label('Smart Expense Tracker').classes('text-3xl font-semibold text-white text-center leading-snug')
                ui.label('Behalte Einnahmen und Ausgaben jederzeit im Blick – schnell, sicher und übersichtlich.')\
                    .classes('text-body2 text-white/80 text-center max-w-xs')

            with ui.column().classes('w-full md:w-1/2 bg-[#F4F6FB] items-center justify-center py-14 px-8'):
                with ui.column().classes('w-full max-w-md bg-white border border-[#E5E9F5] rounded-[28px] shadow-lg p-8 gap-5'):
                    with ui.column().classes('gap-1'):
                        ui.html("<span class='text-grey-600 text-sm uppercase tracking-[0.3em]'>Willkommen</span>", sanitize=False)
                        ui.html(
                            "<span class='text-2xl md:text-3xl font-semibold text-grey-900'>Let's "
                            "<span class='text-blue-600'>Sign In</span></span>",
                            sanitize=False,
                        )
                        ui.label('Gib deine Zugangsdaten ein, um mit dem Smart Expense Tracker zu starten.')\
                            .classes('text-caption text-grey-6')
                    login_email = ui.input('E-Mail').props(
                        'dense rounded filled placeholder="name@example.com" type=email'
                    ).classes('rounded-2xl bg-grey-1')
                    with login_email.add_slot('prepend'):
                        ui.icon('mail').classes('text-blue-500')
                    login_password = ui.input('Passwort', password=True, password_toggle_button=True)\
                        .props('dense rounded filled placeholder="••••••••"').classes('rounded-2xl bg-grey-1')
                    with login_password.add_slot('prepend'):
                        ui.icon('lock').classes('text-blue-500')
                    with ui.row().classes('justify-between items-center w-full'):
                        ui.link('Passwort vergessen?', '#').classes(
                            'text-caption text-blue-600 hover:underline'
                        )
                        # Hinweis auf den Gastmodus in Deutsch für Einsteiger
                        ui.label('Gastmodus verfügbar').classes('text-caption text-grey-5')
                    status_label = ui.label('').classes('text-caption text-red-500 min-h-[18px]')
                    ui.button('Sign In', on_click=lambda: asyncio.create_task(handle_login()))\
                        .classes('w-full bg-[#0F4CFF] text-white hover:bg-blue-600 hover:-translate-y-0.5 '
                                 'transition-all shadow-lg rounded-2xl py-3 text-button font-medium')
                    ui.button('Ohne Anmeldung fortfahren', on_click=skip_login).props('flat')\
                        .classes('w-full text-blue-600 hover:text-blue-700')
                    with ui.row().classes('justify-center gap-2 text-caption text-grey-6'):
                        ui.label('Noch kein Konto?')
                        signup_link = ui.link('Sign Up', '#').classes(
                            'text-blue-600 no-underline hover:underline'
                        )
                        signup_link.on('click', lambda _: signup_dialog.open())
# Navigation / Menüleiste
@ui.page('/')
def home_page():
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)
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

# 4. Vier Hauptregister

@ui.page('/upload')
def upload_page():
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)
    if user.get('guest'):
        with ui.column().classes('items-center justify-center min-h-screen gap-4 q-pa-xl text-center'):
            ui.icon('lock').classes('text-4xl text-indigo-500')
            ui.label('Upload im Gastmodus nicht verfügbar').classes('text-h5 text-grey-8')
            ui.label(
                'Bitte melde dich mit einem echten Konto an, um Belege hochzuladen. '
                'Der Gastmodus dient nur zur Vorschau.'
            ).classes('text-body2 text-grey-6 max-w-lg')
            ui.button('Zur Anmeldung', on_click=lambda: ui.navigate.to('/login'))\
                .classes('bg-indigo-500 text-white hover:bg-indigo-600')
        return
    # Neuer Header und Karten im Figma-Stil
    with ui.row().classes('w-full items-end justify-between q-pl-md q-pr-xl q-pt-sm q-pb-sm bg-gradient-to-r from-white to-blue-50/30 border-b border-white/70'):
        with ui.column().classes('gap-0'):
            ui.label('Beleg hochladen').classes('text-h5')
            ui.label('Neue Belege hinzufügen und verarbeiten').classes('text-caption text-grey-6')
        with ui.row().classes('items-center gap-2'):
            ui.label('Unterstützte Formate').classes('text-caption text-grey-6')
            ui.link('JPG, PNG, PDF', '#').classes('text-indigo-600 text-caption no-underline')

    status_label = ui.label('').classes('text-caption text-grey-6 q-ml-md q-mt-sm')
    user_input = ui.number(label='Benutzer-ID', value=user['user_id'], min=1)\
        .props('dense outlined readonly').classes('q-ml-md').style('max-width: 160px')
    user_input.disable()

    async def run_full_flow(selected: dict | None) -> None:
        if not selected:
            ui.notify('Bitte zuerst eine Datei auswählen.', color='warning')
            return
        try:
            user_id = int(user_input.value or 1)
            status_label.set_text('Beleg wird hochgeladen und gespeichert …')
            upload_result = await asyncio.to_thread(
                process_receipt_upload,
                user_id,
                selected.get('content'),
                selected.get('name'),
            )
            status_label.set_text('Analyse wird durchgeführt …')
            analysis = await analyze_receipt(upload_result['receipt_id'], user_id)
            upload_result['analysis'] = analysis
            status_label.set_text('Upload & Analyse erfolgreich.')
            ui.notify('Beleg verarbeitet', color='positive')
        except Exception as error:
            status_label.set_text(f'Fehler: {error!s}')
            ui.notify(f'Fehler: {error!s}', color='negative')

    async def handle_upload(event) -> None:
        file_info = {"name": event.file.name or 'receipt.bin', "content": await event.file.read()}
        await run_full_flow(file_info)

    with ui.row().classes('w-full gap-4 q-px-md q-pt-md q-pb-lg'):
        # Foto aufnehmen (Uploader versteckt, Button triggert Kamera)
        with ui.card().classes('w-[420px] h-[240px] bg-white/95 rounded-2xl shadow-md border border-white/70 items-center justify-center') as cam_card:
            with ui.column().classes('items-center justify-center gap-2'):
                ui.icon('photo_camera').classes('text-white bg-gradient-to-br from-indigo-500 to-purple-500 rounded-[20px] q-pa-lg').style('font-size: 32px')
                ui.label('Foto aufnehmen').classes('text-subtitle2 text-grey-9')
                ui.label('Kamera verwenden um Beleg zu fotografieren').classes('text-caption text-grey-6')
                cam_u = ui.upload(auto_upload=True, multiple=False)
                cam_u.props('accept="image/*" capture=environment style="display:none"')
                ui.button(icon='add', on_click=lambda: cam_u.run_method('pickFiles')).props('round dense flat').classes('bg-indigo-50 text-indigo-700 hover:bg-indigo-100')
                cam_u.on_upload(lambda e: asyncio.create_task(handle_upload(e)))

        # Datei auswählen (Uploader versteckt, Button triggert Auswahl)
        with ui.card().classes('w-[420px] h-[240px] bg-white/95 rounded-2xl shadow-md border border-white/70 items-center justify-center'):
            with ui.column().classes('items-center justify-center gap-2'):
                ui.icon('description').classes('text-white bg-gradient-to-br from-indigo-500 to-purple-500 rounded-[20px] q-pa-lg').style('font-size: 32px')
                ui.label('Datei auswählen').classes('text-subtitle2 text-grey-9')
                ui.label('PDF oder Bild von Ihrem Gerät auswählen').classes('text-caption text-grey-6')
                file_u = ui.upload(auto_upload=True, multiple=False)
                file_u.props('accept=".pdf,.heic,.heif,.jpg,.jpeg,.png,.webp,image/*" style="display:none"')
                ui.button(icon='add', on_click=lambda: file_u.run_method('pickFiles')).props('round dense flat').classes('bg-indigo-50 text-indigo-700 hover:bg-indigo-100')
                file_u.on_upload(lambda e: asyncio.create_task(handle_upload(e)))

        # Hier ablegen (unsichtbarer Drop-Bereich über gesamte Karte)
        with ui.card().classes('relative w-[420px] h-[240px] bg-gradient-to-br from-white to-blue-50/40 rounded-2xl shadow-md border-dashed border-2 border-grey-4 items-center justify-center'):
            with ui.column().classes('items-center justify-center gap-2 pointer-events-none'):
                ui.icon('upload').classes('text-white bg-emerald-500 rounded-[20px] q-pa-lg').style('font-size: 32px')
                ui.label('Hier ablegen').classes('text-subtitle2 text-grey-9')
                ui.label('Beleg hierher ziehen und ablegen').classes('text-caption text-grey-6')
            drop_u = ui.upload(label='', auto_upload=True, multiple=False)
            drop_u.props('accept=".pdf,.heic,.heif,.jpg,.jpeg,.png,.webp,image/*" style="opacity:0; position:absolute; inset:0; cursor:pointer"')
            drop_u.on_upload(lambda e: asyncio.create_task(handle_upload(e)))

    # Alte Umsetzung überspringen
    return
    # Upload-Seite ohne Monatsanzeige
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
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)
    # Belege-Seite ohne Monatsanzeige

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
            user_id = user.get("user_id") or None
            data = await asyncio.to_thread(
                list_receipts_overview, user_id
            )
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
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)
    display_name = user.get('name') or user.get('email') or 'Smart Expense Nutzer'
    # State: Belegliste für Metriken
    receipts: list[dict] = []
    COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#F97316', '#06B6D4', '#EF4444']
    _count_label = None
    category_chart = None
    chart_container = None
    legend_container = None
    def update_counts():
        if not _count_label:
            return
        selected = get_selected_month()
        count = 0
        for r in receipts:
            date_value = r.get('transaction_date') or r.get('upload_date')
            try:
                d = datetime.fromisoformat(date_value) if date_value else None
            except Exception:
                d = None
            if d and d.year == selected.year and d.month == selected.month:
                count += 1
        _count_label.set_text(str(count))

    def update_category_chart():
        nonlocal category_chart, legend_container, chart_container
        try:
            if not category_chart or legend_container is None:
                return
            selected = get_selected_month()
            sums: dict[str, float] = {}
            for r in receipts:
                date_value = r.get('transaction_date') or r.get('upload_date')
                try:
                    d = datetime.fromisoformat(date_value) if date_value else None
                except Exception:
                    d = None
                if not d or d.year != selected.year or d.month != selected.month:
                    continue
                cat = r.get('category_name') or 'Ohne Kategorie'
                amount = r.get('amount') or 0
                try:
                    amount = float(amount)
                except Exception:
                    amount = 0.0
                sums[cat] = sums.get(cat, 0.0) + amount

            data = [{'name': k, 'value': round(v, 2)} for k, v in sorted(sums.items(), key=lambda kv: kv[1], reverse=True)]
            # Chart neu aufbauen, um Versionsunterschiede zu umgehen
            chart_container.clear()
            with chart_container:
                category_chart = ui.echart({
                    'tooltip': {'trigger': 'item', 'formatter': '{b}: {c} ({d}%)'},
                    'series': [{
                        'type': 'pie',
                        'radius': ['45%', '70%'],
                        'avoidLabelOverlap': True,
                        'itemStyle': {'borderColor': '#fff', 'borderWidth': 2},
                        'label': {'show': False},
                        'labelLine': {'show': False},
                        'data': data if data else [],
                        'color': COLORS,
                    }],
                }).classes('w-[320px] h-[240px]')

            legend_container.clear()
            if not data:
                with legend_container:
                    ui.label('Keine Daten für den ausgewählten Monat').classes('text-caption text-grey-6')
                return
            for idx, item in enumerate(data):
                with legend_container:
                    with ui.row().classes('w-full items-center justify-between'):
                        with ui.row().classes('items-center gap-2'):
                            ui.element('div').style(f'width:10px;height:10px;border-radius:9999px;background:{COLORS[idx % len(COLORS)]}')
                            ui.label(item['name']).classes('text-body2 text-grey-8')
                        ui.label(_format_amount(item['value'], 'CHF')).classes('text-body2 text-grey-8')
        except Exception as exc:
            ui.notify(f'Diagramm-Fehler: {exc}', color='negative')

    async def load_receipts():
        nonlocal receipts
        try:
            user_id = user.get("user_id") or None
            receipts = await asyncio.to_thread(
                list_receipts_overview, user_id
            )
        except Exception as exc:
            ui.notify(f'Belege konnten nicht geladen werden: {exc}', color='negative')
            receipts = []
        update_counts()
        update_category_chart()

    with ui.column().classes('w-full items-stretch justify-start min-h-screen gap-4'):
        # Kopfzeile: rechts ausgerichtete Monatsanzeige (nur auf Übersicht)
        with ui.row().classes('w-full items-end justify-between q-pl-md q-pr-xl q-pt-sm q-pb-sm bg-gradient-to-r from-white to-blue-50/30 border-b border-white/70'):
            # Titelbereich wie im Figma (zentral/links im Content)
            with ui.column().classes('gap-0'):
                ui.label('Dashboard').classes('text-h5')
                ui.label(f'Willkommen zurück, {display_name}').classes('text-caption text-grey-6')
            with ui.row().classes('items-end'):
                month_bar(
                    username=display_name,
                    on_change=lambda _: (update_counts(), update_category_chart()),
                )

        # Kachelnbereich – Kennzahl "Belege"
        with ui.row().classes('w-full gap-4 q-px-md q-pt-md flex-wrap'):
            metric_card = ui.card().classes(
                'w-[340px] h-[180px] bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 items-center justify-center'
            )
            with metric_card:
                with ui.column().classes('items-center justify-center gap-2 q-pt-md'):
                    with ui.row().classes('items-center justify-center'):
                        ui.icon('description').classes('text-indigo-600 bg-indigo-100 rounded-full q-pa-sm').style('font-size: 28px')
                    _count_label = ui.label('-').classes('text-h4 text-grey-9')
                    ui.label('Belege').classes('text-caption text-grey-6')
                    ui.timer(0.3, lambda: update_counts(), once=True)

            chart_card = ui.card().classes(
                'w-[720px] min-h-[360px] bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70'
            )
            with chart_card:
                ui.label('Ausgaben nach Kategorie').classes('text-body1 q-pa-md text-grey-8')
                with ui.row().classes('w-full items-center justify-start gap-8 q-px-md q-pb-md'):
                    chart_container = ui.column().classes('')
                    with chart_container:
                        category_chart = ui.echart({'series': []}).classes('w-[320px] h-[240px]')
                    legend_container = ui.column().classes('gap-2')

        ui.timer(0.1, lambda: asyncio.create_task(load_receipts()), once=True)

@ui.page('/settings')
def settings_page():
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)
    store = _get_user_store(create=True) or {}
    stored_first_name = store.get('settings_first_name') or ''
    stored_last_name = store.get('settings_last_name') or ''
    stored_budget_raw = store.get('settings_budget') or ''
    stored_iban = store.get('settings_iban') or ''
    if isinstance(stored_budget_raw, (int, float)):
        stored_budget = f'{stored_budget_raw:.2f}'
    else:
        stored_budget = str(stored_budget_raw) if stored_budget_raw else ''
    with ui.column().classes(
        'items-center justify-start min-h-screen gap-6 q-pa-md bg-slate-50'
    ):
        ui.label('Einstellungen').classes('text-h5 text-grey-9')
        settings_card = ui.card().classes(
            'w-full max-w-3xl bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 p-6 gap-4'
        )
        with settings_card:
            ui.label('Persoenliche Informationen & Budget').classes(
                'text-subtitle1 text-grey-8'
            )
            with ui.column().classes('w-full gap-4'):
                with ui.row().classes('w-full gap-4 flex-wrap'):
                    first_name_input = ui.input('Vorname').props('outlined dense').classes(
                        'flex-1 min-w-[220px]'
                    )
                    first_name_input.value = stored_first_name
                    last_name_input = ui.input('Nachname').props('outlined dense').classes(
                        'flex-1 min-w-[220px]'
                    )
                    last_name_input.value = stored_last_name
                budget_input = ui.input('Maximales Budget (CHF)').props(
                    'outlined dense type=number min=0 step=0.05'
                ).classes('w-full')
                if stored_budget:
                    budget_input.value = stored_budget
                iban_input = ui.input('IBAN').props(
                    'outlined dense placeholder="CH00 0000 0000 0000 0000 0"'
                ).classes('w-full uppercase')
                iban_input.value = stored_iban
                status_label = ui.label('').classes('text-caption min-h-[20px] text-grey-7')

                def save_settings() -> None:
                    first_name = (first_name_input.value or '').strip()
                    last_name = (last_name_input.value or '').strip()
                    budget_raw = (budget_input.value or '').strip().replace(' ', '')
                    iban_value = (iban_input.value or '').strip().replace(' ', '').upper()
                    current_store = _get_user_store(create=True)
                    if current_store is None:
                        status_label.set_text('Speichern derzeit nicht moeglich.')
                        status_label.style('color: #dc2626')
                        ui.notify('Speichern fehlgeschlagen', color='negative')
                        return
                    if budget_raw:
                        normalized_budget_raw = budget_raw.replace(',', '.')
                        try:
                            budget_amount = float(normalized_budget_raw)
                        except ValueError:
                            status_label.set_text('Bitte gib einen gueltigen Betrag ein.')
                            status_label.style('color: #dc2626')
                            ui.notify('Ungueltiger Budgetbetrag', color='negative')
                            return
                        current_store['settings_budget'] = round(budget_amount, 2)
                        budget_input.value = f'{budget_amount:.2f}'
                    else:
                        current_store['settings_budget'] = ''
                    current_store['settings_first_name'] = first_name
                    current_store['settings_last_name'] = last_name
                    current_store['settings_iban'] = iban_value
                    status_label.set_text('Aenderungen gespeichert.')
                    status_label.style('color: #16a34a')
                    ui.notify('Einstellungen gespeichert', color='positive')

                ui.button('speichern', on_click=save_settings).classes(
                    'self-end bg-indigo-500 text-white rounded-xl px-6 py-2 '
                    'hover:bg-indigo-600 transition-all'
                )

# 5. Wichtiger Hinweis zum Ausführen der Anwendung:
# Die Funktion ui.run() wird normalerweise nicht direkt aufgerufen, wenn man `uvicorn` vom Terminal startet.
# Für das Deployment wird der Server jedoch programmatisch gestartet (siehe unten).

if __name__ == "__main__":
    # Dieser Block wird nur ausgeführt, wenn die Datei direkt mit `python app/main.py` gestartet wird.
    # Er ist entscheidend für das Deployment auf Plattformen wie Google Cloud Run.
    # Liest den PORT aus den Umgebungsvariablen, mit 8000 als Standard für die lokale Entwicklung.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
