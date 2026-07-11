"""Sahayak proxy — FastAPI app (v2, voice-first).

Sits between the browser and a Gemini Live session. The browser streams mic audio
(binary) and camera frames (binary, ~1 fps); the proxy relays them to the Live
session, maps the session's output back to captions + agent audio, and turns
confirmed-field tool calls into a live-filling form + an append-only capture log.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import os

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from .admin import router as admin_router
from .env import load_dotenv
from .live_session import LiveRelay
from .markers import parse_and_strip
from .protocol import (
    audio_event,
    caption_event,
    decode,
    field_update_event,
    form_complete_event,
    form_snapshot_event,
)
from .session import Session, SessionRegistry
from .session_config import LIVE_MODEL, field_source, live_config
from .template_store import get_store
from .vad import chunk_ms

log = logging.getLogger("sahayak")

# Load .env at import so `uvicorn app.main:app` has GOOGLE_API_KEY without the
# caller exporting it first. An exported shell var still wins (setdefault).
load_dotenv()

# Inbound binary media tags (first byte of each binary WS frame from the browser).
MEDIA_AUDIO = 0x01  # 16 kHz PCM16 mic chunk
MEDIA_VIDEO = 0x02  # JPEG camera frame

# The Live model stays silent until it gets input, so kick the session on connect:
# the agent greets and asks for the first field before the user says anything.
OPENING_TRIGGER = "Begin now. Greet the user in their language and ask for the first field."

app = FastAPI(title="Sahayak Proxy", version="0.2.0")
app.include_router(admin_router)
registry = SessionRegistry()
store = get_store()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "sessions": len(registry), "model": LIVE_MODEL}


@app.get("/template")
async def template(id: str | None = None) -> dict:
    """The blank form the UI renders and fills. Defaults to the active template;
    ``?id=<template_id>`` fetches a specific one."""
    if id:
        try:
            return store.get(id)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown template")
    return store.get_active()


def _select_template(websocket: WebSocket) -> dict:
    """Applicant fills the active template, or ``/ws?template=<id>`` for a specific one."""
    tid = websocket.query_params.get("template")
    if tid:
        try:
            return store.get(tid)
        except KeyError:
            pass
    return store.get_active()


def _make_client():
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        return None
    from google import genai

    return genai.Client(api_key=key)


@contextlib.asynccontextmanager
async def _default_relay_cm(session: Session, callbacks: dict):
    """Open a real Gemini Live session and yield a LiveRelay over it.

    Overridable at module level (``app.main.relay_cm = ...``) so tests inject a
    mock session with a scripted receive() stream and never touch the network.
    """
    client = _make_client()
    if client is None:
        raise RuntimeError("GOOGLE_API_KEY not set")
    config = live_config(session.form.template)  # per-template instruction + tools
    async with client.aio.live.connect(model=LIVE_MODEL, config=config) as gsession:
        yield LiveRelay(gsession, **callbacks)


relay_cm = _default_relay_cm


async def _writer(session: Session) -> None:
    """The single task allowed to send on this connection's socket."""
    while True:
        msg = await session.outbound.get()
        await session.ws.send_json(msg)


def _guard(task: asyncio.Task) -> None:
    def _done(t: asyncio.Task) -> None:
        if not t.cancelled() and t.exception() is not None:  # pragma: no cover
            log.exception("background task failed", exc_info=t.exception())

    task.add_done_callback(_done)


def _make_callbacks(session: Session) -> dict:
    """Closures that turn Live-session events into browser events + capture log."""

    def on_field(field_id: str, value: str, source: str) -> bool:
        try:
            field = session.form.apply(field_id, value, source)
        except (KeyError, ValueError):
            log.warning("rejected field capture: %s=%r (%s)", field_id, value, source)
            return False
        session.log.append(
            "field_captured", {"field": field_id, "value": value, "source": source}
        )
        session.outbound.put_nowait(field_update_event(field))
        session.outbound.put_nowait(form_snapshot_event(session.form.snapshot()))
        return True

    def on_complete() -> None:
        session.log.append("form_complete", {"template_id": session.form.template["template_id"]})
        session.outbound.put_nowait(form_complete_event())
        session.outbound.put_nowait(form_snapshot_event(session.form.snapshot()))

    src_map = field_source(session.form.template)

    def on_caption(side: str, text: str, lang: str | None) -> None:
        # Primary capture is the tool path; here we also scrub any stray markers
        # out of the caption and honor them as a fallback.
        fields, complete, clean = parse_and_strip(text)
        for fid, val in fields:
            on_field(fid, val, src_map.get(fid, "voice"))
        if complete:
            on_complete()
        if clean:
            session.outbound.put_nowait(caption_event(side, clean, lang))

    def on_audio(pcm: bytes) -> None:
        session.outbound.put_nowait(audio_event(base64.b64encode(pcm).decode("ascii")))

    def on_interrupted() -> None:
        session.outbound.put_nowait({"type": "interrupted"})

    return {
        "on_field": on_field,
        "on_complete": on_complete,
        "on_caption": on_caption,
        "on_audio": on_audio,
        "on_interrupted": on_interrupted,
    }


async def _pump_browser_to_relay(session: Session, relay: LiveRelay) -> None:
    """Read browser frames until disconnect; route media to the Live session."""
    ws = session.ws
    while True:
        message = await ws.receive()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000))
        frame = decode(message)
        if frame.kind == "binary" and frame.raw:
            tag, payload = frame.raw[0], frame.raw[1:]
            if tag == MEDIA_AUDIO:
                # Proxy-side VAD: bracket each utterance with activity_start/end
                # (automatic VAD is off — it doesn't segment this stream).
                session.audio_bytes_in += len(payload)
                ev = session.vad.process(payload, chunk_ms(payload))
                if ev == "start":
                    await relay.activity_start()
                if session.vad.speaking or ev == "end":
                    await relay.send_audio(payload)
                if ev == "end":
                    await relay.activity_end()
            elif tag == MEDIA_VIDEO:
                await relay.send_frame(payload)
            # unknown tag: ignore
        elif frame.error:
            session.outbound.put_nowait({"type": "error", "detail": frame.error})
        # text control frames (e.g. {"type":"start"}) need no action in the skeleton


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    session = registry.create(template=_select_template(websocket))
    session.ws = websocket
    session.log.append("session_start", {"session_id": session.id})
    session.outbound.put_nowait(form_snapshot_event(session.form.snapshot()))

    writer = asyncio.create_task(_writer(session))
    _guard(writer)
    recv_task: asyncio.Task | None = None

    try:
        async with relay_cm(session, _make_callbacks(session)) as relay:
            session.relay = relay
            recv_task = asyncio.create_task(relay.receive_loop())
            _guard(recv_task)
            await relay.send_text(OPENING_TRIGGER)  # make the agent greet first
            await _pump_browser_to_relay(session, relay)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - surface the failure to the client, don't crash
        log.exception("live session error", exc_info=exc)
        with contextlib.suppress(Exception):
            session.outbound.put_nowait({"type": "error", "detail": "live_error"})
    finally:
        for task in (recv_task, writer):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        if session.relay is not None:
            await session.relay.close()
        try:
            session.log.append("session_end", {"session_id": session.id})
        except OSError:
            pass
        # Diagnostic: if this is ~0 the browser never streamed mic audio (frontend
        # capture problem), not a VAD/turn-taking problem.
        log.info("session %s ended: mic bytes in=%d", session.id, session.audio_bytes_in)
        session.state = "closed"
        registry.remove(session.id)


# Serve the built frontend if present (mounted last so it never shadows the API).
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_FRONTEND_DIST):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="static")
