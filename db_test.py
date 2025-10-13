import os

from dotenv import load_dotenv
import pymssql

# .env Datei laden
load_dotenv()

# Variablen aus der .env lesen
server = os.getenv("AZURE_SQL_SERVER")
database = os.getenv("AZURE_SQL_DB")
username = os.getenv("AZURE_SQL_USER")
password = os.getenv("AZURE_SQL_PASSWORD")
port = os.getenv("AZURE_SQL_PORT", "1433")

# Pruefen, ob alle Werte geladen wurden
if not all([server, database, username, password]):
    raise ValueError("Fehler: Eine oder mehrere Umgebungsvariablen fehlen. Bitte .env pruefen!")

try:
    port = int(port)
except ValueError as exc:
    raise ValueError("Fehler: AZURE_SQL_PORT muss eine gueltige Zahl sein.") from exc

print("Verbinde zur Azure SQL-Datenbank...")

connect_kwargs = {
    "server": server,
    "user": username,
    "password": password,
    "database": database,
    "port": port,
    "timeout": 30,
    "login_timeout": 30,
    "tds_version": "7.4",
}

try:
    with pymssql.connect(**connect_kwargs) as conn:
        with conn.cursor(as_dict=True) as cur:
            # Einfache Testabfrage
            cur.execute(
                """
                SELECT
                        SUSER_SNAME() AS logged_in_user,
                        DB_NAME() AS current_database,
                        CONVERT(varchar(33), SYSUTCDATETIME(), 126) AS server_time
                        """
            )
            row = cur.fetchone()
            print("Verbindung erfolgreich!")
            print(f"Benutzer: {row['logged_in_user']}")
            print(f"Datenbank: {row['current_database']}")
            print(f"Serverzeit: {row['server_time']}")
except pymssql.Error as e:
    print("Verbindung fehlgeschlagen!")
    print("Fehlerdetails:", e)
