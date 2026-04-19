import subprocess
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from delegate.orchestrator import run_single_task, ChainExhausted
from delegate.providers.base import Outcome, ProviderResult


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "a.txt").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def _minimal_cfg(worktree_root: Path) -> dict:
    return {
        "defaults": {"worktree_root": str(worktree_root), "log_path": str(worktree_root / "log.jsonl")},
        "timeouts": {"code-gen": 60, "bulk": 60, "research": 60},
        "providers": {
            "p1": {"cli": "p1"},
            "p2": {"cli": "p2"},
        },
    }


def _brief() -> dict:
    return {
        "brief_version": "1",
        "task": "edit a.txt",
        "read": ["a.txt"],
        "write_allowed": ["a.txt"],
        "new_file_patterns": [],
        "do_not_touch": [],
        "acceptance": ["test"],
        "commit_format": "feat: test",
        "constraints": [],
        "escape_hatch": "x",
    }


def test_first_provider_succeeds(tmp_path, mocker):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    cfg = _minimal_cfg(wt_root)
    chain = [{"provider": "p1", "model": "m1"}]

    # Fake provider that edits a.txt inside the worktree cwd.
    def fake_invoke(*, model, brief, prompt, cwd, timeout_s):
        (cwd / "a.txt").write_text("modified\n")
        return ProviderResult(outcome=Outcome.OK, duration_s=0.1)

    fake_provider = MagicMock()
    fake_provider.invoke.side_effect = fake_invoke
    mocker.patch("delegate.orchestrator.build_provider", return_value=fake_provider)

    result = run_single_task(
        task_type="code-gen", chain=chain, brief=_brief(), cfg=cfg,
        cwd=repo, task_id="t1", batch_id=None,
    )
    assert result["status"] == "ok"
    assert result["provider"] == "p1"
    assert (repo / "a.txt").read_text() == "modified\n"

def test_first_fails_second_succeeds(tmp_path, mocker):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    cfg = _minimal_cfg(wt_root)
    chain = [
        {"provider": "p1", "model": "m1"},
        {"provider": "p2", "model": "m2"},
    ]

    call_count = {"n": 0}
    def fake_invoke(*, model, brief, prompt, cwd, timeout_s):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return ProviderResult(outcome=Outcome.RATE_LIMITED, detail="429")
        (cwd / "a.txt").write_text("second\n")
        return ProviderResult(outcome=Outcome.OK)

    fake = MagicMock()
    fake.invoke.side_effect = fake_invoke
    mocker.patch("delegate.orchestrator.build_provider", return_value=fake)

    result = run_single_task(
        task_type="code-gen", chain=chain, brief=_brief(), cfg=cfg,
        cwd=repo, task_id="t1", batch_id=None,
    )
    assert result["status"] == "ok"
    assert result["provider"] == "p2"

def test_chain_exhausted_raises(tmp_path, mocker):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    cfg = _minimal_cfg(wt_root)
    chain = [{"provider": "p1", "model": "m1"}]

    fake = MagicMock()
    fake.invoke.return_value = ProviderResult(outcome=Outcome.RATE_LIMITED, detail="429")
    mocker.patch("delegate.orchestrator.build_provider", return_value=fake)

    with pytest.raises(ChainExhausted) as exc:
        run_single_task(
            task_type="code-gen", chain=chain, brief=_brief(), cfg=cfg,
            cwd=repo, task_id="t1", batch_id=None,
        )
    assert exc.value.structured["error"] == "chain_exhausted"
    assert len(exc.value.structured["attempts"]) == 1

def test_hard_fail_zen_trap_stops_chain(tmp_path, mocker):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    wt_root = tmp_path / "wt"
    cfg = _minimal_cfg(wt_root)
    chain = [
        {"provider": "p1", "model": "m1"},
        {"provider": "p2", "model": "m2"},
    ]
    fake = MagicMock()
    fake.invoke.return_value = ProviderResult(outcome=Outcome.ZEN_TRAP, detail="insufficient balance")
    mocker.patch("delegate.orchestrator.build_provider", return_value=fake)

    with pytest.raises(ChainExhausted) as exc:
        run_single_task(
            task_type="code-gen", chain=chain, brief=_brief(), cfg=cfg,
            cwd=repo, task_id="t1", batch_id=None,
        )
    # Only one attempt — zen trap stops the chain.
    assert len(exc.value.structured["attempts"]) == 1
    assert exc.value.structured["attempts"][0]["status"] == "zen_trap"
