from __future__ import annotations

import re


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a glob pattern (with ** support) to a compiled regex.

    ** matches zero or more path segments (including separators).
    *  matches within a single path segment only (no /).
    """
    parts = [re.escape(p).replace(r"\*", "[^/]*") for p in pattern.split("**")]
    joined = ".*".join(parts)
    # Replace ALL inline /**/ occurrences (re.sub fixes what str.replace misses
    # on patterns with multiple /**/).
    joined = re.sub(r"/\.\*/", "/(?:.*/|)", joined)
    # Leading **/ (e.g. **/*.py) produces .* at the start — make it optional
    # so the pattern also matches root-level files with no directory prefix.
    if joined.startswith(".*/"):
        joined = "(?:.*/|)" + joined[3:]
    return re.compile("^" + joined + "$")


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(glob_to_regex(p).match(path) for p in patterns)
