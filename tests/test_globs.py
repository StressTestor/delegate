from delegate.globs import glob_to_regex, matches_any


def test_single_star_does_not_cross_separator():
    assert glob_to_regex("src/*.py").match("src/foo.py")
    assert not glob_to_regex("src/*.py").match("src/sub/foo.py")


def test_double_star_matches_nested():
    assert glob_to_regex("src/**/*.py").match("src/a/b/c/foo.py")
    assert glob_to_regex("src/**/*.py").match("src/foo.py")


def test_multi_double_star_all_replaced():
    # The old str.replace bug: only the first /**/ was converted.
    # a/**/b/**/c must match a/x/y/b/z/w/c.
    pat = glob_to_regex("a/**/b/**/c")
    assert pat.match("a/x/b/y/c")
    assert pat.match("a/x/y/b/z/w/c")
    assert pat.match("a/b/c")
    assert not pat.match("a/x/b/y/d")


def test_double_star_at_start():
    assert glob_to_regex("**/*.test.ts").match("src/a/b/foo.test.ts")
    assert glob_to_regex("**/*.test.ts").match("foo.test.ts")


def test_matches_any_returns_true_on_first_hit():
    assert matches_any("src/foo.py", ["*.txt", "src/**/*.py"])
    assert not matches_any("src/foo.py", ["*.txt", "*.md"])


def test_literal_path_no_glob():
    assert glob_to_regex(".env").match(".env")
    assert not glob_to_regex(".env").match(".env.local")


def test_dotglob_prefix():
    assert glob_to_regex(".env*").match(".env")
    assert glob_to_regex(".env*").match(".env.local")
    assert not glob_to_regex(".env*").match("src/.env")
