"""Upload-a-blank-form → field-map, via Gemini vision.

The admin uploads a photo/scan of a blank official form; a non-Live
``generate_content`` call with a JSON response schema returns a draft template
(field-map) the admin reviews and edits before saving. This is the "admin uploads
any form, the agent learns it" pitch, made real. The draft is never auto-saved.
"""

from __future__ import annotations

import json
import os
import re

from .template_store import TemplateError, validate_template

PARSE_MODEL = os.environ.get("SAHAYAK_PARSE_MODEL", "gemini-flash-latest")

# JSON schema the model must return (mirrors a template field-map).
TEMPLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "template_id": {"type": "string"},
        "title": {"type": "string"},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "type": {"type": "string", "enum": ["document", "voice"]},
                    "source_doc": {"type": "string"},
                    "extract": {"type": "string"},
                    "ask": {"type": "string"},
                },
                "required": ["id", "label", "type", "extract", "ask"],
            },
        },
    },
    "required": ["template_id", "title", "fields"],
}

_PROMPT = """\
You are given a photo or scan of a BLANK official form (it has no filled-in values).
Identify every fillable field. Return a field-map as JSON.

For each field give:
- id: a short snake_case identifier
- label: the printed label, as on the form
- type: "document" if the value should be read from an ID document the applicant
  shows to a camera (names, dates of birth, ID/account numbers, IFSC — anything
  printed on Aadhaar/PAN/passbook), or "voice" if it is something the person simply
  says (a nominee name, a relationship, a preference)
- source_doc: for document fields, which document (e.g. "aadhaar", "pan", "passbook")
- extract: one line describing exactly what to capture
- ask: a short, warm sentence in Hindi asking the applicant for it

Also give the form a snake_case template_id and a human title.
Prefer "document" for accuracy-critical printed values. Keep it to the real fields.
"""


class FormParseError(Exception):
    """Raised when the model output can't be turned into a valid template."""


def _slug(text: str, fallback: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", (text or "").strip().lower()).strip("_")
    return s or fallback


def _normalize(draft: dict) -> dict:
    """Coerce model output into a store-valid template (slug ids, unique field ids)."""
    if not isinstance(draft, dict):
        raise FormParseError("model did not return an object")
    draft["template_id"] = _slug(draft.get("template_id") or draft.get("title", ""), "uploaded_form")
    draft["title"] = (draft.get("title") or "Uploaded Form").strip()
    fields = draft.get("fields")
    if not isinstance(fields, list) or not fields:
        raise FormParseError("model returned no fields")
    seen: set[str] = set()
    for i, f in enumerate(fields):
        fid = _slug(f.get("id") or f.get("label", ""), f"field_{i + 1}")
        while fid in seen:
            fid = f"{fid}_2"
        seen.add(fid)
        f["id"] = fid
        if f.get("type") not in ("document", "voice"):
            f["type"] = "voice"
    return draft


def _make_client():
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise FormParseError("GOOGLE_API_KEY not set")
    from google import genai

    return genai.Client(api_key=key)


def parse_blank_form(image_bytes: bytes, mime: str = "image/jpeg", client=None) -> dict:
    """Parse a blank-form image into a validated draft template. Sync (run it in a
    thread from async routes). ``client`` is injectable for tests."""
    client = client or _make_client()
    from google.genai import types

    resp = client.models.generate_content(
        model=PARSE_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime),
            _PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TEMPLATE_SCHEMA,
        ),
    )
    text = getattr(resp, "text", None)
    if not text:
        raise FormParseError("empty response from model")
    try:
        draft = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise FormParseError(f"model returned non-JSON: {exc}") from exc
    draft = _normalize(draft)
    try:
        validate_template(draft)
    except TemplateError as exc:
        raise FormParseError(f"parsed template invalid: {exc}") from exc
    return draft
