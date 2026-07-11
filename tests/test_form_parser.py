import json
from types import SimpleNamespace as NS

import pytest

from app.form_parser import FormParseError, parse_blank_form


class _MockClient:
    """Duck-typed genai client whose models.generate_content returns fixed text."""

    def __init__(self, text):
        self.models = NS(generate_content=lambda **kw: NS(text=text))


VALID = {
    "template_id": "ration_card",
    "title": "Ration Card",
    "fields": [
        {"id": "name", "label": "Name", "type": "document", "source_doc": "aadhaar", "extract": "name", "ask": "नाम?"},
        {"id": "members", "label": "Members", "type": "voice", "extract": "count", "ask": "कितने?"},
    ],
}


def test_returns_validated_draft():
    d = parse_blank_form(b"img", "image/jpeg", client=_MockClient(json.dumps(VALID)))
    assert d["template_id"] == "ration_card"
    assert len(d["fields"]) == 2
    assert d["fields"][0]["type"] == "document"


def test_normalizes_slug_and_dedupes_ids():
    raw = {
        "template_id": "My Form!",
        "title": "My Form",
        "fields": [
            {"id": "Full Name", "label": "Full Name", "type": "document", "extract": "x", "ask": "?"},
            {"id": "Full Name", "label": "dup", "type": "voice", "extract": "y", "ask": "?"},
        ],
    }
    d = parse_blank_form(b"i", "image/jpeg", client=_MockClient(json.dumps(raw)))
    assert d["template_id"] == "my_form"
    ids = [f["id"] for f in d["fields"]]
    assert ids == ["full_name", "full_name_2"]


def test_empty_fields_raises():
    payload = json.dumps({"template_id": "t", "title": "T", "fields": []})
    with pytest.raises(FormParseError):
        parse_blank_form(b"i", "image/jpeg", client=_MockClient(payload))


def test_non_json_raises():
    with pytest.raises(FormParseError):
        parse_blank_form(b"i", "image/jpeg", client=_MockClient("not json at all"))


def test_empty_response_raises():
    with pytest.raises(FormParseError):
        parse_blank_form(b"i", "image/jpeg", client=_MockClient(""))
