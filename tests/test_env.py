"""Regression test for the .env loader.

Bug: `uvicorn app.main:app` raised RuntimeError('GOOGLE_API_KEY not set') because
the app never loaded .env (only the scripts did). These tests pin that the loader
reads a .env file and, critically, does NOT override an already-exported variable.
"""

import os

from app.env import load_dotenv


def test_loads_keys_from_env_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('GOOGLE_API_KEY=abc123\nSAHAYAK_LIVE_MODEL="some-model"\n# comment\n\n')
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("SAHAYAK_LIVE_MODEL", raising=False)

    loaded = load_dotenv(str(env))

    assert loaded["GOOGLE_API_KEY"] == "abc123"
    assert loaded["SAHAYAK_LIVE_MODEL"] == "some-model"  # quotes stripped
    assert os.environ["GOOGLE_API_KEY"] == "abc123"


def test_does_not_override_exported_var(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GOOGLE_API_KEY=from_file\n")
    monkeypatch.setenv("GOOGLE_API_KEY", "from_shell")

    load_dotenv(str(env))

    assert os.environ["GOOGLE_API_KEY"] == "from_shell"  # exported wins


def test_missing_file_is_noop(tmp_path):
    assert load_dotenv(str(tmp_path / "nope.env")) == {}
