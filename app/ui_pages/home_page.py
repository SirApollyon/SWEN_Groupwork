"""Startseite mit kurzer Einführung."""

from __future__ import annotations

from nicegui import ui

from app.helpers.auth_helpers import _ensure_authenticated
from app.ui_layout import nav


@ui.page('/')
def home_page():
    """Zeigt den Begrüßungstext und verweist auf die Navigation."""
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)
    with ui.column().classes('items-center justify-center h-screen text-center gap-4 q-px-xl'):
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
