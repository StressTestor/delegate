"""Live smoke tests for opencode, gemini, and openrouter providers.

Gated behind DELEGATE_LIVE_TEST=1.
  - opencode: requires `opencode` CLI on PATH + OPENCODE_API_KEY set
  - gemini: requires `gemini` CLI on PATH and logged in
  - openrouter: requires OPENROUTER_API_KEY set
"""
from __future__ import annotations

import os
import subprocess
import pytest
from pathlib import Path

from delegate.providers.opencode import OpencodeProvider
from delegate.providers.gemini import GeminiProvider
from delegate.providers.openrouter import OpenrouterProvider
from delegate.providers.base import Outcome

LIVE = os.environ.get("DELEGATE_LIVE_TEST") == "1"
pytestmark = pytest.mark.skipif(not LIVE, reason="set DELEGATE_LIVE_TEST=1 to run live smoke tests")

HELLO_PY = 'def greet(name: str) -> str:\n    return f"Hello, {name}!"\n'
TASK = 'Add a one-line docstring """Return a greeting string.""" inside the greet function body, on the line immediately after def greet. Do not change anything else.'

OPENCODE_CFG = {
    "cli": "opencode",
    "allowlist": ["opencode-go/glm-5", "opencode-go/kimi-k2.5", "opencode-go/minimax-m2.5"],
    "zen_fail_patterns": [
        "insufficient balance", "no resource package", "quota exceeded",
        "1008", "402", "opencode zen", "pay.?as.?you.?go",
        "billing_hard_limit", "insufficient_quota",
    ],
}

GEMINI_CFG = {
    "cli": "gemini",
    "model_flag": "-m",
    "allowlist": ["gemini-2.5-flash", "gemini-2.5-pro"],
}

OPENROUTER_CFG = {
    "api": "https://openrouter.ai/api/v1/chat/completions",
    "key_endpoint": "https://openrouter.ai/api/v1/key",
    "api_key_env": "OPENROUTER_API_KEY",
    "allowlist_suffix": ":free",
}


def _make_git_repo(path: Path) -> None:
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "smoke@delegate.local"],
        ["git", "config", "user.name", "Smoke"],
    ):
        subprocess.run(cmd, cwd=path, check=True, capture_output=True)
    (path / "hello.py").write_text(HELLO_PY)
    subprocess.run(["git", "add", "hello.py"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_opencode_smoke(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text(HELLO_PY)
    provider = OpencodeProvider("opencode-go", OPENCODE_CFG)
    result = provider.invoke(
        model="opencode-go/minimax-m2.5",
        brief={"read": ["hello.py"], "write_allowed": ["hello.py"]},
        prompt=TASK,
        cwd=tmp_path,
        timeout_s=180,
    )
    assert result.is_success(), (
        f"opencode returned {result.outcome.value}: {result.detail!r}"
    )
    content = (tmp_path / "hello.py").read_text()
    assert "Return a greeting string" in content, f"docstring not added; file:\n{content}"


def test_gemini_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # gemini CLI needs GEMINI_API_KEY; GOOGLE_API_KEY is the same credential.
    if not os.environ.get("GEMINI_API_KEY") and os.environ.get("GOOGLE_API_KEY"):
        monkeypatch.setenv("GEMINI_API_KEY", os.environ["GOOGLE_API_KEY"])
    (tmp_path / "hello.py").write_text(HELLO_PY)
    provider = GeminiProvider("gemini-flash", GEMINI_CFG)
    result = provider.invoke(
        model="gemini-2.5-flash",
        brief={"read": ["hello.py"], "write_allowed": ["hello.py"]},
        prompt=TASK,
        cwd=tmp_path,
        timeout_s=120,
    )
    assert result.is_success(), (
        f"gemini returned {result.outcome.value}: {result.detail!r}"
    )
    content = (tmp_path / "hello.py").read_text()
    assert "Return a greeting string" in content, f"docstring not added; file:\n{content}"


def test_openrouter_smoke(tmp_path: Path) -> None:
    _make_git_repo(tmp_path)
    brief = {
        "read": ["hello.py"],
        "write_allowed": ["hello.py"],
        "new_file_patterns": [],
    }
    provider = OpenrouterProvider("openrouter-free", OPENROUTER_CFG)
    result = provider.invoke(
        model="qwen/qwen3-coder:free",
        brief=brief,
        prompt=TASK,
        cwd=tmp_path,
        timeout_s=120,
    )
    # RATE_LIMITED means auth works and the API is reachable — acceptable on free tier.
    reachable = result.is_success() or result.outcome == Outcome.RATE_LIMITED
    assert reachable, (
        f"openrouter returned {result.outcome.value}: {result.detail!r}"
    )
    if result.is_success():
        content = (tmp_path / "hello.py").read_text()
        assert "greet" in content, "hello.py was cleared or truncated"
