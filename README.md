# Smart Expense Tracker
FastAPI backend for receipt upload and OCR (MVP).

## Quickstart
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
Öffne http://127.0.0.1:8000
 → sollte {"message": "Hello from Smart Expense Tracker"} anzeigen

Öffne http://127.0.0.1:8000/health
 → sollte {"status": "ok"} anzeigen

Öffne http://127.0.0.1:8000/docs
 → FastAPI generiert automatisch die Swagger-UI