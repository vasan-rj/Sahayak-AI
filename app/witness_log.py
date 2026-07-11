"""Witness log — the deterministic record.

Append-only JSONL, one file per session. Each entry hash-chains the previous one,
so any in-place edit, reorder, deletion, or insertion in the middle of the log is
detectable by ``verify_chain``.

Design notes (reviewed):
- ``hash_entry`` / ``verify_chain`` are PURE and synchronous so tests stay honest.
- Canonicalization is ONE shared function used at both write and verify time — the
  only way to avoid false-positive tamper detection from whitespace / key-order /
  unicode-normalization drift.
- ``ts`` is a string before it enters the hash (never a raw float — float repr
  varies across platforms).
- All string content is NFC-normalized before hashing so visually-identical
  Hindi/Tamil text from different sources always hashes identically.

Honest limitation: hash-chaining alone cannot detect a CLEAN truncation of the
*tail* of the log (drop the last N whole lines) — there is nothing downstream left
to contradict the forged new end. Catching that needs external anchoring, which is
out of scope. Do not claim the log is tamper-proof against tail-truncation.
"""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from datetime import datetime, timezone

GENESIS_HASH = "0" * 64

# Entry kinds the proxy writes. Kept here so producers can't invent typos silently.
KINDS = frozenset(
    {
        "session_start",
        "session_end",
        "greeting",
        "field_captured",  # a confirmed field value {field, value, source}
        "form_complete",
        "language_switch",
        "tone_adapt",
    }
)


class WitnessLogError(Exception):
    """Raised when a log on disk is unreadable or its integrity is broken on READ.

    This is loud on purpose: a corrupt witness log undermines the entire
    source-of-truth claim. A WRITE failure (disk full, permissions) is a
    different, non-fatal condition and surfaces as the underlying OSError — the
    caller decides whether to keep the session alive.
    """


def _canonical(seq: int, ts: str, kind: str, data: dict, prev_hash: str) -> bytes:
    """Deterministic byte encoding of an entry's hashed material.

    Same function at write and verify time. sort_keys + tight separators kill
    key-order / whitespace drift; NFC normalization + UTF-8 kill unicode drift.
    """
    payload = {"seq": seq, "ts": ts, "kind": kind, "data": data, "prev_hash": prev_hash}
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return unicodedata.normalize("NFC", text).encode("utf-8")


def hash_entry(seq: int, ts: str, kind: str, data: dict, prev_hash: str) -> str:
    return hashlib.sha256(_canonical(seq, ts, kind, data, prev_hash)).hexdigest()


def verify_chain(entries: list[dict]) -> bool:
    """True iff the entry list is a well-formed, unbroken hash chain from genesis.

    Two checks per entry: (1) recompute the hash from stored material — catches
    in-place field tampering; (2) prev_hash links to the prior entry's hash and
    seq is contiguous from 0 — catches deletion, reordering, insertion, dup seq.
    """
    prev = GENESIS_HASH
    for i, e in enumerate(entries):
        try:
            if e["seq"] != i or e["prev_hash"] != prev:
                return False
            if hash_entry(e["seq"], e["ts"], e["kind"], e["data"], e["prev_hash"]) != e["hash"]:
                return False
        except (KeyError, TypeError):
            return False
        prev = e["hash"]
    return True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WitnessLog:
    """Per-session append-only log on disk.

    ``append`` is synchronous and serialized-by-design: the runtime funnels all
    appends for a session through a single writer task (see ``app/session.py``),
    so there is never more than one writer computing prev_hash off the tail.
    """

    def __init__(self, path: str):
        self.path = path
        self._seq: int | None = None
        self._last_hash: str | None = None

    def _load_tail(self) -> None:
        entries = self.read()
        if entries:
            self._seq = entries[-1]["seq"] + 1
            self._last_hash = entries[-1]["hash"]
        else:
            self._seq = 0
            self._last_hash = GENESIS_HASH

    def append(self, kind: str, data: dict | None = None, ts: str | None = None) -> dict:
        if self._seq is None:
            self._load_tail()
        data = data or {}
        ts = ts or _now_iso()
        seq = self._seq
        prev = self._last_hash
        h = hash_entry(seq, ts, kind, data, prev)
        entry = {"seq": seq, "ts": ts, "kind": kind, "data": data, "prev_hash": prev, "hash": h}
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        # A write failure here (OSError) intentionally propagates — it is NOT a
        # WitnessLogError and must not be swallowed as an integrity problem.
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
        self._seq = seq + 1
        self._last_hash = h
        return entry

    def read(self) -> list[dict]:
        """Parse the log. Tolerates a truncated FINAL line (crash mid-write);
        raises WitnessLogError on any corrupt line before the end."""
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
        entries: list[dict] = []
        last_idx = len(raw_lines) - 1
        for idx, line in enumerate(raw_lines):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                # Only the very last line may be a partial write from a crash.
                if idx == last_idx and not line.endswith("\n"):
                    break
                raise WitnessLogError(f"corrupt witness log at line {idx + 1}: {exc}") from exc
        return entries

    def verify(self) -> bool:
        return verify_chain(self.read())
