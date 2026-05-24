# Plan: wiki-run-exec

> **Implementation plan paired with `spec.md`.** The spec says *what*; the
> plan says *how, in what order, with what verification*.

- **Status:** Done
- **Spec:** [`docs/specs/wiki-run-exec/spec.md`](spec.md)
- **Owner:** `llm_wiki_kit/run.py`, `llm_wiki_kit/cli.py:_cmd_run`

## Approach

v1 of `wiki run --exec` shipped in PR #73 (commit `4585e03`). The
construction-phase work-breakdown — pure helpers first, then
orchestrator, then CLI wiring — lives in the merged commit history
and is not duplicated here. This file's job now is to capture the
**single queued follow-on** that the v1 spec explicitly defers, so
a future contributor can pick it up without re-deriving the context.

## Pre-conditions

Already satisfied for v1; carried forward for the queued task:

- ADR-0009 (headless argv shape) — Accepted.
- ADR-0010 (agent passthrough) — Accepted; the *flag insertion
  point* is pinned, but the **resolution-chain inputs** (recipe-
  declared mapping, schedule-entry override) live in RFC-0004.
- RFC-0004 (recipe-declared agent bindings + schedule-entry agent
  override) — **not landed**. This is the blocker for the queued
  task below.

## Steps

Shipped in PR #102 (wiki-agents PR-5).

## Verification gate

Already met for v1 — the merged PR cleared `ruff check`, `ruff
format --check`, `mypy`, and `pytest -m 'not slow'` (and the
spec's acceptance criteria CT-1..CT-17 are all marked `[x]`).

For the queued task above, the gate is the same four commands
plus the new contract tests pinned in that task's spec amendment:

```
ruff check llm_wiki_kit tests
ruff format --check llm_wiki_kit tests
mypy llm_wiki_kit tests
pytest -m 'not slow'
```

## Risks

- **RFC-0004 lands with a different resolution chain than
  ADR-0010 assumed.** Mitigation: ADR-0010 §"What this ADR does
  not cover" explicitly defers the chain to RFC-0004; the kit's
  emit site is a single optional flag pair, so a chain-shape
  change is a SKILL-level edit, not a re-architecture.

## Out of scope

Everything in spec §Non-goals stays out of scope unless the
queued-task amendment above moves it. In particular:

- `OperationExecSucceededEvent` — deferred indefinitely per
  spec §Non-goals.
- SDK-based execution — out per RFC-0003 §"Decisions already
  made".
- Cost / token tracking, streaming exec output, journal-lock
  hold-across-subprocess, partial-work recovery, auto-retry,
  and `--dry-run` — all out per spec §Non-goals.
- Vault-side SKILL contract — owned by the `wiki-schedule`
  vault-side SKILL.md, not by this spec.
- **Env-scrubbing for the exec subprocess.** Discussed in spec
  §Invariants as a possible future ADR; not queued here because
  no concrete bug has surfaced and v1 deliberately tests the
  pass-through. If env scrubbing is needed, it lands as a fresh
  ADR + a separate spec amendment, not by inheriting this plan.
