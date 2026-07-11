"""Headless Live smoke-test — no mic, no camera.

Validates that GOOGLE_API_KEY + LIVE_MODEL + the v2 session config actually open a
Gemini Live session and that the tool schema is accepted. Sends one text turn and
prints the agent's output transcription. Audio/video are venue-tested separately.

Usage:
    export GOOGLE_API_KEY=...            # required
    export SAHAYAK_LIVE_MODEL=...        # optional, to try a specific model id
    python scripts/smoke_live.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai  # noqa: E402

from app.session_config import LIVE_MODEL, live_config  # noqa: E402

PROMPT = "Say a short one-line greeting in Hindi to start filling a form."


def _load_dotenv() -> None:
    """Minimal .env loader (no extra dependency) so the key can live in a
    gitignored .env instead of the shell."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


async def main() -> int:
    _load_dotenv()
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("FAIL: GOOGLE_API_KEY not set")
        return 2

    client = genai.Client(api_key=key)
    print(f"connecting to model: {LIVE_MODEL} ...")
    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=live_config()) as session:
            print("connected. tool schema accepted. sending one text turn ...")
            await session.send_client_content(
                turns={"role": "user", "parts": [{"text": PROMPT}]},
                turn_complete=True,
            )
            got_audio = False
            transcript = []
            async for msg in session.receive():
                sc = getattr(msg, "server_content", None)
                if sc and getattr(sc, "output_transcription", None) and sc.output_transcription.text:
                    transcript.append(sc.output_transcription.text)
                if getattr(msg, "data", None):
                    got_audio = True
                if sc and getattr(sc, "turn_complete", False):
                    break
            print("agent transcript:", "".join(transcript) or "(none)")
            print("received audio bytes:", got_audio)
            print("PASS")
            return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}")
        print("If this is a model-not-found / permission error, set SAHAYAK_LIVE_MODEL")
        print("to a Live model your account can access and retry.")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
