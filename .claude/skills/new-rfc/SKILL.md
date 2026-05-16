---
name: new-rfc
description: Use this skill when the user asks to propose, draft, or open an RFC (request for comments). Triggers on "new RFC", "propose a change to…", "let's get input on…", "draft a proposal". For changes that span multiple modules, modify a top-level directory, modify a convention, or reverse a previous ADR. Do NOT use for already-decided things (use `new-adr`) or single-feature contracts (use `new-spec`).
dependencies:
  - docs/CONVENTIONS.md
  - docs/_templates/rfc.md
---

# Skill: new-rfc

Open a new RFC in `docs/rfc/` from the template. The PR is the discussion
thread; on acceptance the RFC produces ADRs, specs, and/or convention
edits.

The kit's lifecycle and mechanics live in
[`docs/CONVENTIONS.md` § How to add an RFC](../../../docs/CONVENTIONS.md#how-to-add-an-rfc).
This skill is the trigger surface; CONVENTIONS is the procedure.

## When to invoke

Before scaffolding, confirm at least one applies:

- The change spans multiple modules.
- The change adds, removes, or modifies a top-level directory.
- The change modifies a convention in `docs/CONVENTIONS.md` (use
  alongside `update-conventions`).
- The change reverses a previous ADR.
- The user explicitly wants review before implementation.

If the change fits inside one module and breaks no contract, push back:
a normal PR (or a spec, if it's a feature) is enough.

## Procedure

1. Find the next number:

   ```bash
   ls docs/rfc/ | grep -E '^[0-9]{4}' | sed 's/-.*//' | sort -n | tail -1
   ```

   Increment and zero-pad to four digits. RFCs and ADRs use separate
   sequences ([CONVENTIONS § Numbering](../../../docs/CONVENTIONS.md#numbering)).

2. Scaffold from the template:

   ```bash
   cp docs/_templates/rfc.md docs/rfc/NNNN-<kebab-title>.md
   ```

3. Mark `Status: Proposed`. Draft the critical sections — summary,
   motivation, proposal, alternatives (including inaction), drawbacks,
   unresolved questions.

4. Open a PR. The PR description is the discussion thread; iterate on
   the RFC body in response to review comments.

5. When ready to decide: either land the PR with `Status: Accepted`
   alongside any ADRs / specs / convention edits the RFC produces, or
   close with `Status: Rejected` / `Withdrawn` and a one-paragraph
   rationale. Don't leave RFCs open indefinitely.

## What NOT to do

- Don't open an RFC for a decision already made — that's a `new-adr`.
- Don't open an RFC for a single-feature contract — that's a `new-spec`.
- Don't edit an Accepted RFC. Supersede with a new RFC that explicitly
  names the predecessor.
