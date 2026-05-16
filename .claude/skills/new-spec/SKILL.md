---
name: new-spec
description: Use this skill when the user wants to start a new feature with a spec, or wants to write a spec for something they're about to build. Triggers on "new spec", "write a spec for X", "let's spec this out", "start a feature for…". Spec-driven development; the spec drives implementation. Do NOT use for cross-cutting proposals (use `new-rfc`) or recording load-bearing decisions (use `new-adr`).
dependencies:
  - docs/CONVENTIONS.md
  - docs/_templates/spec.md
  - docs/_templates/plan.md
---

# Skill: new-spec

Scaffold a new feature spec under `docs/specs/<thing>/` with `spec.md` and
(when the work needs more than one PR) `plan.md`.

The kit's lifecycle and mechanics live in
[`docs/CONVENTIONS.md` § How to add a spec + plan](../../../docs/CONVENTIONS.md#how-to-add-a-spec--plan).
This skill is the trigger surface; CONVENTIONS is the procedure.

## When to invoke

The spec is the contract; the plan is the strategy. Reach for this skill
when the feature touches multiple files or needs more than one PR.

For a one-line edit, skip the spec. For a load-bearing decision, prefer
`new-adr`. For a cross-cutting proposal that needs review before
implementation, prefer `new-rfc`.

## Procedure

1. Pick a kebab-case feature name — short and noun-y (`webhook-retries`,
   not `improve-the-webhook-retry-experience`).

2. Scaffold from the templates:

   ```bash
   mkdir -p docs/specs/<thing>
   cp docs/_templates/spec.md docs/specs/<thing>/spec.md
   cp docs/_templates/plan.md docs/specs/<thing>/plan.md   # only if multi-PR
   ```

3. Fill in `spec.md` first. Write the **contract tests inside `spec.md`
   before any code** — these encode the acceptance criteria the kit uses
   as the bar for "done"
   ([CONVENTIONS § Tests as the bar for "done"](../../../docs/CONVENTIONS.md#tests-as-the-bar-for-done)).

4. Fill in `plan.md` (when needed). Write the **construction tests
   inside `plan.md` before the EXECUTE phase** — these encode how each
   step will be verified.

5. Cite upward: link the spec to any ADRs whose constraints it inherits,
   and to the RFC that motivated it (if any).

6. Reference the spec from the code it governs (a module-level docstring
   pointing at `docs/specs/<thing>/spec.md` is fine).

## What NOT to do

- Don't spec a feature without first reading existing code in the area —
  drift between spec and code is a bug, not a fresh start.
- Don't bury implementation details in `spec.md`; those belong in
  `plan.md`. The spec stays a contract.
- Don't skip the non-goals section — it prevents scope creep.
- Don't keep the spec frozen after merge — specs are living
  ([CONVENTIONS § The doc hierarchy](../../../docs/CONVENTIONS.md#the-doc-hierarchy)).
  Update it in the same PR as the code change.
