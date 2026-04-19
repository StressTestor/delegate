import subprocess
import pytest
from pathlib import Path
from delegate.worktree import (
    spawn_worktree, merge_worktree, MergeOutcome, ShaMismatch, MergeAborted
)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "a.txt").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_merge_auto_approves_and_commits(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    wt_root.mkdir()
    wt = spawn_worktree(cwd=repo, worktree_root=wt_root, task_slug="t")

    (wt.path / "a.txt").write_text("hello\nworld\n")
    outcome = merge_worktree(
        wt,
        cwd=repo,
        write_allowed=["a.txt"],
        new_file_patterns=[],
        do_not_touch=[],
        commit_format="feat: x",
        delegated_to="test/m",
    )
    assert outcome == MergeOutcome.MERGED
    assert (repo / "a.txt").read_text() == "hello\nworld\n"
    last_msg = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--pretty=%B"],
        check=True, capture_output=True, text=True
    ).stdout
    assert "feat: x" in last_msg
    assert "Delegated-To: test/m" in last_msg


def test_merge_aborts_on_reject(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    wt_root.mkdir()
    wt = spawn_worktree(cwd=repo, worktree_root=wt_root, task_slug="t")

    (wt.path / ".env.local").write_text("SECRET=1")
    with pytest.raises(MergeAborted, match="REJECT"):
        merge_worktree(
            wt, cwd=repo,
            write_allowed=[], new_file_patterns=[],
            do_not_touch=[".env*"],
            commit_format="x", delegated_to="x",
        )
    # Worktree intact after abort.
    assert wt.path.exists()


def test_merge_raises_sha_mismatch_if_cwd_moved(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    wt_root.mkdir()
    wt = spawn_worktree(cwd=repo, worktree_root=wt_root, task_slug="t")
    (wt.path / "a.txt").write_text("x\n")

    # Move cwd forward.
    (repo / "b.txt").write_text("sneak")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "sneak"],
                   check=True, capture_output=True)

    with pytest.raises(ShaMismatch):
        merge_worktree(
            wt, cwd=repo,
            write_allowed=["a.txt"], new_file_patterns=[],
            do_not_touch=[], commit_format="x", delegated_to="x",
        )


def test_merge_ask_paths_approved(tmp_path):
    """ask_fn returns True -> merge proceeds."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    wt_root.mkdir()
    wt = spawn_worktree(cwd=repo, worktree_root=wt_root, task_slug="t")

    # Write a file not in write_allowed -- will be categorized as ASK.
    (wt.path / "a.txt").write_text("hello\nworld\n")
    outcome = merge_worktree(
        wt, cwd=repo,
        write_allowed=[],  # a.txt not in write_allowed -> ASK
        new_file_patterns=[],
        do_not_touch=[],
        commit_format="feat: ask-approved",
        delegated_to="test/ask",
        ask_fn=lambda paths, wt_path: True,  # always approve
    )
    assert outcome == MergeOutcome.MERGED
    assert (repo / "a.txt").read_text() == "hello\nworld\n"


def test_merge_ask_paths_declined(tmp_path):
    """ask_fn returns False -> returns ASK_DECLINED, no commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    wt_root.mkdir()
    wt = spawn_worktree(cwd=repo, worktree_root=wt_root, task_slug="t")

    (wt.path / "a.txt").write_text("hello\nworld\n")
    outcome = merge_worktree(
        wt, cwd=repo,
        write_allowed=[],  # a.txt -> ASK
        new_file_patterns=[],
        do_not_touch=[],
        commit_format="feat: ask-declined",
        delegated_to="test/ask",
        ask_fn=lambda paths, wt_path: False,  # always decline
    )
    assert outcome == MergeOutcome.ASK_DECLINED
    # No commit -- repo file unchanged.
    assert (repo / "a.txt").read_text() == "hello\n"


def test_merge_new_file_via_new_file_patterns(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    wt_root.mkdir()
    wt = spawn_worktree(cwd=repo, worktree_root=wt_root, task_slug="t")

    (wt.path / "src").mkdir()
    (wt.path / "src" / "new.py").write_text("# new\n")
    outcome = merge_worktree(
        wt, cwd=repo,
        write_allowed=[],
        new_file_patterns=["src/**/*.py"],
        do_not_touch=[],
        commit_format="feat: new file",
        delegated_to="test/new",
    )
    assert outcome == MergeOutcome.MERGED
    assert (repo / "src" / "new.py").exists()
