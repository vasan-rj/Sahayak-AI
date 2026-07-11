import pytest

from app.template_store import TemplateError, TemplateStore, validate_template


def _tpl(tid="t1"):
    return {
        "template_id": tid,
        "title": "T",
        "fields": [
            {"id": "a", "label": "A", "type": "document", "source_doc": "aadhaar", "extract": "x", "ask": "?"},
            {"id": "b", "label": "B", "type": "voice", "extract": "y", "ask": "?"},
        ],
    }


def test_seeds_default_on_init(tmp_path):
    s = TemplateStore(str(tmp_path))
    assert "jkp_pension_2a" in s.list_ids()
    assert s.get_active_id() == "jkp_pension_2a"


def test_save_get_list_delete(tmp_path):
    s = TemplateStore(str(tmp_path))
    s.save(_tpl("ration"))
    assert s.get("ration")["title"] == "T"
    assert any(x["template_id"] == "ration" for x in s.list_templates())
    s.delete("ration")
    with pytest.raises(KeyError):
        s.get("ration")


def test_active_pointer(tmp_path):
    s = TemplateStore(str(tmp_path))
    s.save(_tpl("ration"))
    s.set_active("ration")
    assert s.get_active()["template_id"] == "ration"


def test_deleting_active_reassigns(tmp_path):
    s = TemplateStore(str(tmp_path))  # seeds jkp + marks it active
    s.save(_tpl("ration"))
    s.set_active("ration")
    s.delete("ration")
    assert s.get_active_id() == "jkp_pension_2a"


def test_set_active_unknown_raises(tmp_path):
    s = TemplateStore(str(tmp_path))
    with pytest.raises(KeyError):
        s.set_active("nope")


def test_list_summary_marks_active(tmp_path):
    s = TemplateStore(str(tmp_path))
    active = [x for x in s.list_templates() if x["active"]]
    assert len(active) == 1
    assert active[0]["template_id"] == "jkp_pension_2a"
    assert active[0]["field_count"] == 3


def test_validate_rejects_bad_type():
    t = _tpl()
    t["fields"][0]["type"] = "telepathy"
    with pytest.raises(TemplateError):
        validate_template(t)


def test_validate_rejects_duplicate_ids():
    t = _tpl()
    t["fields"][1]["id"] = "a"
    with pytest.raises(TemplateError):
        validate_template(t)


def test_validate_rejects_missing_key():
    t = _tpl()
    del t["fields"][0]["label"]
    with pytest.raises(TemplateError):
        validate_template(t)


def test_validate_rejects_non_slug_template_id():
    with pytest.raises(TemplateError):
        validate_template(_tpl("bad id!"))
