"""Dashboard-Seite ausgelagert: behält alle Statistiken und Diagramme."""

from __future__ import annotations

import asyncio
from datetime import datetime

from nicegui import ui

from app.db import list_receipts_overview
from app.helpers.auth_helpers import _ensure_authenticated
from app.helpers.receipt_helpers import _format_amount
from app.ui_layout import get_selected_month, month_bar, nav


@ui.page('/dashboard')
def dashboard_page():
    """Zeigt die Kennzahlen, Monatsauswahl und das Kategoriendiagramm."""
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)
    display_name = user.get('name') or user.get('email') or 'Smart Expense Nutzer'

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

    with ui.column().classes('w-full items-stretch justify-start min-h-screen gap-4 pt-16 md:pt-0 transition-all z-0'):
        with ui.row().classes('w-full items-end justify-between q-pl-md q-pr-xl q-pt-sm q-pb-sm bg-gradient-to-r from-white to-blue-50/30 border-b border-white/70'):
            with ui.column().classes('gap-0'):
                ui.label('Dashboard').classes('text-h5')
                ui.label(f'Willkommen zurück, {display_name}').classes('text-caption text-grey-6')
            with ui.row().classes('items-end'):
                month_bar(
                    username=display_name,
                    on_change=lambda _: (update_counts(), update_category_chart()),
                )

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

    ui.timer(0.1, load_receipts, once=True)
