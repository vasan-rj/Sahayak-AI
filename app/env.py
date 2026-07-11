"""Minimal .env loader (no external dependency).

Loads KEY=VALUE lines from a .env at the repo root into os.environ so that
`uvicorn app.main:app` picks up GOOGLE_API_KEY / SAHAYAK_* without the caller
having to export them first. Uses setdefault, so a variable already exported in
the shell always wins over the file.
"""

from __future__ import annotations

import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_dotenv(path: str | None = None) -> dict[str, str]:
    """Load .env into os.environ (without overriding existing vars). Returns the
    parsed key/value pairs. A missing file is a no-op."""
    path = path or os.path.join(_REPO_ROOT, ".env")
    loaded: dict[str, str] = {}
    if not os.path.exists(path):
        return loaded
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            loaded[key] = val
            os.environ.setdefault(key, val)
    return loaded
