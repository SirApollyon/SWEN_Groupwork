"""
Integration test for POST /api/receipts/{receipt_id}/analyze using unittest style.
The real analyze_receipt is patched so we only verify handler -> response mapping.
"""

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
from app.main import app  # noqa: E402


class ApiAnalyzeIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_api_analyze_receipt_returns_analysis(self) -> None:
        recorded: dict = {}

        async def fake_analyze(receipt_id: int, user_id: int | None = None):
            # Simulate successful analysis and capture call args
            recorded["args"] = (receipt_id, user_id)
            return {"status": "processed", "raw": {"total_amount": 12.5}}

        with patch.object(main, "analyze_receipt", side_effect=fake_analyze):
            resp = self.client.post(
                "/api/receipts/55/analyze", params={"user_id": "9"}
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["receipt_id"], 55)
        self.assertEqual(body["analysis"]["status"], "processed")
        self.assertEqual(recorded["args"], (55, 9))

    def test_api_analyze_receipt_not_found(self) -> None:
        async def fake_analyze(receipt_id: int, user_id: int | None = None):
            # Simulate domain-level not-found translated to HTTP 404
            raise ValueError("receipt not found")

        with patch.object(main, "analyze_receipt", side_effect=fake_analyze):
            resp = self.client.post("/api/receipts/999/analyze")

        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    def test_api_analyze_receipt_unhandled_error(self) -> None:
        async def fake_analyze(receipt_id: int, user_id: int | None = None):
            # Simulate unexpected exception -> should bubble as HTTP 500
            raise RuntimeError("model offline")

        with patch.object(main, "analyze_receipt", side_effect=fake_analyze):
            resp = self.client.post("/api/receipts/1/analyze")

        self.assertEqual(resp.status_code, 500)
        self.assertIn("model offline", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()
