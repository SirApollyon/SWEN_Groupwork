from __future__ import annotations

import asyncio
from datetime import datetime

from nicegui import ui

from app.db import get_user_settings, list_receipts_overview
from app.helpers.auth_helpers import _ensure_authenticated, _get_user_store
from app.helpers.receipt_helpers import _format_amount
from app.ui_layout import get_selected_month, month_bar, nav

@ui.page('/dashboard/extended')
def dashboard_extended_page():
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)
    display_name = user.get('name') or user.get('email') or 'Smart Expense Nutzer'

    # State
    receipts: list[dict] = []
    monthly_summary: list[dict] = []
    budget_data: dict[str, float] = {}
    income_data: dict[str, float] = {}

    # Palette: blue, lilac/purple, grey tones
    COLORS = ['#1E3A8A', '#3B82F6', '#60A5FA', '#8B5CF6', '#6D28D9', '#A78BFA', '#94A3B8']
    _count_label = None
    total_expense_label = None
    budget_status_label = None
    savings_label = None
    category_chart = None
    chart_container = None
    legend_container = None
    income_expense_chart = None
    income_chart_container = None
    budget_sync_running = False

    def match_month(r, selected):
        date_value = r.get('transaction_date') or r.get('upload_date')
        try:
            d = datetime.fromisoformat(date_value) if date_value else None
        except Exception:
            d = None
        return d and d.year == selected.year and d.month == selected.month

    def update_counts():
        if not _count_label:
            return
        selected = get_selected_month()
        count = sum(1 for r in receipts if match_month(r, selected))
        _count_label.set_text(str(count))

    def update_financial_metrics():
        selected = get_selected_month()
        key = f"{selected.year}-{selected.month:02}"
        expenses = sum(float(r.get("amount") or 0) for r in receipts if match_month(r, selected))
        budget = budget_data.get(key, 0)
        income = income_data.get(key, 0)
        savings = income - expenses
        if total_expense_label: total_expense_label.set_text(_format_amount(expenses, 'CHF'))
        if budget_status_label: budget_status_label.set_text('Unter Budget' if expenses <= budget else 'Über Budget')
        if savings_label: savings_label.set_text(_format_amount(savings, 'CHF'))
        # Re-evaluate budget status using user settings when monthly budget is not set
        store = _get_user_store(create=False) or {}
        try:
            user_budget = float(store.get('settings_budget') or 0)
        except (TypeError, ValueError):
            user_budget = 0.0
        effective_budget = budget if (budget and budget > 0) else user_budget
        if budget_status_label:
            if effective_budget and effective_budget > 0:
                budget_status_label.set_text('Unter Budget' if expenses <= effective_budget else 'Über Budget')
            else:
                budget_status_label.set_text('Kein Budget')

    def update_income_expense_chart():
        nonlocal income_expense_chart, income_chart_container
        if not monthly_summary or income_chart_container is None:
            return
        months = [row["month"].strftime("%Y-%m") for row in monthly_summary]
        income_vals = [row.get("Income", 0) for row in monthly_summary]
        expense_vals = [row.get("Expenses", 0) for row in monthly_summary]
        opts = {
            'tooltip': {'trigger': 'axis'},
            'legend': {'data': ['Einkommen', 'Ausgaben']},
            'xAxis': {'type': 'category', 'data': months},
            'yAxis': {'type': 'value'},
            'series': [
                {'name': 'Einkommen', 'type': 'bar', 'data': income_vals, 'itemStyle': {'color': '#94A3B8'}},
                {'name': 'Ausgaben', 'type': 'bar', 'data': expense_vals, 'itemStyle': {'color': '#3B82F6'}},
            ],
        }
        income_chart_container.clear()
        with income_chart_container:
            income_expense_chart = ui.echart(opts).classes('w-full h-[320px]')

    def update_category_chart():
        nonlocal category_chart, legend_container, chart_container
        try:
            if not category_chart or legend_container is None:
                return
            selected = get_selected_month()
            sums: dict[str, float] = {}
            for r in receipts:
                if not match_month(r, selected):
                    continue
                cat = r.get('category_name') or 'Ohne Kategorie'
                amount = float(r.get('amount') or 0)
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
                        'data': data,
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

    def _compute_monthly_summary(rows: list[dict]) -> list[dict]:
        """Aggregate income/expenses by month from receipt transactions."""
        by_month: dict[str, dict] = {}
        for r in rows:
            date_value = r.get('transaction_date') or r.get('upload_date')
            try:
                d = datetime.fromisoformat(date_value) if date_value else None
            except Exception:
                d = None
            if not d:
                continue
            key = f"{d.year}-{d.month:02}-01"
            if key not in by_month:
                by_month[key] = {
                    'month': datetime(d.year, d.month, 1),
                    'Income': 0.0,
                    'Expenses': 0.0,
                }
            amount = float(r.get('amount') or 0)
            ttype = (r.get('transaction_type') or '').lower()
            if ttype == 'income':
                by_month[key]['Income'] += amount
            else:
                # default treat as expense when unknown
                by_month[key]['Expenses'] += amount
        return sorted(by_month.values(), key=lambda x: x['month'])

    async def sync_user_budget():
        """Lädt das max. Budget aus der Datenbank und aktualisiert den Store."""
        nonlocal budget_sync_running
        user_id = user.get("user_id")
        if not user_id or budget_sync_running:
            return
        budget_sync_running = True
        try:
            settings = await asyncio.to_thread(get_user_settings, user_id)
            value = settings.get('max_budget')
        except Exception as exc:
            ui.notify(f'Budget konnte nicht geladen werden: {exc}', color='warning')
            return
        finally:
            budget_sync_running = False
        store = _get_user_store(create=True) or {}
        if value is None:
            store['settings_budget'] = ''
        else:
            store['settings_budget'] = round(float(value), 2)
        update_financial_metrics()

    async def load_receipts():
        nonlocal receipts, budget_data, income_data, monthly_summary
        try:
            user_id = user.get("user_id") or None
            receipts = await asyncio.to_thread(list_receipts_overview, user_id)
            # Derive monthly summary from loaded receipts
            monthly_summary = _compute_monthly_summary(receipts)

        except Exception as exc:
            ui.notify(f'Belege konnten nicht geladen werden: {exc}', color='negative')
            receipts = []

        update_counts()
        update_category_chart()
        update_financial_metrics()
        update_income_expense_chart()

    with ui.column().classes('w-full items-stretch justify-start min-h-screen gap-4'):
        with ui.row().classes('w-full items-end justify-between q-pl-md q-pr-xl q-pt-sm q-pb-sm bg-gradient-to-r from-white to-blue-50/30 border-b border-white/70'):
            with ui.column().classes('gap-0'):
                ui.label('Dashboard').classes('text-h5')
                ui.label(f'Willkommen zurück, {display_name}').classes('text-caption text-grey-6')
            with ui.row().classes('items-end'):
                month_bar(
                    username=display_name,
                    on_change=lambda _: (
                        update_counts(),
                        update_category_chart(),
                        update_financial_metrics(),
                        update_income_expense_chart()
                    ),
                )

        with ui.row().classes('w-full gap-4 q-px-md q-pt-md flex-wrap'):
            # Belege
            with ui.card().classes('w-[340px] h-[180px] bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 items-center justify-center'):
                with ui.column().classes('items-center justify-center gap-2 q-pt-md'):
                    ui.icon('description').classes('text-indigo-600 bg-indigo-100 rounded-full q-pa-sm').style('font-size: 28px')
                    _count_label = ui.label('-').classes('text-h4 text-grey-9')
                    ui.label('Belege').classes('text-caption text-grey-6')
                    ui.timer(0.3, lambda: update_counts(), once=True)

            # Gesamtausgaben
            with ui.card().classes('w-[340px] h-[180px] bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 items-center justify-center'):
                with ui.column().classes('items-center justify-center gap-2 q-pt-md'):
                    ui.icon('attach_money').classes('text-green-600 bg-green-100 rounded-full q-pa-sm').style('font-size: 28px')
                    total_expense_label = ui.label('-').classes('text-h4 text-grey-9')
                    ui.label('Gesamtausgaben').classes('text-caption text-grey-6')

            # Budgetstatus
            with ui.card().classes('w-[340px] h-[180px] bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 items-center justify-center'):
                with ui.column().classes('items-center justify-center gap-2 q-pt-md'):
                    ui.icon('speed').classes('text-orange-600 bg-orange-100 rounded-full q-pa-sm').style('font-size: 28px')
                    budget_status_label = ui.label('-').classes('text-h4 text-grey-9')
                    ui.label('Budgetstatus').classes('text-caption text-grey-6')

            # Ersparnis
            with ui.card().classes('w-[340px] h-[180px] bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 items-center justify-center'):
                with ui.column().classes('items-center justify-center gap-2 q-pt-md'):
                    ui.icon('savings').classes('text-blue-600 bg-blue-100 rounded-full q-pa-sm').style('font-size: 28px')
                    savings_label = ui.label('-').classes('text-h4 text-grey-9')
                    ui.label('Ersparnis').classes('text-caption text-grey-6')

        # Charts row: Category donut + legend, and Monthly Income vs Expenses
        with ui.row().classes('w-full gap-4 q-px-md q-pb-xl flex-wrap items-stretch'):
            with ui.card().classes('flex-1 min-w-[360px] bg-white/90 rounded-2xl shadow-md border border-white/70'):
                with ui.column().classes('w-full gap-3 q-pa-md'):
                    with ui.row().classes('items-center justify-between'):
                        ui.label('Ausgaben nach Kategorie').classes('text-body1 font-medium')
                        ui.label('aktueller Monat').classes('text-caption text-grey-6')
                    with ui.row().classes('w-full gap-4 items-start'):
                        chart_container = ui.column().classes('items-center justify-center')
                        with ui.column().classes('gap-2 flex-1') as legend_container_ref:
                            legend_container = legend_container_ref
                ui.timer(0.1, lambda: update_category_chart(), once=True)

            with ui.card().classes('flex-[1.2] min-w-[420px] bg-white/90 rounded-2xl shadow-md border border-white/70'):
                with ui.column().classes('w-full gap-3 q-pa-md'):
                    with ui.row().classes('items-center justify-between'):
                        ui.label('Einkommen vs. Ausgaben (Monate)').classes('text-body1 font-medium')
                        ui.label('Summen je Monat').classes('text-caption text-grey-6')
                    income_chart_container = ui.column().classes('w-full')
                    with income_chart_container:
                        income_expense_chart = ui.echart({
                            'tooltip': {'trigger': 'axis'},
                            'legend': {'data': ['Einkommen', 'Ausgaben']},
                            'xAxis': {'type': 'category', 'data': []},
                            'yAxis': {'type': 'value'},
                            'series': [
                                {'name': 'Einkommen', 'type': 'bar', 'data': [], 'itemStyle': {'color': '#94A3B8'}},
                                {'name': 'Ausgaben', 'type': 'bar', 'data': [], 'itemStyle': {'color': '#3B82F6'}},
                            ],
                        }).classes('w-full h-[320px]')
                ui.timer(0.2, lambda: update_income_expense_chart(), once=True)

        # Initial data load
        ui.timer(0.02, lambda: asyncio.create_task(sync_user_budget()), once=True)
        ui.timer(20, lambda: asyncio.create_task(sync_user_budget()))
        ui.timer(0.05, lambda: asyncio.create_task(load_receipts()), once=True)
