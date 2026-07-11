"""Test doubles for the Gemini Live session.

Duck-typed objects with just the attributes LiveRelay reads (it uses getattr
throughout), so tests never import heavy SDK message types or touch the network.
"""

from __future__ import annotations

from types import SimpleNamespace as NS


def caption_msg(user: str | None = None, agent: str | None = None, interrupted: bool = False):
    sc = NS(
        input_transcription=NS(text=user, language_code="hi") if user else None,
        output_transcription=NS(text=agent, language_code="hi") if agent else None,
        interrupted=interrupted,
        turn_complete=False,
    )
    return NS(server_content=sc, data=None, tool_call=None)


def audio_msg(pcm: bytes):
    return NS(server_content=None, data=pcm, tool_call=None)


def tool_msg(*calls: tuple[str, dict]):
    fcs = [NS(id=f"call{i}", name=name, args=args) for i, (name, args) in enumerate(calls)]
    return NS(server_content=None, data=None, tool_call=NS(function_calls=fcs))


class MockLiveSession:
    """A fake AsyncSession. `turns` is a list of message-lists; each receive()
    call consumes one turn, matching google-genai's one-turn-per-receive()."""

    def __init__(self, turns: list[list]):
        self._turns = list(turns)
        self.audio_sent: list[bytes] = []
        self.video_sent: list[bytes] = []
        self.tool_responses: list = []
        self.closed = False

    async def send_realtime_input(self, *, audio=None, video=None, **kw):
        if audio is not None:
            self.audio_sent.append(audio.data if hasattr(audio, "data") else audio)
        if video is not None:
            self.video_sent.append(video.data if hasattr(video, "data") else video)

    async def receive(self):
        if self._turns:
            for m in self._turns.pop(0):
                yield m
        # empty when no turns left -> LiveRelay.receive_loop breaks

    async def send_tool_response(self, *, function_responses):
        self.tool_responses.append(function_responses)

    async def close(self):
        self.closed = True
