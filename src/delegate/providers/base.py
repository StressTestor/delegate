from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Outcome(str, Enum):
    OK = "ok"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILURE = "auth_failure"
    TIMEOUT = "timeout"
    CLI_CRASH = "cli_crash"
    NETWORK_ERROR = "network_error"
    ZEN_TRAP = "zen_trap"
    ALLOWLIST_VIOLATION = "allowlist_violation"
    DIFF_INVALID = "diff_invalid"


RECOVERABLE = {
    Outcome.RATE_LIMITED,
    Outcome.AUTH_FAILURE,
    Outcome.TIMEOUT,
    Outcome.CLI_CRASH,
    Outcome.NETWORK_ERROR,
    Outcome.DIFF_INVALID,
}

HARD_FAIL = {Outcome.ZEN_TRAP, Outcome.ALLOWLIST_VIOLATION}


@dataclass
class ProviderResult:
    outcome: Outcome
    duration_s: float = 0.0
    detail: str = ""
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd_est: float | None = None

    def is_success(self) -> bool:
        return self.outcome == Outcome.OK

    def is_recoverable(self) -> bool:
        return self.outcome in RECOVERABLE

    def is_hard_fail(self) -> bool:
        return self.outcome in HARD_FAIL


class Provider(ABC):
    """Abstract provider interface."""

    def __init__(self, name: str, cfg: dict[str, Any]):
        self.name = name
        self.cfg = cfg

    @abstractmethod
    def invoke(
        self,
        *,
        model: str,
        brief: dict[str, Any],
        prompt: str,
        cwd: Path,
        timeout_s: int,
    ) -> ProviderResult:
        """Invoke the provider on the given brief. cwd is the worktree (or original cwd for research)."""
        raise NotImplementedError
