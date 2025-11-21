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
    budget_label = None
    total_expense_label = None
    budget_status_label = None
    budget_status_icon = None
    budget_diff_label = None
    budget_diff_icon = None
    budget_split_chart = None
    budget_split_container = None
    budget_split_legend = None
    category_chart = None
    chart_container = None
    legend_container = None
    category_trend_chart = None
    category_trend_chart_container = None
    budget_vs_expense_chart = None
    budget_chart_container = None
    budget_sync_running = False
    category_monthly_breakdown: dict[str, dict[str, float]] = {}
    last_effective_budget = 0.0
    last_expenses = 0.0
    category_color_map: dict[str, str] = {}

    def match_month(r, selected):
        """Prüft, ob der Belegzeitpunkt in den aktuell ausgewählten Monat fällt."""
        date_value = r.get('transaction_date') or r.get('upload_date')
        try:
            d = datetime.fromisoformat(date_value) if date_value else None
        except Exception:
            d = None
        return d and d.year == selected.year and d.month == selected.month

    def update_financial_metrics():
        """Berechnet Budgetstatus, Differenz und Gesamtausgaben für den Fokusmonat."""
        nonlocal last_effective_budget, last_expenses
        selected = get_selected_month()
        key = f"{selected.year}-{selected.month:02}"
        expenses = sum(float(r.get("amount") or 0) for r in receipts if match_month(r, selected))
        budget = budget_data.get(key, 0)
        if total_expense_label:
            total_expense_label.set_text(_format_amount(expenses, 'CHF'))
        store = _get_user_store(create=False) or {}
        try:
            user_budget = float(store.get('settings_budget') or 0)
        except (TypeError, ValueError):
            user_budget = 0.0
        effective_budget = budget if (budget and budget > 0) else user_budget
        last_effective_budget = effective_budget if (effective_budget and effective_budget > 0) else 0.0
        last_expenses = expenses
        if last_effective_budget:
            is_under_budget = expenses <= effective_budget
            if budget_status_label:
                budget_status_label.set_text('Unter Budget' if is_under_budget else 'Über Budget')
            if budget_status_icon:
                if is_under_budget:
                    budget_status_icon.classes(remove='text-orange-600 bg-orange-100', add='text-green-600 bg-green-100')
                else:
                    budget_status_icon.classes(remove='text-green-600 bg-green-100', add='text-orange-600 bg-orange-100')
            if budget_diff_label:
                diff_value = effective_budget - expenses
                if diff_value >= 0:
                    budget_diff_label.set_text(_format_amount(diff_value, 'CHF'))
                    budget_diff_label.classes(remove='text-red-600', add='text-green-600')
                    if budget_diff_icon:
                        budget_diff_icon.classes(remove='text-slate-700 text-red-600 bg-slate-100 bg-red-100', add='text-green-600 bg-green-100')
                else:
                    budget_diff_label.set_text(f"-{_format_amount(abs(diff_value), 'CHF')}")
                    budget_diff_label.classes(remove='text-green-600', add='text-red-600')
                    if budget_diff_icon:
                        budget_diff_icon.classes(remove='text-slate-700 text-green-600 bg-slate-100 bg-green-100', add='text-red-600 bg-red-100')
        else:
            if budget_status_label:
                budget_status_label.set_text('Kein Budget')
            if budget_status_icon:
                budget_status_icon.classes(remove='text-green-600 bg-green-100', add='text-orange-600 bg-orange-100')
            if budget_diff_label:
                budget_diff_label.set_text('-')
                budget_diff_label.classes(remove='text-green-600 text-red-600')
            if budget_diff_icon:
                budget_diff_icon.classes(remove='text-green-600 bg-green-100 text-red-600 bg-red-100', add='text-slate-700 bg-slate-100')
        update_budget_split_chart()
    def update_budget_vs_expense_chart():
        """Zeichnet die gruppierten Monatsbalken für Budget vs. Ausgaben."""
        nonlocal budget_vs_expense_chart, budget_chart_container
        if not monthly_summary or budget_chart_container is None:
            return
        months = [row["month"].strftime("%Y-%m") for row in monthly_summary]
        if not months:
            return
        store = _get_user_store(create=False) or {}
        try:
            default_budget = float(store.get('settings_budget') or 0)
        except (TypeError, ValueError):
            default_budget = 0.0
        expenses_series = []
        remaining_series = []
        over_series = []
        for row in monthly_summary:
            month_dt = row["month"]
            month_key = f"{month_dt.year}-{month_dt.month:02}"
            expenses = float(row.get("Expenses") or 0)
            monthly_budget = budget_data.get(month_key, default_budget)
            if monthly_budget and monthly_budget > 0:
                spent_in_budget = min(expenses, monthly_budget)
                remaining = max(monthly_budget - expenses, 0)
                over_budget = max(expenses - monthly_budget, 0)
            else:
                spent_in_budget = expenses
                remaining = 0
                over_budget = 0
            expenses_series.append(round(spent_in_budget, 2))
            remaining_series.append(round(remaining, 2))
            over_series.append(round(over_budget, 2))
        opts = {
            'tooltip': {'trigger': 'axis'},
            'legend': {'data': ['Ausgaben', 'Budget übrig', 'Über Budget']},
            'xAxis': {'type': 'category', 'data': months},
            'yAxis': {'type': 'value'},
            'series': [
                {'name': 'Ausgaben', 'type': 'bar', 'data': expenses_series, 'itemStyle': {'color': '#3B82F6'}},
                {'name': 'Budget übrig', 'type': 'bar', 'data': remaining_series, 'itemStyle': {'color': '#10B981'}},
                {'name': 'Über Budget', 'type': 'bar', 'data': over_series, 'itemStyle': {'color': '#EF4444'}},
            ],
        }
        budget_chart_container.clear()
        with budget_chart_container:
            budget_vs_expense_chart = ui.echart(opts).classes('w-full h-[320px]')

    def update_category_chart():
        """Aktualisiert die Donut-Grafik 'Ausgaben nach Kategorie' inkl. Legende."""
        nonlocal category_chart, legend_container, chart_container
        try:
            if chart_container is None or legend_container is None:
                return
            selected = get_selected_month()
            sums: dict[str, float] = {}
            for r in receipts:
                if not match_month(r, selected):
                    continue
                cat = r.get('category_name') or 'Ohne Kategorie'
                amount = float(r.get('amount') or 0)
                sums[cat] = sums.get(cat, 0.0) + amount

            data = []
            colors_for_data = []
            for k, v in sorted(sums.items(), key=lambda kv: kv[1], reverse=True):
                color = _get_category_color(k)
                data.append({'name': k, 'value': round(v, 2)})
                colors_for_data.append(color)
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
                        'color': colors_for_data,
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
                        color = colors_for_data[idx] if idx < len(colors_for_data) else _get_category_color(item['name'])
                        with ui.row().classes('items-center gap-2'):
                            ui.element('div').style(f'width:10px;height:10px;border-radius:9999px;background:{color}')
                            ui.label(item['name']).classes('text-body2 text-grey-8')
                        ui.label(_format_amount(item['value'], 'CHF')).classes('text-body2 text-grey-8')
        except Exception as exc:
            ui.notify(f'Diagramm-Fehler: {exc}', color='negative')

    def update_budget_split_chart():
        """Zeigt Budget vs. Ausgaben des aktuellen Monats als Donut plus Legende."""
        nonlocal budget_split_chart, budget_split_container, budget_split_legend
        if budget_split_container is None or budget_split_legend is None:
            return
        budget_split_container.clear()
        budget_split_legend.clear()
        if not last_effective_budget or last_effective_budget <= 0:
            with budget_split_container:
                ui.label('Kein Budget definiert.').classes('text-caption text-grey-6')
            with budget_split_legend:
                ui.label('').classes('text-caption text-grey-6')
            return
        remaining = max(last_effective_budget - last_expenses, 0)
        spent_within_budget = min(last_expenses, last_effective_budget)
        data = []
        colors_for_data = []
        if remaining > 0:
            data.append({'name': 'Budget übrig', 'value': round(remaining, 2)})
            colors_for_data.append('#10B981')
        if spent_within_budget > 0:
            data.append({'name': 'Gesamtausgaben', 'value': round(spent_within_budget, 2)})
            colors_for_data.append('#3B82F6')
        if last_expenses > last_effective_budget:
            data.append({'name': 'Über Budget', 'value': round(last_expenses - last_effective_budget, 2)})
            colors_for_data.append('#EF4444')
        if not data:
            with budget_split_container:
                ui.label('Keine Ausgaben für diesen Monat.').classes('text-caption text-grey-6')
            with budget_split_legend:
                ui.label('').classes('text-caption text-grey-6')
            return
        with budget_split_container:
            budget_split_chart = ui.echart({
                'tooltip': {'trigger': 'item', 'formatter': '{b}: {c} ({d}%)'},
                'series': [{
                    'type': 'pie',
                    'radius': ['45%', '70%'],
                    'avoidLabelOverlap': True,
                    'itemStyle': {'borderColor': '#fff', 'borderWidth': 2},
                    'label': {'show': False},
                    'labelLine': {'show': False},
                    'color': colors_for_data or ['#10B981', '#3B82F6', '#EF4444'],
                    'data': data,
                }],
            }).classes('w-[320px] h-[240px]')
        with budget_split_legend:
            if not data:
                ui.label('').classes('text-caption text-grey-6')
            scale = sum(item['value'] for item in data) or 1
            for item, color in zip(data, colors_for_data):
                with ui.row().classes('items-center justify-between text-caption w-full'):
                    with ui.row().classes('items-center gap-2'):
                        ui.element('div').style(f'width:10px;height:10px;border-radius:9999px;background:{color}')
                        ui.label(item['name']).classes('text-grey-7')
                    ui.label(_format_amount(item['value'], 'CHF')).classes('text-grey-8')

    def update_category_trend_chart():
        """Berechnet und zeichnet den Monatsverlauf der Kategorien als gestapelte Balken."""
        nonlocal category_trend_chart, category_trend_chart_container
        if category_trend_chart_container is None:
            return
        category_trend_chart_container.clear()
        if not category_monthly_breakdown:
            with category_trend_chart_container:
                ui.label('Keine Verlaufsdaten vorhanden.').classes('text-caption text-grey-6')
            return
        month_labels = sorted(category_monthly_breakdown.keys())
        if len(month_labels) > 6:
            month_labels = month_labels[-6:]
        totals: dict[str, float] = {}
        for month in month_labels:
            for cat, amount in category_monthly_breakdown[month].items():
                totals[cat] = totals.get(cat, 0.0) + amount
        categories = [cat for cat, _ in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)]
        categories = categories[:6] if len(categories) > 6 else categories
        series = []
        for cat in categories:
            color = _get_category_color(cat)
            data = [round(category_monthly_breakdown[month].get(cat, 0.0), 2) for month in month_labels]
            series.append({'name': cat, 'type': 'bar', 'stack': 'Ausgaben', 'data': data, 'itemStyle': {'color': color}})
        if not series:
            with category_trend_chart_container:
                ui.label('Keine Kategorien mit Daten vorhanden.').classes('text-caption text-grey-6')
            return
        with category_trend_chart_container:
            category_trend_chart = ui.echart({
                'tooltip': {'trigger': 'axis'},
                'legend': {'data': categories},
                'xAxis': {'type': 'category', 'data': month_labels},
                'yAxis': {'type': 'value'},
                'series': series,
            }).classes('w-full h-[320px]')

    def update_budget_display():
        """Spiegelt das maximale Budget aus dem User-Store im KPI-Kärtchen wider."""
        if not budget_label:
            return
        store = _get_user_store(create=False) or {}
        value = store.get('settings_budget')
        if isinstance(value, (int, float)):
            budget_label.set_text(_format_amount(float(value), 'CHF'))
        elif value:
            budget_label.set_text(str(value))
        else:
            budget_label.set_text('Kein Budget')

    def _compute_category_monthly_breakdown(rows: list[dict]) -> dict[str, dict[str, float]]:
        """Aggregiert Ausgabenbetrag je Kategorie/Monat als Basis für Trenddiagramme."""
        breakdown: dict[str, dict[str, float]] = {}
        for r in rows:
            date_value = r.get('transaction_date') or r.get('upload_date')
            try:
                d = datetime.fromisoformat(date_value) if date_value else None
            except Exception:
                d = None
            if not d:
                continue
            month_key = datetime(d.year, d.month, 1).strftime('%Y-%m')
            cat = r.get('category_name') or 'Ohne Kategorie'
            amount = float(r.get('amount') or 0)
            month_entry = breakdown.setdefault(month_key, {})
            month_entry[cat] = month_entry.get(cat, 0.0) + amount
        return breakdown

    def _compute_monthly_summary(rows: list[dict]) -> list[dict]:
        """Bildet Summen der Einnahmen/Ausgaben je Monat aus den Belegdaten."""
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
            update_budget_display()
            update_financial_metrics()
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
        update_budget_display()
        update_financial_metrics()
    async def load_receipts():
        """Lädt alle Belege samt Aggregationen und stößt UI-Updates an."""
        nonlocal receipts, budget_data, income_data, monthly_summary, category_monthly_breakdown, category_color_map
        try:
            user_id = user.get("user_id") or None
            receipts = await asyncio.to_thread(list_receipts_overview, user_id)
            # Derive monthly summary from loaded receipts
            monthly_summary = _compute_monthly_summary(receipts)
            category_monthly_breakdown = _compute_category_monthly_breakdown(receipts)
            category_color_map.clear()

        except Exception as exc:
            ui.notify(f'Belege konnten nicht geladen werden: {exc}', color='negative')
            receipts = []

        update_category_chart()
        update_category_trend_chart()
        update_financial_metrics()
        update_budget_vs_expense_chart()

    with ui.column().classes('w-full items-stretch justify-start min-h-screen gap-4'):
        with ui.row().classes('w-full items-end justify-between q-pl-md q-pr-xl q-pt-sm q-pb-sm bg-gradient-to-r from-white to-blue-50/30 border-b border-white/70'):
            with ui.column().classes('gap-0'):
                ui.label('Dashboard').classes('text-h5')
                ui.label(f'Willkommen zurück, {display_name}').classes('text-caption text-grey-6')
            with ui.row().classes('items-end'):
                month_bar(
                    username=display_name,
                    on_change=lambda _: (
                        update_category_chart(),
                        update_financial_metrics(),
                        update_budget_vs_expense_chart()
                    ),
                )

        with ui.row().classes('w-full gap-4 q-px-md q-pt-md flex-wrap'):
            # Budgetstatus
            with ui.card().classes('w-[340px] h-[180px] bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 items-center justify-center'):
                with ui.column().classes('items-center justify-center gap-2 q-pt-md'):
                    budget_status_icon = ui.icon('speed').classes('text-orange-600 bg-orange-100 rounded-full q-pa-sm').style('font-size: 28px')
                    budget_status_label = ui.label('-').classes('text-h4 text-grey-9')
                    ui.label('Budgetstatus').classes('text-caption text-grey-6')

            # Unter/Über Budget (Differenz)
            with ui.card().classes('w-[340px] h-[180px] bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 items-center justify-center'):
                with ui.column().classes('items-center justify-center gap-2 q-pt-md'):
                    budget_diff_icon = ui.icon('compare_arrows').classes('text-slate-700 bg-slate-100 rounded-full q-pa-sm').style('font-size: 28px')
                    budget_diff_label = ui.label('-').classes('text-h4 text-grey-9 transition-colors duration-200')
                    ui.label('Unter/Über Budget').classes('text-caption text-grey-6 text-center')

            # Gesamtausgaben
            with ui.card().classes('w-[340px] h-[180px] bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 items-center justify-center'):
                with ui.column().classes('items-center justify-center gap-2 q-pt-md'):
                    ui.icon('attach_money').classes('text-blue-600 bg-blue-100 rounded-full q-pa-sm').style('font-size: 28px')
                    total_expense_label = ui.label('-').classes('text-h4 text-grey-9')
                    ui.label('Gesamtausgaben').classes('text-caption text-grey-6')

            # Max. Budget
            with ui.card().classes('w-[340px] h-[180px] bg-white/90 backdrop-blur rounded-2xl shadow-md border border-white/70 items-center justify-center'):
                with ui.column().classes('items-center justify-center gap-2 q-pt-md'):
                    ui.icon('account_balance_wallet').classes('text-grey-700 bg-grey-100 rounded-full q-pa-sm border border-grey-300').style('font-size: 28px')
                    budget_label = ui.label('Kein Budget').classes('text-h4 text-grey-9 text-center')
                    ui.label('Max. Budget').classes('text-caption text-grey-6')
                    ui.timer(0.2, update_budget_display, once=True)

        # Charts row 1: Budget split vs spending and monthly income vs expenses
        with ui.row().classes('w-full gap-4 q-px-md q-pt-md flex-wrap items-stretch'):
            with ui.card().classes('flex-1 min-w-[360px] bg-white/90 rounded-2xl shadow-md border border-white/70'):
                with ui.column().classes('w-full gap-3 q-pa-md'):
                    with ui.row().classes('items-center justify-between'):
                        ui.label('Budget vs. Ausgaben').classes('text-body1 font-medium')
                        ui.label('aktueller Monat').classes('text-caption text-grey-6')
                    budget_split_container = ui.column().classes('items-center justify-center w-full')
                    budget_split_legend = ui.column().classes('w-full gap-1 text-caption text-grey-7')
                ui.timer(0.1, update_budget_split_chart, once=True)

            with ui.card().classes('flex-[1.2] min-w-[420px] bg-white/90 rounded-2xl shadow-md border border-white/70'):
                with ui.column().classes('w-full gap-3 q-pa-md'):
                    with ui.row().classes('items-center justify-between'):
                        ui.label('Budget vs. Ausgaben (Monate)').classes('text-body1 font-medium')
                        ui.label('Budget vs. Ausgaben').classes('text-caption text-grey-6')
                    budget_chart_container = ui.column().classes('w-full')
                ui.timer(0.2, lambda: update_budget_vs_expense_chart(), once=True)

        # Charts row 2: Category donut and stacked monthly categories
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
                        ui.label('Ausgaben nach Kategorie (Monate)').classes('text-body1 font-medium')
                        ui.label('Summen je Monat').classes('text-caption text-grey-6')
                    category_trend_chart_container = ui.column().classes('w-full')
                ui.timer(0.15, update_category_trend_chart, once=True)

        # Initial data load
        ui.timer(0.02, lambda: asyncio.create_task(sync_user_budget()), once=True)
        ui.timer(20, lambda: asyncio.create_task(sync_user_budget()))
        ui.timer(0.05, lambda: asyncio.create_task(load_receipts()), once=True)
    def _get_category_color(category_name: str) -> str:
        """Verteilt Farben gleichmäßig und wiederverwendet sie pro Kategorie."""
        if category_name in category_color_map:
            return category_color_map[category_name]
        color = COLORS[len(category_color_map) % len(COLORS)]
        category_color_map[category_name] = color
        return color
