"""Login-Seite als eigenes Modul, damit die main.py schlanker bleibt."""

from __future__ import annotations

import asyncio

from nicegui import ui

from app.db import authenticate_user, create_user
from app.helpers.auth_helpers import (
    _get_logged_in_user,
    _set_guest_user,
    _set_logged_in_user,
)


@ui.page('/login')
def login_page():
    """Rendert die bestehende Login-Oberfläche – Logik bleibt unverändert, nur ausgelagert."""

    if _get_logged_in_user():
        ui.timer(0.1, lambda: ui.navigate.to('/dashboard/extended'), once=True)
        with ui.column().classes(
            'items-center justify-center h-screen gap-3 text-white'
        ):
            ui.spinner('dots').classes('text-white text-4xl')
            ui.label('Du bist bereits eingeloggt – einen Moment...').classes(
                'text-body2 text-white/80'
            )
        return

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
        ui.navigate.to('/dashboard/extended')

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
        ui.navigate.to('/dashboard/extended')

    def skip_login() -> None:
        """Lädt das Demo-Konto ohne Anmeldung."""
        _set_guest_user()
        ui.notify('Demo-Konto geladen (Benutzer 1).', color='info')
        ui.navigate.to('/dashboard/extended')

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
        ui.button('Registrieren', on_click=handle_signup)\
            .classes('w-full bg-indigo-500 text-white hover:bg-indigo-600 hover:-translate-y-0.5 transition-all shadow-lg rounded-xl')
        ui.button('Abbrechen', on_click=signup_dialog.close).props('flat')\
            .classes('w-full text-indigo-600 hover:text-indigo-700')

    with ui.element('div').classes(
        'min-h-screen w-full bg-[#F4F6FB] flex items-center justify-center px-0 py-0'
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

            with ui.column().classes('w-full md:w-[45%] bg-[#F4F6FB] items-center justify-center py-14 px-8 m-0'):
                with ui.column().classes('w-full max-w-md bg-white border border-[#E5E9F5] rounded-[28px] shadow-lg p-8 gap-5'):
                    with ui.column().classes('gap-1'):
                        ui.html("<span class='text-grey-600 text-sm uppercase tracking-[0.3em]'>Willkommen</span>", sanitize=False)
                        ui.html(
                            "<span class='text-2xl md:text-3xl font-semibold text-gray-800'>Einloggen ",
                            sanitize=False,
                        )
                        ui.label('Gib deine Zugangsdaten ein, um mit dem Smart Expense Tracker zu starten.')\
                            .classes('text-caption text-grey-6')
                    login_email = ui.input('E-Mail').props(
                        'dense rounded filled placeholder="name@example.com" type=email'
                    ).classes('rounded-2xl bg-white-1')
                    with login_email.add_slot('prepend'):
                        ui.icon('mail').classes('text-blue-500')
                    login_password = ui.input('Passwort', password=True, password_toggle_button=True)\
                        .props('dense rounded filled placeholder="••••••••"').classes('rounded-2xl bg-white-1')
                    with login_password.add_slot('prepend'):
                        ui.icon('lock').classes('text-blue-500')
                    with ui.row().classes('justify-between items-center w-full'):
                        ui.link('Passwort vergessen?', '#').classes(
                            'text-caption text-blue-600 hover:underline'
                        )
                    status_label = ui.label('').classes('text-caption text-red-500 min-h-[18px]')
                    ui.button('Login', on_click=handle_login)\
                        .classes('w-full text-white font-medium rounded-2xl py-3 shadow-lg hover:-translate-y-0.5 transition-all border-0')\
                        .style('background:linear-gradient(90deg, #3B82F6 0%, #6D28D9 100%) !important; border:none !important;')
                    ui.button('Im Demo-Modus fortfahren', on_click=skip_login).props('flat')\
                        .classes('w-full text-blue-600 hover:text-blue-700')
                    with ui.row().classes('justify-center gap-2 text-caption text-grey-6'):
                        ui.label('Noch kein Konto?')
                        signup_link = ui.link('Sign Up', '#').classes(
                            'text-blue-600 no-underline hover:underline'
                        )
                        signup_link.on('click', lambda _: signup_dialog.open())
