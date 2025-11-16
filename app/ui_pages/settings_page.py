"""Einstellungs-Seite als eigenes Modul."""

from __future__ import annotations

from nicegui import ui

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
    stored_first_name = store.get('settings_first_name') or ''
    stored_last_name = store.get('settings_last_name') or ''
    stored_budget_raw = store.get('settings_budget') or ''
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
                status_label = ui.label('').classes('text-caption min-h-[20px] text-grey-7')

                def save_settings() -> None:
                    """Speichert die Formularwerte im User-Store und zeigt Feedback im Formular an."""
                    first_name = (first_name_input.value or '').strip()
                    last_name = (last_name_input.value or '').strip()
                    budget_raw = (budget_input.value or '').strip().replace(' ', '')
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
                    status_label.set_text('Aenderungen gespeichert.')
                    status_label.style('color: #16a34a')
                    ui.notify('Einstellungen gespeichert', color='positive')

                ui.button('speichern', on_click=save_settings).classes(
                    'self-end bg-indigo-500 text-white rounded-xl px-6 py-2 '
                    'hover:bg-indigo-600 transition-all'
                )
