"""Fallback marker parsing.

Primary capture is via Live tool-calls (see session_config). But the system
instruction can also be told to emit ``[[FIELD:id=value]]`` and ``[[FORM_COMPLETE]]``
markers in its text; this module extracts them and, importantly, strips ANY such
markers out of the caption text the user/judges see — so a stray marker never leaks
onto the captions bar even when the tool path is doing the real work.
"""

from __future__ import annotations

import re

FIELD_RE = re.compile(r"\[\[FIELD:(?P<id>[a-zA-Z_][a-zA-Z0-9_]*)=(?P<value>.*?)\]\]")
COMPLETE_RE = re.compile(r"\[\[FORM_COMPLETE\]\]")


def parse_and_strip(text: str) -> tuple[list[tuple[str, str]], bool, str]:
    """Return (fields, form_complete, clean_text).

    ``fields`` is a list of (field_id, value) in order of appearance. ``clean_text``
    is ``text`` with every marker removed and surrounding whitespace collapsed.
    """
    if not text:
        return [], False, ""
    fields = [(m.group("id"), m.group("value").strip()) for m in FIELD_RE.finditer(text)]
    complete = bool(COMPLETE_RE.search(text))
    clean = COMPLETE_RE.sub("", FIELD_RE.sub("", text))
    clean = re.sub(r"[ \t]{2,}", " ", clean).strip()
    return fields, complete, clean
