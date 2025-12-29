# Unit Tests: Hashing and Receipt Parsing

## Ziel
Dieses Dokument beschreibt die Unit-Tests fuer das Passwort-Hashing und das Parsen von Analyse-Antworten.

## Test 1: test_db_hash_unittest
### Ziel
Validiert das deterministische Hashing mit Salt sowie Fehlerfaelle bei ungueltigen Eingaben.

### Szenario (Testfaelle)
1) Gleiche Eingabe erzeugt erwarteten Hash-String.
2) Unterschiedliche Salts erzeugen unterschiedliche Hashes (Laenge 64 Zeichen).
3) Ungueltiger Salt (kein Hex) loest ValueError aus.
4) Nicht-ASCII im Passwort loest ValueError aus (mehrere Beispielstrings).

### Voraussetzungen
- Python Umgebung aktiv.
- Keine externe Abhaengigkeit noetig (reine Unit-Tests).

### Ausfuehrung
```powershell
python -m unittest tests/1_unit/test_db_hash_unittest.py
```

## Test 2: test_receipt_analysis_parse_response_unittest
### Ziel
Stellt sicher, dass JSON-Antworten korrekt geparst werden, inklusive Markdown-Codebloecken.

### Szenario (Testfaelle)
1) Reiner JSON-Text wird korrekt geparst.
2) JSON im Markdown-Codeblock wird korrekt erkannt.
3) Ungueltiger Text loest ValueError aus.

### Voraussetzungen
- Python Umgebung aktiv.

### Ausfuehrung
```powershell
python -m unittest tests/1_unit/test_receipt_analysis_parse_response_unittest.py
```

## Troubleshooting
- Fehler bei ValueError-Tests:
  - Pruefe, ob die Eingabevalidierung in `app.db._hash_password` bzw. `app.receipt_analysis.ReceiptAnalyzer._parse_response` angepasst wurde.
- Erwarteter Hash weicht ab:
  - Pruefe, ob Hash-Algorithmus oder Salt-Handling geaendert wurde.
