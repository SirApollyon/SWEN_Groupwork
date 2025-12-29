# Test prüft den API -Endpoint : POST /api/receipts/{receipt_id}/analyze ohne die echte Business Logik auszuführen
# stattdessen wird main.analyse_receipt gemockt um Happy Path und Fehlerübersetzungen (valueerror) zu testen

import sys
from pathlib import Path

#TestClient für Simulation HTTP Request
import pytest
from fastapi.testclient import TestClient

# Allow running from any working directory
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import app.main as main  # noqa: E402
from app.main import app  # noqa: E402


@pytest.mark.integration
def test_api_analyze_receipt_returns_analysis(monkeypatch):
    recorded: dict = {}
#fake_analyze ersetzt die echte analyze_receipt-Funktion
    async def fake_analyze(receipt_id: int, user_id: int | None = None):
        recorded["args"] = (receipt_id, user_id)
        return {"status": "processed", "raw": {"total_amount": 12.5}}
    #monkeypatch.setattr sorgt daüfr das nur API-Handler selbst geprüft wird, ohne dass die echte Analyse durchgeführt wird -> ersetzt main.analyse_receipt

    monkeypatch.setattr(main, "analyze_receipt", fake_analyze)

#Test1: Happy Case: TestClient simuliert HTTP-Request gegen die Fast-API App und liefert UserID = 9 und receiptID = 55

    client = TestClient(app)
    resp = client.post("/api/receipts/55/analyze", params={"user_id": "9"})
#HTTP200 receipt_id kommt korrekt zurück, Analyse Payload wird korrekt weitergereicht --> Argument Flow und Response Mapping wird getestet
    assert resp.status_code == 200
    body = resp.json()
    assert body["receipt_id"] == 55
    assert body["analysis"]["status"] == "processed"
    assert recorded["args"] == (55, 9)

#Test2: API fängt ValueError ab und antwortet mit HTTP 404"not found
@pytest.mark.integration
def test_api_analyze_receipt_not_found(monkeypatch):
    async def fake_analyze(receipt_id: int, user_id: int | None = None):
        raise ValueError("receipt not found")

    monkeypatch.setattr(main, "analyze_receipt", fake_analyze)

    client = TestClient(app)
    resp = client.post("/api/receipts/999/analyze")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
#testet saubere Übersetzung von Domänenfehler in HTTP Fehler


#Test3: unerwartete Fehler --> 500 Internalserver Error
@pytest.mark.integration
def test_api_analyze_receipt_unhandled_error(monkeypatch):
    async def fake_analyze(receipt_id: int, user_id: int | None = None):
        raise RuntimeError("model offline")

    monkeypatch.setattr(main, "analyze_receipt", fake_analyze)

    client = TestClient(app)
    resp = client.post("/api/receipts/1/analyze")

    assert resp.status_code == 500
    assert "model offline" in resp.json()["detail"]
#Kein spezieller Catch, teste globale Fehlerhandling