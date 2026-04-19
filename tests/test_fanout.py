import subprocess
from pathlib import Path
from unittest.mock import MagicMock
from delegate.fanout import run_bulk, BulkResult
from delegate.providers.base import Outcome, ProviderResult


def _init_repo(path: Path):
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    for n in ["a.txt", "b.txt", "c.txt"]:
        (path / n).write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def _cfg(wt_root: Path) -> dict:
    return {
        "defaults": {"worktree_root": str(wt_root), "log_path": str(wt_root / "log.jsonl"), "concurrency": 2},
        "timeouts": {"bulk": 60},
        "circuit_breaker": {"window": 4, "failure_threshold": 0.5, "halt_on_trip": True},
        "providers": {"p1": {"cli": "p1", "rpm_cap": 6000}},
    }


def test_bulk_success_all_files(tmp_path, mocker):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    cfg = _cfg(wt_root)
    chain = [{"provider": "p1", "model": "m1"}]

    def invoke(*, model, brief, prompt, cwd, timeout_s):
        # Each task's worktree cwd is distinct; modify the expected file.
        target = brief["write_allowed"][0]
        (cwd / target).write_text("modified\n")
        return ProviderResult(outcome=Outcome.OK)
    fake = MagicMock()
    fake.invoke.side_effect = invoke
    mocker.patch("delegate.orchestrator.build_provider", return_value=fake)

    result: BulkResult = run_bulk(
        task_type="bulk", chain=chain, cfg=cfg, cwd=repo,
        files=["a.txt", "b.txt", "c.txt"],
        task_template="modify each",
        commit_format="chore: bulk",
        concurrency=2,
    )
    assert result.success == 3
    assert result.failed == 0
    assert result.skipped == 0
    for n in ["a.txt", "b.txt", "c.txt"]:
        assert (repo / n).read_text() == "modified\n"

def test_bulk_circuit_breaker_halts(tmp_path, mocker):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    cfg = _cfg(wt_root)
    chain = [{"provider": "p1", "model": "m1"}]

    fake = MagicMock()
    # All provider calls fail recoverably.
    fake.invoke.return_value = ProviderResult(outcome=Outcome.RATE_LIMITED, detail="429")
    mocker.patch("delegate.orchestrator.build_provider", return_value=fake)

    # 10 files; circuit should trip well before the end.
    files = [f"x{i}.txt" for i in range(10)]
    for f in files:
        (repo / f).write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "add"], check=True, capture_output=True)

    result = run_bulk(
        task_type="bulk", chain=chain, cfg=cfg, cwd=repo,
        files=files, task_template="x", commit_format="x", concurrency=2,
    )
    assert result.circuit_broken
    assert result.skipped > 0
