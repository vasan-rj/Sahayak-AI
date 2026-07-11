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
