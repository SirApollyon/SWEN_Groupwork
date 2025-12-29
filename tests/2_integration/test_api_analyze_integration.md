# Integrationstest: Analyze Receipt API

## Zweck des Tests

Dieser Integrationstest überprüft den API-Endpoint
POST /api/receipts/{receipt_id}/analyze

auf Handler-Ebene. Ziel ist es sicherzustellen, dass der Endpoint:

- korrekt aufgerufen wird,
- die Parameter (`receipt_id`, optional `user_id`) richtig an die Business-Logik weiterreicht,
- das Analyse-Ergebnis korrekt in die HTTP-Response einbettet,
- Exceptions korrekt in HTTP-Statuscodes übersetzt.

Die eigentliche Analyse-Logik wird dabei **nicht ausgeführt**, sondern gezielt ersetzt (Mock).

---

## Teststrategie

- **Framework:** `unittest`
- **HTTP-Simulation:** `fastapi.testclient.TestClient`
- **Mocking:** `unittest.mock.patch.object`
- **Testtyp:** Integrationstest (API-Schicht, ohne echte Business-Logik)

Die Funktion `main.analyze_receipt` wird in jedem Testfall durch eine Fake-Implementierung ersetzt, um gezielt verschiedene Szenarien zu simulieren.

---

## Abgedeckte Testfälle

### 1. Erfolgreicher Analyse-Aufruf (Happy Path)

- `analyze_receipt` liefert ein gültiges Analyse-Payload zurück
- Erwartet:
  - HTTP Status **200**
  - Korrektes Response-Format (`receipt_id`, `analysis`)
  - Korrekte Weitergabe der Argumente (`receipt_id`, `user_id`)

### 2. Fachlicher Fehler: Quittung nicht gefunden

- `analyze_receipt` wirft einen `ValueError`
- Erwartet:
  - HTTP Status **404 (Not Found)**
  - Aussagekräftige Fehlermeldung im Response

### 3. Unerwarteter Fehler

- `analyze_receipt` wirft eine nicht behandelte Exception (`RuntimeError`)
- Erwartet:
  - HTTP Status **500 (Internal Server Error)**
  - Weitergabe der Fehlermeldung im Response

---

## Abgrenzung

Dieser Test prüft **nicht**:

- die tatsächliche Implementierung der Analyse-Logik,
- externe Services oder Datenbanken,
- Performance oder Nebenläufigkeit.

Der Fokus liegt ausschließlich auf der **korrekten Verarbeitung innerhalb der API-Schicht**.

---

## Mehrwert für das Projekt

- Klare Trennung zwischen API-Logik und Business-Logik
- Frühzeitiges Erkennen von Fehlern im Request-/Response-Mapping

