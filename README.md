# Smart Expense Tracker

A prototype web application built with NiceGUI + FastAPI for capturing and managing personal expenses based on uploaded receipts.
Users can upload receipt images (JPG, PNG, HEIC, etc.), which are stored in a database and later processed via OCR.
This project is part of the FFHS/HSLU/OST semester module SWEN.

---

## Features (MVP)
- FastAPI-Backend mit automatischer Swagger-Dokumentation
- Healthcheck-Endpunkt (`/health`)
- Upload-Endpunkt (Basisfunktion)
- Lokaler Start mit virtueller Umgebung (`.venv`)
- Deployment-fähig via Docker

- Unified NiceGUI + FastAPI backend
- Upload interface (browser + mobile camera)
- Direct file storage in Azure SQL (VARBINARY(MAX))
- User-based assignment (user_id, status_id)
- Environment-based DB configuration (.env)
- Local run with virtual environment (venv)
- API endpoint /api/upload for programmatic access

---

## Projektstruktur

```text
SWEN_Groupwork/
 ├─ app/
 │   ├─ __init__.py
 │   ├─ main.py          # NiceGUI + FastAPI entry point
 │   ├─ db.py            # DB connection + insert logic
 │   ├─ init_db.py       # schema setup
 │   └─ db_test.py
 ├─ .env                 # DB credentials (not committed)
 ├─ requirements.txt
 ├─ MANUAL.md
 ├─ README.md
 └─ venv/                # local virtual environment
```

---

## Schnellstart

### Voraussetzungen
- [Python 3.11+](https://www.python.org/downloads/)
- Git
- Azure SQL database access
- (Optional) Docker

### Setup & Installation

#### 1. Clone repository
```bash
git clone https://github.com/SirApollyon/SWEN_Groupwork.git
cd SWEN_Groupwork
```
#### 2. Create virtual environment
```bash
python -m venv .venv
```

Falls mehrere Python-Versionen installiert sind:
```bash
py -3.11 -m venv .venv
```

#### 3. Activation of venv

**Windows (PowerShell):**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser   # einmalig nötig
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux (Bash/Zsh):**
```bash
source .venv/bin/activate
```

#### 4. Install dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Run the App
```bash
uvicorn app.main:app --reload --port 8000
```

Falls `uvicorn` nicht gefunden wird:
```bash
python -m uvicorn app.main:app --reload --port 8000
```

### Test im Browser
- Root (NiceGUI interface): [http://127.0.0.1:8000](http://127.0.0.1:8000)  
  → `{"message":"Hello from Smart Expense Tracker"}`
- Healthcheck: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)  
  → `{"status":"ok"}`
- API-Dokumentation (Swagger-UI): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Tests
```bash
pytest
```

### Optional: Start mit Docker
```bash
docker build -t expense-tracker:dev .
docker run -p 8080:8080 expense-tracker:dev
```
Aufruf: [http://127.0.0.1:8080](http://127.0.0.1:8080)

### Nützliche Tipps
- Wenn `ModuleNotFoundError: No module named 'app'`: sicherstellen, dass `app/` im Projektordner liegt und `__init__.py` enthält.
- Bei Windows-Problemen mit `pip`: immer `python -m pip ...` statt nur `pip` verwenden.
- In VS Code: Python-Interpreter auf `.venv` setzen (`Python: Select Interpreter`).

---

### API endpoints
- # Endpoint  Method  Description
- # /api/upload POST  Uploads a receipt image for a given user_id.
- # /docs GET Auto-generated FastAPI docs.

## Team & Verantwortlichkeiten
- **Infrastruktur & Deployment:** Person A
- **Upload & OCR:** Person B
- **Parsing & Datenextraktion:** Person C
- **Machine Learning:** Person D
- **Reporting & Visualisierung:** Person E
- **UI, Testing, Dokumentation:** alle gemeinsam

---
## Database setup
- # 1.Configure your .env file:
```text
AZURE_SQL_SERVER=bfh-server-01.database.windows.net
AZURE_SQL_DB=smart_expense_tracker
AZURE_SQL_USER=<your_user>
AZURE_SQL_PASSWORD=<your_password>
AZURE_SQL_PORT=1433
```
-  # 2.Run schema initialization once:
```bash
python app/init_db.py
```

- # 3.(Optional) Insert a test user:
```sql
INSERT INTO app.users (name, email) VALUES (N'Test', N'test@example.com');
```
---

## Architekturüberblick
Dieses Projekt setzt auf FastAPI als leichtgewichtiges Backend. Geplanter Ablauf:

```
[Client] --(POST /upload)--> [FastAPI] --(persist)--> [Storage]
                                 ↘(queue)--> [OCR Worker] --> [Parser/ML] --> [DB]
```

- Upload-Service: Nutzer lädt Bild/PDF eines Belegs hoch, Datei wird gespeichert.
- OCR-Parsing (geplant): Extraktion von Händler, Datum, Betrag, einzelnen Positionen.
- Machine Learning (geplant): automatische Kategorisierung von Ausgaben.
- API-First-Ansatz: alle Endpunkte dokumentiert via Swagger-UI.
