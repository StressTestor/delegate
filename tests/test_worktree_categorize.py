from delegate.worktree import categorize_change, Category


def test_write_allowed_is_auto_approve():
    c = categorize_change(
        "src/foo.ts",
        write_allowed=["src/foo.ts"],
        new_file_patterns=[],
        do_not_touch=[],
    )
    assert c == Category.AUTO_APPROVE

def test_new_file_pattern_match_is_auto_approve():
    c = categorize_change(
        "src/foo.test.ts",
        write_allowed=["src/foo.ts"],
        new_file_patterns=["src/**/*.test.ts"],
        do_not_touch=[],
    )
    assert c == Category.AUTO_APPROVE

def test_do_not_touch_match_is_reject():
    c = categorize_change(
        "src/vendor/evil.ts",
        write_allowed=[],
        new_file_patterns=[],
        do_not_touch=["src/vendor/**"],
    )
    assert c == Category.REJECT

def test_env_file_in_do_not_touch_is_reject():
    c = categorize_change(
        ".env.local",
        write_allowed=[],
        new_file_patterns=[],
        do_not_touch=[".env*"],
    )
    assert c == Category.REJECT

def test_unknown_path_is_ask():
    c = categorize_change(
        "src/bar.ts",
        write_allowed=["src/foo.ts"],
        new_file_patterns=["src/**/*.test.ts"],
        do_not_touch=[".env*"],
    )
    assert c == Category.ASK

def test_reject_beats_auto_approve():
    # do_not_touch trumps write_allowed.
    c = categorize_change(
        "src/foo.ts",
        write_allowed=["src/foo.ts"],
        new_file_patterns=[],
        do_not_touch=["src/foo.ts"],
    )
    assert c == Category.REJECT
