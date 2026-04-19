# /delegate — Code Review

**Reviewer**: GLM-5.1  
**Date**: 2026-04-19  
**State**: 107 tests passing (4 live smoke tests gated), 35 commits  
**Files reviewed**: all source, tests, config, install scripts

---

## Architecture Assessment: Solid

Clean dependency graph, no circular imports, no god modules. Each file has a clear job.

| module | job | verdict |
|---|---|---|
| `brief.py` | Build + validate + render task briefs | Clean, no issues |
| `config.py` | Deep-merge TOML config, validate chains | Good shape |
| `worktree.py` | Spawn, categorize, merge, cleanup | Heaviest module, well done |
| `circuit.py` | Sliding-window failure-rate breaker | 28 lines, correct |
| `ratelimit.py` | Thread-safe rpm limiter | Lock-spans-sleep by design, good |
| `progress.py` | Heartbeat thread | Clean context manager |
| `preflight.py` | CLI/env/git/worktree checks | Solid gate |
| `orchestrator.py` | Single-task chain iteration with worktree merge | Core loop, see notes |
| `fanout.py` | Parallel bulk with circuit breaker | See notes |
| `cli.py` | Argparse entry point | Clean wiring |
| `providers/` | 4 providers + registry + base | Good pattern |

---

## Things That Are Good

- **Billing safety** is a standout. Zen-trap detection, allowlist enforcement, and `allowlist_suffix` check on openrouter. Fail-closed on missing allowlist. This is what saves real money.

- **Merge safety** — SHA pin, 3-way apply, `Delegated-To:` trailer, rollback on failure. `merge_worktree` handles untracked files via `--intent-to-add`, with cleanup paths for both apply failure and commit failure. Good defensive coding.

- **Circuit breaker** — correctly requires window to be full before tripping. Sliding window with dequeue is the right data structure.

- **Test coverage** — 111 tests, real git operations for worktree tests, mock providers for orchestrator/fanout, live smoke tests behind a gate. The serialization test (`test_fanout_serialize`) proving merges are serialized under concurrency is smart.

- **Config system** — deep-merge with type mismatch enforcement, `*`-allowlist-suffix validation, chain cross-reference validation. All the right guardrails.

---

## Issues Worth Fixing

### 1. `_glob_to_regex` multi-`/**/` bug

**File**: `worktree.py:61`  
**Severity**: Low (unlikely path patterns, technically incorrect)  
**Carry-forward from**: Task 14 review

`str.replace` only replaces the first occurrence. Pattern `a/**/b/**/c` produces `a(?:.*/|)b.*/c` instead of `a(?:.*/|)b(?:.*/|)c`. Fix:

```python
joined = re.sub(r"/\.\*/" , "/(?:.*/|)/", joined)
```

Or refactor `_glob_to_regex` and `_matches_any` into a shared `globs.py` module.

### 2. `fnmatch` vs regex inconsistency (carry-forward #7)

**File**: `openrouter.py:48`  
**Severity**: Medium (behavioral divergence on `**` patterns)

`openrouter._diff_touches_only_allowed` uses `fnmatch.fnmatch`, which treats `*` as matching `/`. `categorize_change` uses `**`-aware regex via `_glob_to_regex`. A pattern like `src/**/*.test.ts` will behave differently across the two codepaths:

- `categorize_change`: `**` = zero or more path segments (correct)
- `openrouter._diff_touches_only_allowed`: `fnmatch` treats `**` as literal `**` (no special meaning), `*` matches `/` in fnmatch

This means a brief with `new_file_patterns: ["src/**/*.test.ts"]` will categorize correctly at merge time but the openrouter diff validation will reject or accept different paths than expected.

**Recommendation**: Extract `_glob_to_regex` and `_matches_any` into a shared `delegate/globs.py`. Replace `fnmatch.fnmatch` in `openrouter.py:48` with `_matches_any`.

### 3. `_LIMITERS` dict race (carry-forward #5)

**File**: `orchestrator.py:35`  
**Severity**: Resolved

Already addressed with `dict.setdefault()`. GIL protects dict operations in CPython. No action needed.

### 4. `bin/delegate` entry point

**File**: `bin/delegate:4`  
**Severity**: None (cosmetic)

`sys.exit(main())` in both `bin/delegate` and `cli.py:153`. Double `sys.exit` is harmless since `sys.exit` on an int is a no-op if already exiting. No action needed.

### 5. Circuit breaker race window

**File**: `fanout.py:73-94`  
**Severity**: Low (acceptable for v1)

After circuit breaker trips, remaining futures are cancelled. But futures already submitted to the thread pool continue executing until they check `halt.is_set()`. 1-2 extra tasks may complete after the breaker trips. This prevents *new* submissions, not in-flight ones. Acceptable for v1.

### 6. Merge lock bottleneck under high concurrency

**File**: `orchestrator.py:121-162`  
**Severity**: Low (v1 tradeoff)

`_MERGE_LOCK` serializes all merges for bulk. Under high concurrency with slow providers, this could bottleneck. Serializing merges is the safe choice for v1 — 3-way apply on shared HEAD requires serialization. No action needed.

### 7. Inline `import glob`

**File**: `cli.py:125-126`  
**Severity**: None (style note)

`import glob` inside the bulk branch. Works fine, stdlib import is fast. Minor consistency note — `glob.glob` with `recursive=True` handles `**` correctly for the `--files` flag.

### 8. No ARCHITECTURE.md

Per project mandate in `AGENTS.md`, every project needs one. `/delegate` doesn't have one. Should be generated.

### 9. README is minimal

README is 5 lines pointing at the spec. The `SKILL.md` is much better. For a sale-ready repo, the README should stand alone — installation, usage, chains, billing safety, all of it.

### 10. `.delegate-brief.json` orphan risk

**File**: `orchestrator.py:84-94`  
**Severity**: Low

Brief JSON written to worktree before invocation, removed after. If provider crashes or SIGKILLs between write and unlink, it's orphaned. `reset_worktree()` on retry cleans it (`--hard` + `clean -fd`), so only a concern on final failure path. Low risk.

### 11. Dead config key: `openrouter_has_credits`

**File**: `config.default.toml:6`  
**Severity**: Low (unused config)

`openrouter_has_credits = false` is defined but never referenced anywhere in the codebase. Either wire it up (e.g., adjust `rpm_cap` for openrouter when credits are purchased) or remove it to avoid confusion.

---

## What's Missing for v0.1.0

| item | priority |
|------|----------|
| Fix `_glob_to_regex` multi-`/**/` bug | Medium |
| Unify `fnmatch` → regex across openrouter and worktree | Medium |
| Generate `ARCHITECTURE.md` | High (mandate) |
| Expand `README.md` for sale-readiness | High |
| Wire up or remove `openrouter_has_credits` | Low |

---

## Overall

Clean, well-tested, well-structured v1. The billing safety model is the standout — zen-traps, allowlists, and circuit breakers are defense-in-depth against accidental metered usage. Worktree isolation with SHA pins and 3-way merge is solid. 111 tests is thorough. The carry-forward items are all reasonable deferrals.

The fnmatch/regex unification and the `_glob_to_regex` multi-`/**/` bug are the only code-level issues I'd fix before tagging. Everything else is docs and config hygiene.