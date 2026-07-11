"""Card-read go/no-go — the highest-risk assumption in v2.

Captures one frame from the DroidCam device (or reads an image you pass) and asks
the Gemini Live session to read the printed document. A clean read = the whole
document-sourced-field mechanism is green. This is the plan's H0 test.

Usage:
    export GOOGLE_API_KEY=...              # or in .env
    python scripts/read_card_test.py                 # capture from the camera
    python scripts/read_card_test.py path/to/card.jpg  # use an existing image
Env:
    SAHAYAK_CAM_DEVICE   default /dev/video0
    SAHAYAK_CAM_SIZE     default 1920x1080
    SAHAYAK_LIVE_MODEL   override the Live model id
"""

import asyncio
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

from app.env import load_dotenv  # noqa: E402
from app.session_config import LIVE_MODEL  # noqa: E402

SCRATCH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PROMPT = (
    "You are reading an official identity document held up to a camera. "
    "Reply in plain text with: the person's FULL NAME exactly as printed, and any "
    "ID / card NUMBER and DATE OF BIRTH you can see. If the image is too dark or "
    "blurry to read, say exactly 'CANNOT READ' and why."
)


def capture_frame() -> bytes:
    device = os.environ.get("SAHAYAK_CAM_DEVICE", "/dev/video0")
    size = os.environ.get("SAHAYAK_CAM_SIZE", "1920x1080")
    os.makedirs(SCRATCH, exist_ok=True)
    out = os.path.join(SCRATCH, "card_capture.jpg")
    # -ss 1 drops the first second so auto-exposure settles.
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "v4l2",
        "-input_format", "mjpeg", "-video_size", size, "-ss", "1",
        "-i", device, "-frames:v", "1", "-q:v", "2", out, "-y",
    ]
    subprocess.run(cmd, check=True)
    print(f"captured {size} frame -> {out} ({os.path.getsize(out)} bytes)")
    with open(out, "rb") as f:
        return f.read()


async def main() -> int:
    load_dotenv()
    if not os.environ.get("GOOGLE_API_KEY"):
        print("FAIL: GOOGLE_API_KEY not set")
        return 2

    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            jpeg = f.read()
        print(f"using image {sys.argv[1]} ({len(jpeg)} bytes)")
    else:
        jpeg = capture_frame()

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    # This Live model is AUDIO-only; read its spoken answer via output transcription.
    config = {
        "response_modalities": ["AUDIO"],
        "output_audio_transcription": {},
        "system_instruction": "You read printed documents precisely and never invent text.",
    }
    print(f"reading with {LIVE_MODEL} ...")
    async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
        # Package the frame and the question in ONE turn so the model reads THIS
        # image. (Streaming realtime video is how the live app feeds frames; for a
        # one-shot read, inline content is the reliable path.)
        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[
                    types.Part(inline_data=types.Blob(data=jpeg, mime_type="image/jpeg")),
                    types.Part(text=PROMPT),
                ],
            ),
            turn_complete=True,
        )
        out = []
        async for msg in session.receive():
            sc = getattr(msg, "server_content", None)
            if sc and getattr(sc, "output_transcription", None) and sc.output_transcription.text:
                out.append(sc.output_transcription.text)
            if sc and getattr(sc, "turn_complete", False):
                break
        answer = "".join(out).strip()
        print("\n--- MODEL READ ---")
        print(answer or "(no text returned)")
        print("------------------")
        return 0 if answer and "CANNOT READ" not in answer.upper() else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
