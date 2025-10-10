import os
from dotenv import load_dotenv
import pyodbc

#.env-Datei laden

load_dotenv()

#Variabeln aus der .env lesen
server = os.getenv("AZURE_SQL_SERVER")
database = os.getenv("AZURE_SQL_DB")
username = os.getenv("AZURE_SQL_USER")
password = os.getenv("AZURE_SQL_PASSWORD")

#Prüfen, ob alle Werte geladen wurden
if not all([server, database, username, password]):
    raise ValueError("Fehler: Eine oder mehrere Umgebungsvariablen fehlen. Bitte .env prüfen!")

#Verbindungszeichenfolge (ODBC Server 18 ist der Neuste)
conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER=tcp:{server},1433;"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)

print("Verbinde zur Azure SQL-Datenbank...")

try:
    with pyodbc.connect(conn_str) as conn:
        with conn.cursor() as cur:
            #Einfache Testabfrage
            cur.execute("""
                SELECT
                        SUSER_SNAME() AS logged_in_user,
                        DB_NAME() AS current_database,
                        CONVERT(varchar(33), SYSUTCDATETIME(), 126) AS server_time
                        """)
            row = cur.fetchone()
            print("Verbindung erfolgreich!")
            print(f"Benutzer: {row.logged_in_user}")
            print(f"Datenbank: {row.current_database}")
            print(f"Serverzeit: {row.server_time}")
except pyodbc.Error as e:
    print("Verbindung fehlgeschlagen!")
    print("Fehlerdetails:", e)