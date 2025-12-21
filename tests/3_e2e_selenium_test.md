# E2E Selenium Test: Receipt Upload Flow

## Ziel
Dieses Dokument beschreibt den End-to-End Test für den Demo-Login, den Upload, die Analyse und die Ergebnisanzeige.

## Szenario (Schritte)
1) User öffnet `/login`.
2) Klickt "Im Demo-Modus fortfahren".
3) Öffnet `/upload`.
4) Lädt `tests/Testbeleg.jpeg` über das File-Input hoch.
5) Wartet auf die Meldung "Upload & Analyse erfolgreich.".
6) Öffnet `/receipts` und klickt die erste Beleg-Karte.
7) Prüft den Text "Analyse erfolgreich abgeschlossen." im Detaildialog.

## Voraussetzungen
- Python Umgebung aktiv, Abhängigkeiten installiert (`pip install -r requirements.txt`).
- Chrome/Chromium installiert (Selenium Manager lädt den Driver bei Bedarf).
- Zugriff auf Azure SQL und Google GenAI (API Key in `.env`).
- Testdaten in der DB: Kategorien vorhanden und User ID 1 existiert (Demo-User).

## Ausführung
### Standard (Test startet Server selbst)
```powershell
python "tests/3_e2e/test_selenium_receipt_flow.py"
```

### Wenn der Server bereits laeuft
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
Der Test speichert vor dem Upload eine Baseline der bestehenden Belege für `user_id=1`.
Nach dem Test werden alle neuen Belege gelöscht. Zuvor werden zugehörige Transaktionen entfernt.

Hinweis: Führe den Test nur gegen eine Test-DB aus, da Daten gelöscht werden.

## Troubleshooting
- Timeout bei "Upload & Analyse erfolgreich.":
  - Prüfe, ob User ID 1 existiert und Kategorien vorhanden sind.
  - Prüfe `GOOGLE_API_KEY` und DB-Verbindung.
  - Im sichtbaren Browser die Statusmeldung auslesen.
- Selenium/Driver Probleme:
  - Chrome/Chromium installieren.
  - Optional `CHROME_BINARY` setzen.
