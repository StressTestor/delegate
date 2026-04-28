---
name: delegate
description: |
  Dispatch a task to a non-Claude provider (kimi-code, opencode-go, gemini-pro/flash, openrouter-free)
  to conserve Claude usage. Typed chains with fallback, worktree isolation for code-gen, hard-fail
  billing traps, no silent Claude fallback. Use when the task can be done by a cheaper model and you
  want receipts.
allowed-tools:
  - Bash
  - Read
  - Write
---

# /delegate

Manual-only v1. Invoke as `/delegate "task"` or `delegate "task"` from shell.

## install

1. Clone this repo to `/Volumes/onn/delegate/`.
2. Run `./install.sh`. Installs package in editable mode, symlinks skill dir, writes `~/.claude/commands/delegate.md`.
3. Ensure the CLIs referenced by your chains are on PATH: `kimi-code`, `opencode`, `gemini`.
4. If you use openrouter-free: `export OPENROUTER_API_KEY=sk-...` in `~/.zshrc`.

## usage

### code-gen (default)

```bash
/delegate "implement foo() in src/foo.ts" \
  --read src/foo.ts,src/bar.ts \
  --write src/foo.ts \
  --accept "pnpm test src/foo.test.ts passes"
```

Spawns a git worktree at `/Volumes/onn/.delegate-worktrees/...`, runs the chain (`kimi-code` → `opencode-go` → `gemini-pro` → `openrouter-free`), merges back to cwd HEAD with a `Delegated-To:` commit trailer.

### research

```bash
/delegate "summarize src/a.ts, src/b.ts, src/c.ts" \
  --type research \
  --read src/a.ts,src/b.ts,src/c.ts
```

No worktree. Chain: `gemini-pro` → `opencode-go` → `openrouter-free`.

### bulk

```bash
/delegate --type bulk \
  --files "src/**/*.ts" \
  --task "add JSDoc @see link to sibling test file at top of each source file" \
  --concurrency 10
```

Fan-out over matched files. Circuit breaker halts at 50% failure rate over last 10 attempts.

### pin a provider (no fallback)

```bash
/delegate "x" --provider gemini-pro
```

If `gemini-pro` fails, exit non-zero with structured error. No chain fallback.

## chains (defaults)

| type | chain |
|------|-------|
| code-gen | kimi-code → opencode-go → gemini-pro → openrouter-free |
| bulk | openrouter-free → gemini-flash → opencode-go |
| research | gemini-pro → opencode-go → openrouter-free |

Override in `~/.config/delegate/config.toml`. Full default config at `config.default.toml` in this repo.

## billing safety

- **opencode-go**: hard allowlist of 3 models (`glm-5`, `kimi-k2.5`, `minimax-m2.5`). Stderr/stdout scanned for zen-trap patterns (insufficient balance, pay-as-you-go, etc.). Hard-fail on match — no chain advance, exits non-zero.
- **openrouter-free**: hard suffix check — model must end with `:free`.
- **kimi-code / gemini**: any subscribed model.
- **no silent Claude fallback**: chain exhaustion returns structured error.

## receipts

Every attempt logged as JSONL to `~/.claude/skills/delegate/state/delegate.jsonl`. Log line written BEFORE any hard-fail, so the rejected attempt is visible.

## limitations (v1)

- manual only. no auto-routing from other skills.
- worktree is file isolation, not a sandbox. external CLIs run with your shell permissions.
- no session continuity across `/delegate` calls.
- `--provider` pins to one provider with no fallback.
