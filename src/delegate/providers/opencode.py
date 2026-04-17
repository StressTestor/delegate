from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

from .base import Outcome, Provider, ProviderResult
from .kimi import RATE_LIMIT_PAT, AUTH_PAT, NETWORK_PAT


class OpencodeProvider(Provider):
    def __init__(self, name: str, cfg: dict[str, Any]):
        super().__init__(name, cfg)
        patterns = cfg.get("zen_fail_patterns", [])
        self._zen_re = re.compile("|".join(patterns), re.I) if patterns else None

    def invoke(
        self,
        *,
        model: str,
        brief: dict[str, Any],
        prompt: str,
        cwd: Path,
        timeout_s: int,
    ) -> ProviderResult:
        allowlist = self.cfg.get("allowlist", [])
        if allowlist and model not in allowlist:
            return ProviderResult(
                outcome=Outcome.ALLOWLIST_VIOLATION,
                detail=f"model '{model}' not in allowlist {allowlist}",
            )
        cli = self.cfg.get("cli", "opencode")
        cmd = [cli, "run", "-m", model, prompt]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_s
            )
        except subprocess.TimeoutExpired:
            return ProviderResult(outcome=Outcome.TIMEOUT, duration_s=timeout_s)
        except FileNotFoundError as e:
            return ProviderResult(outcome=Outcome.CLI_CRASH, detail=f"CLI not found: {e}")

        duration = time.monotonic() - start
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")

        # Zen trap check FIRST — even rc=0 can indicate zen routing.
        if self._zen_re and self._zen_re.search(combined):
            return ProviderResult(
                outcome=Outcome.ZEN_TRAP, duration_s=duration, detail=combined[:500]
            )

        if proc.returncode == 0:
            return ProviderResult(outcome=Outcome.OK, duration_s=duration)
        if RATE_LIMIT_PAT.search(combined):
            return ProviderResult(outcome=Outcome.RATE_LIMITED, duration_s=duration, detail=proc.stderr[:500])
        if AUTH_PAT.search(combined):
            return ProviderResult(outcome=Outcome.AUTH_FAILURE, duration_s=duration, detail=proc.stderr[:500])
        if NETWORK_PAT.search(combined):
            return ProviderResult(outcome=Outcome.NETWORK_ERROR, duration_s=duration, detail=proc.stderr[:500])
        return ProviderResult(outcome=Outcome.CLI_CRASH, duration_s=duration, detail=proc.stderr[:500])
