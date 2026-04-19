from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import uuid
from pathlib import Path
from typing import Any

from .brief import build_brief, validate_brief
from .config import load_config
from .fanout import run_bulk
from .orchestrator import run_single_task, ChainExhausted
from .preflight import run_preflight


def _csv(s: str) -> list[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


_INTERRUPTED = False


def is_interrupted() -> bool:
    return _INTERRUPTED


def _handle_sigint(signum, frame):
    global _INTERRUPTED
    _INTERRUPTED = True


def install_signal_handlers() -> None:
    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="delegate")
    p.add_argument("task", nargs="?", default=None, help="task description (positional)")
    p.add_argument("--type", choices=["code-gen", "bulk", "research"], default="code-gen")
    p.add_argument("--provider", default=None, help="pin to single provider (no fallback)")
    p.add_argument("--read", type=_csv, default=[])
    p.add_argument("--write", type=_csv, default=[])
    p.add_argument("--new-files", type=_csv, default=[], dest="new_files", help="permitted new-file glob patterns")
    p.add_argument("--do-not-touch", type=_csv, default=[".env*"], dest="do_not_touch")
    p.add_argument("--accept", action="append", default=[], help="acceptance criterion (repeatable)")
    p.add_argument("--constraint", action="append", default=[], help="constraint (repeatable)")
    p.add_argument("--commit-format", default=None, dest="commit_format")
    p.add_argument("--dirty-ok", action="store_true", dest="dirty_ok")
    p.add_argument("--brief", default=None, help="path to JSON brief file (overrides other flags)")
    # Bulk-specific:
    p.add_argument("--files", default=None, help="bulk: glob of files")
    p.add_argument("--task-template", dest="task_template", default=None, help="bulk: task template")
    p.add_argument("--concurrency", type=int, default=1)
    # Misc:
    p.add_argument("--user-config", default="~/.config/delegate/config.toml", dest="user_config")
    return p.parse_args(argv)


def build_brief_from_args(args: argparse.Namespace) -> dict[str, Any]:
    task = args.task or args.task_template or ""
    commit_format = args.commit_format or f"chore(delegate): {task[:60]}"
    return build_brief(
        task=task,
        read=args.read,
        write_allowed=args.write,
        new_file_patterns=args.new_files,
        do_not_touch=args.do_not_touch,
        acceptance=args.accept or ["task completed per description"],
        commit_format=commit_format,
        constraints=args.constraint,
    )


def _resolve_chain(args: argparse.Namespace, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    if args.provider:
        pcfg = cfg["providers"].get(args.provider)
        if not pcfg:
            raise SystemExit(f"unknown provider: {args.provider}")
        model = pcfg.get("default_model") or (pcfg.get("allowlist", [""])[0] if pcfg.get("allowlist") else "")
        if not model:
            raise SystemExit(f"provider {args.provider} has no default_model and no allowlist")
        return [{"provider": args.provider, "model": model}]
    return list(cfg["chains"][args.type])


def main(argv: list[str] | None = None) -> int:
    install_signal_handlers()
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    args = parse_args(argv)

    cfg = load_config(user_config_path=Path(args.user_config).expanduser())

    if args.brief:
        brief = json.loads(Path(args.brief).read_text())
        validate_brief(brief)
    else:
        if not args.task and args.type != "bulk":
            print("error: task (positional) required unless --brief or --type bulk", file=sys.stderr)
            return 2
        if args.type != "bulk":
            brief = build_brief_from_args(args)
            validate_brief(brief)
        else:
            brief = None

    chain = _resolve_chain(args, cfg)
    cwd = Path.cwd()

    try:
        run_preflight(
            task_type=args.type, cwd=cwd, chain=chain, cfg=cfg, dirty_ok=args.dirty_ok,
        )
    except Exception as e:
        print(f"preflight failed: {e}", file=sys.stderr)
        return 2

    task_id = str(uuid.uuid4())

    try:
        if args.type == "bulk":
            import glob
            files = glob.glob(args.files, recursive=True) if args.files else []
            result = run_bulk(
                task_type="bulk", chain=chain, cfg=cfg, cwd=cwd,
                files=files, task_template=args.task_template or args.task or "",
                commit_format=args.commit_format or "chore(delegate): bulk",
                concurrency=args.concurrency,
            )
            print(json.dumps({
                "batch_id": result.batch_id,
                "success": result.success,
                "failed": result.failed,
                "skipped": result.skipped,
                "circuit_broken": result.circuit_broken,
            }, indent=2))
            return 1 if (result.failed or result.circuit_broken) else 0
        else:
            result = run_single_task(
                task_type=args.type, chain=chain, brief=brief, cfg=cfg,
                cwd=cwd, task_id=task_id, batch_id=None,
            )
            print(json.dumps(result, indent=2))
            return 0
    except ChainExhausted as e:
        print(json.dumps(e.structured, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
