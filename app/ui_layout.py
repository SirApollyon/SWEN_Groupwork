"""Layout-Helfer wie Navigation und Monatsauswahl – ausgelagert für Wiederverwendung auf allen Seiten."""

from __future__ import annotations

from datetime import datetime

from nicegui import ui

from app.helpers.auth_helpers import _logout_and_redirect


def _current_path() -> str:
    """Liefert den aktuellen URL-Pfad des Clients, damit wir Navigationspunkte highlighten können."""
    try:
        return ui.context.client.content.path
    except Exception:
        return '/'


def _side_nav_item(label: str, icon: str, path: str, active: bool = False) -> None:
    """Rendert einen Menüeintrag in der Sidebar und markiert ihn bei aktiver Seite."""
    base = (
        'w-full items-center gap-2 px-3 py-2 rounded-xl cursor-pointer '
        'transition-all'
    )
    active_cls = (
        'bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-md'
    )
    inactive_cls = 'text-grey-7 hover:bg-indigo-50 hover:text-indigo-700'
    with ui.row().classes(f'{base} {active_cls if active else inactive_cls}')\
                 .on('click', lambda: ui.navigate.to(path)):
        ui.icon(icon).classes('text-[18px]')
        ui.label(label).classes('text-body2 font-medium')


def nav(user: dict):
    """Stellt die responsive Navigation bereit (Drawer + Burger-Button)."""
    p = _current_path()
    display_name = user.get("name") or user.get("email") or "Demo-Modus"

    with ui.left_drawer(value=False).props('bordered show-if-above').classes(
        'w-64 bg-white/80 backdrop-blur p-4 transition-transform duration-300 ease-in-out md:static md:translate-x-0'
    ) as drawer:
        with ui.column().classes('gap-3'):
            with ui.row().classes('items-center justify-between'):
                ui.button(icon='menu', on_click=lambda: drawer.toggle())\
                    .props('flat round dense')\
                    .classes('md:hidden text-indigo-600')
                with ui.column().classes('gap-0'):
                    ui.label('Smart Expense Tracker').classes('text-subtitle1 font-semibold')
                    ui.label('Ihre persönliche Finanzübersicht').classes('text-caption text-grey-6')

            ui.separator().classes('q-my-sm')

            _side_nav_item('Dashboard', 'dashboard', '/dashboard', active=(p == '/dashboard'))
            _side_nav_item('Dashboard+', 'insights', '/dashboard/extended', active=(p == '/dashboard/extended'))
            _side_nav_item('Belege', 'receipt_long', '/receipts', active=(p == '/receipts'))
            _side_nav_item('Hochladen', 'upload', '/upload', active=(p == '/upload'))
            _side_nav_item('Einstellungen', 'settings', '/settings', active=(p == '/settings'))

    # Burger-Button: sichtbar bis 1023 px (md & lg hidden), damit Mobile/Tablet Benutzer:innen navigieren können.
    with ui.row().classes(
        'md:hidden lg:hidden fixed top-4 left-4 z-50 items-center gap-2 '
        'bg-white/90 backdrop-blur border border-white/80 shadow-lg rounded-full px-3 py-2'
    ):
        ui.button(icon='menu', on_click=lambda: drawer.toggle())\
            .props('flat round dense')\
            .classes('text-indigo-600')


GERMAN_MONTHS = [
    'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
]


def _first_of_month(dt: datetime) -> datetime:
    """Schneidet einen gegebenen Tag auf den Monatsanfang zurecht."""
    return dt.replace(day=1)


def _shift_month(dt: datetime, delta: int) -> datetime:
    """Verschiebt ein Datum um delta Monate – wichtig für die Monatsnavigation."""
    y, m = dt.year, dt.month
    m0 = (m - 1) + delta
    y += m0 // 12
    m = (m0 % 12) + 1
    return datetime(y, m, 1)


def _format_month_de(dt: datetime) -> str:
    """Formatiert den Monat in gut lesbares Deutsch."""
    return f"{GERMAN_MONTHS[dt.month - 1]} {dt.year}"


GLOBAL_SELECTED_MONTH = _first_of_month(datetime.today())


def get_selected_month() -> datetime:
    """Liest den aktuell im UI gewählten Monat aus (fällt auf GLOBAL zurück, wenn kein Client aktiv ist)."""
    try:
        client = ui.context.client
        if not hasattr(client, 'selected_month'):
            client.selected_month = _first_of_month(datetime.today())
        return client.selected_month
    except Exception:
        return GLOBAL_SELECTED_MONTH


def set_selected_month(value: datetime) -> None:
    """Speichert die neue Monatsauswahl sowohl am Client als auch im Fallback."""
    value = _first_of_month(value)
    try:
        ui.context.client.selected_month = value
    except Exception:
        pass
    global GLOBAL_SELECTED_MONTH
    GLOBAL_SELECTED_MONTH = value


def month_bar(username: str = 'Giuliano', on_change=None) -> None:
    """Zeigt die Monatsnavigation an und ruft bei Wechsel den Callback auf."""
    current = get_selected_month()

    def update(delta: int) -> None:
        """Verschiebt den ausgewählten Monat um `delta` und aktualisiert die abhängigen Anzeigen."""
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
