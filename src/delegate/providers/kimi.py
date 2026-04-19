from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

from .base import Outcome, Provider, ProviderResult

RATE_LIMIT_PAT = re.compile(r"\b(429|rate.?limit|too many requests)\b", re.I)
AUTH_PAT = re.compile(r"\b(401|403|unauthori[sz]ed|auth.*fail|token.*invalid|token.*expired)\b", re.I)
NETWORK_PAT = re.compile(r"\b(connection refused|dns|tls handshake|unexpected eof|econnreset)\b", re.I)


class KimiProvider(Provider):
    def invoke(
        self,
        *,
        model: str,
        brief: dict[str, Any],
        prompt: str,
        cwd: Path,
        timeout_s: int,
    ) -> ProviderResult:
        cli = self.cfg.get("cli", "kimi-code")
        cmd = [cli, "-m", model, "-y", "-p", prompt]
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

        if proc.returncode == 0:
            return ProviderResult(outcome=Outcome.OK, duration_s=duration)
        if RATE_LIMIT_PAT.search(combined):
            return ProviderResult(outcome=Outcome.RATE_LIMITED, duration_s=duration, detail=proc.stderr[:500])
        if AUTH_PAT.search(combined):
            return ProviderResult(outcome=Outcome.AUTH_FAILURE, duration_s=duration, detail=proc.stderr[:500])
        if NETWORK_PAT.search(combined):
            return ProviderResult(outcome=Outcome.NETWORK_ERROR, duration_s=duration, detail=proc.stderr[:500])
        return ProviderResult(outcome=Outcome.CLI_CRASH, duration_s=duration, detail=proc.stderr[:500])
