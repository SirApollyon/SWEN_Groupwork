"""Hilfsfunktionen für Anmeldung, Storage und Weiterleitungen – ausgelagert für bessere Übersicht."""

from __future__ import annotations

from typing import Any

from nicegui import app as ng_app, ui


# Diese Funktionen kapseln sämtlichen Umgang mit dem Benutzer-Speicher,
# damit sie von allen Pages importiert werden können ohne doppelten Code.
def _get_user_store(create: bool = False) -> dict | None:
    """Liefert den benutzerspezifischen Storage (persistiert über Seitenwechsel)."""
    try:
        store = ng_app.storage.user
        if store is not None:
            return store
    except Exception:
        store = None

    client = getattr(ui.context, "client", None)
    if not client:
        return None
    root_storage = getattr(client, "storage", None)
    if not root_storage:
        return None

    contains_user_key = False
    try:
        contains_user_key = "user" in root_storage  # type: ignore[operator]
    except Exception:
        contains_user_key = False

    if not contains_user_key:
        if not create:
            return None
        try:
            root_storage["user"] = {}  # type: ignore[index]
        except Exception:
            try:
                setattr(root_storage, "user", {})
            except Exception:
                return None

    store = None
    getter = getattr(root_storage, "get", None)
    if callable(getter):
        try:
            store = getter("user")
        except Exception:
            store = None
    if store is None:
        try:
            store = getattr(root_storage, "user")
        except Exception:
            store = None

    if isinstance(store, dict):
        return store

    if store is None:
        if not create:
            return None
        normalized: dict[str, Any] = {}
    else:
        try:
            normalized = dict(store)
        except TypeError:
            normalized = {}

    stored_ok = False
    try:
        root_storage["user"] = normalized  # type: ignore[index]
        stored_ok = True
    except Exception:
        pass
    if not stored_ok:
        try:
            setattr(root_storage, "user", normalized)
            stored_ok = True
        except Exception:
            return None

    refreshed = None
    if stored_ok:
        getter = getattr(root_storage, "get", None)
        if callable(getter):
            try:
                refreshed = getter("user")
            except Exception:
                refreshed = None
        if refreshed is None:
            try:
                refreshed = getattr(root_storage, "user")
            except Exception:
                refreshed = None

    return refreshed if isinstance(refreshed, dict) else normalized


def _get_logged_in_user() -> dict | None:
    """Liest die gespeicherten Benutzerdaten aus dem Browser-Speicher."""
    storage = _get_user_store(create=False)
    if storage is None:
        return None

    guest_flag = storage.get("guest")
    if guest_flag:
        return {
            "user_id": None,
            "email": None,
            "name": "Demo-Modus",
            "guest": True,
        }

    user_id = storage.get("user_id")
    if user_id is None:
        return None
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        return None
    return {
        "user_id": user_id_int,
        "email": storage.get("email"),
        "name": storage.get("name"),
        "guest": bool(storage.get("guest")),
    }


def _set_logged_in_user(user: dict) -> None:
    """Speichert Benutzerinformationen nach erfolgreicher Anmeldung."""
    store = _get_user_store(create=True)
    if store is None:
        return
    store.pop("guest", None)
    store["user_id"] = int(user.get("user_id"))
    store["email"] = user.get("email")
    store["name"] = user.get("name")


def _set_guest_user() -> None:
    """Aktiviert den Demo-Modus ohne Anmeldung."""
    store = _get_user_store(create=True)
    if store is None:
        return
    store.clear()
    store["user_id"] = 1
    store["email"] = None
    store["name"] = "Demo-Konto"
    store["guest"] = False


def _clear_logged_in_user() -> None:
    """Löscht gespeicherte Anmeldedaten (z.B. beim Ausloggen)."""
    store = _get_user_store(create=False)
    if not store:
        return
    try:
        store.clear()
    except AttributeError:
        for key in list(store.keys()):
            del store[key]


def _redirect_to_login(message: str | None = None) -> None:
    """Zeigt einen kurzen Hinweis und leitet anschließend zur Login-Seite um."""
    ui.timer(0.1, lambda: ui.navigate.to("/login"), once=True)
    with ui.column().classes(
        "items-center justify-center h-screen gap-3 text-grey-6"
    ):
        ui.spinner("dots").classes("text-primary text-4xl")
        ui.label(message or "Weiterleitung zum Login ...").classes(
            "text-body2 text-grey-6"
        )


def _ensure_authenticated(message: str | None = None) -> dict | None:
    """Gibt den eingeloggten Benutzer zurück oder leitet andernfalls zum Login um."""
    user = _get_logged_in_user()
    if not user:
        _redirect_to_login(message)
        return None
    return user


def _logout_and_redirect() -> None:
    """Meldet den aktuellen Benutzer ab und führt zurück zur Login-Seite."""
    try:
        _clear_logged_in_user()
    finally:
        ui.navigate.to("/login")
