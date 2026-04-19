"""Live smoke test for the kimi-code provider.

Gated behind DELEGATE_LIVE_TEST=1 — requires kimi-code CLI installed and logged in.
"""
from __future__ import annotations

import os
import pytest
from pathlib import Path

from delegate.providers.kimi import KimiProvider
from delegate.providers.base import Outcome

LIVE = os.environ.get("DELEGATE_LIVE_TEST") == "1"
pytestmark = pytest.mark.skipif(not LIVE, reason="set DELEGATE_LIVE_TEST=1 to run live smoke tests")

HELLO_PY = 'def greet(name: str) -> str:\n    return f"Hello, {name}!"\n'
TASK = 'Add a one-line docstring """Return a greeting string.""" inside the greet function body, on the line immediately after def greet. Do not change anything else.'


def test_kimi_smoke(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text(HELLO_PY)
    provider = KimiProvider("kimi-code", {"cli": "kimi-code"})
    result = provider.invoke(
        model="kimi-code/kimi-for-coding",
        brief={"read": ["hello.py"], "write_allowed": ["hello.py"]},
        prompt=TASK,
        cwd=tmp_path,
        timeout_s=120,
    )
    assert result.is_success(), (
        f"kimi-code returned {result.outcome.value}: {result.detail!r}"
    )
    # Verify the file was actually touched.
    content = (tmp_path / "hello.py").read_text()
    assert "Return a greeting string" in content, f"docstring not added; file:\n{content}"
