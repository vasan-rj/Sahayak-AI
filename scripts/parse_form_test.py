"""Headless smoke-test for the upload-a-blank-form → field-map parser.

Runs app.form_parser.parse_blank_form on an image and prints the generated
field-map. Confirms the vision model + response schema before the admin UI
depends on it.

Usage:
    export GOOGLE_API_KEY=...             # or in .env
    export SAHAYAK_PARSE_MODEL=...        # optional model override
    python scripts/parse_form_test.py path/to/blank_form.jpg
    python scripts/parse_form_test.py     # defaults to data/card_capture.jpg
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.env import load_dotenv  # noqa: E402
from app.form_parser import PARSE_MODEL, parse_blank_form  # noqa: E402

DEFAULT_IMG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "card_capture.jpg"
)


def main() -> int:
    load_dotenv()
    if not os.environ.get("GOOGLE_API_KEY"):
        print("FAIL: GOOGLE_API_KEY not set")
        return 2
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMG
    if not os.path.exists(path):
        print(f"FAIL: image not found: {path}")
        return 2
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        data = f.read()
    print(f"parsing {path} ({len(data)} bytes) with {PARSE_MODEL} ...")
    try:
        draft = parse_blank_form(data, mime)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    print("\n--- GENERATED FIELD-MAP ---")
    print(json.dumps(draft, ensure_ascii=False, indent=2))
    print("---------------------------")
    print(f"PASS ({len(draft['fields'])} fields)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
