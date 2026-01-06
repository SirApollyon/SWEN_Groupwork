# Integrationstest: Upload Receipt API

## Zweck des Tests

Dieser Integrationstest prueft den API-Endpoint
POST /api/upload

auf Handler-Ebene. Ziel ist es sicherzustellen, dass der Endpoint:

- den Upload einer JPEG-Datei korrekt entgegennimmt,
- die Datei durch die Upload-Pipeline schleust (Normalisierung, Persistierung, Folge-Analyse),
- die Rueckgabe der Business-Logik korrekt in die HTTP-Response einbettet.

Die eigentliche Bildverarbeitung und Persistierung werden dabei **nicht ausgefuehrt**, sondern gezielt ersetzt (Mocks/Stubs).

---

## Teststrategie

- **Framework:** `unittest`
- **HTTP-Simulation:** `fastapi.testclient.TestClient`
- **Mocking:** `unittest.mock.patch.object`
- **Testtyp:** Integrationstest (API-Schicht, ohne echte Business-Logik)

Die Funktionen `upload_service.normalize_upload_image`, `upload_service.insert_receipt` und `main.analyze_receipt` werden fuer die Tests stubbed, um gezielt den Ablauf der Pipeline zu kontrollieren.

---

## Abgedeckte Testfaelle

### 1. Erfolgreicher Upload mit Folge-Analyse (Happy Path)

- Test schickt ein kameratypisches JPEG-Fixture an `/api/upload`
- Erwartet:
  - HTTP Status **200**
  - Response enthaelt `receipt_id`, Dateiname und Dateigroesse
  - Analyse-Payload wird durchgereicht (`analysis.ok` ist `True`)
  - Pipeline-Aufrufe erfolgen mit korrekten Argumenten:
    - Normalisierung erhaelt die Rohbytes
    - Persistierung erhaelt `user_id` und normalisierte Bytes
    - Analyse wird mit erzeugter `receipt_id` und `user_id` getriggert

---

## Abgrenzung

Dieser Test prueft **nicht**:

- die echte Bild-Normalisierung,
- die Persistierung in einer Datenbank oder im Dateisystem,
- die reale Analyse-Logik.

Der Fokus liegt ausschliesslich auf der **korrekten Verarbeitung innerhalb der API-Schicht**.

---

## Mehrwert fuer das Projekt

- Absicherung der Upload-Pipeline ohne Abhaengigkeit von Speicher oder Vision-Logik
- Schnelles Feedback, falls sich Request-/Response-Formate oder Aufrufreihenfolgen aendern
