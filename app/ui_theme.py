"""Zentrales Theme-Modul für NiceGUI, damit alle Oberflächen gleich aussehen."""

from nicegui import ui

# Dieses Nachschlagewerk bündelt häufig genutzte Gestaltungswerte, damit man sie überall gleich verwenden kann.
THEME: dict[str, object] = {
    "font_sizes": {"title": "text-h5", "caption": "text-caption text-grey-6"},
    "radius": "rounded-2xl",
    "shadow": "shadow-md",
    "padding": "p-6 md:p-10",
}

# Einheitliche Card-Klasse speziell für die Upload-Kacheln.
UPLOAD_CARD = (
    'w-[420px] h-[240px] bg-white/95 rounded-2xl shadow-md border '
    'border-white/70 items-center justify-center transition-transform duration-300 ease-in-out'
)


def set_colors() -> None:
    """Richtet die globale Farbpalette samt Gradient ein, damit alle Komponenten das gleiche Farbschema haben."""

    # ui.colors definiert Grundfarben wie Primär, Akzent usw., die NiceGUI für Buttons und andere Komponenten nutzt.
    ui.colors(
        primary='linear-gradient(90deg, #3B82F6 0%, #6D28D9 100%)',
        secondary='#6366F1',
        accent='#A855F7',
        positive='#22C55E',
        negative='#EF4444',
        warning='#F59E0B',
        info='#3B82F6',
        dark='#0B0B0B',
    )


def set_global_styles() -> None:
    """Injiziert globales CSS, damit Schriftarten, Buttons, Karten und Abstände einheitlich aussehen."""

    # ui.add_head_html fügt eigenen CSS-Code in den <head> der Seite ein, wodurch wir globale Regeln setzen können.
    ui.add_head_html(
        '''
        <style>
            /* Lädt die gewünschten Google-Fonts und stellt sicher, dass sie überall verfügbar sind. */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Poppins:wght@500;600&display=swap');

            :root {
                --font-base: 'Inter', 'Roboto', sans-serif;
                --font-heading: 'Poppins', 'Inter', sans-serif;
                --bg-page: #F4F6FB;
                --text-base: #1f2937;
            }

            /* Setzt Grundlayout und Schriftarten für den gesamten Body. */
            body {
                font-family: var(--font-base);
                background: var(--bg-page);
                color: var(--text-base);
                margin: 0;
            }

            /* Hebt Überschriften hervor, damit sie klar erkennbar sind. */
            h1, h2, h3, h4, h5, h6 {
                font-family: var(--font-heading);
                color: #1f2a44;
            }

            /* Vereinheitlicht Buttons: leicht abgerundet, sanfter Hover-Effekt. */
            .nicegui-button {
                border-radius: 12px !important;
                transition: filter 0.2s ease, transform 0.2s ease;
            }

            .nicegui-button:hover {
                filter: brightness(1.05);
                transform: translateY(-1px);
            }

            /* Karten bekommen eine sanfte Schattierung und Blur, um sich vom Hintergrund abzuheben. */
            .nicegui-card {
                border-radius: 20px;
                box-shadow: 0 20px 45px -25px rgba(15, 76, 255, 0.4);
                backdrop-filter: blur(8px);
            }

            /* Einheitliche Hintergrundfarbe für Drawer und andere Paneele. */
            .nicegui-drawer {
                background: rgba(255, 255, 255, 0.9);
                backdrop-filter: blur(8px);
            }
        </style>
        '''
    )
