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
    assert "-m" in called_args
    assert "gemini-2.5-pro" in called_args
    assert "-p" in called_args
    assert "-y" in called_args

def test_gemini_cli_crash(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["gemini"], returncode=1, stdout="", stderr="boom"
    ))
    p = GeminiProvider("gemini-pro", {"cli": "gemini", "model_flag": "-m"})
    r = p.invoke(model="gemini-2.5-pro", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.CLI_CRASH
