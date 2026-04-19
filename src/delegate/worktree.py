from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


@dataclass
class Worktree:
    path: Path
    base_sha: str
    slug: str


def _slugify(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:maxlen] or "task"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=True,
    )


def spawn_worktree(*, cwd: Path, worktree_root: Path, task_slug: str) -> Worktree:
    worktree_root.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    slug = _slugify(task_slug)
    path = worktree_root / f"{ts}-{slug}"
    base_sha = _git(cwd, "rev-parse", "HEAD").stdout.strip()
    _git(cwd, "worktree", "add", "--detach", str(path), base_sha)
    return Worktree(path=path, base_sha=base_sha, slug=slug)


def reset_worktree(wt: Worktree) -> None:
    _git(wt.path, "reset", "--hard")
    _git(wt.path, "clean", "-fd")


def cleanup_worktree(wt: Worktree, *, cwd: Path) -> None:
    _git(cwd, "worktree", "remove", "--force", str(wt.path))


class Category(str, Enum):
    AUTO_APPROVE = "auto_approve"
    REJECT = "reject"
    ASK = "ask"


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a glob pattern (with ** support) to a compiled regex."""
    parts = [re.escape(p).replace(r"\*", "[^/]*") for p in pattern.split("**")]
    joined = ".*".join(parts)
    # /**/ -> zero or more path segments (** absorbs the slashes)
    joined = joined.replace("/.*/" , "(?:.*/|)")
    return re.compile("^" + joined + "$")


def _matches_any(path: str, globs: list[str]) -> bool:
    return any(_glob_to_regex(g).match(path) for g in globs)


def categorize_change(
    path: str,
    *,
    write_allowed: list[str],
    new_file_patterns: list[str],
    do_not_touch: list[str],
) -> Category:
    # REJECT first — do_not_touch trumps everything.
    if _matches_any(path, do_not_touch):
        return Category.REJECT
    if path in write_allowed or _matches_any(path, write_allowed):
        return Category.AUTO_APPROVE
    if _matches_any(path, new_file_patterns):
        return Category.AUTO_APPROVE
    return Category.ASK
