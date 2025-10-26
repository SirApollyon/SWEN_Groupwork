# -*- coding: utf-8 -*-
"""
Hilfsfunktionen für den Datenbankzugriff (Azure SQL).

Dieses Modul enthält alle Funktionen, die für die Interaktion mit der
Azure SQL-Datenbank benötigt werden. Es kümmert sich um das Herstellen
von Verbindungen, das Ausführen von SQL-Abfragen und das Zurückgeben der Ergebnisse.
"""

import os
from datetime import date, datetime
from decimal import Decimal
from dotenv import load_dotenv
import pymssql

# Lädt Umgebungsvariablen aus einer .env-Datei.
# Das ist nützlich, um sensible Daten wie Passwörter nicht direkt im Code zu speichern.
# Stattdessen werden sie aus einer lokalen .env-Datei oder den Umgebungsvariablen des Systems geladen.
load_dotenv()

# --- Datenbank-Verbindungseinstellungen ---
# Die folgenden Werte werden aus den Umgebungsvariablen gelesen.
SERVER = os.getenv("AZURE_SQL_SERVER")
DATABASE = os.getenv("AZURE_SQL_DB")
USER = os.getenv("AZURE_SQL_USER")
PWD = os.getenv("AZURE_SQL_PASSWORD")
PORT = int(
    os.getenv("AZURE_SQL_PORT", "1433")
)  # Standard-Port 1433, falls nicht anders angegeben

# Ein Dictionary, das alle Verbindungsparameter sammelt.
# Das macht den Code sauberer, da wir nicht jeden Parameter einzeln übergeben müssen.
CONNECT_KW = dict(
    server=SERVER,
    user=USER,
    password=PWD,
    database=DATABASE,
    port=PORT,
    timeout=30,
    login_timeout=30,
    tds_version="7.4",  # Wichtig für die Kompatibilität mit Azure SQL
)


def insert_receipt(user_id: int, content: bytes):
    """
    Speichert einen neuen Beleg (als Bild-Bytes) in der Datenbank.

    Args:
        user_id: Die ID des Benutzers, dem der Beleg gehört.
        content: Der Dateiinhalt des Belegs (z.B. ein JPG- oder PNG-Bild).

    Returns:
        Ein Dictionary mit den Basisdaten des neu erstellten Belegs,
        wie receipt_id, upload_date und status_id.
    """
    if not content:
        raise ValueError(
            "Die hochgeladene Datei ist leer und kann nicht gespeichert werden."
        )

    # 'with' stellt sicher, dass die Verbindung zur Datenbank automatisch geschlossen wird,
    # auch wenn Fehler auftreten.
    with pymssql.connect(**CONNECT_KW) as conn:
        # Ein 'cursor' wird benötigt, um SQL-Befehle auszuführen.
        # 'as_dict=True' sorgt dafür, dass die Ergebnisse als Dictionary (key-value)
        # statt als Tupel zurückgegeben werden, was den Code lesbarer macht.
        with conn.cursor(as_dict=True) as cur:
            # 1. Überprüfen, ob der Benutzer existiert, bevor wir einen Beleg hinzufügen.
            cur.execute(
                "SELECT user_id FROM app.users WHERE user_id=%s",
                (user_id,),
            )
            if not cur.fetchone():
                raise ValueError(f"Benutzer mit der ID {user_id} wurde nicht gefunden.")

            # 2. Den neuen Beleg in die Tabelle 'receipts' einfügen.
            # 'OUTPUT INSERTED.*' gibt die Werte der gerade eingefügten Zeile zurück.
            cur.execute(
                """
                INSERT INTO app.receipts (user_id, receipt_image)
                OUTPUT INSERTED.receipt_id, INSERTED.upload_date, INSERTED.status_id
                VALUES (%s, %s)
                """,
                (
                    user_id,
                    content,
                ),  # Die Parameter werden sicher eingefügt, um SQL-Injection zu verhindern.
            )
            row = cur.fetchone()  # Das Ergebnis der 'OUTPUT'-Klausel abrufen.

            # 'commit()' speichert die Änderungen dauerhaft in der Datenbank.
            conn.commit()

            # Die zurückgegebenen Daten für die weitere Verwendung vorbereiten.
            return {
                "receipt_id": row["receipt_id"],
                "upload_date": row[
                    "upload_date"
                ].isoformat(),  # Datum in einen Standard-String umwandeln
                "status_id": row["status_id"],
            }


def load_receipt_image(receipt_id: int) -> dict:
    """
    Lädt das Bild und die zugehörigen Metadaten für eine bestimmte Beleg-ID.

    Args:
        receipt_id: Die ID des Belegs, der geladen werden soll.

    Returns:
        Ein Dictionary, das 'receipt_id', 'user_id' und 'receipt_image' (als Bytes) enthält.
    """
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(
                """
                SELECT receipt_id, user_id, receipt_image
                FROM app.receipts
                WHERE receipt_id=%s
                """,
                (receipt_id,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Beleg mit der ID {receipt_id} nicht gefunden.")
            return row


def mark_receipt_status(
    receipt_id: int,
    *,
    status_id: int,
    extracted_text: str | None = None,
    error_message: str | None = None,
) -> None:
    """
    Aktualisiert den Status, den extrahierten Text oder eine Fehlermeldung für einen Beleg.
    Das Sternchen (*) in den Parametern erzwingt, dass alle folgenden Argumente
    mit ihrem Namen angegeben werden müssen (z.B. status_id=2).

    Args:
        receipt_id: Die ID des zu aktualisierenden Belegs.
        status_id: Die neue Status-ID (z.B. 1 für 'in Bearbeitung', 2 für 'erfolgreich').
        extracted_text: Der aus dem Beleg extrahierte Text (optional).
        error_message: Eine Fehlermeldung, falls bei der Verarbeitung etwas schiefgelaufen ist (optional).
    """
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE app.receipts
                SET status_id=%s,
                    extracted_text=%s,
                    error_message=%s
                WHERE receipt_id=%s
                """,
                (status_id, extracted_text, error_message, receipt_id),
            )
            conn.commit()


# Standardwerte für automatisch angelegte Konten, falls in .env definiert
AUTO_ACCOUNT_NAME = os.getenv("AUTO_ACCOUNT_NAME", "Standardkonto")
AUTO_ACCOUNT_CURRENCY = os.getenv("AUTO_ACCOUNT_CURRENCY", "CHF")


def get_primary_account_id(user_id: int) -> int:
    """
    Sucht das Hauptkonto eines Benutzers. Wenn keines existiert, wird automatisch ein neues erstellt.

    Args:
        user_id: Die ID des Benutzers.

    Returns:
        Die ID des Hauptkontos.
    """
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            # Zuerst versuchen, ein existierendes Konto zu finden.
            cur.execute(
                """
                SELECT TOP 1 account_id
                FROM app.accounts
                WHERE user_id=%s
                ORDER BY account_id
                """,
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                return row["account_id"]

            # Wenn kein Konto gefunden wurde, ein neues Standardkonto anlegen.
            account_name = f"{AUTO_ACCOUNT_NAME} {datetime.utcnow():%Y%m%d%H%M%S}"
            cur.execute(
                """
                INSERT INTO app.accounts (user_id, account_name, balance, currency)
                OUTPUT INSERTED.account_id
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, account_name, Decimal("0.00"), AUTO_ACCOUNT_CURRENCY),
            )
            new_row = cur.fetchone()
            conn.commit()

            if not new_row:
                raise RuntimeError("Das Standardkonto konnte nicht erstellt werden.")

            return new_row["account_id"]


def get_category_id_by_name(user_id: int, category_name: str) -> int | None:
    """
    Sucht die ID einer Kategorie anhand ihres Namens. Die Suche ignoriert Groß- und Kleinschreibung.

    Args:
        user_id: Die ID des Benutzers.
        category_name: Der Name der gesuchten Kategorie.

    Returns:
        Die ID der Kategorie oder None, wenn keine passende Kategorie gefunden wurde.
    """
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(
                """
                SELECT category_id
                FROM app.categories
                WHERE user_id=%s AND LOWER(name)=LOWER(%s)
                """,
                (user_id, category_name),
            )
            row = cur.fetchone()
            return row["category_id"] if row else None


def list_user_categories(user_id: int) -> list[dict]:
    """
    Listet alle Kategorien für einen bestimmten Benutzer auf.

    Args:
        user_id: Die ID des Benutzers.

    Returns:
        Eine Liste von Dictionaries, wobei jedes Dictionary eine Kategorie repräsentiert.
        Enthält 'category_id', 'name' und 'type'.
    """
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(
                """
                SELECT category_id, name, [type]
                FROM app.categories
                WHERE user_id=%s
                ORDER BY name
                """,
                (user_id,),
            )
            return (
                cur.fetchall() or []
            )  # Gibt eine leere Liste zurück, wenn keine Kategorien gefunden wurden.


def update_receipt_issuer(
    receipt_id: int,
    *,
    issuer_name: str | None = None,
    issuer_street: str | None = None,
    issuer_city: str | None = None,
    issuer_postal_code: str | None = None,
    issuer_country: str | None = None,
    issuer_latitude: float | None = None,
    issuer_longitude: float | None = None,
) -> None:
    """
    Aktualisiert die Informationen zum Aussteller eines Belegs (z.B. Name und Adresse des Geschäfts).

    Args:
        receipt_id: Die ID des zu aktualisierenden Belegs.
        issuer_...: Die neuen Daten des Ausstellers.
    """
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE app.receipts
                SET issuer_name=%s,
                    issuer_street=%s,
                    issuer_city=%s,
                    issuer_postal_code=%s,
                    issuer_country=%s,
                    issuer_latitude=%s,
                    issuer_longitude=%s
                WHERE receipt_id=%s
                """,
                (
                    issuer_name,
                    issuer_street,
                    issuer_city,
                    issuer_postal_code,
                    issuer_country,
                    issuer_latitude,
                    issuer_longitude,
                    receipt_id,
                ),
            )
            conn.commit()


def insert_transaction_record(
    *,
    account_id: int,
    amount: Decimal,
    category_id: int | None,
    description: str,
    txn_date: date,
    txn_type: str,
    currency: str = "CHF",
    receipt_id: int | None = None,
) -> dict:
    """
    Fügt eine neue Transaktion (z.B. eine Ausgabe oder Einnahme) in die Datenbank ein.

    Args:
        account_id: Das Konto, auf dem die Transaktion stattfindet.
        amount: Der Betrag der Transaktion.
        category_id: Die zugehörige Kategorie (optional).
        description: Eine Beschreibung der Transaktion.
        txn_date: Das Datum der Transaktion.
        txn_type: Der Typ der Transaktion ('income' oder 'expense').
        currency: Die Währung (Standard ist 'CHF').
        receipt_id: Der zugehörige Beleg (optional).

    Returns:
        Ein Dictionary mit der ID der neuen Transaktion und dem Erstellungszeitpunkt.
    """
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(
                """
                INSERT INTO app.transactions (
                    account_id, amount, category_id, receipt_id,
                    [description], [date], [type], currency
                )
                OUTPUT INSERTED.transaction_id, INSERTED.created_at
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    account_id,
                    amount,
                    category_id,
                    receipt_id,
                    description,
                    txn_date,
                    txn_type,
                    currency,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return {
                "transaction_id": row["transaction_id"],
                "created_at": row["created_at"].isoformat(),
            }


def fetch_db_heartbeat() -> dict:
    """
    Liest Diagnosedaten (Servername, Datenbankname, Serverzeit) aus der Datenbank.
    Praktisch für API-Healthchecks.
    """
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(
                """
                SELECT
                    @@SERVERNAME AS server_name,
                    DB_NAME() AS database_name,
                    SYSDATETIMEOFFSET() AS server_time
                """
            )
            row = cur.fetchone() or {}
            server_time = row.get("server_time")
            return {
                "server": row.get("server_name"),
                "database": row.get("database_name"),
                "server_time": (
                    server_time.isoformat()
                    if hasattr(server_time, "isoformat")
                    else None
                ),
            }
