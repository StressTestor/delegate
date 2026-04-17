import pytest
from delegate.brief import build_brief, validate_brief, render_prompt, BriefError


def test_build_brief_from_args_has_all_required_fields():
    b = build_brief(
        task="implement foo()",
        read=["src/foo.ts"],
        write_allowed=["src/foo.ts"],
        new_file_patterns=[],
        do_not_touch=[],
        acceptance=["tests pass"],
        commit_format="feat(foo): add",
        constraints=[],
    )
    assert b["brief_version"] == "1"
    assert b["task"] == "implement foo()"
    assert "BLOCKER" in b["escape_hatch"]

def test_validate_brief_accepts_canonical():
    b = build_brief(
        task="x", read=[], write_allowed=[], new_file_patterns=[],
        do_not_touch=[], acceptance=["x"], commit_format="x", constraints=[],
    )
    validate_brief(b)  # no raise

def test_validate_brief_rejects_bad_version():
    b = build_brief(
        task="x", read=[], write_allowed=[], new_file_patterns=[],
        do_not_touch=[], acceptance=["x"], commit_format="x", constraints=[],
    )
    b["brief_version"] = "99"
    with pytest.raises(BriefError):
        validate_brief(b)

def test_validate_brief_rejects_missing_required():
    with pytest.raises(BriefError, match="acceptance"):
        validate_brief({"brief_version": "1", "task": "x"})

def test_render_prompt_contains_all_sections():
    b = build_brief(
        task="implement foo()",
        read=["src/foo.ts", "src/bar.ts"],
        write_allowed=["src/foo.ts"],
        new_file_patterns=["src/**/*.test.ts"],
        do_not_touch=[".env*"],
        acceptance=["tests pass"],
        commit_format="feat(foo): add",
        constraints=["match bar.ts style"],
    )
    p = render_prompt(b)
    assert "implement foo()" in p
    assert "src/foo.ts" in p
    assert "src/bar.ts" in p
    assert "src/**/*.test.ts" in p
    assert ".env*" in p
    assert "tests pass" in p
    assert "feat(foo): add" in p
    assert "match bar.ts style" in p
    assert "BLOCKER" in p
