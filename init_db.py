import os
from dotenv import load_dotenv
import pymssql
import re

# Zugangsdaten aus .env-Datei laden
load_dotenv()

server   = os.getenv("AZURE_SQL_SERVER")
database = os.getenv("AZURE_SQL_DB")
user     = os.getenv("AZURE_SQL_USER")
pwd      = os.getenv("AZURE_SQL_PASSWORD")
port     = int(os.getenv("AZURE_SQL_PORT", "1433"))

# SQL-Datei öffnen
with open("DB_schema.sql", "r", encoding="utf-8") as f:
    script = f.read()

# SQL-Text bereinigen
script = "\n".join(l for l in re.sub(r"/\*.*?\*/|--.*?$", "", script, flags=re.S|re.M).splitlines() if l.strip())

print("Verbinde mit Datenbank...")

# Verbindung aufbauen und Skript ausführen
with pymssql.connect(server=server, user=user, password=pwd, database=database, port=port) as conn:
    cur = conn.cursor()
    for stmt in re.split(r"(?im)^\s*GO\s*$", script):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()

print("DB-Schema erfolgreich ausgeführt.")