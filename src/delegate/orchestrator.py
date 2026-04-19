from __future__ import annotations

import datetime
import json
import subprocess
import threading
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from importlib.resources import files

from .brief import render_prompt
from .logger import Logger
from .providers import build_provider
from .ratelimit import RateLimiter
from .worktree import (
    spawn_worktree, reset_worktree, merge_worktree,
    MergeOutcome, ShaMismatch, MergeAborted,
)

# Load and compile error schema once at import time.
_ERROR_SCHEMA = json.loads(
    files("delegate.schemas").joinpath("error.schema.json").read_text()
)
_ERROR_VALIDATOR = Draft202012Validator(_ERROR_SCHEMA)


_LIMITERS: dict[str, RateLimiter] = {}
_MERGE_LOCK = threading.Lock()


def _limiter_for(pname: str, pcfg: dict[str, Any]) -> RateLimiter:
    return _LIMITERS.setdefault(pname, RateLimiter(rpm=int(pcfg.get("rpm_cap", 60))))


class ChainExhausted(RuntimeError):
    def __init__(self, structured: dict[str, Any]):
        super().__init__(structured["error"])
        self.structured = structured


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _needs_worktree(task_type: str) -> bool:
    return task_type in ("code-gen", "bulk")


def run_single_task(
    *,
    task_type: str,
    chain: list[dict[str, Any]],
    brief: dict[str, Any],
    cfg: dict[str, Any],
    cwd: Path,
    task_id: str,
    batch_id: str | None,
) -> dict[str, Any]:
    logger = Logger(Path(cfg["defaults"]["log_path"]).expanduser())
    timeout_s = cfg["timeouts"].get(task_type, 600)
    worktree_root = Path(cfg["defaults"]["worktree_root"]).expanduser()
    prompt = render_prompt(brief)

    attempts: list[dict[str, Any]] = []
    worktrees_retained: list[str] = []

    wt = None
    if _needs_worktree(task_type):
        wt = spawn_worktree(cwd=cwd, worktree_root=worktree_root, task_slug=brief["task"])

    invoke_cwd = wt.path if wt else cwd

    for entry in chain:
        pname = entry["provider"]
        model = entry["model"]
        pcfg = cfg["providers"][pname]
        provider = build_provider(pname, pcfg)

        if wt:
            reset_worktree(wt)
            (wt.path / ".delegate-brief.json").write_text(json.dumps(brief, indent=2))

        _limiter_for(pname, pcfg).acquire()
        result = provider.invoke(
            model=model, brief=brief, prompt=prompt, cwd=invoke_cwd, timeout_s=timeout_s,
        )

        if wt:
            (wt.path / ".delegate-brief.json").unlink(missing_ok=True)

        # ALWAYS write log line first, before any fail decision.
        log_entry = {
            "ts": _now_iso(),
            "task_id": task_id,
            "batch_id": batch_id,
            "chain": task_type,
            "provider": pname,
            "model": model,
            "status": result.outcome.value,
            "duration_s": result.duration_s,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "cost_usd_est": result.cost_usd_est,
            "worktree": str(wt.path) if wt else None,
            "error": result.detail or None,
        }
        logger.write(log_entry)
        attempts.append({
            "provider": pname,
            "model": model,
            "status": result.outcome.value,
            "detail": result.detail or "",
        })

        if result.is_success():
            if wt:
                try:
                    with _MERGE_LOCK:
                        if batch_id is not None:
                            # Bulk: prior merges in the same batch advanced HEAD;
                            # refresh so SHA pin passes for this task.
                            wt.base_sha = subprocess.run(
                                ["git", "-C", str(cwd), "rev-parse", "HEAD"],
                                check=True, capture_output=True, text=True,
                            ).stdout.strip()
                        merge_outcome = merge_worktree(
                            wt, cwd=cwd,
                            write_allowed=brief["write_allowed"],
                            new_file_patterns=brief["new_file_patterns"],
                            do_not_touch=brief["do_not_touch"],
                            commit_format=brief["commit_format"],
                            delegated_to=f"{pname}/{model}",
                            ask_fn=None,
                        )
                    if merge_outcome == MergeOutcome.MERGED:
                        return {"status": "ok", "provider": pname, "model": model, "task_id": task_id}
                    else:
                        attempts[-1]["status"] = "ask_declined"
                        attempts[-1]["detail"] = "user declined merge"
                        worktrees_retained.append(str(wt.path))
                        break
                except ShaMismatch as e:
                    attempts[-1]["status"] = "sha_mismatch"
                    attempts[-1]["detail"] = str(e)
                    worktrees_retained.append(str(wt.path))
                    # Update log with corrected status.
                    log_entry["status"] = "sha_mismatch"
                    log_entry["error"] = str(e)
                    logger.write(log_entry)
                    break
                except MergeAborted as e:
                    attempts[-1]["status"] = "merge_aborted"
                    attempts[-1]["detail"] = str(e)
                    worktrees_retained.append(str(wt.path))
                    break
            else:
                return {"status": "ok", "provider": pname, "model": model, "task_id": task_id}

        if result.is_hard_fail():
            if wt:
                worktrees_retained.append(str(wt.path))
            break

        # Recoverable: keep going, reset will happen at top of next iter.

    structured = {
        "error": "chain_exhausted",
        "chain": task_type,
        "task_id": task_id,
        "attempts": attempts,
        "worktrees_retained": worktrees_retained,
        "next_steps": (
            "Review attempts above. Decide whether to retry, fix config, or abort. "
            "No automatic Claude fallback."
        ),
    }
    # Validate structured error against schema before raising — fail loud if malformed.
    errors = list(_ERROR_VALIDATOR.iter_errors(structured))
    if errors:
        raise RuntimeError(
            f"BUG: chain_exhausted structured error failed schema validation: "
            + "; ".join(e.message for e in errors)
        )
    raise ChainExhausted(structured)
