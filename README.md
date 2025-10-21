# Smart Expense Tracker

Ein Web-App-Prototyp (FastAPI + Uvicorn), um persönliche Ausgaben anhand von Quittungen zu erfassen.  
Nutzer können Belege hochladen, die später per OCR verarbeitet und automatisch kategorisiert werden.  
Dies ist ein Semesterprojekt im Rahmen der FFHS.

---

## Features (MVP)
- FastAPI-Backend mit automatischer Swagger-Dokumentation
- Healthcheck-Endpunkt (`/health`)
- Upload-Endpunkt (Basisfunktion)
- Lokaler Start mit virtueller Umgebung (`.venv`)
- Deployment-fähig via Docker

---

## Projektstruktur

```text
groupwork/
 ├─ app/
 │   ├─ __init__.py
 │   └─ main.py
 ├─ tests/
 ├─ requirements.txt
 ├─ Dockerfile
 ├─ README.md
 └─ .venv/                # (lokal erstellt, nicht im Repo)
```

---

## Schnellstart

### Voraussetzungen
- [Python 3.11+](https://www.python.org/downloads/)
- Git
- (Optional) Docker

### Setup & Installation

#### 1. Repository klonen
```bash
git clone <REPO-URL> groupwork
cd groupwork
```

#### 2. Virtuelle Umgebung erstellen
```bash
python -m venv .venv
```

Falls mehrere Python-Versionen installiert sind:
```bash
py -3.11 -m venv .venv
```

#### 3. Aktivieren der venv

**Windows (PowerShell):**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser   # einmalig nötig
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux (Bash/Zsh):**
```bash
source .venv/bin/activate
```

#### 4. Abhängigkeiten installieren
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Starten der App
```bash
uvicorn app.main:app --reload
```

Falls `uvicorn` nicht gefunden wird:
```bash
python -m uvicorn app.main:app --reload
```

### Test im Browser
- Root: [http://127.0.0.1:8000](http://127.0.0.1:8000)  
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

## Team & Verantwortlichkeiten
- **Infrastruktur & Deployment:** Person A
- **Upload & OCR:** Person B
- **Parsing & Datenextraktion:** Person C
- **Machine Learning:** Person D
- **Reporting & Visualisierung:** Person E
- **UI, Testing, Dokumentation:** alle gemeinsam

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
