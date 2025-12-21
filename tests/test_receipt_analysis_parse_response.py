import pytest

from app.receipt_analysis import ReceiptAnalyzer


def test_parses_plain_json():
    text = '{"is_receipt": true, "total_amount": 12.5}'
    data = ReceiptAnalyzer._parse_response(text)
    assert data["is_receipt"] is True
    assert data["total_amount"] == 12.5


def test_parses_markdown_json_block():
    text = "```json\n{\"is_receipt\": false}\n```"
    data = ReceiptAnalyzer._parse_response(text)
    assert data["is_receipt"] is False


def test_raises_on_invalid_json():
    with pytest.raises(ValueError):
        ReceiptAnalyzer._parse_response("not-json")
