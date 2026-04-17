from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from .base import Outcome, Provider, ProviderResult
from .kimi import RATE_LIMIT_PAT, AUTH_PAT, NETWORK_PAT


class GeminiProvider(Provider):
    def invoke(
        self,
        *,
        model: str,
        brief: dict[str, Any],
        prompt: str,
        cwd: Path,
        timeout_s: int,
    ) -> ProviderResult:
        cli = self.cfg.get("cli", "gemini")
        model_flag = self.cfg.get("model_flag", "-m")
        cmd = [cli, model_flag, model, "-p", prompt, "-y"]
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
