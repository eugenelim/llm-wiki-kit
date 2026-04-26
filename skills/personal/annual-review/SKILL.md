---
name: annual-review
description: "Synthesize four quarterly reviews + the year's accomplishments (grouped by dimension) + hobby trajectory (which grew, atrophied, started, paused) + fitness trajectory (programs completed, PR summary, indicator-lift deltas, body trajectory) + decisions + projects + portfolio additions + reading log into a year retrospective with per-dimension reflections, durable themes, decision audit, and next-year theme proposal. Reads wiki/accomplishments/*.md, wiki/hobbies/{slug}/sessions/*.md, wiki/fitness/sessions/*.md, wiki/fitness/body/*.md, wiki/fitness/programs/*.md, and the canonical exercise PR histories. Use in December (or whenever the user's annual rhythm hits), on request \"run my annual review\", or after major life events that re-anchor the trajectory."
license: MIT
metadata:
  variant: personal
---

# Annual Review Skill (Personal Variant)

Synthesize four quarterly reviews + the year's decisions + projects + portfolio additions + reading log into a year retrospective. Identify durable themes, audit major decisions, propose a next-year theme + goals.

## When to Use

- December (or whenever the user's annual rhythm hits)
- On request: "Run my annual review"
- After major life events that re-anchor the trajectory (role change, relocation, etc.)

## Inputs

User provides:
- Optional: a specific year-theme to evaluate against
- Optional: explicit year if not the most recent

Reads:
- All four `wiki/reviews/quarterly/*.md` from the year
- All `wiki/accomplishments/*.md` with `date:` in the year — the in-the-moment log; primary input to per-dimension reflections
- All `wiki/hobbies/{slug}/sessions/*.md` with `date:` in the year — for hobby-trajectory analysis (which hobbies grew, atrophied, started, paused)
- All `wiki/hobbies/{slug}/overview.md` — for `status:` audit and `current_focus:` shifts
- All `wiki/fitness/sessions/*.md` with `date:` in the year — fitness session counts per modality, PR distribution, programmatic adherence
- All `wiki/fitness/body/*.md` with `date:` in the year — body trajectory (weight + measurements over the year)
- All `wiki/fitness/programs/*.md` — programs completed during the year, mesocycle adherence, indicator-lift movement
- All `wiki/fitness/exercises/*.md` — `pr_estimated_1rm` snapshots and `## PR History` for PR-trajectory rendering
- `wiki/goals/*.md` modified during the year (goals were declared at the start; this audits them)
- `wiki/decisions/*.md` from the year
- All projects with `created:` or `modified:` in the year
- Portfolio additions from `wiki/portfolio/`
- Reading log via `wiki/books/*.md` with status changing to `done` during the year
- Previous year's annual review (if exists) — for trajectory
- The review template at `_templates/review.md`

## Algorithm

1. **Aggregate quarterly reviews.** Pull each quarter's shipped, themes, goal-progress, decision audit, trajectory.
2. **Aggregate accomplishments by dimension.** Read all `wiki/accomplishments/*.md` with `date:` in the year. Group by `dimension:`. Within each dimension, sort by `impact:` (`major` → `significant` → `meaningful` → `micro`) then by date. Counts per dimension feed the synopsis; `significant` and `major` entries anchor each dimension's reflection.
3. **Detect durable themes per dimension.** Within each dimension's accomplishments, look for repeating context patterns (e.g., "schema sign-off" appearing across 3 career wins). These per-dimension themes are richer than year-wide themes alone.
4. **Detect cross-dimension durable themes.** Topics that span multiple quarters AND multiple dimensions are the year's real overarching themes (e.g., "transitioning to platform engineering" might span `career` + `craft` + `learning` + `network`).
5. **Major decisions audit.** Identify the 5-10 most consequential decisions of the year. For each: rationale, outcome, learning. Cross-link to accomplishments where the decision led to a captured win.
6. **Portfolio + portfolio-eligible projects.** What public-facing work shipped? Pull from `dimension: craft` and `dimension: career` accomplishments with high impact; what's portfolio-eligible but not yet promoted?
7. **Reading impact.** Of books finished this year, which actually changed thinking? Cross-reference `dimension: learning` accomplishments with `evidence:` linking to specific books.
8. **Trajectory check.** Compare to prior year. Is the durable-theme set converging or diverging? Which dimensions grew (more accomplishments year-over-year)? Which atrophied?
9. **Propose next year.** Theme + 3-5 specific goals + skill priorities. Anchor proposals against weak dimensions (low count or low impact) or shifts surfaced in the trajectory.
10. **Mark accomplishments reviewed.** Update `status: reviewed-annually` on every accomplishment included in this review.

## Output

Write `wiki/reviews/annual/{YYYY}.md` using `_templates/review.md` with `review_cadence: annual`:

```yaml
---
type: review
review_cadence: annual
period: {YYYY}
created: {today}
modified: {today}
tags: [review, annual]
status: current
---
```

Body sections:
- `## Synopsis` — 3-4 sentences on the year, including a count of accomplishments per dimension (e.g., "career: 8, craft: 12, learning: 6, …")
- `## Major Shipments` — top 10 completions across all dimensions
- `## Goal Audit` — what was declared a year ago vs. what happened
- `## Reflections by Dimension` — **one subsection per dimension that has accomplishments this year**:
    - `### Career` — accomplishments list (significant + major elevated, meaningful summarized, micro counted), themes detected, carry-forward observations
    - `### Craft` — same structure
    - `### Learning` — same structure (cross-link to books/courses)
    - `### Network` — same (cross-link to people pages updated)
    - `### Health` — same
    - `### Finance` — same
    - `### Relationships` — same
    - `### Side-project` — same
    - `### Community` — same
    - `### Personal-growth` — same
    - Skip dimensions with zero accomplishments rather than rendering empty subsections.
- `## Cross-Dimension Themes` — 3-5 durable themes that span multiple dimensions (the year's real story)
- `## Hobby Trajectory` — per-hobby session counts year-over-year, status changes, new hobbies started, hobbies turned dormant or done. Cross-link milestone accomplishments tagged `related_hobby:`.
- `## Fitness Trajectory` — programs completed; PR summary (top 5-10 across exercises); session counts per modality; body-weight + measurement trajectory; indicator-lift year-over-year deltas; recovery-quality trend (sleep / energy averages from body-metric snapshots). Cross-link PRs tagged `dimension: health` + `related_program:`.
- `## Major Decisions` — 5-10 most consequential, with audit; cross-link to anchored accomplishments
- `## Portfolio Year-in-Review` — public-facing work + portfolio-eligible projects
- `## Trajectory` — comparison to prior year; converging or diverging? Which dimensions grew, which atrophied?
- `## Next Year — Theme & Goals` — proposed theme + 3-5 goals + skill priorities; anchored against weak dimensions where relevant
- `## Cross-References` — quarterly reviews, accomplishments index, projects, goals, key books

## Side-effects

1. **Update `wiki/reviews/annual/index.md`**.
2. **Mark accomplishments reviewed.** Bump `status: reviewed-annually` on every `wiki/accomplishments/*.md` included in the review.
3. **Trigger [[career-narrative-refresh]]** — the annual review is the strongest input to the narrative; `dimension: career` and `dimension: craft` accomplishments feed it directly.
4. **Trigger [[skill-gap-analysis]]** — proposed next-year goals reveal skill priorities; weak dimensions surface as gap candidates.
5. **Author or refresh `wiki/goals/{next-year}.md`** based on next-year proposal.
6. **Append to `log/changelog.md`**.

## Interactive Review

```
Annual review for {YYYY}:

Major shipments (10):
  - Kafka observability talk (conference, peer-reviewed)
  - Personal site v2 (public)
  - 47 atomic notes (knowledge graph compounding)
  - 4 quarterly reviews (planning rhythm sustained)
  - …

Goal audit (5 declared):
  ✓ Hit: 2  ↻ Progressed: 2  ✗ Stalled: 1
  Stalled goal: "Read 24 books." Reality: 14 books, but with deeper engagement.
  Drop goal-count target for next year? Replace with depth metric?

Durable themes (year-level):
  1. Event-driven architecture (work + personal projects + atomic notes)
  2. Career narrative consolidation (3 quarterly refreshes)
  3. Writing as a public practice (talks + blog + portfolio)

Reflective prompts:
  1. What was this year's *one* thing if you had to pick?
  2. What surprised you most about how the year actually went vs. how you planned it?
  3. What's a theme worth committing to for next year?
  4. What's a habit / practice that should die in the new year?

Save the annual with your reflections + next-year proposal?
```

## Failure Modes

- **Year has fewer than 4 quarterly reviews.** Note the gap. Annual review still possible from the available material; flag for the user that next year's review will be richer if quarterly is sustained.
- **Previous year's annual review absent.** No trajectory comparison. Establish baseline.

## Cadence

- **Annual:** Once per year, typically December or year-end.
- **Cowork scheduled task** can prompt on the first Sunday of December as a soft reminder.
