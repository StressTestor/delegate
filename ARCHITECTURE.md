# architecture

## what it is

`delegate` is a Python CLI and Claude Code skill that dispatches coding, bulk, and research tasks to non-Claude AI providers. the goal is to conserve Claude usage limits by routing routine work to kimi-code, opencode-go, gemini, and openrouter's free tier.

## stack

| layer | technology | version |
|---|---|---|
| language | Python | 3.13+ |
| config | tomllib (stdlib) | — |
| schema validation | jsonschema (Draft 2020-12) | >=4.22 |
| HTTP client | httpx | >=0.27 |
| date-time validation | rfc3339-validator | >=0.1 |
| testing | pytest, pytest-mock | >=8.2, >=3.14 |
| packaging | setuptools | >=68 |

## directory structure

```
delegate/
├── src/delegate/
│   ├── __init__.py
│   ├── brief.py           # build + validate + render task briefs
│   ├── circuit.py         # sliding-window failure-rate circuit breaker
│   ├── cli.py             # argparse entry point, signal handlers, main()
│   ├── config.py          # TOML loader with deep-merge and chain validation
│   ├── config.default.toml# default provider configs, rpm caps, chains
│   ├── fanout.py          # parallel bulk execution via ThreadPoolExecutor
│   ├── globs.py           # shared glob→regex with ** support
│   ├── logger.py          # JSONL append-only receipt logger
│   ├── orchestrator.py    # single-task chain iteration with worktree merge
│   ├── preflight.py       # CLI/env/git checks before chain runs
│   ├── progress.py        # Heartbeat daemon thread for long-running tasks
│   ├── ratelimit.py       # thread-safe rpm limiter (lock spans sleep)
│   ├── worktree.py        # git worktree lifecycle + categorize + merge
│   ├── schemas/
│   │   ├── brief.schema.json   # validates task brief structure
│   │   ├── error.schema.json   # validates chain_exhausted error payload
│   │   └── log.schema.json     # validates JSONL log entries
│   └── providers/
│       ├── base.py        # Provider ABC, ProviderResult, Outcome enum
│       ├── kimi.py        # kimi-code CLI wrapper
│       ├── opencode.py    # opencode CLI wrapper + zen-trap detection
│       ├── gemini.py      # gemini CLI wrapper
│       └── openrouter.py  # OpenRouter HTTP API + diff-apply loop
├── bin/delegate           # executable shim → delegate.cli:main
├── install/delegate.md    # Claude Code slash command shim
├── install.sh             # idempotent install: pip editable + skill symlink
├── SKILL.md               # skill documentation (usage, chains, billing safety)
├── tests/                 # 114 tests (107 unit + 7 glob + 4 live smoke)
└── pyproject.toml
```

## key patterns

### provider invocation

all providers implement `Provider.invoke(model, brief, prompt, cwd, timeout_s) → ProviderResult`. `Outcome` is a typed enum: `OK`, `RECOVERABLE` (rate-limited, network error), `HARD_FAIL` (zen-trap, allowlist violation). chain iteration in `orchestrator.py` stops on `HARD_FAIL` or first `OK`.

### chain types

| chain | providers (default order) | worktree |
|---|---|---|
| `code-gen` | kimi-code → opencode-go → gemini-pro → openrouter-free | yes |
| `bulk` | openrouter-free → gemini-flash → opencode-go | yes |
| `research` | gemini-pro → opencode-go → openrouter-free | no |

### worktree isolation (code-gen + bulk)

1. `spawn_worktree` — detached HEAD at current SHA, SHA captured before creation
2. provider invokes in the worktree path
3. `merge_worktree` — categorizes changed paths (AUTO_APPROVE / ASK / REJECT), SHA pin check, `git apply --3way`, commit with `Delegated-To:` trailer
4. merges are serialized under `_MERGE_LOCK` (bulk only); SHA is refreshed inside the lock for bulk to account for prior merges advancing HEAD

### billing safety

- **zen-trap**: opencode provider scans combined stdout+stderr for billing error patterns before checking exit code. rc=0 with billing errors → `HARD_FAIL`
- **allowlist**: opencode-go and gemini enforce model allowlists. missing or empty allowlist → `HARD_FAIL` (fail closed, not open)
- **allowlist_suffix**: openrouter enforces `:free` suffix on all models
- **circuit breaker**: sliding deque window, trips at `>threshold` failure rate, halts remaining bulk tasks

### glob matching

`globs.py` provides `glob_to_regex` and `matches_any`. `**` matches zero or more path segments. used by both `categorize_change` (worktree path decisions) and `openrouter._diff_touches_only_allowed` (diff security checks). consistent behavior across both codepaths.

### path security (openrouter)

`_diff_touches_only_allowed` checks ALL 6 path references in a unified diff header: `a/` side, `b/` side, `rename from`, `rename to`, `copy from`, `copy to`. prevents exfiltration via rename/copy tricks (e.g. aliasing `.env` onto an allowlisted write target).

## environment variables

| var | scope | purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | runtime | openrouter provider auth |
| `OPENCODE_API_KEY` | runtime | opencode-go provider auth |
| `GOOGLE_API_KEY` | runtime | gemini CLI auth |
| `DELEGATE_LIVE_TEST` | test | set to `1` to run live smoke tests |

## data flow

```
cli.py
  → load_config (TOML deep-merge, chain validation)
  → build_brief (JSON schema validated)
  → preflight (CLI on PATH, env vars set, git clean)
  → run_single_task (orchestrator) or run_bulk (fanout)
      → spawn_worktree (code-gen/bulk only)
      → for each chain entry:
          → limiter.acquire (rpm cap)
          → Heartbeat (15s stderr ticks)
          → provider.invoke (subprocess or HTTP)
          → logger.write (JSONL receipt)
          → merge_worktree (code-gen/bulk, under _MERGE_LOCK)
      → ChainExhausted (schema-validated) if all providers fail
```

## log format

JSONL at `~/.claude/skills/delegate/state/delegate.jsonl`. each line is a validated log entry:

```json
{
  "ts": "2026-04-19T00:00:00Z",
  "task_id": "abc123",
  "batch_id": null,
  "chain": "code-gen",
  "provider": "kimi-code",
  "model": "kimi-code/kimi-for-coding",
  "status": "ok",
  "duration_s": 42.1,
  "tokens_in": null,
  "tokens_out": null,
  "cost_usd_est": null,
  "worktree": "/Volumes/onn/.delegate-worktrees/20260419-000000-fix-bug",
  "error": null
}
```

## worktree root

default: `/Volumes/onn/.delegate-worktrees/`. worktrees are retained on failure for inspection. cleaned up on successful merge.

## testing

```
pytest              # 114 unit tests (fast, no network, no providers)
DELEGATE_LIVE_TEST=1 pytest tests/test_smoke_*.py   # 4 live provider tests
```

unit tests use real git repos for worktree tests. provider tests mock subprocess. fanout serialization test proves merges are serialized under concurrency.

## known limitations (v0.1)

- `_MERGE_LOCK` is in-process only — no cross-process protection if two delegate instances run simultaneously against the same repo
- openrouter free tier has strict rpm caps (15/min); circuit breaker catches cascading failures
- no retry with backoff inside the chain — next provider is tried immediately on recoverable failure

---

_last updated: 2026-04-19_
