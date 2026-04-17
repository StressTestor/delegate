import subprocess
from pathlib import Path
from delegate.providers.opencode import OpencodeProvider
from delegate.providers.base import Outcome


OPENCODE_CFG = {
    "cli": "opencode",
    "allowlist": ["glm-5", "kimi-k2.5", "minimax-m2.5"],
    "zen_fail_patterns": [
        "insufficient balance", "no resource package", "quota exceeded",
        "1008", "402", "opencode zen", "pay.?as.?you.?go",
        "billing_hard_limit", "insufficient_quota",
    ],
}


def test_opencode_rejects_non_allowlisted_model_before_invoke(mocker, tmp_path):
    spy = mocker.patch("subprocess.run")
    p = OpencodeProvider("opencode-go", OPENCODE_CFG)
    r = p.invoke(model="not-on-list", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.ALLOWLIST_VIOLATION
    spy.assert_not_called()

def test_opencode_success(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["opencode"], returncode=0, stdout="done", stderr=""
    ))
    p = OpencodeProvider("opencode-go", OPENCODE_CFG)
    r = p.invoke(model="minimax-m2.5", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.OK

def test_opencode_zen_trap_on_insufficient_balance(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["opencode"], returncode=1, stdout="", stderr="Error 1008: insufficient balance"
    ))
    p = OpencodeProvider("opencode-go", OPENCODE_CFG)
    r = p.invoke(model="minimax-m2.5", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.ZEN_TRAP
    assert "insufficient balance" in r.detail

def test_opencode_zen_trap_on_payg_mention(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["opencode"], returncode=0, stdout="routed via pay-as-you-go", stderr=""
    ))
    p = OpencodeProvider("opencode-go", OPENCODE_CFG)
    r = p.invoke(model="minimax-m2.5", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.ZEN_TRAP


def test_opencode_rejects_when_allowlist_missing(mocker, tmp_path):
    spy = mocker.patch("subprocess.run")
    cfg = {"cli": "opencode", "zen_fail_patterns": ["x"]}  # no allowlist key
    p = OpencodeProvider("opencode-go", cfg)
    r = p.invoke(model="anything", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.ALLOWLIST_VIOLATION
    spy.assert_not_called()

def test_opencode_rejects_when_allowlist_empty(mocker, tmp_path):
    spy = mocker.patch("subprocess.run")
    cfg = {"cli": "opencode", "allowlist": [], "zen_fail_patterns": ["x"]}
    p = OpencodeProvider("opencode-go", cfg)
    r = p.invoke(model="anything", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.ALLOWLIST_VIOLATION
    spy.assert_not_called()

def test_opencode_zen_trap_on_bare_1008(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["opencode"], returncode=1, stdout="", stderr="request failed code 1008"
    ))
    p = OpencodeProvider("opencode-go", OPENCODE_CFG)
    r = p.invoke(model="minimax-m2.5", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.ZEN_TRAP

def test_opencode_zen_trap_on_bare_402(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=["opencode"], returncode=1, stdout="", stderr="HTTP 402 required"
    ))
    p = OpencodeProvider("opencode-go", OPENCODE_CFG)
    r = p.invoke(model="minimax-m2.5", brief={}, prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.ZEN_TRAP
