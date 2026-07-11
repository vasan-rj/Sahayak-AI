"""Wire protocol seam.

The browser and the proxy speak ONE internal envelope. Media (audio/video) rides
as binary WebSocket frames — never base64-in-JSON, which is +33% bytes and would
push codec-sized payloads through the JSON parser on the event loop, silently
setting a latency floor. Control/caption/event messages ride as JSON text.

``decode`` dispatches on frame type. When the Gemini Live wiring lands, its
provider-specific translation belongs here at the boundary — the frontend never
sees raw provider messages, and the witness log never fills with vendor noise.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class Frame:
    kind: str  # "text" | "binary"
    data: dict | None = None  # parsed JSON object (text frames)
    raw: bytes | None = None  # binary payload (media frames)
    error: str | None = None  # "bad_json" | "not_object" | "empty_frame"


def decode(message: dict) -> Frame:
    """Decode a Starlette ``websocket.receive`` message into a Frame.

    Binary frames are handed through untouched (media path). Text frames are
    parsed and validated; malformed input yields a Frame with ``error`` set so
    the caller can reply without dropping the socket.
    """
    if message.get("bytes") is not None:
        return Frame(kind="binary", raw=message["bytes"])
    text = message.get("text")
    if text is None:
        return Frame(kind="text", error="empty_frame")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return Frame(kind="text", error="bad_json")
    if not isinstance(obj, dict):
        return Frame(kind="text", error="not_object")
    return Frame(kind="text", data=obj)


# --- Outbound event envelopes (proxy -> browser) -----------------------------
# One place that defines the wire shape the React client consumes.


def caption_event(side: str, text: str, lang: str | None = None, final: bool = True) -> dict:
    """A live caption line. side is "user" or "agent"."""
    return {"type": "caption", "side": side, "text": text, "lang": lang, "final": final}


def field_update_event(field: dict) -> dict:
    """One field just got confirmed; carries the field snapshot."""
    return {"type": "field_update", "field": field}


def form_snapshot_event(snapshot: dict) -> dict:
    """The full current form state (drives the live-filling UI)."""
    return {"type": "form_snapshot", "form": snapshot}


def form_complete_event() -> dict:
    return {"type": "form_complete"}


def audio_event(data_b64: str) -> dict:
    """A chunk of agent audio (base64-encoded PCM) for the browser to play."""
    return {"type": "audio", "data": data_b64}
