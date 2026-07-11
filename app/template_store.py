"""File-backed template store — makes Sahayak multi-form.

Each template is one JSON file under the store dir (env ``SAHAYAK_TEMPLATE_DIR``,
default ``./data/templates``); ``_active.txt`` names the template the applicant app
fills. No DB — matches the file-based capture log, zero new deps. On first init the
hardcoded ``TEMPLATE`` (the demo form) is seeded so nothing breaks.
"""

from __future__ import annotations

import json
import os
import re

from .session_config import TEMPLATE

_SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_REQUIRED_FIELD_KEYS = ("id", "label", "type", "extract", "ask")


class TemplateError(Exception):
    """Raised when a template fails validation."""


def validate_template(t: dict) -> dict:
    """Validate a template's shape. Returns it unchanged, or raises TemplateError."""
    if not isinstance(t, dict):
        raise TemplateError("template must be an object")
    for key in ("template_id", "title", "fields"):
        if not t.get(key):
            raise TemplateError(f"missing '{key}'")
    if not _SLUG_RE.match(t["template_id"]):
        raise TemplateError("template_id must be a slug ([A-Za-z0-9_-])")
    if not isinstance(t["fields"], list) or not t["fields"]:
        raise TemplateError("fields must be a non-empty list")
    seen: set[str] = set()
    for f in t["fields"]:
        if not isinstance(f, dict):
            raise TemplateError("each field must be an object")
        for key in _REQUIRED_FIELD_KEYS:
            if not f.get(key):
                raise TemplateError(f"field '{f.get('id', '?')}' missing '{key}'")
        if f["type"] not in ("document", "voice"):
            raise TemplateError(f"field '{f['id']}' has invalid type '{f['type']}'")
        if f["id"] in seen:
            raise TemplateError(f"duplicate field id '{f['id']}'")
        seen.add(f["id"])
    return t


def _default_dir() -> str:
    return os.environ.get("SAHAYAK_TEMPLATE_DIR", os.path.join(os.getcwd(), "data", "templates"))


class TemplateStore:
    def __init__(self, directory: str | None = None):
        self.dir = directory or _default_dir()
        os.makedirs(self.dir, exist_ok=True)
        self.seed_default()

    def _path(self, tid: str) -> str:
        return os.path.join(self.dir, f"{tid}.json")

    @property
    def _active_file(self) -> str:
        return os.path.join(self.dir, "_active.txt")

    def seed_default(self) -> None:
        if not self.list_ids():
            self.save(TEMPLATE)
            self.set_active(TEMPLATE["template_id"])

    def list_ids(self) -> list[str]:
        return sorted(
            f[:-5] for f in os.listdir(self.dir) if f.endswith(".json")
        )

    def list_templates(self) -> list[dict]:
        active = self.get_active_id()
        summaries = []
        for tid in self.list_ids():
            t = self.get(tid)
            summaries.append(
                {
                    "template_id": tid,
                    "title": t["title"],
                    "field_count": len(t["fields"]),
                    "active": tid == active,
                }
            )
        return summaries

    def get(self, tid: str) -> dict:
        path = self._path(tid)
        if not os.path.exists(path):
            raise KeyError(tid)
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save(self, template: dict) -> dict:
        validate_template(template)
        with open(self._path(template["template_id"]), "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        return template

    def delete(self, tid: str) -> None:
        path = self._path(tid)
        if os.path.exists(path):
            os.remove(path)
        if self.get_active_id() == tid:
            remaining = self.list_ids()
            if remaining:
                self.set_active(remaining[0])
            elif os.path.exists(self._active_file):
                os.remove(self._active_file)

    def get_active_id(self) -> str | None:
        if os.path.exists(self._active_file):
            with open(self._active_file, encoding="utf-8") as f:
                tid = f.read().strip()
            if tid and os.path.exists(self._path(tid)):
                return tid
        ids = self.list_ids()
        return ids[0] if ids else None

    def get_active(self) -> dict:
        tid = self.get_active_id()
        return self.get(tid) if tid else TEMPLATE

    def set_active(self, tid: str) -> None:
        if not os.path.exists(self._path(tid)):
            raise KeyError(tid)
        with open(self._active_file, "w", encoding="utf-8") as f:
            f.write(tid)


_STORE: TemplateStore | None = None


def get_store() -> TemplateStore:
    """Process-wide store singleton (reads SAHAYAK_TEMPLATE_DIR on first use)."""
    global _STORE
    if _STORE is None:
        _STORE = TemplateStore()
    return _STORE
