from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from .base import Outcome, Provider, ProviderResult

MAX_RETRIES = 3
SYSTEM_PROMPT = (
    "You are a code editor. Respond with ONLY a unified diff against the files "
    "provided. No prose, no code fences, just the diff. If you cannot produce a "
    "valid diff, respond with a single line starting with BLOCKER: and exit."
)


def _diff_touches_only_allowed(diff_text: str, write_allowed: list[str], new_file_patterns: list[str]) -> tuple[bool, str]:
    paths = re.findall(r"^diff --git a/\S+ b/(\S+)$", diff_text, re.M)
    if not paths:
        return False, "no diff headers found"
    for p in paths:
        if p in write_allowed:
            continue
        if any(fnmatch.fnmatch(p, pat) for pat in new_file_patterns):
            continue
        return False, f"diff touches disallowed path: {p}"
    return True, ""


class OpenrouterProvider(Provider):
    def invoke(
        self,
        *,
        model: str,
        brief: dict[str, Any],
        prompt: str,
        cwd: Path,
        timeout_s: int,
    ) -> ProviderResult:
        suffix = self.cfg.get("allowlist_suffix", "")
        if suffix and not model.endswith(suffix):
            return ProviderResult(
                outcome=Outcome.ALLOWLIST_VIOLATION,
                detail=f"model '{model}' must end with '{suffix}'",
            )
        api_key = os.environ.get(self.cfg.get("api_key_env", "OPENROUTER_API_KEY"))
        if not api_key:
            return ProviderResult(
                outcome=Outcome.AUTH_FAILURE,
                detail=f"env var {self.cfg.get('api_key_env')} not set",
            )

        url = self.cfg["api"]
        write_allowed = list(brief.get("write_allowed", []))
        new_file_patterns = list(brief.get("new_file_patterns", []))

        file_blocks: list[str] = []
        for rel in brief.get("read", []):
            fp = cwd / rel
            if fp.exists():
                file_blocks.append(f"--- {rel} ---\n{fp.read_text()}")
            else:
                file_blocks.append(f"--- {rel} ---\n(not present; may be new)")
        user_msg = prompt + "\n\n" + "\n\n".join(file_blocks)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        start = time.monotonic()
        last_detail = ""
        total_tokens_in = 0
        total_tokens_out = 0
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = httpx.post(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": messages},
                    timeout=timeout_s,
                )
                resp.raise_for_status()
            except httpx.ConnectError as e:
                return ProviderResult(outcome=Outcome.NETWORK_ERROR, detail=str(e))
            except httpx.TimeoutException as e:
                return ProviderResult(outcome=Outcome.TIMEOUT, detail=str(e))
            except httpx.HTTPStatusError as e:
                sc = e.response.status_code
                if sc == 429:
                    return ProviderResult(outcome=Outcome.RATE_LIMITED, detail=f"HTTP {sc}")
                if sc in (401, 403):
                    return ProviderResult(outcome=Outcome.AUTH_FAILURE, detail=f"HTTP {sc}")
                return ProviderResult(outcome=Outcome.CLI_CRASH, detail=f"HTTP {sc}")

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            total_tokens_in += int(usage.get("prompt_tokens", 0))
            total_tokens_out += int(usage.get("completion_tokens", 0))

            ok, reason = _diff_touches_only_allowed(content, write_allowed, new_file_patterns)
            if not ok:
                last_detail = f"attempt {attempt + 1}: {reason}"
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"Invalid: {reason}. Respond with ONLY a unified diff, nothing else.",
                })
                continue

            check = subprocess.run(
                ["git", "apply", "--check"],
                input=content, text=True, cwd=cwd, capture_output=True,
            )
            if check.returncode != 0:
                last_detail = f"attempt {attempt + 1}: git apply --check: {check.stderr.strip()}"
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"Previous diff failed git apply --check: {check.stderr}. Respond with ONLY a valid unified diff.",
                })
                continue

            apply = subprocess.run(
                ["git", "apply"], input=content, text=True, cwd=cwd, capture_output=True
            )
            if apply.returncode != 0:
                last_detail = f"apply failed: {apply.stderr.strip()}"
                continue

            return ProviderResult(
                outcome=Outcome.OK,
                duration_s=time.monotonic() - start,
                tokens_in=total_tokens_in,
                tokens_out=total_tokens_out,
            )

        return ProviderResult(
            outcome=Outcome.DIFF_INVALID,
            duration_s=time.monotonic() - start,
            detail=last_detail,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
        )
