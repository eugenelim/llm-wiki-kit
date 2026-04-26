---
name: weekly-review
description: "Read recent activity (changelog, modified pages, projects, decisions, books, meetings, accomplishments logged, hobby sessions, fitness sessions, body metrics) over the last 7 days; produce a structured weekly-review page surfacing what shipped, what was learned, what's blocked, what's next, themes detected, hobby-session counts per hobby, fitness-session counts per modality, PRs set, body-weight delta, and an energy reflection. Surfaces uncaptured wins (offer log-accomplishment), unlogged hobby touches (offer log-hobby-session), and unlogged workouts (offer log-fitness-session). The canonical personal-OS operation. Use Sunday evening or Monday morning on a fixed cadence, or on request: \"run my weekly review\"."
license: MIT
metadata:
  variant: personal
---

# Weekly Review Skill (Personal Variant)

The canonical personal-OS operation. Read recent activity (changelog, modified pages, projects, decisions, books, meetings) over the last 7 days; produce a structured weekly review page that surfaces what shipped, what was learned, what's blocked, what's next, themes detected, and an energy reflection.

## When to Use

- Sunday evening or Monday morning, on a fixed cadence
- After a significant week (major project shipped, role change, big decision)
- On request: "Run my weekly review"

This is the personal-variant analogue of *sprint-planning* (work) and *meal-planning* (family) — same role, different domain. For solo maintainers, the vault dies without a recurring rhythm that produces visible weekly value; this operation IS that rhythm.

## Inputs

User provides:
- Optional: a specific focus or theme for the week
- Optional: explicit period if different from the default 7-day window

Reads:
- `log/changelog.md` — entries from the last 7 days
- All wiki pages with `modified:` in the last 7 days (notes, books, projects, decisions, meetings, applications, portfolio)
- Active project pages (their Current State sections)
- `wiki/goals/` — the lens for evaluating progress
- Most recent weekly review at `wiki/reviews/weekly/` — for carry-over and theme continuity
- The review template at `_templates/review.md`

## Algorithm

1. **Compute recency.** Identify all wiki content modified in the 7-day window.
2. **Categorize activity.** Group modifications by type: shipped (status moved to done, portfolio additions), learned (new notes / books with key claims), decided (decision-log entries), conversed (meetings), blocked (active items unchanged for >5 days).
3. **Detect themes.** Topics or domains appearing 3+ times across the week's content (multiple notes on the same topic; a book + project + decision sharing a theme).
4. **Carry-over.** Read the previous weekly review's "What's Next" section. Note which items shipped, which carry over, which got dropped.
5. **Generate reflective prompts** for interactive review:
   - "What did you ship this week that you're proud of?"
   - "What got blocked, and was it your blocker or someone else's?"
   - "What did you learn that surprised you?"
   - "What's the one thing you want next week to be about?"
   - "Are any active projects no longer aligned with current goals?"
6. **Compose the output** using the review template.

## Output

Write `wiki/reviews/weekly/{YYYY-MM-DD}.md` using `_templates/review.md`:

```yaml
---
type: review
review_cadence: weekly
period: {YYYY-WW}
created: {today}
modified: {today}
tags: [review, weekly]
status: current
---
```

Body sections (per the template): Synopsis, What I Shipped, What I Learned, What's Blocked, What's Next (cap at 5), Themes I Noticed, Energy & Reflection, Cross-References.

## Side-effects

1. **Update `wiki/reviews/weekly/index.md`** with the new week's link.
2. **Surface themes for [[knowledge-consolidation]]** — if 3+ atomic notes share a theme, propose creating or updating a topic page during the next consolidation run.
3. **Surface stalled goals.** If `wiki/goals/` hasn't been updated in 4+ weeks, flag for the next quarterly review.
4. **Append to `log/changelog.md`**: "Weekly review: [[reviews/weekly/{YYYY-MM-DD}]]."

## Interactive Review

The review is collaborative — the skill structures and prompts; the user fills in reflection. Present:

```
Weekly review for {YYYY-WW}:

Activity summary:
  Shipped: 4 items (talk draft v2, atomic note on actor models, decision to decline fellowship, …)
  Learned: 2 books finished, 7 atomic notes added
  Decided: 1 decision logged
  Met with: Sarah, Jake (×2), Maria
  Blocked: Acme application (referral pending), personal-site decision (overdue)

Themes detected (potential consolidation):
  - "Event-driven thinking" — 4 references across notes and project work
  - "Tool evaluation methodology" — 3 references across project and decision

Reflective prompts (please answer):
  1. What are you proudest of this week?
  2. What's the one thing you want next week to be about?
  3. Anything draining energy that should be re-examined?
  4. Are active projects still aligned with goals?

Save the review with your reflections?
```

The user fills the prompts; the skill saves the final review.

## Failure Modes

- **Empty week (vacation, sick, etc.).** Produce a brief review acknowledging the gap. Don't fabricate activity. Carry-over from the previous review's "What's Next" still applies.
- **Week 1 (first ever review).** No prior weekly review for carry-over. Note this is the starter; future reviews will reference it.
- **Multiple reviews already this week.** Rare. Surface and ask whether to add a mid-week supplemental or replace the existing one.
- **Goals page absent.** Surface: "no goals page found — weekly review evaluates progress against goals; consider authoring `wiki/goals/2026-q2.md` first." Skip goal-evaluation rather than failing.

## Cadence

- **Manual:** Run Sunday evening or Monday morning. A fixed time + place builds the habit.
- **Scheduled:** A Cowork weekly task could prompt the user every Sunday at 6pm. The skill itself runs on user invocation; the schedule is the reminder, not the trigger.
