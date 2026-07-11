# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Sahayak** — a solo build for the Google DeepMind Bangalore Hackathon (2026-07-11), Problem Statement 1 (Gemini Live API + Live Translate). A real-time multimodal agent: a phone camera watches a paper form on the table, the agent explains it in the user's spoken language (Hindi/Tamil), and **interrupts the moment a field is filled wrong** — before a clerk would reject it.

As of this file's writing the project is **pre-code**: only planning docs and this repo exist. Build the actual app here in `Sahayak-AI/` (the git repo root, where this file lives).

## Layout

- `../context/` — the spec set (a sibling dir, NOT tracked in this repo). Read these before writing code; they ARE the source of truth.
  - `PRD.md` — acceptance criteria (AC-1…AC-6). **The demo IS the spec.**
  - `ARCHITECTURE.md` — topology, session config design, witness-log design, fallback tiers.
  - `FORM_PACK_SPEC.md` — the mock form's field map. This exact map goes into `session_config.py`.
  - `IMPLEMENTATION_PLAN.md` — hour-by-hour build order + kill-switches.
  - `DEMO_SCRIPT.md`, `PITCH_DECK_OUTLINE.md` — stage choreography.
- `Sahayak-AI/` (this repo) — all code lives here.

## Planned commands (from ../context/README.md — no code exists yet)

```bash
export GOOGLE_API_KEY=...
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn app.main:app --port 8000   # serves UI + WS at http://localhost:8000
```

Runtime rig: phone-as-webcam (DroidCam/USB, USB preferred over wifi) feeds a virtual cam; one laptop, one phone, one printed form. No database, no queue, no GPU.

## Architecture (the big picture)

Three tiers: **browser (React) ↔ FastAPI proxy ↔ Gemini Live API**. The proxy exists so the API key stays server-side, every session event flows through one place, reconnect/resume lives in Python, and the `/verify` pass can make a separate model call without touching the client.

Guiding principle: **perception is probabilistic; the record is deterministic.** The Live session sees/hears/judges/interrupts. The proxy logs every event to an append-only, hash-chained witness log and owns the `/verify` sweep. Nothing about the user's paperwork rides on model vibes alone.

Data flow:
- Browser → proxy (WS): mic audio (PCM), video frames (JPEG, ~1 fps, ~768px during filling).
- Proxy → Live API: forwards audio both ways, samples/forwards frames.
- Proxy → browser (WS): agent audio, live English captions (both sides), events, verify results.
- `POST /verify`: proxy sends 2–3 full-res frames + a structured field-by-field checklist request; parses leniently; renders ✓/✕/blank; appends verdicts to the witness log.

**`session_config.py` is the most important file in the repo.** It carries: the Live model + response modality AUDIO + input/output transcription ENABLED (transcription = captions AND witness log, one stream two uses); VAD/barge-in config (tune at venue); the frame policy; and the system instruction that engineers the proactive interruption (AC-2) — including the `FORM MAP` from `FORM_PACK_SPEC.md` and the explicit "INTERRUPT IMMEDIATELY, unprompted, when writing contradicts a field's expected content" directive.

Witness log: append-only JSONL on disk, each entry hash-chaining the previous. The model prefixes machine-parseable markers (e.g. `[[CATCH:father_name]]`) in its transcript; the proxy parses them into log entries and strips them from captions. Server owns it, so it is refresh-safe.

## Non-obvious constraints & rules

- **AC-driven build.** No feature starts while an acceptance criterion is red. Every hour, ask which AC a task turns green.
- **The interruption beat (AC-2) is never cut. It IS the project.** Everything else exists to frame it. If spontaneous interruption isn't ≥8/10 reliable via prompt engineering, fall back to the **Tier-2 watchdog** (proxy sends a silent text turn "inspect the latest frame against the form map; correct now if wrong" every ~5s) — externally identical, disclosed honestly if asked. Tier-3 fallback: push-to-talk half-duplex + on-demand frame checks.
- **The honest latency claim is "within a second or two," not mid-stroke** — frame sampling is ~1 fps. Do not overclaim in code comments, UI copy, or docs.
- **The form is a mock prop** (fictional "Jan Kalyan Pension Yojana", JKP-2A). Disclose freely. The agent knows the demo form's fields via the system-prompt field map — this is not universal OCR form parsing, and that boundary is in scope by design.
- **Positioning discipline:** Sahayak is a task companion for live paperwork, NOT an education chatbot/tutor. It witnesses and intervenes in real work; it never teaches curriculum.
- **Captions always English** regardless of spoken language, so judges follow. Language switch (Hindi↔Tamil) is pure user behavior — no client toggle; the Live model follows the spoken language.
- **Cut order if behind:** tone beat (AC-5) → Tamil switch (keep Hindi + captions) → field-tracker UI (keep witness log). Never cut the interruption.
- Demo hygiene lives in code too: a `demo-reset` script (restart session, clear witness log, camera-focus check, one warm caption round-trip), captions ≥20px, hotspot fallback network.
