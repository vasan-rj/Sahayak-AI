"""Session configuration — the make-or-break file (v2, voice-first).

Carries the hardcoded template field-map, the voice-first system instruction, the
structured-capture tool declarations, and the Gemini Live session config builder.

v2 mechanism: the agent reads documents / hears speech and, when a field is
confirmed by the user, calls the ``record_field`` tool with a structured value and
its source (document|voice). ``form_complete`` fires when every field is confirmed.
Tool-calling is the primary capture path (robust, language-agnostic); the
``[[FIELD:...]]`` marker parser in ``markers.py`` is a fallback only.
"""

from __future__ import annotations

import os

# --- The hardcoded template (one form, no admin-upload UI) --------------------
# From context/new/TEMPLATE_AND_PROMPT.md. Two document-sourced fields + one
# voice-sourced field, so the demo is not "just an OCR app".
TEMPLATE = {
    "template_id": "jkp_pension_2a",
    "title": "Jan Kalyan Pension Yojana — Application",
    "fields": [
        {
            "id": "applicant_name",
            "label": "Name of Applicant",
            "type": "document",
            "source_doc": "aadhaar",
            "extract": "full name exactly as printed",
            "ask": "अपना आधार कार्ड कैमरे के सामने दिखाइए।",
        },
        {
            "id": "dob",
            "label": "Date of Birth",
            "type": "document",
            "source_doc": "aadhaar",
            "extract": "date of birth in DD/MM/YYYY",
            "ask": "आधार कार्ड पर आपकी जन्मतिथि देख लेता हूँ।",
        },
        {
            "id": "nominee_name",
            "label": "Nominee Name",
            "type": "voice",
            "extract": "the name the user speaks",
            "ask": "आप किसे nominee बनाना चाहते हैं? उनका नाम बताइए।",
        },
    ],
}

# --- Per-template builders ----------------------------------------------------
# The admin dashboard makes the app multi-form: the system instruction and the
# record_field tool's field-id enum are built FROM the active template, not baked
# into a constant. The functions below take a template; the module-level values
# further down are the defaults built from TEMPLATE (the seed / demo form).


def field_ids(template: dict) -> list[str]:
    return [f["id"] for f in template["fields"]]


def field_source(template: dict) -> dict:
    """field_id -> "document"|"voice", inferred from type. Used by the marker
    fallback path, which (unlike record_field) carries no explicit source."""
    return {
        f["id"]: ("document" if f["type"] == "document" else "voice")
        for f in template["fields"]
    }


def _fields_for_prompt(template: dict) -> str:
    lines = []
    for f in template["fields"]:
        if f["type"] == "document":
            lines.append(
                f'- {f["id"]} ("{f["label"]}"): DOCUMENT from {f.get("source_doc", "a document")} — '
                f'extract {f["extract"]}. Ask: "{f["ask"]}"'
            )
        else:
            lines.append(
                f'- {f["id"]} ("{f["label"]}"): VOICE — {f["extract"]}. Ask: "{f["ask"]}"'
            )
    return "\n".join(lines)


def build_system_instruction(template: dict) -> str:
    return f"""\
You are Sahayak, a voice-first form-filling companion for people who may not read
or write. You help them complete an official form by talking to them and by looking
at their documents through a live camera. You are patient, warm, and speak in short,
simple sentences.

LANGUAGE: Speak the user's language. Default Hindi. If the user speaks Tamil, switch
to Tamil instantly and continue — never announce the switch, just follow. Never
require the user to read or write anything, and never ask them to spell anything.

THE FORM ({template["title"]}) — fill these fields in order:
{_fields_for_prompt(template)}

FOR EACH FIELD:
- If it is a DOCUMENT field: ask the user to show the named document to the camera
  (use the field's ask text). Look at the document and read the exact value. Names
  and dates must be exact. If you cannot see it clearly, ask them to hold it steady
  or closer — never guess.
- If it is a VOICE field: ask the field's question and take the answer from speech.
- THEN always confirm the value back by voice in their language:
  "मैंने लिखा: <value> — सही है?" Wait for approval before moving on. If they say it
  is wrong, ask again. Never advance an unconfirmed field.

WHEN A FIELD IS CONFIRMED: call the record_field tool with the field_id, the exact
value, and source ("document" if you read it from a card, "voice" if the user spoke
it). Speak the natural confirmation as usual — the tool call is in addition to, not
instead of, talking to the user.

WHEN ALL FIELDS ARE CONFIRMED: call the form_complete tool.

TONE: If the user's voice sounds frustrated, confused, or tired, slow down, use
simpler words, and reassure them ("कोई बात नहीं, मैं हूँ ना, धीरे-धीरे करते हैं").
Respond to how they feel, not only to what they say.

NEVER invent a value you cannot see or did not hear. NEVER ask the user to read the
form. Keep spoken turns short.
"""


def build_record_field_tool(template: dict) -> dict:
    return {
        "name": "record_field",
        "description": "Record a form field value AFTER the user has confirmed it out loud.",
        "parameters": {
            "type": "object",
            "properties": {
                "field_id": {
                    "type": "string",
                    "enum": field_ids(template),
                    "description": "Which form field this value fills.",
                },
                "value": {"type": "string", "description": "The exact confirmed value."},
                "source": {
                    "type": "string",
                    "enum": ["document", "voice"],
                    "description": "Where the value came from: a document read by camera, or the user's speech.",
                },
            },
            "required": ["field_id", "value", "source"],
        },
    }


FORM_COMPLETE_TOOL = {
    "name": "form_complete",
    "description": "Signal that every field has been captured and confirmed.",
    "parameters": {"type": "object", "properties": {}},
}


def build_tools(template: dict) -> list:
    return [{"function_declarations": [build_record_field_tool(template), FORM_COMPLETE_TOOL]}]


# --- Module-level defaults (built from the seed template, for back-compat) ----
FIELD_IDS = field_ids(TEMPLATE)
FIELD_SOURCE = field_source(TEMPLATE)
SYSTEM_INSTRUCTION = build_system_instruction(TEMPLATE)
RECORD_FIELD_TOOL = build_record_field_tool(TEMPLATE)

# --- Live model (env-overridable) ---------------------------------------------
# gemini-3.1-flash-live-preview verified working (connect + tools + transcription
# + audio) via scripts/smoke_live.py. Other Live models on the account:
# gemini-3.5-live-translate-preview (Live Translate), gemini-2.5-flash-native-audio-*.
LIVE_MODEL = os.environ.get("SAHAYAK_LIVE_MODEL", "gemini-3.1-flash-live-preview")


def live_config(template: dict | None = None) -> dict:
    """Build the LiveConnectConfig dict for google-genai (2.x) for a template.

    Returned as a plain dict so this module needs no google-genai import (keeps
    pure-logic tests import-light). ``app/live_session.py`` passes it to
    ``client.aio.live.connect(config=...)``. Defaults to the seed TEMPLATE.
    """
    template = template or TEMPLATE
    return {
        "response_modalities": ["AUDIO"],
        "system_instruction": build_system_instruction(template),
        "input_audio_transcription": {},  # enable user-speech transcription (captions)
        "output_audio_transcription": {},  # enable agent-speech transcription (captions)
        "tools": build_tools(template),
        # Reactive turn-taking: automatic VAD stays on (so the user can barge in and
        # the model pauses itself), with high sensitivity and a short trailing
        # silence so the agent answers quickly once the user stops talking.
        "realtime_input_config": {
            "automatic_activity_detection": {
                "start_of_speech_sensitivity": "START_SENSITIVITY_HIGH",
                "end_of_speech_sensitivity": "END_SENSITIVITY_HIGH",
                "prefix_padding_ms": 200,
                "silence_duration_ms": 450,
            },
        },
    }
