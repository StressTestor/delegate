import subprocess
from pathlib import Path
from delegate.providers.gemini import GeminiProvider
from delegate.providers.base import Outcome


def test_gemini_success_passes_model_flag(mocker, tmp_path):
    mock_run = mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["gemini"], returncode=0, stdout="done", stderr=""
    ))
    p = GeminiProvider("gemini-pro", {"cli": "gemini", "model_flag": "-m"})
    p.invoke(model="gemini-2.5-pro", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    called_args = mock_run.call_args.args[0]
    assert called_args == ["gemini", "-m", "gemini-2.5-pro", "-y", "-p", "x"]

def test_gemini_cli_crash(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["gemini"], returncode=1, stdout="", stderr="boom"
    ))
    p = GeminiProvider("gemini-pro", {"cli": "gemini", "model_flag": "-m"})
    r = p.invoke(model="gemini-2.5-pro", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.CLI_CRASH

def test_gemini_timeout(mocker, tmp_path):
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="gemini", timeout=1))
    p = GeminiProvider("gemini-pro", {"cli": "gemini", "model_flag": "-m"})
    r = p.invoke(model="gemini-2.5-pro", brief={}, prompt="x", cwd=tmp_path, timeout_s=1)
    assert r.outcome == Outcome.TIMEOUT

def test_gemini_rate_limit(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["gemini"], returncode=1, stdout="", stderr="HTTP 429 rate limit exceeded"
    ))
    p = GeminiProvider("gemini-pro", {"cli": "gemini", "model_flag": "-m"})
    r = p.invoke(model="gemini-2.5-pro", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.RATE_LIMITED
