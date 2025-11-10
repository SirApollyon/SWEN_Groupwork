"""UI-spezifische Mini-Helfer, damit wiederkehrende Anzeigen zentral gepflegt werden können."""

from __future__ import annotations

from nicegui import ui


def notify_error(message: str, *, caption: str | None = None) -> None:
    """Zeigt eine konsistente rote Snackbar – ideal für Anfänger:innen als visuelles Feedback."""
    ui.notify(message if caption is None else f"{caption}: {message}", color='negative')


def notify_success(message: str) -> None:
    """Zeigt eine grüne Snackbar für Erfolgsmeldungen."""
    ui.notify(message, color='positive')
