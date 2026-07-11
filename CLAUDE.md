# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Sahayak** — a solo build for the Google DeepMind Bangalore Hackathon (2026-07-11), Problem Statement 1 (Gemini Live API + Live Translate).

**The project pivoted mid-hackathon to v2 (voice-first).** The active spec is `../context/new/`; the older `../context/` docs describe the abandoned v1 (pen-watching) concept — do not build from them.

**v2:** voice-first form completion for people who can't read/write. A phone camera + a Gemini Live session let the user complete an official form by **speaking and showing their documents** (Aadhaar/PAN). The agent reads the form aloud in the user's language (Hindi/Tamil), captures each value by voice or by reading a document via camera, **confirms every value back by voice**, and the digital form fills itself live. A printable finished form is the finale.

The code exists and works: deterministic parts are tested here; the mic/camera/Live path is venue-verified.

## Layout

- `../context/new/` — the **active** v2 spec (sibling dir, not tracked): `README.md`, `IMPLEMENTATION_PLAN.md` (5-hour, floor-first), `DEMO_SCRIPT.md`, `TEMPLATE_AND_PROMPT.md` (the field-map + system instruction).
- `../context/` — superseded v1 docs. Ignore unless doing historical archaeology.
- `Sahayak-AI/` (this repo) — all code. See `README.md` here for the file map and run/test commands.

## Commands

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
export GOOGLE_API_KEY=...                 # required for the Live session
cd frontend && npm install && npm run build && cd ..
uvicorn app.main:app --port 8000          # serves UI + WS at http://localhost:8000

pytest                                    # backend deterministic tests
cd frontend && npm test                   # frontend tests
python scripts/smoke_live.py              # headless Live connect + one text turn
```

Reloading backend: `uvicorn app.main:app --reload --reload-dir app` — keeps the reloader off the `data/` capture-log tree so a log write never drops a live session. Runtime rig: phone-as-webcam (DroidCam over USB), one laptop.

## Architecture (the big picture)

Three tiers: **browser (React) ↔ FastAPI proxy ↔ Gemini Live API**. The proxy keeps the API key server-side, funnels every session event through one place, and owns the deterministic record.

Guiding principle: **perception is probabilistic; the record is deterministic.** The Live session sees/hears/speaks; the proxy owns an append-only, hash-chained **capture log** — one `field_captured` entry per confirmed value, with its source (document|voice).

Key files (details in `README.md`):
- **`app/session_config.py`** is the most important file: the hardcoded `TEMPLATE` (`jkp_pension_2a`, 3 fields), the voice-first `SYSTEM_INSTRUCTION`, the `record_field`/`form_complete` tool declarations, `LIVE_MODEL` (env `SAHAYAK_LIVE_MODEL`), and `live_config()` (response modality AUDIO + input/output audio transcription + tools).
- **`app/live_session.py`** `LiveRelay` — wraps the google-genai Live session; injectable for zero-network mock tests.
- **`app/form_state.py`**, **`app/markers.py`**, **`app/witness_log.py`** — the deterministic core.

Data flow: browser sends mic PCM16 16 kHz (binary, tag `0x01`) and camera JPEG ~1 fps (binary, tag `0x02`); proxy relays to the Live session; agent audio + captions + live form snapshots flow back. Capture happens via **Live tool-calling** (`record_field`) — the marker parser is a fallback only.

## Non-obvious constraints & rules

- **google-genai must be 2.x** (pinned `==2.11.0`). v1's `0.8.0` lacked transcription, `send_realtime_input`, and VAD config — the whole v2 mechanism depends on 2.x. Do not downgrade.
- **The core loop (ask → see doc / hear voice → confirm → fill) is never cut.** It IS the project. If behind: cut the voice-sourced field + tone beat → demo pure document-to-form capture. Language switch + tone frame the loop; they are not the loop.
- **Capture is structured (tool calls), not scraped from transcribed speech.** Parsing `[[FIELD:...]]` brackets out of TTS is fragile; `record_field` is the primary path.
- **Confirm before advance.** Never mark a field confirmed without the user's spoken approval — that confirmation is the trust model. The model is instructed to read documents (never ask the user to spell) and never invent a value it can't see/hear.
- **One hardcoded template.** No admin-upload UI — pitched as roadmap. Document reading (printed cards) is far more reliable than handwriting; that reliability is why v2 is lower-risk than v1.
- **Captions read from ~1m** (≥20px). Language switch (Hindi↔Tamil) is pure user behavior — no toggle; the Live model follows the spoken language.
- **Honest boundary:** the capture log is tamper-evident against edits and mid-file deletions, NOT clean tail-truncation. For a fully illiterate user a human submit/thumbprint step remains. Don't overclaim.
- **Positioning discipline:** a task companion completing real paperwork, NOT an education chatbot.
