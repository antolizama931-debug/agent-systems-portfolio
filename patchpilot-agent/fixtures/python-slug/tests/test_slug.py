from slug import slugify


def test_slug_collapses_separators():
    assert slugify("Agent   Control Plane") == "agent-control-plane"


def test_slug_removes_punctuation():
    assert slugify("PatchPilot: Safe & Fast") == "patchpilot-safe-fast"

