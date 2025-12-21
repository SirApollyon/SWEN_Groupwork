import unittest

from app.receipt_analysis import ReceiptAnalyzer


class TestParseResponse(unittest.TestCase):
    def test_parses_plain_json(self):
        text = '{"is_receipt": true, "total_amount": 12.5}'
        data = ReceiptAnalyzer._parse_response(text)
        self.assertEqual(data["is_receipt"], True)
        self.assertEqual(data["total_amount"], 12.5)

    def test_parses_markdown_json_block(self):
        text = "```json\n{\"is_receipt\": false}\n```"
        data = ReceiptAnalyzer._parse_response(text)
        self.assertEqual(data["is_receipt"], False)

    def test_raises_on_invalid_json(self):
        with self.assertRaises(ValueError):
            ReceiptAnalyzer._parse_response("not-json")


if __name__ == "__main__":
    unittest.main()
