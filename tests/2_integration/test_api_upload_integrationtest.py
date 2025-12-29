import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

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


class ApiUploadIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_api_upload_stores_fixture_and_triggers_analysis(self) -> None:
        recorded: dict = {}  # capture what our stubs receive

        def fake_normalize(data: bytes):
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

        image_bytes = _load_fixture_bytes()  # camera-like JPEG fixture

        with patch.object(
            upload_service, "normalize_upload_image", side_effect=fake_normalize
        ), patch.object(
            upload_service, "insert_receipt", side_effect=fake_insert_receipt
        ), patch.object(
            main, "analyze_receipt", side_effect=fake_analyze
        ):
            resp = self.client.post(
                "/api/upload",
                data={"user_id": "1"},
                files={"file": ("Testbeleg.jpeg", image_bytes, "image/jpeg")},
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["receipt_id"], 321)
        self.assertEqual(body["filename"], "Testbeleg.jpeg")
        self.assertEqual(body["size_bytes"], len(image_bytes))
        self.assertTrue(body["analysis"]["ok"])

        # verify pipeline calls in correct order/shape
        self.assertEqual(recorded["insert_user"], 1)
        self.assertEqual(recorded["insert_bytes"], image_bytes)
        self.assertEqual(recorded["normalized"], image_bytes)
        self.assertEqual(recorded["analyze_args"], (321, 1))


if __name__ == "__main__":
    unittest.main()
