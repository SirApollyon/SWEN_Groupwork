# -*- coding: utf-8 -*-
"""
Dieses Skript verwendet ein KI-Modell (Google GenAI), um Informationen
aus Bildern von Belegen zu extrahieren und in einer Datenbank zu speichern.
"""

import asyncio
import json
import os
from datetime import datetime, date
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict, Optional, Tuple, List

from geopy import geocoders
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from google.genai import Client, types
from PIL import Image, UnidentifiedImageError

# Importiert Datenbank-Funktionen aus einer anderen Datei im Projekt.
from app.db import (
    get_category_id_by_name,
    get_primary_account_id,
    insert_transaction_record,
    list_user_categories,
    load_receipt_image,
    mark_receipt_status,
    update_receipt_issuer,
)

# Dies ist die Anweisung für das KI-Modell.
# Es beschreibt, welche Informationen extrahiert werden sollen und in welchem Format.
PROMPT = """
You are a financial assistant that extracts structured data from receipt images. 
You MUST respond with strict JSON using the following schema:

{
  "is_receipt": boolean,
  "total_amount": number | null,
  "currency": string | null,
  "transaction_date": "YYYY-MM-DD" | null,
  "category": string | null,
  "description": string | null,
  "type": "expense" | "income" | null,
  "issuer_name": string | null,
  "issuer_street": string | null,
  "issuer_city": string | null,
  "issuer_postal_code": string | null,
  "issuer_country": string | null
}

Wenn Informationen fehlen, verwende null. Füge keine Erklärungen hinzu.
"""


class ReceiptAnalyzer:
    """
    Diese Klasse kümmert sich um die Analyse eines einzelnen Belegs.
    Sie lädt das Bild, sendet es an das KI-Modell und verarbeitet die Antwort.
    """

    def __init__(self) -> None:
        """Initialisiert den Analyzer und den Google GenAI Client."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Der GOOGLE_API_KEY wurde nicht in der Umgebung gefunden."
            )
        self.client = Client(api_key=api_key)
        self.model_name = os.getenv("GOOGLE_RECEIPT_MODEL", "gemma-3-27b-it")

    def analyze(self, receipt_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Hauptmethode zur Analyse eines Belegs.
        Sie lädt das Bild, fragt das KI-Modell ab und speichert das Ergebnis.
        """
        try:
            # 1. Belegdaten aus der Datenbank laden
            receipt_row = load_receipt_image(receipt_id)
            resolved_user_id = user_id or receipt_row.get("user_id")
            if not resolved_user_id:
                raise ValueError("Beleg ist keinem Benutzer zugeordnet.")

            # 2. Benutzerkategorien abrufen
            categories = list_user_categories(resolved_user_id)
            if not categories:
                return self._handle_error(
                    receipt_id,
                    "Für diesen Benutzer sind keine Kategorien konfiguriert.",
                    "no_categories",
                )

            # 3. Prompt für das KI-Modell erstellen
            prompt_text = self._build_prompt(categories)

            # 4. KI-Modell mit Bild und Prompt abfragen
            image_bytes = receipt_row["receipt_image"]
            response_text = self._query_model(image_bytes, prompt_text)

            # 5. Antwort des Modells (JSON) verarbeiten
            parsed_data = self._parse_response(response_text)

            # 6. Prüfen, ob es sich um einen Beleg handelt
            if not parsed_data.get("is_receipt"):
                return self._handle_error(
                    receipt_id,
                    "Das Modell hat das Bild nicht als Beleg klassifiziert.",
                    "ignored",
                    raw=parsed_data,
                )

            # 7. Transaktionsdaten erstellen und speichern
            return self._process_transaction(
                receipt_id, resolved_user_id, parsed_data, response_text
            )

        except Exception as e:
            # Allgemeine Fehlerbehandlung
            return self._handle_error(receipt_id, str(e), "analysis_error")

    def _process_transaction(
        self,
        receipt_id: int,
        user_id: int,
        parsed_data: Dict[str, Any],
        raw_response: str,
    ) -> Dict[str, Any]:
        """Verarbeitet die extrahierten Daten und speichert sie als Transaktion."""

        # Extrahiere Betrag und Kategorie
        amount = self._to_decimal(parsed_data.get("total_amount"))
        category_name = self._safe_str(parsed_data.get("category"))

        if amount is None or not category_name:
            return self._handle_error(
                receipt_id,
                "Betrag oder Kategorie fehlen in der Antwort.",
                "incomplete",
                raw=parsed_data,
            )

        # Standardwerte für fehlende Felder festlegen
        txn_date = self._parse_date(parsed_data.get("transaction_date")) or date.today()
        txn_type = self._safe_str(parsed_data.get("type")) or "expense"
        description = self._safe_str(parsed_data.get("description")) or "Beleg-Import"
        currency = self._safe_str(parsed_data.get("currency")) or "CHF"

        # IDs für Konto und Kategorie aus der Datenbank holen
        account_id = get_primary_account_id(user_id)
        category_id = get_category_id_by_name(user_id, category_name)

        if category_id is None:
            return self._handle_error(
                receipt_id,
                f"Kategorie '{category_name}' nicht gefunden.",
                "category_not_found",
                raw=parsed_data,
            )

        # Transaktion in der Datenbank speichern
        transaction = insert_transaction_record(
            account_id=account_id,
            amount=amount,
            category_id=category_id,
            description=description,
            txn_date=txn_date,
            txn_type=txn_type,
            currency=currency,
            receipt_id=receipt_id,
        )

        # Ausstellerinformationen aktualisieren (inkl. Geocoding)
        issuer_payload = self._update_issuer_info(receipt_id, parsed_data)

        # Status des Belegs auf "verarbeitet" setzen
        mark_receipt_status(receipt_id, status_id=2, extracted_text=raw_response)

        return {
            "status": "processed",
            "raw": parsed_data,
            "transaction": transaction,
            "issuer": issuer_payload,
        }

    def _update_issuer_info(
        self, receipt_id: int, parsed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extrahiert Ausstellerinfos, findet Koordinaten und speichert sie."""
        issuer_payload = self._extract_issuer_fields(parsed_data)
        lat, lon = self._geocode_latlon(issuer_payload)

        issuer_payload["issuer_latitude"] = lat
        issuer_payload["issuer_longitude"] = lon

        update_receipt_issuer(receipt_id, **issuer_payload)
        return issuer_payload

    def _handle_error(
        self,
        receipt_id: int,
        error_message: str,
        status: str,
        raw: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Zentrale Funktion zur Behandlung von Fehlern während der Analyse."""
        mark_receipt_status(
            receipt_id,
            status_id=3,  # Status für Fehler
            error_message=error_message,
        )
        response = {"status": status, "error": error_message}
        if raw:
            response["raw"] = raw
        return response

    def _build_prompt(self, categories: List[Dict]) -> str:
        """Erstellt den Prompt für das KI-Modell, inklusive der erlaubten Kategorien."""
        # Fügt die Liste der erlaubten Kategorien zum Basis-Prompt hinzu.
        # Das hilft dem Modell, eine passende Kategorie auszuwählen.
        lines = [
            PROMPT,
            "",
            "Erlaubte Kategorien (Name | Typ):",
        ]
        for cat in categories:
            lines.append(f"- {cat['name']} | {cat['type']}")
        lines.append(
            "Du MUSST das Feld 'category' auf genau einen der obigen Namen setzen."
        )
        return "\n".join(lines)

    def _query_model(self, image_bytes: bytes, prompt_text: str) -> str:
        """Sendet das Bild und den Prompt an das KI-Modell."""
        media_type = self._guess_media_type(image_bytes)

        # Die Anfrage an das Modell besteht aus dem Prompt und dem Bild.
        # Die `types.Content` Struktur ist notwendig für die API.
        request_contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part(text=prompt_text),
                    types.Part(
                        inline_data=types.Blob(data=image_bytes, mime_type=media_type)
                    ),
                ],
            )
        ]

        # Sendet die Anfrage und gibt die Antwort als Text zurück.
        # Der Model-Name muss übergeben werden und der Aufruf erfolgt über `client.models`
        response = self.client.models.generate_content(
            model=self.model_name, contents=request_contents
        )
        return response.text

    @staticmethod
    def _extract_issuer_fields(parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Extrahiert die Adressfelder des Ausstellers aus der Antwort."""
        return {
            "issuer_name": ReceiptAnalyzer._safe_str(parsed.get("issuer_name")),
            "issuer_street": ReceiptAnalyzer._safe_str(parsed.get("issuer_street")),
            "issuer_city": ReceiptAnalyzer._safe_str(parsed.get("issuer_city")),
            "issuer_postal_code": ReceiptAnalyzer._safe_str(
                parsed.get("issuer_postal_code")
            ),
            "issuer_country": ReceiptAnalyzer._safe_str(parsed.get("issuer_country")),
        }

    def _geocode_latlon(
        self, issuer: Dict[str, Any]
    ) -> Tuple[Optional[float], Optional[float]]:
        """Versucht, aus einer Adresse geografische Koordinaten (Breiten- und Längengrad) zu ermitteln."""
        address_parts = [
            issuer.get("issuer_street"),
            issuer.get("issuer_postal_code"),
            issuer.get("issuer_city"),
            issuer.get("issuer_country"),
        ]
        address = ", ".join(part for part in address_parts if part)

        if not address:
            return None, None

        try:
            # Verwendet den Nominatim-Dienst für das Geocoding.
            geocoder = geocoders.Nominatim(
                user_agent=os.getenv("GEOCODER_USER_AGENT", "receipt-analyzer")
            )
            location = geocoder.geocode(address, timeout=10)
            if location:
                return float(location.latitude), float(location.longitude)
        except (GeocoderTimedOut, GeocoderServiceError):
            # Fehler bei der Verbindung zum Geocoding-Dienst.
            return None, None
        return None, None

    @staticmethod
    def _guess_media_type(data: bytes) -> str:
        """Bestimmt den Medientyp (z.B. 'image/jpeg') des Bildes."""
        # Dies ist wichtig, damit das KI-Modell weiß, wie es die Daten interpretieren soll.
        try:
            with Image.open(BytesIO(data)) as img:
                fmt = (img.format or "").strip().lower()
        except (UnidentifiedImageError, OSError):
            fmt = None
        if fmt == "jpg":
            fmt = "jpeg"
        return f"image/{fmt}" if fmt else "image/jpeg"

    @staticmethod
    def _parse_response(text: str) -> Dict[str, Any]:
        """Verwandelt die Text-Antwort des Modells in ein Python-Dictionary (JSON)."""
        text = text.strip()
        # Manchmal packt das Modell den JSON-Code in Markdown-Blöcke (```json ... ```).
        # Dieser Code entfernt diese Blöcke.
        if text.startswith("```") and text.endswith("```"):
            text = "\n".join(text.splitlines()[1:-1])

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(
                "Die Antwort des KI-Modells war kein gültiges JSON."
            ) from e

    # -- Hilfsfunktionen zur Datenkonvertierung --

    @staticmethod
    def _to_decimal(value: Any) -> Optional[Decimal]:
        """Wandelt einen Wert sicher in ein Decimal-Objekt um."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        """Wandelt einen String im ISO-Format (YYYY-MM-DD) in ein Datumsobjekt um."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value)).date()
        except Exception:
            return None

    @staticmethod
    def _safe_str(value: Any) -> Optional[str]:
        """Wandelt einen Wert sicher in einen String um und entfernt Leerzeichen."""
        if value is None:
            return None
        value = str(value).strip()
        return value or None


# -- Singleton-Pattern für den Analyzer --
# Dies stellt sicher, dass nur eine Instanz des ReceiptAnalyzer erstellt wird.
# Das spart Ressourcen, da der KI-Client nicht bei jeder Anfrage neu initialisiert werden muss.
_analyzer: Optional[ReceiptAnalyzer] = None


def _get_analyzer() -> ReceiptAnalyzer:
    """Gibt die globale Analyzer-Instanz zurück und erstellt sie bei Bedarf."""
    global _analyzer
    if _analyzer is None:
        _analyzer = ReceiptAnalyzer()
    return _analyzer


async def analyze_receipt(
    receipt_id: int, user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Asynchrone Wrapper-Funktion.
    Ermöglicht es, die blockierende Analyse in einem separaten Thread auszuführen,
    damit die Benutzeroberfläche nicht einfriert.
    """
    loop = asyncio.get_running_loop()
    analyzer = _get_analyzer()
    # Führt die 'analyze'-Methode in einem Executor aus (separater Thread).
    return await loop.run_in_executor(
        None, lambda: analyzer.analyze(receipt_id, user_id)
    )
