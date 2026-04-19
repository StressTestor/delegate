from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
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
