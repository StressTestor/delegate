from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable
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


class MergeOutcome(str, Enum):
    MERGED = "merged"
    ASK_DECLINED = "ask_declined"


class ShaMismatch(RuntimeError):
    pass


class MergeAborted(RuntimeError):
    pass


def _changed_paths(wt_path: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(wt_path), "status", "--porcelain"],
        check=True, capture_output=True, text=True,
    ).stdout
    paths: list[str] = []
    for line in out.splitlines():
        segment = line[3:]
        if " -> " in segment:
            segment = segment.split(" -> ", 1)[1]
        paths.append(segment.strip())
    return paths


def merge_worktree(
    wt: Worktree,
    *,
    cwd: Path,
    write_allowed: list[str],
    new_file_patterns: list[str],
    do_not_touch: list[str],
    commit_format: str,
    delegated_to: str,
    ask_fn: Callable[[list[str], Path], bool] | None = None,
) -> MergeOutcome:
    paths = _changed_paths(wt.path)
    if not paths:
        return MergeOutcome.MERGED

    decisions: list[tuple[str, Category]] = [
        (p, categorize_change(
            p,
            write_allowed=write_allowed,
            new_file_patterns=new_file_patterns,
            do_not_touch=do_not_touch,
        )) for p in paths
    ]
    rejects = [p for p, c in decisions if c == Category.REJECT]
    if rejects:
        raise MergeAborted(
            f"REJECT paths prevented merge: {rejects}. Worktree retained at {wt.path}"
        )
    asks = [p for p, c in decisions if c == Category.ASK]
    if asks:
        if ask_fn is None:
            raise MergeAborted(
                f"ASK paths require interactive approval but no ask_fn provided: {asks}"
            )
        if not ask_fn(asks, wt.path):
            return MergeOutcome.ASK_DECLINED

    # SHA pin check.
    current_sha = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if current_sha != wt.base_sha:
        raise ShaMismatch(
            f"cwd HEAD moved: base {wt.base_sha}, current {current_sha}. "
            f"Worktree retained at {wt.path}"
        )

    # Capture diff from worktree.
    try:
        diff = subprocess.run(
            ["git", "-C", str(wt.path), "diff", "HEAD", "--", *paths],
            check=True, capture_output=True, text=True,
        ).stdout
        # Include untracked (new) files in the diff via intent-to-add.
        untracked = subprocess.run(
            ["git", "-C", str(wt.path), "ls-files", "--others", "--exclude-standard", "--", *paths],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        if untracked:
            subprocess.run(
                ["git", "-C", str(wt.path), "add", "--intent-to-add", *untracked],
                check=True, capture_output=True,
            )
            diff = subprocess.run(
                ["git", "-C", str(wt.path), "diff", "HEAD", "--", *paths],
                check=True, capture_output=True, text=True,
            ).stdout
    except subprocess.CalledProcessError as e:
        raise MergeAborted(
            f"failed to capture worktree diff: {e.stderr.strip()}. Worktree retained at {wt.path}"
        ) from e

    # Short-circuit: nothing meaningful to apply (mode changes, binary, etc.).
    if not diff.strip():
        cleanup_worktree(wt, cwd=cwd)
        return MergeOutcome.MERGED

    # Apply with 3-way.
    apply = subprocess.run(
        ["git", "-C", str(cwd), "apply", "--3way"],
        input=diff, text=True, capture_output=True,
    )
    if apply.returncode != 0:
        raise MergeAborted(
            f"git apply --3way failed: {apply.stderr.strip()}. Worktree retained at {wt.path}"
        )

    # Stage + commit.
    try:
        subprocess.run(["git", "-C", str(cwd), "add", *paths], check=True, capture_output=True)
        commit_msg = f"{commit_format}\n\nDelegated-To: {delegated_to}"
        subprocess.run(
            ["git", "-C", str(cwd), "commit", "-m", commit_msg],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise MergeAborted(
            f"failed to stage/commit: {e.stderr.strip()}. Worktree retained at {wt.path}"
        ) from e

    cleanup_worktree(wt, cwd=cwd)
    return MergeOutcome.MERGED
