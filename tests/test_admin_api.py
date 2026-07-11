"""Admin API tests via TestClient. The store + capture logs use the temp dirs set
in conftest; the parse-form model call is monkeypatched (no network)."""

import os

from fastapi.testclient import TestClient

import app.main as main
from app.witness_log import WitnessLog


def _client():
    return TestClient(main.app)


def test_list_templates_includes_seed():
    with _client() as c:
        r = c.get("/admin/templates")
    assert r.status_code == 200
    assert "jkp_pension_2a" in [t["template_id"] for t in r.json()]


def test_create_get_activate_delete_flow():
    tpl = {
        "template_id": "ration",
        "title": "Ration Card",
        "fields": [{"id": "name", "label": "Name", "type": "voice", "extract": "n", "ask": "नाम?"}],
    }
    with _client() as c:
        assert c.post("/admin/templates", json=tpl).status_code == 200
        assert c.get("/admin/templates/ration").json()["title"] == "Ration Card"
        assert c.post("/admin/templates/ration/activate").json()["active"] == "ration"
        # the applicant /template endpoint now serves the active (ration) form
        assert c.get("/template").json()["template_id"] == "ration"
        assert c.delete("/admin/templates/ration").json()["ok"] is True
        assert c.get("/admin/templates/ration").status_code == 404


def test_create_invalid_template_400():
    bad = {
        "template_id": "x",
        "title": "X",
        "fields": [{"id": "a", "label": "A", "type": "telepathy", "extract": "e", "ask": "?"}],
    }
    with _client() as c:
        assert c.post("/admin/templates", json=bad).status_code == 400


def test_parse_form_returns_draft(monkeypatch):
    draft = {
        "template_id": "uploaded",
        "title": "Uploaded",
        "fields": [{"id": "a", "label": "A", "type": "voice", "extract": "e", "ask": "?"}],
    }
    monkeypatch.setattr("app.admin.parse_blank_form", lambda data, mime: draft)
    with _client() as c:
        r = c.post("/admin/parse-form", files={"file": ("f.jpg", b"bytes", "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["template_id"] == "uploaded"


def test_sessions_list_and_detail():
    log_dir = main.registry.log_dir
    sid = "sess_admin_test"
    log = WitnessLog(os.path.join(log_dir, f"{sid}.jsonl"))
    log.append("session_start", {"session_id": sid})
    log.append("field_captured", {"field": "a", "value": "X", "source": "voice"})
    log.append("form_complete", {})
    log.append("session_end", {})

    with _client() as c:
        listing = c.get("/admin/sessions").json()
        detail = c.get(f"/admin/sessions/{sid}").json()

    row = next(s for s in listing if s["id"] == sid)
    assert row["fields"] == 1 and row["complete"] is True
    assert detail["verified"] is True
    assert detail["entries"][1]["kind"] == "field_captured"


def test_session_detail_404_for_unknown():
    with _client() as c:
        assert c.get("/admin/sessions/nope").status_code == 404
