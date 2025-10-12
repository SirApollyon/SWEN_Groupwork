# run_db_schema.py
import os, re
from dotenv import load_dotenv
import pyodbc

load_dotenv()

server   = os.getenv("AZURE_SQL_SERVER")
database = os.getenv("AZURE_SQL_DB")
username = os.getenv("AZURE_SQL_USER")
password = os.getenv("AZURE_SQL_PASSWORD")

if not all([server, database, username, password]):
    raise ValueError("Fehler: .env unvollständig (Server/DB/User/Passwort).")

base_dir = os.path.dirname(os.path.abspath(__file__))
sql_path = os.path.join(base_dir, "DB_schema.sql")  # ggf. Pfad anpassen

with open(sql_path, "r", encoding="utf-8") as f:
    raw_sql = f.read().strip()

# an Zeilen mit nur "GO" (beliebige Groß/Kleinschreibung, vor/nachher Whitespace) splitten
batches = [s.strip() for s in re.split(r"(?im)^\s*GO\s*$", raw_sql) if s.strip()]

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER=tcp:{server},1433;"
    f"DATABASE={database};"
    f"UID={username};PWD={password};"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=120;"
)

print(f"Führe {len(batches)} SQL-Batches aus ...")

try:
    with pyodbc.connect(conn_str, autocommit=True, timeout=120) as conn:
        with conn.cursor() as cur:
            # optionaler Ping
            cur.execute("SELECT 1")
            cur.fetchone()

            for i, stmt in enumerate(batches, 1):
                preview = stmt[:80].replace("\n", " ")
                print(f"[{i}/{len(batches)}] EXEC: {preview} ...")
                cur.execute(stmt)
                # evtl. result sets „leeren“, damit der Cursor bereit ist
                while cur.nextset():
                    pass

    print("Schema erfolgreich ausgeführt.")
except pyodbc.Error as e:
    print("Fehler beim Ausführen des Schemas.")
    print("Details:", e)