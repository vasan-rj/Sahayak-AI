"""Energy-based voice activity detection for the proxy.

gemini-3.1-flash-live-preview's automatic activity detection does not segment our
streamed mic audio (verified: streaming real speech under auto-VAD yields no turn).
So the proxy runs auto-VAD OFF and marks turns itself: this watches the RMS energy
of each incoming PCM16 chunk and emits "start" when the user begins speaking and
"end" after a short trailing silence. The /ws pump turns those into the Live
session's ``activity_start`` / ``activity_end`` signals.

Hands-free by design — the user is holding a document to the camera, not a button.
"""

from __future__ import annotations

import audioop  # stdlib (Python 3.10); RMS of 16-bit samples
import os


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class EnergyVAD:
    def __init__(
        self,
        start_rms: int | None = None,
        end_rms: int | None = None,
        silence_ms: int | None = None,
    ):
        # start > end gives hysteresis: needs a clear onset to start, tolerates
        # dips before declaring the utterance over.
        self.start_rms = start_rms if start_rms is not None else _int_env("SAHAYAK_VAD_START_RMS", 700)
        self.end_rms = end_rms if end_rms is not None else _int_env("SAHAYAK_VAD_END_RMS", 400)
        self.silence_ms = silence_ms if silence_ms is not None else _int_env("SAHAYAK_VAD_SILENCE_MS", 800)
        self.speaking = False
        self._silence = 0.0

    def process(self, pcm16: bytes, ms: float) -> str | None:
        """Feed one PCM16 mono chunk of duration ``ms``. Returns "start" on the
        chunk where speech begins, "end" once silence has lasted silence_ms, else None."""
        if not pcm16:
            return None
        rms = audioop.rms(pcm16, 2)
        if not self.speaking:
            if rms >= self.start_rms:
                self.speaking = True
                self._silence = 0.0
                return "start"
            return None
        # speaking
        if rms < self.end_rms:
            self._silence += ms
        else:
            self._silence = 0.0
        if self._silence >= self.silence_ms:
            self.speaking = False
            self._silence = 0.0
            return "end"
        return None


def chunk_ms(pcm16: bytes, rate: int = 16000) -> float:
    """Duration of a mono PCM16 chunk in milliseconds."""
    return (len(pcm16) / 2) / rate * 1000.0
