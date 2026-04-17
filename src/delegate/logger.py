from __future__ import annotations

import json
import threading
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class LogValidationError(ValueError):
    pass


def _load_validator() -> Draft202012Validator:
    raw = files("delegate.schemas").joinpath("log.schema.json").read_text()
    return Draft202012Validator(
        json.loads(raw),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


class Logger:
    """Append-only JSONL logger with schema validation."""

    def __init__(self, path: Path):
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._validator = _load_validator()

    def write(self, entry: dict[str, Any]) -> None:
        errs = list(self._validator.iter_errors(entry))
        if errs:
            raise LogValidationError(
                "log entry invalid: " + "; ".join(e.message for e in errs)
            )
        line = json.dumps(entry, separators=(",", ":"))
        with self._lock:
            with self._path.open("a") as f:
                f.write(line + "\n")
