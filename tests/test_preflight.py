import subprocess
import pytest
from pathlib import Path
from delegate.preflight import run_preflight, PreflightError


def _init_repo(path: Path, dirty: bool = False) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "a.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)
    if dirty:
        (path / "a.txt").write_text("changed")


def test_preflight_passes_clean_code_gen(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    chain = [{"provider": "kimi-code", "model": "k2p5"}]
    cfg = {"providers": {"kimi-code": {"cli": "echo"}}, "defaults": {"worktree_root": str(tmp_path / "wt")}}
    run_preflight(task_type="code-gen", cwd=tmp_path, chain=chain, cfg=cfg, dirty_ok=False)

def test_preflight_rejects_dirty_tree_without_flag(tmp_path):
    _init_repo(tmp_path, dirty=True)
    chain = [{"provider": "kimi-code", "model": "k2p5"}]
    cfg = {"providers": {"kimi-code": {"cli": "echo"}}, "defaults": {"worktree_root": str(tmp_path / "wt")}}
    with pytest.raises(PreflightError, match="dirty"):
        run_preflight(task_type="code-gen", cwd=tmp_path, chain=chain, cfg=cfg, dirty_ok=False)

def test_preflight_allows_dirty_with_flag(tmp_path):
    _init_repo(tmp_path, dirty=True)
    chain = [{"provider": "kimi-code", "model": "k2p5"}]
    cfg = {"providers": {"kimi-code": {"cli": "echo"}}, "defaults": {"worktree_root": str(tmp_path / "wt")}}
    run_preflight(task_type="code-gen", cwd=tmp_path, chain=chain, cfg=cfg, dirty_ok=True)

def test_preflight_requires_git_for_code_gen(tmp_path):
    chain = [{"provider": "kimi-code", "model": "k2p5"}]
    cfg = {"providers": {"kimi-code": {"cli": "echo"}}, "defaults": {"worktree_root": str(tmp_path / "wt")}}
    with pytest.raises(PreflightError, match="git repo"):
        run_preflight(task_type="code-gen", cwd=tmp_path, chain=chain, cfg=cfg, dirty_ok=False)

def test_preflight_skips_git_for_research(tmp_path):
    chain = [{"provider": "kimi-code", "model": "k2p5"}]
    cfg = {"providers": {"kimi-code": {"cli": "echo"}}, "defaults": {"worktree_root": str(tmp_path / "wt")}}
    run_preflight(task_type="research", cwd=tmp_path, chain=chain, cfg=cfg, dirty_ok=False)

def test_preflight_requires_openrouter_key_when_chained(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    chain = [{"provider": "openrouter-free", "model": "x:free"}]
    cfg = {
        "providers": {"openrouter-free": {"api_key_env": "OPENROUTER_API_KEY"}},
        "defaults": {"worktree_root": str(tmp_path / "wt")},
    }
    with pytest.raises(PreflightError, match="OPENROUTER_API_KEY"):
        run_preflight(task_type="code-gen", cwd=tmp_path, chain=chain, cfg=cfg, dirty_ok=False)

def test_preflight_requires_cli_on_path(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    chain = [{"provider": "kimi-code", "model": "k2p5"}]
    cfg = {"providers": {"kimi-code": {"cli": "this-cli-does-not-exist-xyz-12345"}}, "defaults": {"worktree_root": str(tmp_path / "wt")}}
    with pytest.raises(PreflightError, match="not on PATH"):
        run_preflight(task_type="code-gen", cwd=tmp_path, chain=chain, cfg=cfg, dirty_ok=False)
