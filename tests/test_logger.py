import json
from pathlib import Path
import pytest
from delegate.logger import Logger, LogValidationError


def test_logger_writes_jsonl(tmp_path):
    log_file = tmp_path / "delegate.jsonl"
    lg = Logger(log_file)
    lg.write({
        "ts": "2026-04-17T14:00:00Z",
        "task_id": "t1",
        "batch_id": None,
        "chain": "code-gen",
        "provider": "kimi-code",
        "model": "k2p5",
        "status": "ok",
    })
    lg.write({
        "ts": "2026-04-17T14:00:01Z",
        "task_id": "t1",
        "batch_id": None,
        "chain": "code-gen",
        "provider": "opencode-go",
        "model": "minimax-m2.5",
        "status": "rate_limited",
    })
    lines = log_file.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["provider"] == "kimi-code"
    assert json.loads(lines[1])["status"] == "rate_limited"

def test_logger_creates_parent_dir(tmp_path):
    log_file = tmp_path / "nested/dir/delegate.jsonl"
    lg = Logger(log_file)
    lg.write({"ts": "2026-04-17T14:00:00Z", "task_id": "x", "chain": "code-gen",
              "provider": "p", "model": "m", "status": "ok"})
    assert log_file.exists()

def test_logger_validates_against_schema(tmp_path):
    lg = Logger(tmp_path / "l.jsonl")
    with pytest.raises(LogValidationError):
        lg.write({"ts": "t", "provider": "p"})  # missing required fields

def test_logger_rejects_invalid_ts_format(tmp_path):
    # ts must be a valid date-time (format_checker enabled).
    lg = Logger(tmp_path / "l.jsonl")
    with pytest.raises(LogValidationError):
        lg.write({"ts": "not-a-date", "task_id": "x", "chain": "code-gen",
                  "provider": "p", "model": "m", "status": "ok"})

def test_logger_rejects_negative_duration(tmp_path):
    lg = Logger(tmp_path / "l.jsonl")
    with pytest.raises(LogValidationError):
        lg.write({"ts": "2026-04-17T14:00:00Z", "task_id": "x", "chain": "code-gen",
                  "provider": "p", "model": "m", "status": "ok", "duration_s": -1.0})
