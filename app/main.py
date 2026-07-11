"""Sahayak proxy — FastAPI app.

Walking skeleton: proves the browser<->proxy WebSocket pipe and stands up the
deterministic record (witness log) with a /verify contract stub. The Gemini Live
relay drops into the /ws handler's frame dispatch next.
"""

from __future__ import annotations

import asyncio
import contextlib
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .protocol import decode
from .session import Session, SessionRegistry
from .session_config import FORM_MAP

app = FastAPI(title="Sahayak Proxy", version="0.1.0")
registry = SessionRegistry()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "sessions": len(registry)}


@app.post("/verify")
async def verify() -> JSONResponse:
    """Discrete verify pass — deterministic canned shape for now.

    Verify is intentionally an HTTP call OFF the Live socket: a repeatable
    adjudication, not part of the probabilistic stream. This locks the frontend
    contract today; the real high-res-frame sweep fills in the verdicts later.
    """
    checklist = [
        {"field": f["id"], "label": f["label"], "verdict": "unchecked", "reason": ""}
        for f in FORM_MAP
    ]
    return JSONResponse({"checklist": checklist, "stub": True})


async def _writer(session: Session) -> None:
    """The single task allowed to send on this connection's socket."""
    while True:
        msg = await session.outbound.get()
        await session.ws.send_json(msg)


def _guard(task: asyncio.Task) -> None:
    """Surface exceptions from fire-and-forget tasks instead of swallowing them."""

    def _done(t: asyncio.Task) -> None:
        if not t.cancelled():
            exc = t.exception()
            if exc is not None:  # pragma: no cover - defensive
                import logging

                logging.getLogger("sahayak").exception("background task failed", exc_info=exc)

    task.add_done_callback(_done)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    session = registry.create()
    session.ws = websocket  # attach live socket to the session
    session.log.append("session_start", {"session_id": session.id})

    writer = asyncio.create_task(_writer(session))
    _guard(writer)

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            frame = decode(message)

            if frame.kind == "binary":
                # Media path seam — real audio/video relay lands here. Echo
                # skeleton has nothing to do with binary yet.
                continue
            if frame.error:
                session.outbound.put_nowait({"type": "error", "detail": frame.error})
                continue

            data = frame.data or {}
            if data.get("type") == "ping":
                session.outbound.put_nowait({"type": "pong", "payload": data.get("payload")})
            else:
                session.outbound.put_nowait({"type": "echo", "payload": data})
    except WebSocketDisconnect:
        pass
    finally:
        # One teardown path: cancel the writer, then write session_end exactly
        # once — identical on clean disconnect, exception, or cancellation.
        writer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await writer
        try:
            session.log.append("session_end", {"session_id": session.id})
        except OSError:  # a write failure at teardown must not mask the disconnect
            pass
        session.state = "closed"
        registry.remove(session.id)


# Serve the built frontend if present (after `npm run build`). Mounted last so it
# never shadows /health, /verify, or /ws.
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="static")
