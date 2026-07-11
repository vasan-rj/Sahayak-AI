"""LiveRelay — the bridge to the Gemini Live API session.

Wraps a connected google-genai ``AsyncSession`` and maps its message stream onto
plain callbacks the proxy uses to drive the browser and the capture log:

- output audio         -> on_audio(pcm_bytes)
- input transcription  -> on_caption("user", text, lang)     (user speech)
- output transcription -> on_caption("agent", text, lang)    (agent speech)
- record_field tool    -> on_field(field_id, value, source)  (structured capture)
- form_complete tool   -> on_complete()
- interrupted (barge-in)-> on_interrupted()

The connected session is INJECTED, so tests drive a scripted mock stream with no
network. ``main.py`` owns the real ``client.aio.live.connect(...)`` context and
passes the session in.

Note: google-genai ``receive()`` yields one model turn then stops (it breaks after
``turn_complete``), so a continuous session must call ``receive()`` repeatedly —
``receive_loop`` does exactly that until the socket closes or ``close()`` is called.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Awaitable, Callable, Optional

from google.genai import types

AUDIO_IN_MIME = "audio/pcm;rate=16000"  # Live API expects 16 kHz PCM16 mic input
FRAME_MIME = "image/jpeg"


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class LiveRelay:
    def __init__(
        self,
        session: Any,
        *,
        on_audio: Optional[Callable[[bytes], Any]] = None,
        on_caption: Optional[Callable[[str, str, Optional[str]], Any]] = None,
        on_field: Optional[Callable[[str, str, str], Awaitable[bool] | bool]] = None,
        on_complete: Optional[Callable[[], Any]] = None,
        on_interrupted: Optional[Callable[[], Any]] = None,
    ):
        self._session = session
        self._on_audio = on_audio
        self._on_caption = on_caption
        self._on_field = on_field
        self._on_complete = on_complete
        self._on_interrupted = on_interrupted
        self._closed = False

    # --- browser -> Gemini ----------------------------------------------------
    async def send_audio(self, pcm: bytes) -> None:
        await self._session.send_realtime_input(
            audio=types.Blob(data=pcm, mime_type=AUDIO_IN_MIME)
        )

    async def send_frame(self, jpeg: bytes) -> None:
        await self._session.send_realtime_input(
            video=types.Blob(data=jpeg, mime_type=FRAME_MIME)
        )

    # --- Gemini -> proxy ------------------------------------------------------
    async def receive_loop(self) -> None:
        while not self._closed:
            saw_message = False
            async for msg in self._session.receive():
                saw_message = True
                await self._handle(msg)
            if not saw_message:
                break  # receive() yielded nothing -> the session ended

    async def _handle(self, msg: Any) -> None:
        sc = getattr(msg, "server_content", None)
        if sc is not None:
            it = getattr(sc, "input_transcription", None)
            if it and getattr(it, "text", None) and self._on_caption:
                await _maybe_await(
                    self._on_caption("user", it.text, getattr(it, "language_code", None))
                )
            ot = getattr(sc, "output_transcription", None)
            if ot and getattr(ot, "text", None) and self._on_caption:
                await _maybe_await(
                    self._on_caption("agent", ot.text, getattr(ot, "language_code", None))
                )
            if getattr(sc, "interrupted", False) and self._on_interrupted:
                await _maybe_await(self._on_interrupted())

        data = getattr(msg, "data", None)
        if data and self._on_audio:
            await _maybe_await(self._on_audio(data))

        tc = getattr(msg, "tool_call", None)
        if tc and getattr(tc, "function_calls", None):
            await self._handle_tool_calls(tc.function_calls)

    async def _handle_tool_calls(self, function_calls: list) -> None:
        responses = []
        for fc in function_calls:
            args = fc.args or {}
            if fc.name == "record_field" and self._on_field:
                ok = await _maybe_await(
                    self._on_field(
                        args.get("field_id"), args.get("value"), args.get("source")
                    )
                )
                resp = {"status": "recorded" if ok else "rejected"}
            elif fc.name == "form_complete":
                if self._on_complete:
                    await _maybe_await(self._on_complete())
                resp = {"status": "ok"}
            else:
                resp = {"status": "unknown_tool"}
            responses.append(
                types.FunctionResponse(id=fc.id, name=fc.name, response=resp)
            )
        if responses:
            await self._session.send_tool_response(function_responses=responses)

    async def close(self) -> None:
        self._closed = True
        try:
            await self._session.close()
        except Exception:  # noqa: BLE001 - closing a dead socket must not raise
            pass
