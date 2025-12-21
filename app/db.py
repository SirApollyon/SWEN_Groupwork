# -*- coding: utf-8 -*-
"""
Hilfsfunktionen für den Datenbankzugriff (Azure SQL).

Dieses Modul enthält alle Funktionen, die für die Interaktion mit der
Azure SQL-Datenbank benötigt werden. Es kümmert sich um das Herstellen
von Verbindungen, das Ausführen von SQL-Abfragen und das Zurückgeben der Ergebnisse.
"""

import os
import hashlib
import secrets
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


def _generate_salt() -> str:
    """Erzeugt zufälliges Salz, damit Passwörter nicht erratbar sind."""
    return secrets.token_hex(16)


def _hash_password(password: str, salt: str) -> str:
    """Berechnet einen Hash aus Passwort und Salz per PBKDF2."""
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        120_000,
    )
    return digest.hex()


def create_user(name: str | None, email: str, password: str) -> dict:
    """
    Legt einen neuen Benutzer in Azure SQL an und speichert ein sicheres Passwort.

    Args:
        name: Anzeigename des Benutzers (optional).
        email: E-Mail-Adresse, die als Login dient.
        password: Gewähltes Passwort im Klartext.

    Returns:
        Ein Dictionary mit den Basisdaten des neuen Benutzers.
    """
    if not email:
        raise ValueError("Eine E-Mail-Adresse wird benötigt.")
    if not password:
        raise ValueError("Ein Passwort wird benötigt.")

    cleaned_email = email.strip().lower()
    cleaned_name = name.strip() if name else None

    salt = _generate_salt()
    password_hash = _hash_password(password, salt)

    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(
                "SELECT user_id FROM app.users WHERE LOWER(email)=LOWER(%s)",
                (cleaned_email,),
            )
            if cur.fetchone():
                raise ValueError(
                    "Für diese E-Mail-Adresse existiert bereits ein Konto."
                )
            cur.execute(
                """
                INSERT INTO app.users (name, email)
                OUTPUT INSERTED.user_id, INSERTED.name, INSERTED.email, INSERTED.creation_date
                VALUES (%s, %s)
                """,
                (cleaned_name, cleaned_email),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Der neue Benutzer konnte nicht angelegt werden.")

            cur.execute(
                """
                INSERT INTO app.user_credentials (user_id, password_hash, salt)
                VALUES (%s, %s, %s)
                """,
                (row["user_id"], password_hash, salt),
            )
            conn.commit()

            creation = row["creation_date"]
            created_at = (
                creation.isoformat() if isinstance(creation, (datetime, date)) else None
            )
            return {
                "user_id": row["user_id"],
                "name": row["name"],
                "email": row["email"],
                "creation_date": created_at,
            }


def authenticate_user(email: str, password: str) -> dict:
    """
    Prüft Anmeldedaten und liefert Benutzerinformationen bei Erfolg.

    Args:
        email: E-Mail-Adresse des Kontos.
        password: Passwort im Klartext.

    Returns:
        Ein Dictionary mit Benutzer-ID, Name und E-Mail.
    """
    if not email or not password:
        raise ValueError("Bitte E-Mail und Passwort eingeben.")

    cleaned_email = email.strip().lower()

    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(
                """
                SELECT
                    u.user_id,
                    u.name,
                    u.email,
                    u.creation_date,
                    cred.password_hash,
                    cred.salt
                FROM app.users AS u
                JOIN app.user_credentials AS cred
                    ON cred.user_id = u.user_id
                WHERE LOWER(u.email)=LOWER(%s)
                """,
                (cleaned_email,),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("E-Mail oder Passwort ist nicht korrekt.")

            expected_hash = row["password_hash"]
            salt = row["salt"]
            calculated_hash = _hash_password(password, salt)
            if calculated_hash != expected_hash:
                raise ValueError("E-Mail oder Passwort ist nicht korrekt.")

            creation = row["creation_date"]
            created_at = (
                creation.isoformat() if isinstance(creation, (datetime, date)) else None
            )
            return {
                "user_id": row["user_id"],
                "name": row["name"],
                "email": row["email"],
                "creation_date": created_at,
            }


def get_user_settings(user_id: int) -> dict:
    """
    Lädt optionale Einstellungen wie das maximale Budget für einen Benutzer.

    Args:
        user_id: ID des Benutzers, dessen Einstellungen gelesen werden sollen.

    Returns:
        Dictionary mit einzelnen Settings (z.B. {'max_budget': 1200.0}).
    """
    if not user_id:
        raise ValueError("Eine gültige Benutzer-ID ist erforderlich.")

    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(
                "SELECT max_budget FROM app.user_settings WHERE user_id=%s",
                (user_id,),
            )
            row = cur.fetchone() or {}

    max_budget = row.get("max_budget")
    if isinstance(max_budget, Decimal):
        max_budget = float(max_budget)

    return {"max_budget": max_budget}


def save_user_settings(user_id: int, *, max_budget: float | None = None) -> None:
    """
    Speichert (oder legt an) die persönlichen Einstellungen eines Benutzers.

    Args:
        user_id: ID des Benutzers.
        max_budget: Optionales maximales Budget in CHF.
    """
    if not user_id:
        raise ValueError("Eine gültige Benutzer-ID ist erforderlich.")

    normalized_budget: float | None
    if max_budget is None:
        normalized_budget = None
    else:
        normalized_budget = round(float(max_budget), 2)

    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                MERGE app.user_settings AS target
                USING (SELECT %s AS user_id, %s AS max_budget) AS source
                ON target.user_id = source.user_id
                WHEN MATCHED THEN
                    UPDATE SET max_budget = source.max_budget, updated_at = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT (user_id, max_budget) VALUES (source.user_id, source.max_budget);
                """,
                (user_id, normalized_budget),
            )
            conn.commit()


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


def list_receipts_overview(user_id: int | None = None) -> list[dict]:
    """
    Liefert eine kompakte Ǭbersicht aller Belege mit den wichtigsten Transaktionsinformationen.

    Args:
        user_id: Optionaler Filter, um nur Belege eines bestimmten Benutzers zurǬckzugeben.

    Returns:
        Eine Liste von Dictionaries pro Beleg mit Status, Betrag, Kategorie usw.
    """
    params = (user_id, user_id)
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(
                """
                SELECT
                    r.receipt_id,
                    r.user_id,
                    r.upload_date,
                    r.status_id,
                    s.status_name,
                    r.issuer_name,
                    r.issuer_city,
                    r.issuer_country,
                    CASE WHEN DATALENGTH(r.receipt_image) > 0 THEN 1 ELSE 0 END AS has_image,
                    t.amount,
                    t.currency,
                    t.[date]       AS transaction_date,
                    t.[description] AS description,
                    t.[type]       AS transaction_type,
                    c.name         AS category_name,
                    c.[type]       AS category_type
                FROM app.receipts AS r
                LEFT JOIN app.transactions AS t
                    ON t.receipt_id = r.receipt_id
                LEFT JOIN app.categories AS c
                    ON t.category_id = c.category_id
                LEFT JOIN app.receipt_status AS s
                    ON r.status_id = s.status_id
                WHERE (%s IS NULL OR r.user_id = %s)
                ORDER BY r.upload_date DESC, r.receipt_id DESC
                """,
                params,
            )
            rows = cur.fetchall() or []

    overview: list[dict] = []
    for row in rows:
        amount = row.get("amount")
        if isinstance(amount, Decimal):
            amount = float(amount)

        tx_date = row.get("transaction_date")
        if isinstance(tx_date, (date, datetime)):
            tx_date_iso = tx_date.isoformat()
        else:
            tx_date_iso = None

        upload_date = row.get("upload_date")
        if isinstance(upload_date, (date, datetime)):
            upload_iso = upload_date.isoformat()
        else:
            upload_iso = None

        overview.append(
            {
                "receipt_id": row.get("receipt_id"),
                "user_id": row.get("user_id"),
                "upload_date": upload_iso,
                "status_id": row.get("status_id"),
                "status_name": row.get("status_name"),
                "issuer_name": row.get("issuer_name"),
                "issuer_city": row.get("issuer_city"),
                "issuer_country": row.get("issuer_country"),
                "has_image": bool(row.get("has_image")),
                "amount": amount,
                "currency": row.get("currency"),
                "transaction_date": tx_date_iso,
                "description": row.get("description"),
                "transaction_type": row.get("transaction_type"),
                "category_name": row.get("category_name"),
                "category_type": row.get("category_type"),
            }
        )

    return overview


def get_receipt_detail(receipt_id: int) -> dict:
    """
    Holt alle Details zu einem einzelnen Beleg einschlie�Ylich Bild, Transaktion und Ausstellerinfos.

    Args:
        receipt_id: Die ID des gesuchten Belegs.

    Returns:
        Ein Dictionary mit allen relevanten Detailinformationen.
    """
    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(
                """
                SELECT
                    r.receipt_id,
                    r.user_id,
                    r.upload_date,
                    r.status_id,
                    s.status_name,
                    r.extracted_text,
                    r.error_message,
                    r.issuer_name,
                    r.issuer_street,
                    r.issuer_city,
                    r.issuer_postal_code,
                    r.issuer_country,
                    r.issuer_latitude,
                    r.issuer_longitude,
                    r.receipt_image,
                    t.transaction_id,
                    t.amount,
                    t.currency,
                    t.[date]        AS transaction_date,
                    t.[description] AS description,
                    t.[type]        AS transaction_type,
                    c.category_id,
                    c.name          AS category_name,
                    c.[type]        AS category_type
                FROM app.receipts AS r
                LEFT JOIN app.transactions AS t
                    ON t.receipt_id = r.receipt_id
                LEFT JOIN app.categories AS c
                    ON t.category_id = c.category_id
                LEFT JOIN app.receipt_status AS s
                    ON r.status_id = s.status_id
                WHERE r.receipt_id = %s
                """,
                (receipt_id,),
            )
            row = cur.fetchone()

    if not row:
        raise ValueError(f"Beleg mit der ID {receipt_id} wurde nicht gefunden.")

    amount = row.get("amount")
    if isinstance(amount, Decimal):
        amount = float(amount)

    tx_date = row.get("transaction_date")
    if isinstance(tx_date, (date, datetime)):
        tx_date_iso = tx_date.isoformat()
    else:
        tx_date_iso = None

    upload_date = row.get("upload_date")
    if isinstance(upload_date, (date, datetime)):
        upload_iso = upload_date.isoformat()
    else:
        upload_iso = None

    return {
        "receipt_id": row.get("receipt_id"),
        "user_id": row.get("user_id"),
        "upload_date": upload_iso,
        "status_id": row.get("status_id"),
        "status_name": row.get("status_name"),
        "extracted_text": row.get("extracted_text"),
        "error_message": row.get("error_message"),
        "issuer": {
            "name": row.get("issuer_name"),
            "street": row.get("issuer_street"),
            "city": row.get("issuer_city"),
            "postal_code": row.get("issuer_postal_code"),
            "country": row.get("issuer_country"),
            "latitude": row.get("issuer_latitude"),
            "longitude": row.get("issuer_longitude"),
        },
        "receipt_image": row.get("receipt_image"),
        "transaction": {
            "transaction_id": row.get("transaction_id"),
            "amount": amount,
            "currency": row.get("currency"),
            "date": tx_date_iso,
            "description": row.get("description"),
            "type": row.get("transaction_type"),
            "category_id": row.get("category_id"),
            "category_name": row.get("category_name"),
            "category_type": row.get("category_type"),
        },
    }


def delete_receipt(receipt_id: int, *, user_id: int | None = None) -> None:
    """
    L?scht einen Beleg und entfernt zugeh?rige Verkn?pfungen.

    Args:
        receipt_id: Die zu l?schende ID.
        user_id: Optionaler Besitzer-Check.
    """
    if not receipt_id:
        raise ValueError("Es muss eine g?ltige Receipt-ID angegeben werden.")

    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor(as_dict=True) as cur:
            if user_id is None:
                cur.execute(
                    "SELECT receipt_id FROM app.receipts WHERE receipt_id=%s",
                    (receipt_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT receipt_id
                    FROM app.receipts
                    WHERE receipt_id=%s AND user_id=%s
                    """,
                    (receipt_id, user_id),
                )
            if not cur.fetchone():
                raise ValueError(
                    "Beleg wurde nicht gefunden oder geh?rt einem anderen Benutzer."
                )

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app.transactions SET receipt_id=NULL WHERE receipt_id=%s",
                (receipt_id,),
            )
            cur.execute(
                "DELETE FROM app.receipts WHERE receipt_id=%s",
                (receipt_id,),
            )
            conn.commit()


def delete_transactions_for_receipt(receipt_id: int) -> int:
    """
    L?scht Transaktionen, die an einen Beleg gebunden sind.

    Args:
        receipt_id: Die Beleg-ID, deren Transaktionen entfernt werden sollen.

    Returns:
        Anzahl gel?schter Transaktionen.
    """
    if not receipt_id:
        raise ValueError("Es muss eine g?ltige Receipt-ID angegeben werden.")

    with pymssql.connect(**CONNECT_KW) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM app.transactions WHERE receipt_id=%s",
                (receipt_id,),
            )
            deleted = cur.rowcount or 0
            conn.commit()
            return deleted


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


def get_category_id_by_name(category_name: str) -> int | None:
    """
    Sucht die ID einer Kategorie anhand ihres Namens. Die Suche ignoriert Groß- und Kleinschreibung.

    Args:
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
                WHERE LOWER(name)=LOWER(%s)
                """,
                (category_name,),
            )
            row = cur.fetchone()
            return row["category_id"] if row else None


def list_categories() -> list[dict]:
    """
    Listet alle verfügbaren Kategorien auf.

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
                ORDER BY name
                """,
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
