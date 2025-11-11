# Smart Expense Tracker

Smart Expense Tracker is a proof-of-concept web application that combines NiceGUI and FastAPI to capture, store, and analyze receipt images. Receipts are uploaded through a web interface or REST API, persisted in Azure SQL, and enriched via Google GenAI plus optional geocoding. The project was created for the SWEN semester module (FFHS/HSLU/OST) and is optimized for quick local runs as well as container deployments.

---

## Highlights
- Single FastAPI application that hosts both the JSON API and the NiceGUI front end
- Dual upload paths (drag & drop file picker and mobile camera capture)
- Receipt storage in Azure SQL including user binding, status tracking, and binary payload
- Automated analysis pipeline powered by Google GenAI and geopy for issuer enrichment
- Ready-to-use Dockerfile and Cloud Run configuration for container deployments (live at https://smart-expense-tracker-530070868085.europe-west8.run.app)
- Health check, Swagger UI, and pytest-based smoke tests for quick verification

---

## System Overview

```
[Browser / Mobile] --(NiceGUI)--> [/]
        |                               \
        |                                -> FastAPI (uvicorn)
        |                                      |
[API Clients] --------(REST)-------------------+
                                               |
                                               v
                                        Azure SQL DB
                                               |
                                               v
                                  ReceiptAnalyzer (Google GenAI + geopy)
```

1. Users upload an image via the NiceGUI page or `POST /api/upload`.
2. The backend validates file size, stores the binary in Azure SQL, and records metadata.
3. `ReceiptAnalyzer` loads the stored image, calls Google GenAI to extract structured data, and optionally geocodes issuer information.
4. Results are written back into the database so they can be consumed by downstream services.

---

## Project Structure

```text
SWEN_Groupwork/
├── app/
│   ├── __init__.py
│   ├── main.py              # NiceGUI + FastAPI entry point
│   ├── db.py                # DB helpers (insert + queries)
│   ├── receipt_analysis.py  # Google GenAI based analysis pipeline
│   ├── manual_analysis.py   # CLI helper for manual checks
│   ├── init_db.py           # Schema bootstrapper
│   └── db_test.py
├── DB_schema.sql
├── Dockerfile
├── README.md
├── MANUAL.md
├── requirements.txt
└── render.yaml / .env / etc.
```

---

## Prerequisites
- Python 3.11 or newer
- Git
- Azure SQL database or compatible SQL Server instance
- Docker (optional, for containerized runs)
- Google GenAI API access (for automatic receipt analysis)

---

## Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/SirApollyon/SWEN_Groupwork.git
cd SWEN_Groupwork
```

### 2. Create a virtual environment
```bash
python -m venv .venv
```
On Windows with multiple Python versions:
```powershell
py -3.11 -m venv .venv
```

### 3. Activate the environment
```powershell
# Windows (PowerShell)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser  # once
.\.venv\Scripts\Activate.ps1
```
```bash
# macOS / Linux
source .venv/bin/activate
```

### 4. Install dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Configuration (.env)

Create a `.env` file in the project root and fill in your credentials:

| Variable | Description | Example |
| --- | --- | --- |
| `AZURE_SQL_SERVER` | Fully qualified SQL Server host | `bfh-server-01.database.windows.net` |
| `AZURE_SQL_DB` | Database name | `smart_expense_tracker` |
| `AZURE_SQL_USER` | Login/user name | `my_user` |
| `AZURE_SQL_PASSWORD` | Password | `super_secret` |
| `AZURE_SQL_PORT` | TCP port (default 1433) | `1433` |
| `GOOGLE_API_KEY` | Google GenAI API key for receipt analysis | `ya29...` |
| `GOOGLE_RECEIPT_MODEL` | Optional override for the GenAI model | `gemma-3-27b-it` |
| `GEOCODER_USER_AGENT` | Identifier for Nominatim geocoding calls | `receipt-analyzer` |

The backend loads these values through `python-dotenv`, so restarting uvicorn after editing `.env` is enough.

---

## Database Setup
1. Initialize the schema (creates tables, seed data, etc.):
   ```bash
   python app/init_db.py
   ```
2. (Optional) Insert a test user so uploads can be associated with a valid `user_id`:
   ```sql
   INSERT INTO app.users (name, email) VALUES (N'Test', N'test@example.com');
   ```
3. `DB_schema.sql` contains the complete schema if you need to inspect or migrate it manually.

---

## Running the Application

### Local development (auto reload)
```bash
uvicorn app.main:app --reload --port 8000
```
If `uvicorn` is not on your PATH:
```bash
python -m uvicorn app.main:app --reload --port 8000
```

### Available endpoints
- NiceGUI front end: `http://127.0.0.1:8000/` (live deployment: https://smart-expense-tracker-530070868085.europe-west8.run.app)
- Health check: `http://127.0.0.1:8000/health`
- Swagger / OpenAPI docs: `http://127.0.0.1:8000/docs` (live docs: https://smart-expense-tracker-530070868085.europe-west8.run.app/docs#/)

Uploading a file through NiceGUI automatically triggers the full persistence + analysis flow. Using the API allows you to integrate other clients into the same pipeline.

---

## Docker Workflow
```bash
docker build -t expense-tracker:dev .
docker run --rm -p 8080:8080 --env-file .env expense-tracker:dev
```
Then open `http://127.0.0.1:8080`. The provided `render.yaml` and Dockerfile are compatible with Google Cloud Run; set the `PORT` environment variable accordingly.

### Local Docker deployment
1. **Prepare environment file**: ensure `.env` contains all DB + API keys. Docker uses the same file via `--env-file .env`.
2. **Build**: `docker build -t expense-tracker:dev .` (rerun after code changes to refresh the image).
3. **Run locally**: `docker run --rm -p 8080:8080 --env-file .env -e PORT=8080 expense-tracker:dev`. The app inside listens on `$PORT` (defaults to 8000). The `-p` flag maps container port 8080 to your host; adjust if you need a different host port.
4. **Verify**: open `http://localhost:8080/` for NiceGUI, `http://localhost:8080/docs` for Swagger, or hit `/health`. Use `docker logs <container_id>` if you want to tail the output.
5. **Stop**: press `Ctrl+C` if running in the foreground, or `docker stop <container_id>` when detached. The `--rm` flag ensures the container is cleaned up automatically.

---

## Google Cloud Run Deployment
- The repository is connected to Google Cloud Run; every push to the default branch triggers a GitHub build & deploy workflow that rebuilds the container and releases it to `https://smart-expense-tracker-530070868085.europe-west8.run.app`.
- Detailed API docs of the live service are always available at `https://smart-expense-tracker-530070868085.europe-west8.run.app/docs#/`.
- The deployment uses the same Dockerfile as local runs, so any change validated locally translates directly to Cloud Run once committed.

---

## Tests and Tooling
```bash
python -m pytest
```
Current tests cover the DB helpers; extend them as new features land. For linting/formatting you can plug in `ruff`, `black`, or similar tools via `setup.cfg`.

---

## API Reference

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/upload` | Uploads a receipt image for a given `user_id`, stores it, and immediately runs the analyzer. |
| `POST` | `/api/receipts/{receipt_id}/analyze` | Re-runs the analyzer for an existing receipt (uses optional `user_id`). |
| `DELETE` | `/api/receipts/{receipt_id}` | Removes a stored receipt (optionally enforcing ownership via `user_id`) and detaches linked transactions. |
| `GET` | `/health` | Lightweight readiness check used for monitoring. |
| `GET` | `/docs` | Swagger UI (FastAPI auto-generated, hosted at https://smart-expense-tracker-530070868085.europe-west8.run.app/docs#/). |

The `/api/upload` endpoint expects `multipart/form-data` with fields `file` (binary) and `user_id` (form value).

---

## Troubleshooting
- **`ModuleNotFoundError: No module named 'app'`**: ensure you are running commands from the project root and that `.venv` is activated.
- **`uvicorn` command not found**: run `python -m uvicorn ...` or reinstall dependencies inside the active environment.
- **Database connection failures**: verify that your IP is allowed to reach Azure SQL and that TLS / firewall settings permit the connection.
- **Google GenAI errors**: double-check `GOOGLE_API_KEY`, project quotas, and the selected `GOOGLE_RECEIPT_MODEL`.
- **Large uploads rejected**: files above 20 MB are blocked by the application (see `MAX_BYTES` in `app/services/receipt_upload_service.py`).

---

## Team & Responsibilities
- **Infrastructure & Deployment**: Person A
- **Upload Service & OCR pipeline**: Person B
- **Parsing & Data Extraction**: Person C
- **Machine Learning Enhancements**: Person D
- **Reporting & Visualization**: Person E
- **UI, Testing, Documentation**: Collective responsibility

Feel free to adapt the assignments above to your actual team structure.
