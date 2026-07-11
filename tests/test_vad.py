"""Proxy-side VAD: energy detection + turn bracketing.

Auto-VAD doesn't segment the mic stream for this Live model, so the proxy detects
speech and sends activity_start/end itself. These tests pin that behavior without
any network.
"""

import asyncio
import struct

from app.live_session import LiveRelay
from app.vad import EnergyVAD, chunk_ms
from tests.mocks import MockLiveSession

RATE = 16000


def _pcm(amp: int, ms: int = 100) -> bytes:
    n = int(RATE * ms / 1000)
    return struct.pack(f"<{n}h", *([amp] * n))


LOUD = _pcm(8000)
QUIET = _pcm(0)


def test_chunk_ms():
    assert abs(chunk_ms(b"\x00" * 3200) - 100.0) < 0.1  # 1600 samples @16k = 100ms


def test_start_on_speech_then_end_after_silence():
    v = EnergyVAD(start_rms=700, end_rms=400, silence_ms=300)
    events = []
    for _ in range(3):
        events.append(v.process(LOUD, 100))
    for _ in range(4):
        events.append(v.process(QUIET, 100))
    assert events[0] == "start"
    assert events.count("start") == 1
    assert events.count("end") == 1
    assert v.speaking is False


def test_subthreshold_never_starts():
    v = EnergyVAD(start_rms=700, end_rms=400, silence_ms=300)
    low = _pcm(100)  # rms ~100, below start
    assert all(v.process(low, 100) is None for _ in range(6))
    assert v.speaking is False


def test_brief_dip_does_not_end_turn():
    v = EnergyVAD(start_rms=700, end_rms=400, silence_ms=300)
    assert v.process(LOUD, 100) == "start"
    assert v.process(QUIET, 100) is None  # 100ms silence < 300ms window
    assert v.process(LOUD, 100) is None  # speech resumes, silence counter resets
    assert v.speaking is True


def test_pump_logic_brackets_audio_with_activity_markers():
    """Mirror the /ws pump: VAD drives activity_start … audio … activity_end."""
    mock = MockLiveSession([])
    relay = LiveRelay(mock)
    vad = EnergyVAD(start_rms=700, end_rms=400, silence_ms=300)

    async def run():
        for chunk in [LOUD, LOUD, QUIET, QUIET, QUIET, QUIET]:
            ev = vad.process(chunk, chunk_ms(chunk))
            if ev == "start":
                await relay.activity_start()
            if vad.speaking or ev == "end":
                await relay.send_audio(chunk)
            if ev == "end":
                await relay.activity_end()

    asyncio.run(run())
    assert mock.activity == ["start", "end"]
    assert len(mock.audio_sent) >= 2  # speech chunks forwarded to the session
