# delegate

dispatch coding, bulk, and research tasks to non-Claude providers. conserve Claude usage limits by routing routine work to kimi-code, opencode-go, gemini, and openrouter's free tier.

built as a Claude Code skill — runs as `/delegate` inside a session.

---

## why

Claude has usage limits. a lot of coding work (bulk reformats, docstring passes, research lookups) doesn't need Claude. delegate routes those tasks to subscription-covered or free-tier providers, with typed fallback chains and billing safety built in.

## providers

| provider | type | billing | notes |
|---|---|---|---|
| `kimi-code` | CLI (kimi-code) | subscription | kimi-for-coding, fast for code edits |
| `opencode-go` | CLI (opencode) | subscription | minimax-m2.5, uses opencode-go plan |
| `gemini-pro` | CLI (gemini) | subscription | gemini-2.5-pro, long context |
| `gemini-flash` | CLI (gemini) | subscription | gemini-2.5-flash, faster |
| `openrouter-free` | HTTP API | free | `:free` suffix enforced, no edits |

## chains

| chain | providers (order) | worktree isolation |
|---|---|---|
| `code-gen` | kimi → opencode-go → gemini-pro → openrouter-free | yes |
| `bulk` | openrouter-free → gemini-flash → opencode-go | yes |
| `research` | gemini-pro → opencode-go → openrouter-free | no |

first provider to return OK wins. hard failures (zen-trap, allowlist violation) stop the chain immediately — no silent billing.

## install

```sh
./install.sh
```

installs the package (editable), creates the slash command at `~/.claude/commands/delegate.md`, and seeds a user config at `~/.config/delegate/config.toml`.

requires: `kimi-code` (pipx), `opencode`, `gemini` CLIs on PATH. `OPENROUTER_API_KEY` in env for openrouter.

## usage

as a slash command inside Claude Code:

```
/delegate "add type hints to all functions in payments.py" --type code-gen --write payments.py
```

as a CLI:

```sh
delegate "add type hints to all functions in payments.py" \
  --type code-gen \
  --write payments.py \
  --accept "all functions have type hints"
```

bulk mode (one task per file):

```sh
delegate --type bulk \
  --files "src/**/*.py" \
  --task-template "add docstrings to all public functions" \
  --commit-format "docs({file}): add docstrings"
```

## billing safety

delegate is built to not surprise you with a bill.

- **zen-trap detection**: opencode scans stderr for billing errors even on rc=0. routes to next provider on hit.
- **allowlist enforcement**: opencode-go and gemini require models to be on an explicit allowlist. missing allowlist = hard fail, not open access.
- **`:free` suffix enforcement**: openrouter rejects any model without `:free` suffix before making a request.
- **circuit breaker**: bulk runs trip at >50% failure rate over a 10-task window. halts remaining tasks on trip.

## receipts

every invocation writes a JSONL entry to `~/.claude/skills/delegate/state/delegate.jsonl`:

```json
{
  "ts": "2026-04-19T00:00:00Z",
  "task_id": "abc123",
  "provider": "kimi-code",
  "model": "kimi-code/kimi-for-coding",
  "status": "ok",
  "duration_s": 38.4,
  "cost_usd_est": null
}
```

## config

user config at `~/.config/delegate/config.toml`. deep-merged over defaults. example:

```toml
[defaults]
worktree_root = "~/.delegate-worktrees"

[providers.kimi-code]
rpm_cap = 200  # if you're on a higher tier

[[chains.code-gen]]
provider = "kimi-code"
model = "kimi-code/kimi-for-coding"
```

## v0.1 limitations

- manual only — no automatic scheduling or task queuing
- `_MERGE_LOCK` is in-process; two simultaneous instances against the same repo will race
- openrouter free tier has 15 rpm cap and strict context limits
- no retry with backoff — next provider is tried immediately on recoverable failure

## tests

```sh
pytest                                                   # 114 unit tests
DELEGATE_LIVE_TEST=1 pytest tests/test_smoke_*.py        # 4 live provider tests
```
