from types import SimpleNamespace

from mudmut_core import design


def _req(req_id, req_type, title, description):
    return SimpleNamespace(req_id=req_id, req_type=req_type, title=title, description=description)


def test_requirements_text_format():
    rs = SimpleNamespace(requirements=[
        _req("REQ-1", "functional", "Do X", "The SWC shall do X."),
        _req("REQ-2", "timing", "10ms cycle", "Run every 10 ms."),
    ])
    text = design.requirements_text(rs)
    assert "[REQ-1] (functional) Do X\n  Description: The SWC shall do X." in text
    assert "[REQ-2] (timing) 10ms cycle\n  Description: Run every 10 ms." in text


def test_requirements_text_accepts_enum_type():
    from enum import Enum

    class T(Enum):
        FUNCTIONAL = "functional"

    r = SimpleNamespace(req_id="REQ-9", req_type=T.FUNCTIONAL, title="T", description="D")
    text = design.requirements_text([r])
    assert "[REQ-9] (functional) T" in text


def test_requirements_to_dicts_normalizes_enum():
    from enum import Enum

    class T(Enum):
        SAFETY = "safety"

    r = SimpleNamespace(req_id="REQ-9", req_type=T.SAFETY, title="T", description="D")
    r.model_dump = lambda: {"req_id": "REQ-9", "req_type": T.SAFETY, "title": "T"}
    out = design.requirements_to_dicts([r])
    assert out[0]["req_type"] == "safety"
