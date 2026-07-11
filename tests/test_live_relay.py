"""KEY integration test: a scripted mock Live stream drives the whole capture
path end to end (form fills, capture log chains, form_complete fires) with no
network. This is the closest deterministic proxy for the real Live session.
"""

import asyncio

from app.form_state import FormState
from app.live_session import LiveRelay
from app.witness_log import WitnessLog
from tests.mocks import MockLiveSession, audio_msg, caption_msg, tool_msg


def _run(coro):
    return asyncio.run(coro)


def test_scripted_stream_fills_form_and_logs(tmp_path):
    form = FormState()
    log = WitnessLog(str(tmp_path / "capture.jsonl"))
    log.append("session_start")

    captions: list[tuple] = []
    audio_out: list[bytes] = []
    complete_fired = {"v": False}

    def on_field(field_id, value, source):
        try:
            form.apply(field_id, value, source)
        except (KeyError, ValueError):
            return False
        log.append("field_captured", {"field": field_id, "value": value, "source": source})
        return True

    def on_complete():
        complete_fired["v"] = True
        log.append("form_complete", {})

    def on_caption(side, text, lang):
        captions.append((side, text, lang))

    def on_audio(pcm):
        audio_out.append(pcm)

    # One turn: agent speaks, sends audio, then confirms all three fields via
    # tool calls (two document-sourced, one voice-sourced), then form_complete.
    turn = [
        caption_msg(agent="नमस्ते, चलिए फॉर्म भरते हैं।"),
        audio_msg(b"\x00\x01\x02\x03"),
        tool_msg(("record_field", {"field_id": "applicant_name", "value": "RAJESH KUMAR", "source": "document"})),
        tool_msg(("record_field", {"field_id": "dob", "value": "01/01/1990", "source": "document"})),
        tool_msg(("record_field", {"field_id": "nominee_name", "value": "SUNITA DEVI", "source": "voice"})),
        tool_msg(("form_complete", {})),
    ]
    mock = MockLiveSession([turn])
    relay = LiveRelay(
        mock,
        on_audio=on_audio,
        on_caption=on_caption,
        on_field=on_field,
        on_complete=on_complete,
    )

    _run(relay.receive_loop())

    # Form fully filled with correct sources.
    snap = form.snapshot()
    assert snap["complete"] is True
    by_id = {f["id"]: f for f in snap["fields"]}
    assert by_id["applicant_name"]["value"] == "RAJESH KUMAR"
    assert by_id["applicant_name"]["source"] == "document"
    assert by_id["nominee_name"]["source"] == "voice"

    # Callbacks fired.
    assert complete_fired["v"] is True
    assert captions == [("agent", "नमस्ते, चलिए फॉर्म भरते हैं।", "hi")]
    assert audio_out == [b"\x00\x01\x02\x03"]

    # Capture log: session_start + 3 field_captured + form_complete, chain valid.
    entries = log.read()
    kinds = [e["kind"] for e in entries]
    assert kinds == ["session_start", "field_captured", "field_captured", "field_captured", "form_complete"]
    assert entries[1]["data"] == {"field": "applicant_name", "value": "RAJESH KUMAR", "source": "document"}
    assert log.verify() is True

    # Each record_field got a tool response back to the model.
    assert len(mock.tool_responses) == 4


def test_unknown_field_is_rejected_not_applied(tmp_path):
    form = FormState()

    def on_field(field_id, value, source):
        try:
            form.apply(field_id, value, source)
            return True
        except (KeyError, ValueError):
            return False

    turn = [tool_msg(("record_field", {"field_id": "ghost", "value": "x", "source": "voice"}))]
    mock = MockLiveSession([turn])
    relay = LiveRelay(mock, on_field=on_field)
    _run(relay.receive_loop())

    assert form.is_complete() is False
    # The model still receives a (rejected) tool response so the turn can continue.
    assert mock.tool_responses[0][0].response == {"status": "rejected"}


def test_send_audio_and_frame_route_to_session():
    mock = MockLiveSession([])
    relay = LiveRelay(mock)
    _run(relay.send_audio(b"pcm"))
    _run(relay.send_frame(b"jpeg"))
    assert mock.audio_sent == [b"pcm"]
    assert mock.video_sent == [b"jpeg"]
