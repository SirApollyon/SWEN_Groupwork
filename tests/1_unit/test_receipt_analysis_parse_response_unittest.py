import unittest

from app.receipt_analysis import ReceiptAnalyzer


# ## Tests fuer ReceiptAnalyzer._parse_response
# - Prüft die JSON-Auswertung in verschiedenen Eingabeformaten.
class TestParseResponse(unittest.TestCase):
    def test_parses_plain_json(self):
        # **Gegeben:** reiner JSON-Text als String
        text = '{"is_receipt": true, "total_amount": 12.5}'
        # **Wenn:** geparst wird
        data = ReceiptAnalyzer._parse_response(text)
        # **Dann:** Felder sind korrekt extrahiert
        self.assertEqual(data["is_receipt"], True)
        self.assertEqual(data["total_amount"], 12.5)

    def test_parses_markdown_json_block(self):
        # **Gegeben:** JSON in einem Markdown-Codeblock
        text = "```json\n{\"is_receipt\": false}\n```"
        # **Wenn:** geparst wird
        data = ReceiptAnalyzer._parse_response(text)
        # **Dann:** JSON wird trotz Codeblock korrekt erkannt
        self.assertEqual(data["is_receipt"], False)

    def test_raises_on_invalid_json(self):
        # **Gegeben/Wenn:** ungültiger Text
        with self.assertRaises(ValueError):
            # **Dann:** Parser signalisiert Fehler
            ReceiptAnalyzer._parse_response("not-json")


# ## Direkter Testlauf via CLI
if __name__ == "__main__":
    unittest.main()
