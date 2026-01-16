# E2E Selenium Test: Receipt Upload Flow

## Ziel
Dieses Dokument beschreibt den End-to-End Test f�r den Demo-Login, den Upload, die Analyse und die Ergebnisanzeige.

## Szenario (Schritte)
1) User �ffnet `/login`.
2) Klickt "Im Demo-Modus fortfahren".
3) �ffnet `/upload`.
4) L�dt `tests/Testbeleg.jpeg` �ber das File-Input hoch.
5) Wartet auf die Meldung "Upload & Analyse erfolgreich.".
6) �ffnet `/receipts` und klickt die erste Beleg-Karte.
7) Pr�ft den Text "Analyse erfolgreich abgeschlossen." im Detaildialog.

## Voraussetzungen
- Python Umgebung aktiv, Abh�ngigkeiten installiert (`pip install -r requirements.txt`).
- Chrome/Chromium installiert (Selenium Manager l�dt den Driver bei Bedarf).
- Zugriff auf Azure SQL und Google GenAI (API Key in `.env`).
- Testdaten in der DB: Kategorien vorhanden und User ID 1 existiert (Demo-User).

## Ausf�hrung
### Standard (Test startet Server selbst)
```powershell
python "tests/3_e2e/test_selenium_receipt_flow.py"
```

### Wenn der Server bereits l�uft
```powershell
$env:E2E_START_SERVER = "0"
$env:E2E_BASE_URL = "http://127.0.0.1:8000"
python "tests/3_e2e/test_selenium_receipt_flow.py"
```

### Sichtbarer Browser
```powershell
$env:E2E_HEADLESS = "0"
python "tests/3_e2e/test_selenium_receipt_flow.py"
```

## Konfiguration (Environment Variablen)
- `E2E_BASE_URL` (Default: `http://127.0.0.1:8000`)
- `E2E_START_SERVER` (Default: `1`)
- `E2E_TIMEOUT` (Default: `120` Sekunden)
- `E2E_SERVER_TIMEOUT` (Default: `30` Sekunden)
- `E2E_HEADLESS` (Default: `1`)
- `CHROME_BINARY` (optional, eigener Chrome/Chromium Pfad)

## Cleanup-Verhalten
Der Test speichert vor dem Upload eine Baseline der bestehenden Belege f�r `user_id=1`.
Nach dem Test werden alle neuen Belege gel�scht. Zuvor werden zugeh�rige Transaktionen entfernt.

Hinweis: F�hre den Test nur gegen eine Test-DB aus, da Daten gel�scht werden.

## Troubleshooting
- Timeout bei "Upload & Analyse erfolgreich.":
  - Pr�fe, ob User ID 1 existiert und Kategorien vorhanden sind.
  - Pr�fe `GOOGLE_API_KEY` und DB-Verbindung.
  - Im sichtbaren Browser die Statusmeldung auslesen.
- Selenium/Driver Probleme:
  - Chrome/Chromium installieren.
  - Optional `CHROME_BINARY` setzen.
