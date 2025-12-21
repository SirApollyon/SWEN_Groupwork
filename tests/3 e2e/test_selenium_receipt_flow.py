from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.db import delete_receipt, delete_transactions_for_receipt, list_receipts_overview


def _http_ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:
            return response.status < 500
    except Exception:
        return False


def _wait_for_http(url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _http_ready(url):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Server did not respond in time: {url}")


def _start_server(repo_root: Path, base_url: str) -> subprocess.Popen:
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8000
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    return subprocess.Popen(cmd, cwd=str(repo_root), env=env)


def _build_driver() -> webdriver.Chrome:
    options = Options()
    if os.getenv("E2E_HEADLESS", "1") != "0":
        options.add_argument("--headless")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    chrome_binary = os.getenv("CHROME_BINARY")
    if chrome_binary:
        options.binary_location = chrome_binary
    return webdriver.Chrome(options=options)


class TestReceiptFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.base_url = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        cls.server_timeout = int(os.getenv("E2E_SERVER_TIMEOUT", "30"))
        cls.server_process: subprocess.Popen | None = None

        start_server = os.getenv("E2E_START_SERVER", "1") != "0"
        login_url = f"{cls.base_url}/login"
        if start_server and not _http_ready(login_url):
            cls.server_process = _start_server(cls.repo_root, cls.base_url)
        _wait_for_http(login_url, cls.server_timeout)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.server_process:
            cls.server_process.terminate()
            try:
                cls.server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cls.server_process.kill()

    def setUp(self) -> None:
        self.driver = _build_driver()
        self.driver.set_page_load_timeout(60)
        timeout = int(os.getenv("E2E_TIMEOUT", "240"))
        self.wait = WebDriverWait(self.driver, timeout)

    def tearDown(self) -> None:
        self.driver.quit()

    def _find_file_input(self) -> webdriver.remote.webelement.WebElement:
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        for element in inputs:
            if element.is_displayed():
                return element
        if inputs:
            return inputs[0]
        raise AssertionError("No file input found on upload page.")

    def _list_receipt_ids(self, user_id: int) -> set[int]:
        receipts = list_receipts_overview(user_id)
        return {
            receipt["receipt_id"]
            for receipt in receipts
            if receipt.get("receipt_id") is not None
        }

    def _cleanup_new_receipts(self, baseline_ids: set[int], user_id: int) -> None:
        latest_ids = self._list_receipt_ids(user_id)
        new_ids = sorted(latest_ids - baseline_ids, reverse=True)
        for receipt_id in new_ids:
            delete_transactions_for_receipt(receipt_id)
            delete_receipt(receipt_id, user_id=user_id)

    def test_demo_upload_analyze_flow(self) -> None:
        receipt_path = self.repo_root / "tests" / "Testbeleg.jpeg"
        self.assertTrue(receipt_path.exists(), "Fixture missing: tests/Testbeleg.jpeg")
        user_id = 1
        baseline_ids = self._list_receipt_ids(user_id)
        self.addCleanup(self._cleanup_new_receipts, baseline_ids, user_id)

        # Step 1: Open the login page.
        self.driver.get(f"{self.base_url}/login")

        # Step 2: Use the demo mode login.
        demo_button = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(., 'Im Demo-Modus fortfahren')]")
            )
        )
        demo_button.click()
        self.wait.until(EC.url_contains("/dashboard/extended"))

        # Step 3: Open the upload page and upload the receipt fixture.
        self.driver.get(f"{self.base_url}/upload")
        self.wait.until(
            lambda driver: driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        )
        file_input = self._find_file_input()
        file_input.send_keys(str(receipt_path))

        # Step 4: Wait for the upload + analysis to finish.
        self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[contains(., 'Upload & Analyse erfolgreich.')]")
            )
        )

        # Step 5: Open the receipts page and verify the analysis result is shown.
        self.driver.get(f"{self.base_url}/receipts")
        first_card = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".receipt-card"))
        )
        first_card.click()
        self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[contains(., 'Analyse erfolgreich abgeschlossen.')]")
            )
        )


if __name__ == "__main__":
    unittest.main()
