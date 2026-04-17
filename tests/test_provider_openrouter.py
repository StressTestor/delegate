import subprocess
from pathlib import Path
from unittest.mock import MagicMock
import httpx
from delegate.providers.openrouter import OpenrouterProvider
from delegate.providers.base import Outcome


CFG = {
    "api": "https://openrouter.ai/api/v1/chat/completions",
    "api_key_env": "OPENROUTER_API_KEY",
    "allowlist_suffix": ":free",
}

VALID_DIFF = """diff --git a/foo.txt b/foo.txt
index e69de29..d95f3ad 100644
--- a/foo.txt
+++ b/foo.txt
@@ -0,0 +1 @@
+hello
"""


def _mock_response(content: str, status_code: int = 200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    resp.raise_for_status = MagicMock()
    return resp


def test_rejects_model_without_free_suffix(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    p = OpenrouterProvider("openrouter-free", CFG)
    r = p.invoke(model="openai/gpt-4", brief={"read": [], "write_allowed": [], "new_file_patterns": []},
                 prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.ALLOWLIST_VIOLATION

def test_missing_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    p = OpenrouterProvider("openrouter-free", CFG)
    r = p.invoke(model="x:free", brief={"read": [], "write_allowed": [], "new_file_patterns": []},
                 prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.AUTH_FAILURE

def test_network_error(monkeypatch, mocker, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    mocker.patch("httpx.post", side_effect=httpx.ConnectError("refused"))
    p = OpenrouterProvider("openrouter-free", CFG)
    r = p.invoke(model="x:free", brief={"read": [], "write_allowed": [], "new_file_patterns": []},
                 prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.NETWORK_ERROR

def test_rate_limited(monkeypatch, mocker, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    mock_resp = _mock_response("", status_code=429)
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=mock_resp
    )
    mocker.patch("httpx.post", return_value=mock_resp)
    p = OpenrouterProvider("openrouter-free", CFG)
    r = p.invoke(model="x:free", brief={"read": [], "write_allowed": [], "new_file_patterns": []},
                 prompt="x", cwd=tmp_path, timeout_s=30)
    assert r.outcome == Outcome.RATE_LIMITED

def test_apply_valid_diff(monkeypatch, mocker, tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "foo.txt").write_text("")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True)

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    mocker.patch("httpx.post", return_value=_mock_response(VALID_DIFF))
    p = OpenrouterProvider("openrouter-free", CFG)
    r = p.invoke(
        model="x:free",
        brief={"read": ["foo.txt"], "write_allowed": ["foo.txt"], "new_file_patterns": []},
        prompt="add hello",
        cwd=tmp_path,
        timeout_s=30,
    )
    assert r.outcome == Outcome.OK
    assert (tmp_path / "foo.txt").read_text() == "hello\n"

def test_invalid_diff_exhausts_retries(monkeypatch, mocker, tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    mocker.patch("httpx.post", return_value=_mock_response("not a diff"))
    p = OpenrouterProvider("openrouter-free", CFG)
    r = p.invoke(
        model="x:free",
        brief={"read": [], "write_allowed": [], "new_file_patterns": []},
        prompt="x",
        cwd=tmp_path,
        timeout_s=30,
    )
    assert r.outcome == Outcome.DIFF_INVALID
