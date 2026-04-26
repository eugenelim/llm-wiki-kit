---
name: decision-check
description: "Audit personal decisions made in the last 12 months against current goals; surface decisions that may no longer align without auto-resolving them. Use quarterly, after a major life or career shift that changes the goal landscape, before annual-review (which uses the audit), or on request: \"audit my recent decisions\"."
license: MIT
metadata:
  variant: personal
---

# Decision Check Skill (Personal Variant)

Audit personal decisions made in the last 12 months against current goals. Surface decisions that may no longer align — without auto-resolving them. The decision log is a thinking tool; this operation refreshes its alignment with where you actually are now.

## When to Use

- Quarterly (default cadence)
- After a major life or career shift that changes the goal landscape
- Before [[annual-review]] — decision-check informs the annual decision audit
- On request: "Audit my recent decisions"

## Inputs

User provides:
- Optional: time window (default 12 months)
- Optional: focus filter (e.g., "career decisions only")

Reads:
- All `wiki/decisions/*.md` modified or created in the window
- `wiki/goals/*.md` — current goals as the alignment lens
- Recent quarterly reviews `wiki/reviews/quarterly/*.md` — for context on what changed
- Active projects `wiki/projects/*/overview.md` — to identify decisions that affect in-flight work
- Recent atomic notes `wiki/notes/` — to surface evidence that contradicts past decisions

## Algorithm

1. **Inventory decisions.** Read all decision pages in the window. For each: date, choice made, rationale, expected outcome.
2. **Classify each.**
   - **Ratified** — recent evidence (atomic notes, project outcomes, conversations) confirms the decision was right
   - **Drifted** — current goals have shifted such that the rationale may no longer apply
   - **Counter-evidence** — recent learning contradicts a load-bearing premise of the decision
   - **Stale** — decision was about a now-irrelevant context (job changed, project ended, etc.)
   - **Untested** — too soon to evaluate; no evidence either way
3. **Surface the ones worth revisiting.** Drifted + counter-evidence + (sometimes) stale.
4. **Don't auto-resolve.** Decisions are revisited deliberately, not by automation. The skill surfaces; the user decides.

## Output

Inline markdown report (does NOT write a wiki page — this is a conversational audit):

```
Decision check ({window} months back, {N} decisions reviewed):

RATIFIED ({count}):
  - [[decisions/2026-01-04-decline-fellowship]] — confirmed by Q1 outcomes
  - [[decisions/2025-11-12-lean-into-talks]] — confirmed by 2 talks shipped in Q1
  - {others, briefly}

DRIFTED ({count}):
  - [[decisions/2025-08-22-stay-IC-track]]
    Rationale at the time: "want to stay close to the code; not ready for management"
    Drift: Recent quarterly review surfaced "growing interest in technical leadership."
    Atomic notes from the last 3 months show repeated wrestling with leadership questions.
    → Consider: revisit this decision in next quarterly review.

COUNTER-EVIDENCE ({count}):
  - [[decisions/2025-09-15-pick-rust-for-side-project]]
    Rationale at the time: "long-term type safety; team momentum at work"
    Counter-evidence: Last 6 months — abandoned the side project twice; recent
    note "[[notes/rust-friction-vs-go-for-systems-tools]]" is honest about the
    cost. The rationale's premise (team momentum) doesn't apply to side projects
    where you're solo.
    → Consider: revisit; the side project may be better served by Go.

STALE ({count}):
  - [[decisions/2025-05-08-conference-budget]] — context (team's Q3 budget) no
    longer applies; you're a different team now
    → Mark as stale; archive.

UNTESTED ({count}):
  - {recent decisions where no evidence has accumulated yet}

Apply: revisit DRIFTED decisions in next quarterly review? Archive STALE
decisions now?
```

## Side-effects

1. **Optionally update frontmatter** on stale decisions: change `status: archived` and add note explaining context shift.
2. **No mass changes** — every revision is the user's deliberate act.
3. **Append to `log/changelog.md`**: "Decision check: {N} decisions reviewed, {M} flagged for revisit."

## Interactive Review

The output IS the review. The user reads, picks specific decisions to dig into, and either:
- Confirms the original decision still holds → no action
- Updates the decision page with a "revisited on {date}" note + current state
- Authors a new decision that supersedes the old (link both ways)
- Archives stale decisions

## Failure Modes

- **No decisions logged in the window.** Either you haven't logged decisions (consider doing so going forward — it makes future-you's audit possible) or it really was a stable period.
- **All decisions ratified.** Could mean the goal landscape hasn't shifted (good); could mean the audit's evidence-gathering is too lenient (worth checking the criteria).
- **Many decisions drifted.** Strong signal that goals have meaningfully changed; the next quarterly review should explicitly address the drift.

## Cadence

- **Quarterly:** Run with each quarterly review or just before.
- **On demand:** When a major shift suggests many decisions might need revisiting.
- **No scheduled push:** Decision check is reflective; scheduled would produce noise.
