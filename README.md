# Sahayak-AI

**Voice-first form completion for people the digital economy can't reach.** A person
who can't read or write completes an official form by speaking and showing their
documents to a camera — and watches it fill itself. Built for the Google DeepMind
Bangalore Hackathon (PS1 — Live API / Live Translate).

The agent reads the form aloud in the user's language (Hindi/Tamil), captures each
value by **voice** or by **reading the user's documents** (Aadhaar/PAN) through the
camera, **confirms every value back** ("मैंने लिखा: राजेश कुमार — सही है?"), and the
digital form populates live. Design thesis carried from v1: **the perception is
probabilistic; the record is deterministic** — a hash-chained capture log records
every confirmed value with its source (document|voice).

## The loop

1. Agent greets, asks for the first field.
2. For each template field: **document** field → agent asks for the card, reads it via
   camera; **voice** field → agent asks, user speaks.
3. Agent confirms the value back by voice; user approves → the field fills on screen.
4. When all fields are confirmed, the completed form renders clean and printable.

## Architecture

```
Browser (React)  --WS-->  FastAPI proxy  --google-genai-->  Gemini Live API
  mic PCM16 16kHz (binary, tag 0x01)        session lifecycle       (audio + video,
  camera JPEG ~1fps (binary, tag 0x02)      relay both ways          transcription,
  <-- agent audio, EN captions,             marker/tool capture       tool-calling)
      live form snapshots, form_complete     -> form + capture log
```

- **Capture is via Live tool-calling** (`record_field`, `form_complete` function
  declarations) — structured and language-agnostic. A `[[FIELD:id=value]]` marker
  parser (`app/markers.py`) is a fallback and also scrubs stray markers from captions.
- **Capture log** = per-session append-only, hash-chained JSONL (`app/witness_log.py`);
  each confirmed field is a `field_captured` entry `{field, value, source}`.
- **One hardcoded template** (`jkp_pension_2a`, 3 fields). Admin-upload-any-form is
  roadmap, not built.

```
app/
  main.py            FastAPI: /health, /template, WS /ws relay
  live_session.py    LiveRelay over the Gemini Live session (injectable for tests)
  session_config.py  TEMPLATE, system instruction, record_field/form_complete tools, LIVE_MODEL
  form_state.py      the live-filling form (per-field value/status/source)
  markers.py         [[FIELD]]/[[FORM_COMPLETE]] fallback parser + caption scrub
  witness_log.py     append-only, hash-chained capture log
  session.py         Session + registry, single-writer outbound queue
  protocol.py        binary media in / JSON events out
frontend/src/
  App.tsx            layout, event reducer, language badge, captions
  useMedia.ts        mic/camera capture + agent-audio playback (venue-verified)
  useWebSocket.ts    typed event stream + binary send
  Form.tsx           the form that fills itself live + printable finale
scripts/smoke_live.py  headless connect + one text turn (no audio)
```

## Run

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_API_KEY=...                 # required for the Live session
export SAHAYAK_LIVE_MODEL=...             # optional; override the Live model id
cd frontend && npm install && npm run build && cd ..
uvicorn app.main:app --port 8000          # open http://localhost:8000
```

Dev (frontend proxies /ws, /health, /template to :8000):

```bash
cd frontend && npm run dev
```

Reloading backend: `uvicorn app.main:app --reload --reload-dir app` keeps the
reloader off the `data/` capture-log tree so a log write never drops a live session.

## Test

```bash
. .venv/bin/activate && pytest          # markers, form_state, live_relay (mock), witness_log, ws (mock relay)
cd frontend && npm test                 # Form, useWebSocket, reducer
python scripts/smoke_live.py            # headless Live connect + one text turn (needs GOOGLE_API_KEY)
```

The mic/camera/audio path (`useMedia.ts`) needs real hardware and is verified at the
venue, not in CI.

## Honest boundaries

- For a fully illiterate user there is still a human submit/thumbprint step — Sahayak
  makes the **capture** accurate, in-language, and confirmed by the applicant, not the
  submission itself.
- Session content is ephemeral; the capture log stays local.
- The capture log is tamper-evident against edits and mid-file deletions, **not**
  against a clean truncation of the tail (that needs external anchoring — out of scope).
- One baked-in template; generalization (OCR any uploaded form to build the field-map)
  is near-term, not demoed.
