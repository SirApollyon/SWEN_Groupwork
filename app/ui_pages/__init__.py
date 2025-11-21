"""Aggregiert alle NiceGUI-Seiten, damit main.py sie nur importieren muss."""

# Durch diese Imports werden die @ui.page Dekoratoren ausgeführt und die Seiten registriert.
from .dashboard_extended_page import dashboard_extended_page  # noqa: F401
from . import home_page  # noqa: F401
from . import login_page  # noqa: F401
from . import receipts_page  # noqa: F401
from . import settings_page  # noqa: F401
from . import upload_page  # noqa: F401

__all__ = [
    "dashboard_extended_page",
    "home_page",
    "login_page",
    "receipts_page",
    "settings_page",
    "upload_page",
]
