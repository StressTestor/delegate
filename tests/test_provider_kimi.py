import subprocess
from pathlib import Path
from delegate.providers.kimi import KimiProvider
from delegate.providers.base import Outcome


def test_kimi_success(mocker, tmp_path):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = subprocess.CompletedProcess(
        args=["kimi"], returncode=0, stdout="done", stderr=""
    )
    p = KimiProvider("kimi-code", {"cli": "kimi"})
    r = p.invoke(model="k2p5", brief={}, prompt="do x", cwd=tmp_path, timeout_s=60)
    assert r.outcome == Outcome.OK

def test_kimi_cli_crash(mocker, tmp_path):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = subprocess.CompletedProcess(
        args=["kimi"], returncode=1, stdout="", stderr="boom"
    )
    p = KimiProvider("kimi-code", {"cli": "kimi"})
    r = p.invoke(model="k2p5", brief={}, prompt="x", cwd=tmp_path, timeout_s=60)
    assert r.outcome == Outcome.CLI_CRASH
    assert "boom" in r.detail

def test_kimi_timeout(mocker, tmp_path):
    mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="kimi", timeout=1))
    p = KimiProvider("kimi-code", {"cli": "kimi"})
    r = p.invoke(model="k2p5", brief={}, prompt="x", cwd=tmp_path, timeout_s=1)
    assert r.outcome == Outcome.TIMEOUT

def test_kimi_rate_limit_detected_in_stderr(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["kimi"], returncode=2, stdout="", stderr="HTTP 429 rate limit exceeded"
    ))
    p = KimiProvider("kimi-code", {"cli": "kimi"})
    r = p.invoke(model="k2p5", brief={}, prompt="x", cwd=tmp_path, timeout_s=60)
    assert r.outcome == Outcome.RATE_LIMITED


def test_kimi_invokes_correct_argv(mocker, tmp_path):
    mock_run = mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    ))
    p = KimiProvider("kimi-code", {"cli": "kimi"})
    p.invoke(model="k2p5", brief={}, prompt="do x", cwd=tmp_path, timeout_s=60)
    args, kwargs = mock_run.call_args
    assert args[0] == ["kimi", "-m", "k2p5", "-p", "do x"]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["timeout"] == 60
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True

def test_kimi_cli_not_found(mocker, tmp_path):
    mocker.patch("subprocess.run", side_effect=FileNotFoundError(2, "No such file", "kimi"))
    p = KimiProvider("kimi-code", {"cli": "kimi"})
    r = p.invoke(model="k2p5", brief={}, prompt="x", cwd=tmp_path, timeout_s=60)
    assert r.outcome == Outcome.CLI_CRASH
    assert "CLI not found" in r.detail

def test_kimi_auth_failure(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["kimi"], returncode=1, stdout="", stderr="HTTP 401 Unauthorized"
    ))
    p = KimiProvider("kimi-code", {"cli": "kimi"})
    r = p.invoke(model="k2p5", brief={}, prompt="x", cwd=tmp_path, timeout_s=60)
    assert r.outcome == Outcome.AUTH_FAILURE

def test_kimi_network_error(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["kimi"], returncode=1, stdout="", stderr="connection refused"
    ))
    p = KimiProvider("kimi-code", {"cli": "kimi"})
    r = p.invoke(model="k2p5", brief={}, prompt="x", cwd=tmp_path, timeout_s=60)
    assert r.outcome == Outcome.NETWORK_ERROR
