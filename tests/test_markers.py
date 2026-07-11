from app.markers import parse_and_strip


def test_no_markers_passthrough():
    fields, complete, clean = parse_and_strip("नमस्ते, चलिए शुरू करते हैं।")
    assert fields == []
    assert complete is False
    assert clean == "नमस्ते, चलिए शुरू करते हैं।"


def test_single_field_marker_extracted_and_stripped():
    fields, complete, clean = parse_and_strip("ok [[FIELD:applicant_name=RAJESH KUMAR]] done")
    assert fields == [("applicant_name", "RAJESH KUMAR")]
    assert complete is False
    assert "[[" not in clean
    assert clean == "ok done"


def test_multiple_fields_in_order():
    text = "[[FIELD:applicant_name=RAJESH]] and [[FIELD:dob=01/01/1990]]"
    fields, _, clean = parse_and_strip(text)
    assert fields == [("applicant_name", "RAJESH"), ("dob", "01/01/1990")]
    assert clean == "and"


def test_form_complete_marker():
    fields, complete, clean = parse_and_strip("सब हो गया [[FORM_COMPLETE]]")
    assert complete is True
    assert fields == []
    assert clean == "सब हो गया"


def test_empty_string():
    assert parse_and_strip("") == ([], False, "")


def test_malformed_marker_left_alone():
    # Missing closing brackets -> not a valid marker, stays in the caption text.
    fields, complete, clean = parse_and_strip("[[FIELD:dob=01/01/1990")
    assert fields == []
    assert complete is False
    assert "[[FIELD:dob=01/01/1990" in clean
