"""Upload-Seite als separates Modul – gleiche UI, nur sauber aufgeteilt."""

from __future__ import annotations

import asyncio

from nicegui import ui

from app.helpers.auth_helpers import _ensure_authenticated
from app.helpers.ui_helpers import notify_error, notify_success
from app.ui_layout import nav
from app.receipt_analysis import analyze_receipt
from app.services.receipt_upload_service import process_receipt_upload
from app.ui_theme import UPLOAD_CARD


@ui.page('/upload', reconnect_timeout=120.0)
def upload_page():
    """Zeigt die responsive Upload-Ansicht (inkl. Kamera/Desktop-Optionen)."""
    user = _ensure_authenticated()
    if not user:
        return
    nav(user)
    user_id = int(user.get('user_id') or 0)
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

    # Tablets definieren wir wie im Tailwind-Default: md (>=768px) bis <lg (1024px), daher greifen die Klassen weiter unten.
    with ui.column().classes('w-full pt-16 md:pt-0 transition-all z-0'):
        with ui.row().classes('w-full items-end justify-between q-pl-md q-pr-xl q-pt-sm q-pb-sm bg-gradient-to-r from-white to-blue-50/30 border-b border-white/70 z-0'):
            with ui.column().classes('gap-0'):
                ui.label('Beleg hochladen').classes('text-h5')
                ui.label('Neue Belege hinzufügen und verarbeiten').classes('text-caption text-grey-6')
            with ui.row().classes('items-center gap-2'):
                ui.label('Unterstützte Formate').classes('text-caption text-grey-6')
                ui.link('JPG, PNG, PDF', '#').classes('text-indigo-600 text-caption no-underline')

        status_label = ui.label('').classes('text-caption text-grey-6 q-ml-md q-mt-sm')

        async def run_full_flow(selected: dict | None) -> None:
            """Startet Upload + Analyse für die gewählte Datei."""
            if not selected:
                notify_error('Bitte zuerst eine Datei auswählen.')
                return
            try:
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
                notify_success('Beleg verarbeitet')
            except Exception as error:
                status_label.set_text(f'Fehler: {error!s}')
                notify_error(str(error))

        async def handle_upload(event) -> None:
            file_info = {"name": event.file.name or 'receipt.bin', "content": await event.file.read()}
            await run_full_flow(file_info)

        with ui.row().classes('w-full gap-4 q-px-md q-pt-md q-pb-lg flex-wrap items-stretch z-0'):
            # Mobile + Tablets (<1024px) sehen die Kamera-Kachel, damit vor Ort Fotos möglich bleiben.
            with ui.card().classes(f'flex lg:hidden {UPLOAD_CARD}'):
                with ui.column().classes('items-center justify-center gap-2'):
                    ui.icon('photo_camera').classes('text-white bg-gradient-to-br from-blue-500 to-blue-700 rounded-[20px] q-pa-lg').style('font-size: 32px')
                    ui.label('Foto aufnehmen').classes('text-subtitle2 text-grey-9')
                    ui.label('Kamera verwenden um Beleg zu fotografieren').classes('text-caption text-grey-6')
                    cam_u = ui.upload(auto_upload=True, multiple=False)
                    cam_u.props('accept="image/*" capture=environment style="display:none"')
                    ui.button(icon='add', on_click=lambda: cam_u.run_method('pickFiles')).props('round dense flat').classes('bg-indigo-50 text-indigo-700 hover:bg-indigo-100')
                    cam_u.on_upload(handle_upload)

            with ui.card().classes(f'flex {UPLOAD_CARD}'):
                with ui.column().classes('items-center justify-center gap-2'):
                    ui.icon('description').classes('text-white bg-gradient-to-br from-blue-500 to-blue-700 rounded-[20px] q-pa-lg').style('font-size: 32px')
                    ui.label('Datei auswählen').classes('text-subtitle2 text-grey-9')
                    ui.label('PDF oder Bild von Ihrem Gerät auswählen').classes('text-caption text-grey-6')
                    file_u = ui.upload(auto_upload=True, multiple=False)
                    file_u.props('accept=".pdf,.heic,.heif,.jpg,.jpeg,.png,.webp,image/*" style="display:none"')
                    ui.button(icon='add', on_click=lambda: file_u.run_method('pickFiles')).props('round dense flat').classes('bg-indigo-50 text-indigo-700 hover:bg-indigo-100')
                    file_u.on_upload(handle_upload)

            # Tablets (>=768px) und Desktop bekommen zusätzlich Drag & Drop.
            with ui.card().classes(
                'relative hidden md:flex bg-gradient-to-br from-white to-blue-50/40 rounded-2xl shadow-md '
                'border-dashed border-2 border-grey-4 items-center justify-center transition-transform duration-300 ease-in-out '
                'w-[420px] h-[240px]'
            ):
                with ui.column().classes('items-center justify-center gap-2 pointer-events-none'):
                    ui.icon('upload').classes('text-white bg-gradient-to-br from-blue-500 to-blue-700 rounded-[20px] q-pa-lg').style('font-size: 32px')
                    ui.label('Drag and Drop').classes('text-subtitle2 text-grey-9')
                    ui.label('Beleg hierher ziehen und ablegen').classes('text-caption text-grey-6')
                drop_u = ui.upload(label='', auto_upload=True, multiple=False)
                drop_u.props('accept=".pdf,.heic,.heif,.jpg,.jpeg,.png,.webp,image/*" style="opacity:0; position:absolute; inset:0; cursor:pointer"')
                drop_u.on_upload(handle_upload)

    return
