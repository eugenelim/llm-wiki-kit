---
name: update-conventions
description: Use this skill when the user wants to substantively change `docs/CONVENTIONS.md` — modify how the team works in this repo. Triggers on "change the convention for…", "update the rules", "amend our process", "let's revise how we do X". Substantive convention changes go through RFC review, not a direct PR. Typo and broken-link fixes don't count — those land as normal PRs.
dependencies:
  - docs/CONVENTIONS.md
  - .claude/skills/new-rfc/SKILL.md
---

# Skill: update-conventions

Substantive edits to `docs/CONVENTIONS.md` change how everyone works in
the repo. They don't land as a normal PR — they go through RFC review
first.

This is the
[`docs/CONVENTIONS.md` § When this file is wrong](../../../docs/CONVENTIONS.md#when-this-file-is-wrong)
pattern: flag drift, don't work around it. Fix via RFC for substantive
shifts; normal PR for cleanups.

## When to invoke

Reach for this skill when the proposed change would alter how a future
agent or contributor *acts* on the repo — adding a step, removing a
gate, changing what counts as "done", changing the PR-scope rule, etc.

**Exception — not in scope here:** typo fixes, broken-link fixes,
formatting tweaks, and other purely-mechanical edits that don't change
meaning. Those land as a normal PR with no RFC.

If you're unsure whether an edit is substantive: err toward the RFC.
The cost of an extra RFC is small; the cost of an unannounced rule
change is large.

## Procedure

1. **Push back on direct edits.** If the user starts editing
   `docs/CONVENTIONS.md` directly, stop and explain that substantive
   convention changes go through RFC.

2. **Open the RFC.** Use the `new-rfc` skill, with the RFC scoped to
   "change CONVENTIONS section X to Y". List the convention(s) changing
   and include the proposed text — the diff, essentially — in the
   RFC's proposal section.

3. **Land the convention edit alongside the RFC's acceptance.** On RFC
   acceptance, the edits to `docs/CONVENTIONS.md` land in the same PR
   that flips `Status:` to `Accepted`. One PR, one commit, one record.

4. **Update follow-on artifacts.** If the convention change implies
   downstream edits (AGENTS.md, ADRs that referenced the old
   convention, spec templates), include them in the same PR or list
   them as follow-on tasks in the RFC's outcome section.

## What NOT to do

- Don't edit `docs/CONVENTIONS.md` substantively in a normal PR —
  surface the change as an RFC first.
- Don't edit `docs/CHARTER.md` directly at all — the charter is frozen;
  changes go through RFC.
- Don't bundle a convention change with unrelated code in the same PR —
  the convention edit and its RFC are the PR's reason for existing.
