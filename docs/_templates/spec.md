# Spec: <thing>

> **Living document.** Updated alongside the code. Drift between spec and
> code is a bug — fix the code or the spec in the same PR.

- **Status:** Draft | Implemented | Deprecated
- **Owner:** <module or person>
- **Related:** RFC-NNNN, ADR-NNNN, `docs/specs/<thing>/plan.md`

## What this is

One paragraph defining the thing and its boundary. A reader should be
able to tell from this paragraph what the thing *is* and what it *isn't*.

## Inputs

What does this thing receive? File paths, function arguments, environment,
journal events. Be exact about types and required fields.

## Outputs

What does this thing produce? Return values, files written, journal
events appended, side effects.

## Behavior

Step-by-step what happens between input and output. Include:

- **Happy path** — the canonical flow
- **Edge cases** — what happens when an input is missing, malformed,
  conflicting with prior state
- **Error cases** — what raises, what's caught, what's surfaced to the user

## Invariants

What must always be true before, during, and after this thing runs?

- Things that hold even on failure
- Things the user can rely on
- Things tests verify

## Contracts with other modules

Who calls this? Who does it call? What does the journal record about it?

## Acceptance criteria

What does "done" look like? These translate directly into tests.

- [ ] <observable behavior>
- [ ] <invariant tested>
- [ ] <error case covered>

## Non-goals

What this thing *won't* do, in case anyone asks.
