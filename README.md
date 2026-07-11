# Sahayak-AI

Real-time multimodal form-filling companion. A phone camera watches a paper form;
a Gemini Live API session guides the user in Hindi/Tamil, interrupts wrong fields
unprompted, and closes with a verify pass. Built for the Google DeepMind Live API
hackathon.

Design thesis: **the perception is probabilistic; the record is deterministic.**
The Live session sees, hears, judges, and interrupts. The proxy owns an
append-only, hash-chained witness log and a discrete `/verify` pass.

> Status: **walking skeleton.** The browser ↔ proxy WebSocket pipe, the witness
> log, and the `/verify` contract are in place and tested. The Gemini Live relay
> drops into the `/ws` frame dispatch next — it is not wired yet.

## Layout

```
app/
  main.py            FastAPI: /health, POST /verify (stub), WS /ws (echo skeleton)
  protocol.py        wire seam: binary frame -> media, text frame -> JSON envelope
  session.py         Session + registry; per-connection outbound queue (single writer)
  session_config.py  FORM_MAP, system instruction, flag_field tool schema (stub)
  witness_log.py     append-only JSONL, hash-chained, tamper-detecting
tests/               pytest: witness-log integrity + WS behavior
frontend/            Vite + React + TS: 4-panel shell, useWebSocket hook (vitest)
```

## Run

Backend:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_API_KEY=...            # not needed until the Live wiring lands
# --reload-dir app keeps the reloader off the witness-log tree (data/), so a log
# append never restarts the server and drops a live session mid-demo.
uvicorn app.main:app --port 8000 --reload --reload-dir app
```

Frontend (dev, proxies /ws + /health + /verify to :8000):

```bash
cd frontend && npm install && npm run dev
```

Production single-origin (proxy serves the built UI at `/`):

```bash
cd frontend && npm run build && cd ..
uvicorn app.main:app --port 8000      # open http://localhost:8000
```

## Test

```bash
. .venv/bin/activate && pytest        # backend: witness log + WS
cd frontend && npm test               # frontend: WS hook
```

## Witness log integrity — what it does and does not prove

Each entry hash-chains the previous one, so `verify_chain` detects any in-place
edit, reordering, deletion, or insertion in the **middle** of the log.

**Known limitation (by design):** hash-chaining alone cannot detect a *clean
truncation of the tail* — dropping the last N whole lines leaves nothing
downstream to contradict the forged new end. Catching that needs external
anchoring, which is out of scope. The log is tamper-evident against edits and
mid-file deletions, not against someone cleanly lopping off the end.
