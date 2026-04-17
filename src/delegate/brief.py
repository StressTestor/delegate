from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator

ESCAPE_HATCH = (
    "If blocked or unsure, write your blocker to STDOUT prefixed with "
    "BLOCKER: and exit non-zero. Do not guess."
)


class BriefError(ValueError):
    pass


def _load_schema() -> dict[str, Any]:
    raw = files("delegate.schemas").joinpath("brief.schema.json").read_text()
    return json.loads(raw)


def build_brief(
    *,
    task: str,
    read: list[str],
    write_allowed: list[str],
    new_file_patterns: list[str],
    do_not_touch: list[str],
    acceptance: list[str],
    commit_format: str,
    constraints: list[str],
) -> dict[str, Any]:
    return {
        "brief_version": "1",
        "task": task,
        "read": list(read),
        "write_allowed": list(write_allowed),
        "new_file_patterns": list(new_file_patterns),
        "do_not_touch": list(do_not_touch),
        "acceptance": list(acceptance),
        "commit_format": commit_format,
        "constraints": list(constraints),
        "escape_hatch": ESCAPE_HATCH,
    }


def validate_brief(brief: dict[str, Any]) -> None:
    schema = _load_schema()
    errs = list(Draft202012Validator(schema).iter_errors(brief))
    if errs:
        paths = ", ".join("/".join(str(p) for p in e.absolute_path) or "<root>" for e in errs)
        msg = "; ".join(e.message for e in errs)
        raise BriefError(f"brief validation failed at [{paths}]: {msg}")


def _fmt_list(items: list[str]) -> list[str]:
    return [f"  - {p}" for p in items] or ["  (none)"]


def render_prompt(brief: dict[str, Any]) -> str:
    lines = [
        f"TASK: {brief['task']}",
        "",
        "FILES TO READ:",
        *_fmt_list(brief["read"]),
        "",
        "FILES YOU MAY MODIFY (write_allowed):",
        *_fmt_list(brief["write_allowed"]),
        "",
        "NEW FILE PATTERNS PERMITTED:",
        *_fmt_list(brief["new_file_patterns"]),
        "",
        "DO NOT TOUCH:",
        *_fmt_list(brief["do_not_touch"]),
        "",
        "ACCEPTANCE CRITERIA:",
        *[f"  - {c}" for c in brief["acceptance"]],
        "",
        "CONSTRAINTS:",
        *_fmt_list(brief["constraints"]),
        "",
        f"COMMIT MESSAGE FORMAT: {brief['commit_format']}",
        "",
        f"ESCAPE HATCH: {brief['escape_hatch']}",
    ]
    return "\n".join(lines)
