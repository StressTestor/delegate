# claude.md — agent instructions for working on delegate

read this before making changes. the things in here are invariants, not preferences.

## what delegate is

a Python CLI + Claude Code skill that dispatches tasks to non-Claude providers (kimi, opencode-go, gemini, openrouter) so Claude usage limits last longer. see ARCHITECTURE.md for the full module map and data flow.

## invariants you do not break

### billing safety

this is the whole reason delegate exists. do not weaken any of:

- **zen-trap detection** in `providers/opencode.py`. runs BEFORE the rc=0 check because zen routing can return 0 with billing errors in stderr. if you add new zen patterns to `config.default.toml`, they must be tested.
- **allowlist enforcement** in `providers/opencode.py` and `providers/gemini.py`. missing or empty allowlist → HARD_FAIL. this is fail-closed by design. never default to "allow all."
- **allowlist_suffix** in `providers/openrouter.py`. models must end with `:free`. do not add a way to bypass this.
- **HARD_FAIL stops the chain**. never convert a HARD_FAIL to RECOVERABLE or retry it. the whole point is to not silently hemorrhage money.

### merge safety

in `worktree.py`:

- **SHA pin**: captured BEFORE `git worktree add` in `spawn_worktree`. checked inside the merge lock before applying. never skip this check.
- **`_MERGE_LOCK` in `orchestrator.py`**: serializes all merges. required because bulk runs hit the same cwd concurrently and `git apply --3way` is not safe under parallel index writes.
- **SHA refresh inside the lock is bulk-only** (`if batch_id is not None`). do NOT make it unconditional — that would defeat the SHA pin for code-gen mode.
- **categorize before apply**: REJECT paths must abort the merge, ASK paths need explicit approval, AUTO_APPROVE goes through. `do_not_touch` trumps everything.
- **rollback on failure**: `git apply --3way` or commit failure must `git checkout HEAD -- .` before raising. never leave conflict markers in cwd.

### path glob behavior

`globs.py` is the single source of truth for `**` matching. both `worktree.categorize_change` and `openrouter._diff_touches_only_allowed` MUST use `matches_any` from it. do not reintroduce `fnmatch` for path patterns — it treats `*` as matching `/`, which causes silent divergence between the two codepaths.

### openrouter path security

`_diff_touches_only_allowed` checks ALL 6 path references in each diff header: `a/`, `b/`, `rename from`, `rename to`, `copy from`, `copy to`. never remove any of those checks. a rename diff can exfiltrate `.env` onto an allowlisted target if you only check one side.

## development workflow

### running tests

```sh
pytest                                       # 114 unit tests, no network
DELEGATE_LIVE_TEST=1 pytest tests/test_smoke_*.py  # 4 live provider smokes
```

live smokes need `kimi-code`, `opencode`, `gemini` CLIs on PATH and `OPENROUTER_API_KEY` + `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in env.

### adding a new provider

1. new file under `src/delegate/providers/<name>.py` subclassing `Provider`
2. register it in `providers/__init__.py` via `build_provider`
3. add config stanza to `config.default.toml` with allowlist (or `allowlist_suffix` for HTTP providers)
4. add to chain(s) in `config.default.toml`
5. tests: mock subprocess.run for unit tests. live smoke test gated by `DELEGATE_LIVE_TEST=1`.
6. update ARCHITECTURE.md stack/chain tables and README provider table.

### adding config keys

if you add a key to `config.default.toml`, it must be:
- referenced somewhere in the code (no dead keys — we removed `openrouter_has_credits` for this reason)
- tested in `test_config_default.py`
- documented in README if user-facing

### modifying schemas

`schemas/*.json` are validated at runtime. if you change one:
- test against real payloads (not just synthetic)
- update the schema version if breaking
- add values to enums explicitly (e.g. `log.schema.json` status enum)

## things to NOT do

- **no retry loops inside the orchestrator**. chain iteration IS the retry mechanism. next provider on recoverable failure. no exponential backoff, no in-chain retries.
- **no "smart" defaults that change behavior based on env**. config is explicit. if you want different behavior, put it in the user config.
- **no secrets in code or config defaults**. env vars only. `api_key_env` field points at the env var name.
- **no `Co-Authored-By: Claude` trailers** in commits. (joe's convention.)
- **no emojis** in docs, code, or commit messages unless specifically requested.
- **no creating files outside this repo** — plans, review artifacts, scratch notes all live elsewhere.

## commit conventions

conventional commits. lowercase. imperative mood. no period.

```
feat(provider): add deepseek provider wrapper
fix(worktree): expand directory entries before categorize
refactor(globs): unify ** behavior across worktree and openrouter
docs(readme): add bulk mode example
test(smoke): gate kimi smoke behind DELEGATE_LIVE_TEST
```

## if you're stuck

- `ARCHITECTURE.md` — module map, data flow, patterns
- `README.md` — user-facing usage
- `SKILL.md` — Claude Code skill manifest with all usage modes
- tests/ — behavior specs. a test failing means something real broke. fix the code, not the test.
