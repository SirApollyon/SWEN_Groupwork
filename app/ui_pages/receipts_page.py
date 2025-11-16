"""Receipts-Seite als eigenes Modul – übernimmt 1:1 die bisherige UI."""

from __future__ import annotations

import asyncio

from nicegui import ui

from app.db import delete_receipt, get_receipt_detail, list_receipts_overview
from app.helpers.auth_helpers import _ensure_authenticated
from app.helpers.receipt_helpers import (
    CATEGORY_BADGE_BASE,
    CATEGORY_STYLE_MAP,
    DEFAULT_CATEGORY_STYLE,
    DEFAULT_STATUS_STYLE,
    PLACEHOLDER_IMAGE_DATA_URL,
    STATUS_BADGE_BASE,
    STATUS_STYLE_MAP,
    _format_amount,
    _format_date,
    _image_to_data_url,
)
from app.ui_layout import nav


@ui.page('/receipts')
def receipts_page():
    """Zeigt alle Belege inkl. Filter, Detaildialog und Responsive Cards."""
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)

    receipts: list[dict] = []
    filtered: list[dict] = []
    category_options: list[str] = ["Alle Kategorien"]

    with ui.column().classes(
        "w-full items-center min-h-screen gap-6 q-pa-xl"
    ):
        header_row = ui.row().classes("w-full max-w-6xl items-end justify-between")
        with header_row:
            ui.label("Belegübersicht").classes("text-h5")
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
                detail_caption = ui.label(" ").classes("text-caption text-grey-6")
            with ui.column().classes("w-7/12 gap-3"):
                with ui.row().classes("items-center justify-between gap-2"):
                    ui.label("Extrahierte Informationen").classes(
                        "text-body1 font-semibold text-grey-8"
                    )
                    detail_status_badge = ui.label("Unbekannt").classes(
                        f"{STATUS_BADGE_BASE} bg-grey-200 text-grey-600"
                    )
                detail_info_label = ui.label(" ").classes("text-caption text-primary")
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
        """Aktualisiert die Kopfzeile mit der Anzahl der aktuell sichtbaren Belege."""
        if not receipts:
            total_count_label.set_text("Keine Belege vorhanden")
        else:
            total_count_label.set_text(
                f"{len(filtered)} von {len(receipts)} Belegen angezeigt"
            )

    def apply_filters() -> None:
        """Filtert die Belegliste anhand Suchtext und Kategorie-Auswahl."""
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
        """Rendert das Kartengrid neu, damit die Filterergebnisse sichtbar werden."""
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
                    lambda e, rid=receipt_id: show_receipt_detail(rid),
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
                        with ui.row().classes(
                            "items-end justify-between gap-2 w-full"
                        ):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(category_name).classes(
                                    f"{CATEGORY_BADGE_BASE} {category_classes}"
                                )
                                ui.label(status_style["label"]).classes(
                                    f"{STATUS_BADGE_BASE} {status_style['classes']}"
                                )
                            delete_icon = ui.icon("delete_outline").classes(
                                "receipt-delete-icon text-grey-5 hover:text-red-500 cursor-pointer text-2xl transition-colors"
                            )
                            delete_icon.on(
                                "click.stop",
                                lambda e, rid=receipt_id: handle_delete_click(rid),
                            )


    async def handle_delete_click(receipt_id: int) -> None:
        """Löscht den ausgewählten Beleg, aktualisiert die UI und zeigt Feedback an."""
        nonlocal receipts, filtered
        try:
            await asyncio.to_thread(
                delete_receipt,
                receipt_id,
                user_id=user.get("user_id"),
            )
        except ValueError as exc:
            ui.notify(str(exc), color="negative")
            return
        except Exception as exc:
            ui.notify(f"Beleg konnte nicht gelöscht werden: {exc}", color="negative")
            return

        receipts = [r for r in receipts if r.get("receipt_id") != receipt_id]
        filtered = [r for r in filtered if r.get("receipt_id") != receipt_id]
        ui.notify("Beleg wurde gelöscht.", color="positive")
        render_cards()


    async def show_receipt_detail(receipt_id: int) -> None:
        """Befüllt den Detaildialog zum gewünschten Beleg und öffnet ihn."""
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
        """Lädt alle Belege vom Backend und setzt Filter sowie UI-Elemente zurück."""
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
    ui.timer(0.1, load_data, once=True)
