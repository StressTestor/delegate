from __future__ import annotations

import math
import threading
import uuid
from concurrent.futures import CancelledError, ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .brief import build_brief
from .circuit import CircuitBreaker
from .orchestrator import run_single_task, ChainExhausted


@dataclass
class BulkResult:
    batch_id: str
    success: int = 0
    failed: int = 0
    skipped: int = 0
    circuit_broken: bool = False
    failures: list[dict[str, Any]] = field(default_factory=list)


def _effective_concurrency(user_conc: int, chain: list[dict[str, Any]], cfg: dict[str, Any]) -> int:
    # Use the lowest rpm_cap in the chain as the binding constraint; scale by 0.75.
    caps = [cfg["providers"][e["provider"]].get("rpm_cap", 60) for e in chain]
    min_cap = min(caps) if caps else 60
    return max(1, min(user_conc, math.ceil(min_cap * 0.75)))


def run_bulk(
    *,
    task_type: str,
    chain: list[dict[str, Any]],
    cfg: dict[str, Any],
    cwd: Path,
    files: list[str],
    task_template: str,
    commit_format: str,
    concurrency: int,
) -> BulkResult:
    batch_id = str(uuid.uuid4())
    result = BulkResult(batch_id=batch_id)
    cb_cfg = cfg.get("circuit_breaker", {"window": 10, "failure_threshold": 0.5, "halt_on_trip": True})
    cb = CircuitBreaker(window=cb_cfg["window"], threshold=cb_cfg["failure_threshold"])
    halt = threading.Event()
    eff_conc = _effective_concurrency(concurrency, chain, cfg)

    def _one(file: str) -> tuple[str, bool, str]:
        if halt.is_set():
            return (file, False, "circuit_halted")
        brief = build_brief(
            task=f"{task_template} (file: {file})",
            read=[file], write_allowed=[file], new_file_patterns=[],
            do_not_touch=[], acceptance=["file modified per task"],
            commit_format=commit_format, constraints=[],
        )
        try:
            run_single_task(
                task_type=task_type, chain=chain, brief=brief, cfg=cfg,
                cwd=cwd, task_id=f"{batch_id}:{file}", batch_id=batch_id,
            )
            return (file, True, "")
        except ChainExhausted as e:
            last = e.structured["attempts"][-1] if e.structured["attempts"] else {}
            return (file, False, last.get("status", "unknown"))

    futures: list[Future] = []
    with ThreadPoolExecutor(max_workers=eff_conc) as ex:
        for f in files:
            futures.append(ex.submit(_one, f))

        for fut in futures:
            try:
                file, ok, detail = fut.result()
            except CancelledError:
                result.skipped += 1
                continue
            if detail == "circuit_halted":
                result.skipped += 1
                continue
            cb.record(success=ok)
            if ok:
                result.success += 1
            else:
                result.failed += 1
                result.failures.append({"file": file, "detail": detail})
            if cb.tripped() and cb_cfg.get("halt_on_trip", True):
                result.circuit_broken = True
                halt.set()
                for other in futures:
                    other.cancel()

    return result
