"""WebSocket + HTTP scaffold tests via FastAPI TestClient.

TestClient WS is synchronous-in-process — exactly enough for echo, malformed
input, and the session -> witness-log integration. It does NOT exercise real
concurrent bidirectional pumping; that needs a real async harness once the
Gemini reader/writer tasks exist (tracked follow-up, not today).
"""

import os

from fastapi.testclient import TestClient

from app.main import app, registry
from app.witness_log import WitnessLog


def test_health():
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_verify_stub_contract():
    with TestClient(app) as c:
        r = c.post("/verify")
    body = r.json()
    assert r.status_code == 200
    assert body["stub"] is True
    assert len(body["checklist"]) == 8
    assert body["checklist"][1]["field"] == "father_name"


def test_ws_ping_pong():
    with TestClient(app) as c:
        with c.websocket_connect("/ws") as ws:
            ws.send_json({"type": "ping", "payload": "namaste"})
            assert ws.receive_json() == {"type": "pong", "payload": "namaste"}


def test_ws_echo_non_ping():
    with TestClient(app) as c:
        with c.websocket_connect("/ws") as ws:
            ws.send_json({"type": "note", "x": 1})
            assert ws.receive_json() == {"type": "echo", "payload": {"type": "note", "x": 1}}


def test_ws_malformed_frame_errors_but_socket_survives():
    with TestClient(app) as c:
        with c.websocket_connect("/ws") as ws:
            ws.send_text("{not valid json")
            err = ws.receive_json()
            assert err == {"type": "error", "detail": "bad_json"}
            # Socket is still usable after the bad frame.
            ws.send_json({"type": "ping", "payload": 7})
            assert ws.receive_json() == {"type": "pong", "payload": 7}


def test_ws_non_object_frame_errors():
    with TestClient(app) as c:
        with c.websocket_connect("/ws") as ws:
            ws.send_text("[1, 2, 3]")
            assert ws.receive_json() == {"type": "error", "detail": "not_object"}


def test_ws_session_start_and_end_logged():
    before = set(os.listdir(registry.log_dir))
    with TestClient(app) as c:
        with c.websocket_connect("/ws") as ws:
            ws.send_json({"type": "ping"})
            ws.receive_json()
    new = set(os.listdir(registry.log_dir)) - before
    assert len(new) == 1
    log = WitnessLog(os.path.join(registry.log_dir, new.pop()))
    entries = log.read()
    kinds = [e["kind"] for e in entries]
    assert kinds[0] == "session_start"
    assert kinds[-1] == "session_end"
    assert log.verify() is True
