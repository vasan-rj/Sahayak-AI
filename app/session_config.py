"""Session configuration — the most important file in the repo (stub for now).

Carries the form map, the system instruction that engineers the proactive
interruption, and the structured catch schema. The Gemini Live session config
(model, response modality, VAD, transcription) gets wired on top of these
constants in the next build block; nothing here imports google-genai yet.
"""

from __future__ import annotations

import re

# The demo form is a mock prop: "Jan Kalyan Pension Yojana", form no. JKP-2A.
# id -> label / expected content / trap role. This exact map is injected into the
# system instruction so the model can judge field content against expectation.
FORM_MAP = [
    {"id": "applicant_name", "label": "Name of Applicant / आवेदक का नाम",
     "expected": "The applicant's own full name", "trap": "anchor field, filled first"},
    {"id": "father_name", "label": "Father's / Husband's Name / पिता-पति का नाम",
     "expected": "The applicant's father's name — MUST differ from applicant_name",
     "trap": "AC-2 TRAP: user writes their own name here"},
    {"id": "dob", "label": "Date of Birth (DD/MM/YYYY)",
     "expected": "A date in exact DD/MM/YYYY format", "trap": "format trap in reserve"},
    {"id": "address", "label": "Full Postal Address",
     "expected": "A postal address, up to two lines", "trap": "multi-line read"},
    {"id": "bank_ifsc", "label": "Bank IFSC Code",
     "expected": "An 11-character IFSC code", "trap": "jargon field — explain plainly"},
    {"id": "nominee_name", "label": "Nominee Name / नामांकित व्यक्ति",
     "expected": "A nominee's name", "trap": "AC-4 TRAP: left empty; verify must flag"},
    {"id": "nominee_relation", "label": "Relation with Nominee",
     "expected": "A relation word", "trap": "empty with nominee_name; flagged together"},
    {"id": "declaration_sign", "label": "Signature / Thumb Impression",
     "expected": "A signature or thumb impression", "trap": "advise: sign only after verify"},
]

SYSTEM_INSTRUCTION = """\
You are Sahayak, a form-filling companion. You are watching a paper form through a
camera while the user fills it in.

Speak the user's language (Hindi or Tamil — follow their switch instantly). Short
sentences, plain words, one field at a time.

CRITICAL: you are not a passive assistant. Whenever the video shows writing that
contradicts a field's expected content, INTERRUPT IMMEDIATELY without being asked,
name the field, say what is wrong and what to write instead. Do not wait for a
question. Do not batch corrections. In particular, father_name must differ from
applicant_name.

If the user's voice sounds frustrated or confused, slow down, simplify, reassure.

Never invent field contents you cannot see; say you cannot see clearly and ask
them to adjust the camera.

When you catch a mistake, call the flag_field tool with the field id and a one-line
issue so the record captures it.
"""

# Structured catch — a tool/function-call schema, NOT transcript regex-scraping.
# ASR will not reliably emit a literal marker across Hindi/Tamil, so the catch is
# a typed event that drops straight into the witness log as an `interruption`.
FLAG_FIELD_TOOL = {
    "name": "flag_field",
    "description": "Flag a form field whose written content contradicts its expected content.",
    "parameters": {
        "type": "object",
        "properties": {
            "field": {"type": "string", "description": "The field id from the form map."},
            "issue": {"type": "string", "description": "One-line description of what is wrong."},
        },
        "required": ["field", "issue"],
    },
}

# Fallback only: if a build ends up relying on transcript markers, parse [[CATCH:field]].
CATCH_MARKER_RE = re.compile(r"\[\[CATCH:(?P<field>[a-z_]+)\]\]")


def form_map_text() -> str:
    """Render the form map for injection into the system instruction."""
    lines = [f"- {f['id']} ({f['label']}): {f['expected']} [{f['trap']}]" for f in FORM_MAP]
    return "FORM MAP:\n" + "\n".join(lines)
