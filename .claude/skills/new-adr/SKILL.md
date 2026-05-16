---
name: new-adr
description: Use this skill when the user asks to create, write, draft, or open a new ADR (architecture decision record). Triggers on phrases like "new ADR", "write an ADR for…", "record this decision", "let's ADR this". For load-bearing decisions the kit will reference as a constraint. Do NOT use for cross-cutting proposals (use `new-rfc`) or feature contracts (use `new-spec`).
dependencies:
  - docs/CONVENTIONS.md
  - docs/_templates/adr.md
---

# Skill: new-adr

Record a load-bearing decision as a new ADR in `docs/adr/` with the next
sequential number.

The kit's lifecycle and mechanics live in
[`docs/CONVENTIONS.md` § How to add an ADR](../../../docs/CONVENTIONS.md#how-to-add-an-adr).
This skill is the trigger surface; CONVENTIONS is the procedure.

## When to invoke

Before scaffolding, confirm the decision is **load-bearing** per
[CONVENTIONS § What counts as "load-bearing" (ADR-worthy)?](../../../docs/CONVENTIONS.md#what-counts-as-load-bearing-adr-worthy):

- It would be expensive to reverse.
- Future code will reference it as a constraint.
- Reasonable people would disagree, and a tiebreak is needed.

If those tests don't fit, push back. Single-feature internals go in a
spec. Open-ended discussion goes in an RFC.

## Procedure

1. Find the next number:

   ```bash
   ls docs/adr/ | grep -E '^[0-9]{4}' | sed 's/-.*//' | sort -n | tail -1
   ```

   Increment and zero-pad to four digits. Don't reuse numbers, even for
   withdrawn ADRs ([CONVENTIONS § Numbering](../../../docs/CONVENTIONS.md#numbering)).

2. Scaffold from the template:

   ```bash
   cp docs/_templates/adr.md docs/adr/NNNN-<kebab-title>.md
   ```

3. Fill in **context** (constraints in play), **decision** (declarative
   opening sentence), **consequences** (including the honest downsides),
   and **alternatives** (with rejection rationales).

4. Mark `Status: Proposed`.

5. Open the PR alongside the change the ADR justifies — or as its own
   PR, whichever produces clearer history
   ([CONVENTIONS § PR scope](../../../docs/CONVENTIONS.md#pr-scope)).

6. On merge, flip `Status:` to `Accepted` and don't touch it again.
   ADRs are frozen — if the decision turns out wrong, supersede with a
   new ADR rather than editing.

## What NOT to do

- Don't draft an ADR for an undecided question — that's an RFC.
- Don't edit an Accepted ADR. Supersede it with a new ADR and mark the
  original `Status: Superseded by ADR-NNNN`.
- Don't bundle multiple decisions into one ADR. One decision, one record.
