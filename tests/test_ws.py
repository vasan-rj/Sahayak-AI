"""WebSocket + HTTP tests. The Gemini Live session is replaced by a scripted mock
(via app.main.relay_cm), so the full proxy path — capture -> form -> browser
events + capture log — is exercised with no network.
"""

import contextlib
import os

from fastapi.testclient import TestClient

import app.main as main
from app.live_session import LiveRelay
from app.witness_log import WitnessLog
from tests.mocks import MockLiveSession, audio_msg, caption_msg, tool_msg

SCRIPTED_TURN = [
    caption_msg(agent="नमस्ते, आधार दिखाइए।"),
    audio_msg(b"\x10\x20"),
    tool_msg(("record_field", {"field_id": "applicant_name", "value": "RAJESH KUMAR", "source": "document"})),
    tool_msg(("record_field", {"field_id": "dob", "value": "01/01/1990", "source": "document"})),
    tool_msg(("record_field", {"field_id": "nominee_name", "value": "SUNITA DEVI", "source": "voice"})),
    tool_msg(("form_complete", {})),
]


_LAST_MOCK: dict = {}


@contextlib.asynccontextmanager
async def _fake_relay_cm(session, callbacks):
    mock = MockLiveSession([list(SCRIPTED_TURN)])
    _LAST_MOCK["m"] = mock
    yield LiveRelay(mock, **callbacks)


def _use_mock_relay(monkeypatch):
    monkeypatch.setattr(main, "relay_cm", _fake_relay_cm)


def test_health():
    with TestClient(main.app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "model" in body


def test_template_endpoint():
    with TestClient(main.app) as c:
        r = c.get("/template")
    body = r.json()
    assert body["template_id"] == "jkp_pension_2a"
    assert [f["id"] for f in body["fields"]] == ["applicant_name", "dob", "nominee_name"]


def test_ws_scripted_session_fills_form(monkeypatch):
    _use_mock_relay(monkeypatch)
    before = set(os.listdir(main.registry.log_dir))

    events = []
    with TestClient(main.app) as c:
        with c.websocket_connect("/ws") as ws:
            # Read until the form completes (guard against runaway).
            for _ in range(40):
                msg = ws.receive_json()
                events.append(msg)
                if msg["type"] == "form_complete":
                    break

    types_seen = [e["type"] for e in events]
    assert types_seen[0] == "form_snapshot"  # initial blank form pushed on connect
    assert "caption" in types_seen
    assert "audio" in types_seen
    assert types_seen.count("field_update") == 3
    assert "form_complete" in types_seen

    # Final snapshot before completion shows every field confirmed.
    snaps = [e for e in events if e["type"] == "form_snapshot"]
    assert snaps[-1]["form"]["complete"] is True
    by_id = {f["id"]: f for f in snaps[-1]["form"]["fields"]}
    assert by_id["applicant_name"]["value"] == "RAJESH KUMAR"
    assert by_id["nominee_name"]["source"] == "voice"

    # Capture log written and hash-chain intact.
    new = set(os.listdir(main.registry.log_dir)) - before
    assert len(new) == 1
    log = WitnessLog(os.path.join(main.registry.log_dir, new.pop()))
    kinds = [e["kind"] for e in log.read()]
    assert kinds[0] == "session_start"
    assert kinds.count("field_captured") == 3
    assert "form_complete" in kinds
    assert kinds[-1] == "session_end"
    assert log.verify() is True


def test_ws_sends_opening_trigger(monkeypatch):
    """Regression: the agent must greet first. The proxy sends an opening text
    turn on connect, otherwise the Live model stays silent (no audio)."""
    _use_mock_relay(monkeypatch)
    with TestClient(main.app) as c:
        with c.websocket_connect("/ws") as ws:
            for _ in range(40):
                if ws.receive_json()["type"] == "form_complete":
                    break
    mock = _LAST_MOCK["m"]
    assert mock.client_content, "no opening turn was sent — agent would be silent"
    assert "Begin now" in str(mock.client_content[0][0])


def test_caption_event_shape(monkeypatch):
    _use_mock_relay(monkeypatch)
    with TestClient(main.app) as c:
        with c.websocket_connect("/ws") as ws:
            found = None
            for _ in range(40):
                msg = ws.receive_json()
                if msg["type"] == "caption":
                    found = msg
                    break
    assert found is not None
    assert found["side"] == "agent"
    assert found["text"] == "नमस्ते, आधार दिखाइए।"
    assert found["lang"] == "hi"
