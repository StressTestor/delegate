import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock
from delegate.fanout import run_bulk
from delegate.providers.base import Outcome, ProviderResult


def _init_repo(path: Path, files: list[str]):
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    for n in files:
        (path / n).write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_bulk_serializes_merges_under_concurrency(tmp_path, mocker):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo, ["a.txt", "b.txt", "c.txt", "d.txt"])
    wt_root = tmp_path / "wt"
    cfg = {
        "defaults": {"worktree_root": str(wt_root), "log_path": str(wt_root / "log.jsonl"), "concurrency": 4},
        "timeouts": {"bulk": 60},
        "circuit_breaker": {"window": 10, "failure_threshold": 0.99, "halt_on_trip": False},
        "providers": {"p1": {"cli": "p1", "rpm_cap": 6000}},
    }
    chain = [{"provider": "p1", "model": "m1"}]

    # Track concurrent merge detection via a shared sentinel.
    active = {"n": 0, "max": 0}
    lock = threading.Lock()

    def invoke(*, model, brief, prompt, cwd, timeout_s):
        target = brief["write_allowed"][0]
        (cwd / target).write_text("modified\n")
        return ProviderResult(outcome=Outcome.OK)

    fake = MagicMock()
    fake.invoke.side_effect = invoke
    mocker.patch("delegate.orchestrator.build_provider", return_value=fake)

    # Wrap merge_worktree to count concurrent entries.
    import delegate.orchestrator as orch
    original = orch.merge_worktree
    def tracked_merge(*args, **kwargs):
        with lock:
            active["n"] += 1
            active["max"] = max(active["max"], active["n"])
        try:
            return original(*args, **kwargs)
        finally:
            with lock:
                active["n"] -= 1
    mocker.patch("delegate.orchestrator.merge_worktree", side_effect=tracked_merge)

    result = run_bulk(
        task_type="bulk", chain=chain, cfg=cfg, cwd=repo,
        files=["a.txt", "b.txt", "c.txt", "d.txt"],
        task_template="x", commit_format="chore: bulk", concurrency=4,
    )
    assert result.success == 4
    assert active["max"] == 1, f"merges should be serialized; saw {active['max']} concurrent"
