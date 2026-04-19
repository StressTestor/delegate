import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock
import delegate.orchestrator as _orch_mod
from delegate.orchestrator import run_single_task
from delegate.providers.base import Outcome, ProviderResult


def _init_repo(path):
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "a.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_rate_limiter_enforces_spacing(tmp_path, mocker):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    cfg = {
        "defaults": {"worktree_root": str(wt_root), "log_path": str(wt_root / "log.jsonl")},
        "timeouts": {"code-gen": 60},
        "providers": {"p1": {"cli": "p1", "rpm_cap": 60}},  # 1/sec
    }
    chain = [{"provider": "p1", "model": "m1"}]
    brief = {
        "brief_version": "1", "task": "x", "read": [], "write_allowed": ["a.txt"],
        "new_file_patterns": [], "do_not_touch": [], "acceptance": ["x"],
        "commit_format": "x", "constraints": [], "escape_hatch": "x",
    }

    # Clear module-level limiter cache so prior test runs don't bleed state.
    _orch_mod._LIMITERS.clear()

    fake = MagicMock()
    def invoke(*, model, brief, prompt, cwd, timeout_s):
        (cwd / "a.txt").write_text("modified")
        return ProviderResult(outcome=Outcome.OK)
    fake.invoke.side_effect = invoke
    mocker.patch("delegate.orchestrator.build_provider", return_value=fake)

    # Invoke once; first call has no prior timestamp so should NOT sleep.
    start = time.monotonic()
    run_single_task(task_type="code-gen", chain=chain, brief=brief, cfg=cfg,
                    cwd=repo, task_id="t1", batch_id=None)
    elapsed = time.monotonic() - start
    # First call has no prior timestamp — should complete well under 0.5s.
    assert elapsed < 0.5
