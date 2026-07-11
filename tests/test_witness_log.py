"""Deterministic tests for the witness log — the source-of-truth claim, verified.

Covers: append/read, genesis edge, unicode (Hindi/Tamil) hash stability, and the
tamper surface — in-place edit, reorder, deletion, mid-file corruption, and the
crash-truncated final line. The one attack hash-chaining cannot catch (clean
tail-truncation) is asserted as a KNOWN limitation, not a passing defense.
"""

import json

import pytest

from app.witness_log import (
    GENESIS_HASH,
    WitnessLog,
    WitnessLogError,
    hash_entry,
    verify_chain,
)

FIXED_TS = "2026-07-11T00:00:00+00:00"


def _log(tmp_path):
    return WitnessLog(str(tmp_path / "s.jsonl"))


def test_empty_log_verifies_and_reads_nothing(tmp_path):
    log = _log(tmp_path)
    assert log.read() == []
    assert log.verify() is True  # demo-reset clears the log; empty is valid


def test_append_then_read_roundtrip(tmp_path):
    log = _log(tmp_path)
    e0 = log.append("session_start", {"session_id": "abc"}, ts=FIXED_TS)
    e1 = log.append("field_captured", {"field": "dob"}, ts=FIXED_TS)
    assert e0["seq"] == 0 and e0["prev_hash"] == GENESIS_HASH
    assert e1["seq"] == 1 and e1["prev_hash"] == e0["hash"]
    assert log.read() == [e0, e1]
    assert log.verify() is True


def test_genesis_only_log(tmp_path):
    log = _log(tmp_path)
    log.append("session_start", ts=FIXED_TS)
    entries = log.read()
    assert len(entries) == 1
    assert entries[0]["prev_hash"] == GENESIS_HASH
    assert verify_chain(entries) is True


def test_unicode_hindi_tamil_hashes_stable(tmp_path):
    """Core path: the product speaks Hindi/Tamil. Identical content must hash
    identically, and the chain must verify with non-ASCII in the data."""
    log = _log(tmp_path)
    data = {"field": "applicant_name", "value": "राजेश कुमार", "note": "தமிழ்"}
    e = log.append("field_captured", data, ts=FIXED_TS)
    # Same material recomputes to the same hash.
    assert hash_entry(0, FIXED_TS, "field_captured", data, GENESIS_HASH) == e["hash"]
    assert log.verify() is True
    # And it survives a read round-trip (UTF-8 on disk).
    assert log.read()[0]["data"]["value"] == "राजेश कुमार"


def test_tamper_inplace_edit_of_value_char(tmp_path):
    """Flip a character inside a field VALUE (not JSON structure) in a MIDDLE
    entry — verify_chain must return False via hash mismatch."""
    log = _log(tmp_path)
    log.append("session_start", {"session_id": "abc"}, ts=FIXED_TS)
    log.append("field_captured", {"field": "dob", "value": "AAAA"}, ts=FIXED_TS)
    log.append("session_end", {"session_id": "abc"}, ts=FIXED_TS)

    entries = log.read()
    entries[1]["data"]["value"] = "AAAB"  # tampered value, hash left stale
    assert verify_chain(entries) is False


def test_tamper_reorder_entries(tmp_path):
    """Swapping two whole valid entries breaks seq/prev_hash linkage."""
    log = _log(tmp_path)
    log.append("session_start", ts=FIXED_TS)
    log.append("field_captured", {"field": "dob"}, ts=FIXED_TS)
    log.append("session_end", ts=FIXED_TS)

    entries = log.read()
    entries[1], entries[2] = entries[2], entries[1]
    assert verify_chain(entries) is False


def test_tamper_delete_middle_entry(tmp_path):
    """Deleting a middle entry breaks the prev_hash of the next."""
    log = _log(tmp_path)
    log.append("session_start", ts=FIXED_TS)
    log.append("field_captured", {"field": "dob"}, ts=FIXED_TS)
    log.append("session_end", ts=FIXED_TS)

    entries = log.read()
    del entries[1]
    assert verify_chain(entries) is False


def test_forged_genesis_prev_hash_rejected(tmp_path):
    """Entry 0 must chain to the real GENESIS_HASH, not any well-formed string."""
    entries = [
        {"seq": 0, "ts": FIXED_TS, "kind": "session_start", "data": {},
         "prev_hash": "f" * 64, "hash": hash_entry(0, FIXED_TS, "session_start", {}, "f" * 64)},
    ]
    assert verify_chain(entries) is False


def test_corrupt_middle_line_raises(tmp_path):
    log = _log(tmp_path)
    log.append("session_start", ts=FIXED_TS)
    log.append("session_end", ts=FIXED_TS)
    # Corrupt the FIRST line (not the last) — a real integrity failure on read.
    lines = (tmp_path / "s.jsonl").read_text().splitlines()
    lines[0] = "{not json"
    (tmp_path / "s.jsonl").write_text("\n".join(lines) + "\n")
    with pytest.raises(WitnessLogError):
        log.read()


def test_truncated_final_line_tolerated(tmp_path):
    """Crash mid-write leaves a partial last line with no trailing newline —
    tolerated as 'writer died here', not a corruption error."""
    log = _log(tmp_path)
    log.append("session_start", ts=FIXED_TS)
    with open(tmp_path / "s.jsonl", "a", encoding="utf-8") as f:
        f.write('{"seq": 1, "ts": "partial')  # no newline, truncated
    entries = log.read()  # must not raise
    assert len(entries) == 1
    assert verify_chain(entries) is True


def test_clean_tail_truncation_is_the_known_gap(tmp_path):
    """KNOWN LIMITATION: dropping whole trailing lines cleanly cannot be caught
    by hash-chaining alone. This test documents the gap so the source-of-truth
    claim is not overstated."""
    log = _log(tmp_path)
    log.append("session_start", ts=FIXED_TS)
    log.append("field_captured", {"field": "dob"}, ts=FIXED_TS)
    log.append("session_end", ts=FIXED_TS)

    lines = (tmp_path / "s.jsonl").read_text().splitlines()
    truncated = [json.loads(lines[0])]  # keep only the first entry, cleanly
    # The surviving prefix still verifies — that is exactly why tail-truncation
    # is undetectable without external anchoring.
    assert verify_chain(truncated) is True
