---
name: bug-fix
description: Use this skill when the user wants to fix a defect — a deviation between current behavior and intended behavior in existing code. Triggers on "fix bug", "fix this bug", "diagnose and fix", "investigate this regression", "this is broken", "crash", "wrong output", "perf regression". For defect-shaped tasks that touch more than one file. Do NOT use for new features (use `new-spec`) or refactors unrelated to fixing incorrect behavior.
dependencies:
  - docs/CONVENTIONS.md
  - .claude/skills/work-loop/SKILL.md
---

# Skill: bug-fix

Fix a defect in the smallest, most root-causing way. Reproduce before
fixing; write the failing test first; pin the contract, not the
implementation; minimum diff; the commit body explains why.

This skill is the trigger surface and the discipline. The execution
loop is in
[`.claude/skills/work-loop/SKILL.md` § FIX phase](../work-loop/SKILL.md);
the bar for "done" is in
[`docs/CONVENTIONS.md` § Tests as the bar for "done"](../../../docs/CONVENTIONS.md#tests-as-the-bar-for-done).

## When to invoke

Reach for this skill on any defect-shaped task: regression, incorrect
output, crash, performance regression. Even a one-line fix benefits
from walking the discipline — it forces "am I fixing the cause or
hiding it?"

For multi-file changes that go beyond fixing one defect — opportunistic
refactors, new features that happened to surface from the bug — stop and
use `new-spec` instead. Bug fixes stay scoped.

## Procedure

1. **Reproduce first.** Don't draft a fix until you have one of: a
   failing test, documented manual steps that fail reliably, or a
   captured stack trace / error / log signature.

2. **Write the failing test.** Pin the observable contract — what the
   code is supposed to do — not the implementation. Cite the spec the
   contract was meant to uphold (`docs/specs/<thing>/spec.md`). If no
   spec exists for the contract being violated, surface that gap.

3. **Identify root cause.** Where does the defect actually live? When
   did it start (`git log -S`, `git bisect`)? Does the same pattern
   exist elsewhere?

4. **Apply the minimum fix.** The smallest change that makes the test
   pass. Decline to address adjacent issues in the same PR.

5. **Verify root vs symptom.** Reject catch-all handlers, defensive
   checks at every call site, retries wrapping flaky code, or feature
   flags masking the bug.

6. **Keep the regression test.** The failing test becomes a permanent
   guard against recurrence.

7. **Document in the commit body.** What was wrong, why it happened,
   and why the fix takes the shape it does. Follow
   [CONVENTIONS § Commit messages](../../../docs/CONVENTIONS.md#commit-messages)
   (v2: `v2: task <N> - <summary>`; post-v2: Conventional Commits).

## What NOT to do

- Don't fix forward without reproduction.
- Don't bundle cleanup or refactors with the fix — separate PRs.
- Don't adjust the spec to match buggy behavior. If the spec is wrong,
  open an RFC / ADR for the change; if the code is wrong, fix the code.
- Don't close an issue as unreproducible without documenting the steps
  you tried.
