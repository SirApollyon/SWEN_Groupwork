import sys
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Allow running from any working directory
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import app.main as main  # noqa: E402
import app.services.receipt_upload_service as upload_service  # noqa: E402
from app.main import app  # noqa: E402


def _load_fixture_bytes() -> bytes:
    fixture = ROOT / "tests" / "Testbeleg.jpeg"
    with fixture.open("rb") as fh:
        return fh.read()


@pytest.mark.integration
def test_api_upload_stores_fixture_and_triggers_analysis(monkeypatch):
    recorded: dict = {}  # capture what our stubs receive

    def fake_normalize(data: bytes):
        # In real life we would resize/convert; here we keep bytes for easy asserts
        recorded["normalized"] = data
        return data, "image/jpeg"

    def fake_insert_receipt(user_id: int, content: bytes):
        recorded["insert_user"] = user_id
        recorded["insert_bytes"] = content
        return {
            "receipt_id": 321,
            "upload_date": "2024-01-01T00:00:00Z",
            "status_id": 1,
        }

    async def fake_analyze(receipt_id: int, user_id: int | None = None):
        recorded["analyze_args"] = (receipt_id, user_id)
        return {"ok": True, "total_amount": 12.34}

    monkeypatch.setattr(upload_service, "normalize_upload_image", fake_normalize)
    monkeypatch.setattr(upload_service, "insert_receipt", fake_insert_receipt)
    monkeypatch.setattr(main, "analyze_receipt", fake_analyze)

    client = TestClient(app)
    image_bytes = _load_fixture_bytes()  # camera-like JPEG fixture

    resp = client.post(
        "/api/upload",
        data={"user_id": "1"},
        files={"file": ("Testbeleg.jpeg", image_bytes, "image/jpeg")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["receipt_id"] == 321
    assert body["filename"] == "Testbeleg.jpeg"
    assert body["size_bytes"] == len(image_bytes)
    assert body["analysis"]["ok"] is True

    # verify pipeline calls in correct order/shape
    assert recorded["insert_user"] == 1
    assert recorded["insert_bytes"] == image_bytes
    assert recorded["normalized"] == image_bytes
    assert recorded["analyze_args"] == (321, 1)
