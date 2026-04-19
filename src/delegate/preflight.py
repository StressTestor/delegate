from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


class PreflightError(RuntimeError):
    pass


def _is_git_repo(cwd: Path) -> bool:
    r = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and r.stdout.strip() == "true"


def _is_dirty(cwd: Path) -> bool:
    r = subprocess.run(
        ["git", "-C", str(cwd), "status", "--porcelain"],
        check=True, capture_output=True, text=True,
    )
    return bool(r.stdout.strip())


def run_preflight(
    *,
    task_type: str,
    cwd: Path,
    chain: list[dict[str, Any]],
    cfg: dict[str, Any],
    dirty_ok: bool,
) -> None:
    providers = cfg.get("providers", {})
    # 1. CLIs on PATH (for CLI providers in the chain).
    for entry in chain:
        pcfg = providers.get(entry["provider"], {})
        cli = pcfg.get("cli")
        if cli and not shutil.which(cli):
            raise PreflightError(f"CLI '{cli}' (provider {entry['provider']}) not on PATH")
    # 2. Env vars (openrouter).
    for entry in chain:
        pcfg = providers.get(entry["provider"], {})
        env_var = pcfg.get("api_key_env")
        if env_var and not os.environ.get(env_var):
            raise PreflightError(f"env var {env_var} not set (required by {entry['provider']})")
    # 3. Git repo required for code-gen and bulk.
    if task_type in ("code-gen", "bulk"):
        if not _is_git_repo(cwd):
            raise PreflightError(f"{cwd} is not inside a git repo (required for {task_type})")
        if _is_dirty(cwd) and not dirty_ok:
            raise PreflightError(
                f"git tree at {cwd} is dirty; pass --dirty-ok to proceed anyway"
            )
    # 4. worktree_root writable.
    if task_type in ("code-gen", "bulk"):
        wt_root = Path(os.path.expanduser(cfg["defaults"]["worktree_root"]))
        try:
            wt_root.mkdir(parents=True, exist_ok=True)
            test_file = wt_root / ".preflight-probe"
            test_file.write_text("x")
            test_file.unlink()
        except OSError as e:
            raise PreflightError(f"worktree_root {wt_root} not writable: {e}") from e
