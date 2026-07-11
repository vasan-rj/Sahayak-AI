import pytest

from app.form_state import FormState


def test_initial_snapshot_all_pending():
    fs = FormState()
    snap = fs.snapshot()
    assert snap["template_id"] == "jkp_pension_2a"
    assert [f["id"] for f in snap["fields"]] == ["applicant_name", "dob", "nominee_name"]
    assert all(f["status"] == "pending" and f["value"] is None for f in snap["fields"])
    assert snap["complete"] is False


def test_apply_document_field_records_source():
    fs = FormState()
    field = fs.apply("applicant_name", "RAJESH KUMAR", "document")
    assert field["status"] == "confirmed"
    assert field["value"] == "RAJESH KUMAR"
    assert field["source"] == "document"
    assert fs.remaining() == ["dob", "nominee_name"]


def test_apply_voice_field_records_source():
    fs = FormState()
    field = fs.apply("nominee_name", "SUNITA DEVI", "voice")
    assert field["source"] == "voice"


def test_complete_only_when_all_confirmed():
    fs = FormState()
    fs.apply("applicant_name", "RAJESH KUMAR", "document")
    fs.apply("dob", "01/01/1990", "document")
    assert fs.is_complete() is False
    fs.apply("nominee_name", "SUNITA DEVI", "voice")
    assert fs.is_complete() is True
    assert fs.snapshot()["complete"] is True


def test_unknown_field_raises():
    fs = FormState()
    with pytest.raises(KeyError):
        fs.apply("ghost_field", "x", "voice")


def test_invalid_source_raises():
    fs = FormState()
    with pytest.raises(ValueError):
        fs.apply("dob", "01/01/1990", "telepathy")


def test_snapshot_is_a_copy():
    fs = FormState()
    snap = fs.snapshot()
    snap["fields"][0]["value"] = "MUTATED"
    # mutating the snapshot must not corrupt internal state
    assert fs.snapshot()["fields"][0]["value"] is None
