"""Einstellungs-Seite als eigenes Modul."""

from __future__ import annotations

import asyncio

from nicegui import ui

from app.db import get_user_settings, save_user_settings
from app.helpers.auth_helpers import _ensure_authenticated, _get_user_store
from app.ui_layout import nav


@ui.page('/settings')
def settings_page():
    """Stellt Formular zur Verwaltung persönlicher Daten & Budget bereit."""
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)
    store = _get_user_store(create=True) or {}
    stored_budget_value = store.get('settings_budget')
    needs_db_budget = stored_budget_value in (None, '')
    if needs_db_budget and user.get('user_id'):
        try:
            db_settings = get_user_settings(user['user_id'])
            db_budget = db_settings.get('max_budget')
            if db_budget is not None:
                stored_budget_value = db_budget
                store['settings_budget'] = db_budget
        except Exception as exc:
            ui.notify(f'Budget konnte nicht aus der Datenbank geladen werden: {exc}', color='warning')
            stored_budget_value = stored_budget_value or ''
    stored_budget_raw = stored_budget_value or ''
    if isinstance(stored_budget_raw, (int, float)):
        stored_budget = f'{stored_budget_raw:.2f}'
    else:
        stored_budget = str(stored_budget_raw) if stored_budget_raw else ''

    with ui.column().classes(
        'items-center justify-start min-h-screen gap-6 q-pa-md'
    ):
        ui.label('Einstellungen').classes('text-h5')
        settings_card = ui.card().classes(
            'w-full max-w-3xl bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 p-6 gap-4'
        )
        with settings_card:
            ui.label('Budgetverwaltung').classes(
                'text-subtitle1 text-grey-8'
            )
            with ui.column().classes('w-full gap-4'):
                budget_input = ui.input('Maximales Budget (CHF)').props(
                    'outlined dense type=number min=0 step=0.05'
                ).classes('w-full')
                if stored_budget:
                    budget_input.value = stored_budget
                status_label = ui.label('').classes('text-caption min-h-[20px] text-grey-7')

                async def save_settings() -> None:
                    """Speichert die Budget-Einstellung persistent."""
                    budget_raw = (budget_input.value or '').strip().replace(' ', '')
                    current_store = _get_user_store(create=True)
                    if current_store is None:
                        status_label.set_text('Speichern derzeit nicht moeglich.')
                        status_label.style('color: #dc2626')
                        ui.notify('Speichern fehlgeschlagen', color='negative')
                        return
                    budget_amount: float | None = None
                    if budget_raw:
                        normalized_budget_raw = budget_raw.replace(',', '.')
                        try:
                            budget_amount = round(float(normalized_budget_raw), 2)
                        except ValueError:
                            status_label.set_text('Bitte gib einen gueltigen Betrag ein.')
                            status_label.style('color: #dc2626')
                            ui.notify('Ungueltiger Budgetbetrag', color='negative')
                            return
                        if budget_amount < 0:
                            status_label.set_text('Budget muss positiv sein.')
                            status_label.style('color: #dc2626')
                            ui.notify('Budget darf nicht negativ sein', color='negative')
                            return
                    user_id = user.get('user_id')
                    if user_id:
                        try:
                            await asyncio.to_thread(
                                save_user_settings,
                                user_id,
                                max_budget=budget_amount,
                            )
                        except Exception as exc:
                            status_label.set_text('Datenbank-Update fehlgeschlagen.')
                            status_label.style('color: #dc2626')
                            ui.notify(f'Einstellungen konnten nicht gespeichert werden: {exc}', color='negative')
                            return
                    if budget_amount is not None:
                        current_store['settings_budget'] = budget_amount
                        budget_input.value = f'{budget_amount:.2f}'
                    else:
                        current_store['settings_budget'] = ''
                        budget_input.value = ''
                    current_store.pop('settings_first_name', None)
                    current_store.pop('settings_last_name', None)
                    status_label.set_text('Aenderungen gespeichert.')
                    status_label.style('color: #16a34a')
                    ui.notify('Einstellungen gespeichert', color='positive')

                ui.button('speichern', on_click=save_settings).classes(
                    'self-end bg-indigo-500 text-white rounded-xl px-6 py-2 '
                    'hover:bg-indigo-600 transition-all'
                )
