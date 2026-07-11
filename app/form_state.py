"""Per-session form state — the digital form that fills itself live.

Derived from the hardcoded template. Each field starts ``pending``; a confirmed
capture moves it to ``confirmed`` with a value and a source (document|voice). The
form is ``complete`` once every field is confirmed. ``snapshot`` is the browser
payload that drives the live-filling UI and the printable finale.
"""

from __future__ import annotations

import copy

from .session_config import TEMPLATE


class FormState:
    def __init__(self, template: dict | None = None):
        self.template = template or TEMPLATE
        self._order = [f["id"] for f in self.template["fields"]]
        self._fields = {
            f["id"]: {
                "id": f["id"],
                "label": f["label"],
                "type": f["type"],
                "value": None,
                "status": "pending",
                "source": None,
            }
            for f in self.template["fields"]
        }

    def apply(self, field_id: str, value: str, source: str) -> dict:
        """Confirm a field. Raises KeyError for an unknown field id (a model that
        hallucinates a field must fail loudly, not corrupt the form)."""
        if field_id not in self._fields:
            raise KeyError(field_id)
        if source not in ("document", "voice"):
            raise ValueError(f"invalid source: {source!r}")
        f = self._fields[field_id]
        f["value"] = value
        f["source"] = source
        f["status"] = "confirmed"
        return copy.deepcopy(f)

    def is_complete(self) -> bool:
        return all(f["status"] == "confirmed" for f in self._fields.values())

    def remaining(self) -> list[str]:
        return [fid for fid in self._order if self._fields[fid]["status"] != "confirmed"]

    def snapshot(self) -> dict:
        return {
            "template_id": self.template["template_id"],
            "title": self.template["title"],
            "fields": [copy.deepcopy(self._fields[fid]) for fid in self._order],
            "complete": self.is_complete(),
        }
