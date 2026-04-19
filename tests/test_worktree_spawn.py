import subprocess
from pathlib import Path
from delegate.worktree import spawn_worktree, reset_worktree, cleanup_worktree


def _init_repo(path: Path) -> str:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "a.txt").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True
    ).stdout.strip()
    return sha


def test_spawn_creates_detached_worktree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    sha = _init_repo(repo)
    wt_root = tmp_path / "wt"
    wt_root.mkdir()

    wt = spawn_worktree(cwd=repo, worktree_root=wt_root, task_slug="test")
    assert wt.path.exists()
    assert (wt.path / "a.txt").read_text() == "hello\n"
    assert wt.base_sha == sha

    # Detached HEAD: verify.
    head = subprocess.run(
        ["git", "-C", str(wt.path), "symbolic-ref", "HEAD"],
        capture_output=True, text=True
    )
    assert head.returncode != 0, "expected detached HEAD (no symbolic ref)"

def test_reset_worktree_discards_changes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    wt_root.mkdir()
    wt = spawn_worktree(cwd=repo, worktree_root=wt_root, task_slug="test")
    (wt.path / "a.txt").write_text("modified")
    (wt.path / "new.txt").write_text("extra")
    reset_worktree(wt)
    assert (wt.path / "a.txt").read_text() == "hello\n"
    assert not (wt.path / "new.txt").exists()

def test_cleanup_worktree_removes_it(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    wt_root.mkdir()
    wt = spawn_worktree(cwd=repo, worktree_root=wt_root, task_slug="test")
    cleanup_worktree(wt, cwd=repo)
    assert not wt.path.exists()
