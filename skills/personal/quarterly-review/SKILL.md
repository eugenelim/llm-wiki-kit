---
name: quarterly-review
description: "Synthesize a quarter (12-13 weekly reviews + the quarter's accomplishments grouped by dimension + hobby-session counts per hobby + fitness program progress, indicator-lift trends, PRs set, body trajectory + goal progress + decisions + projects shipped) into a quarterly-review page with per-dimension reflections, theme detection, goal-progress audit, decision-alignment check, and next-quarter intent. Reads wiki/accomplishments/*.md, wiki/hobbies/{slug}/sessions/*.md, wiki/fitness/sessions/*.md, wiki/fitness/body/*.md, and active wiki/fitness/programs/*.md. Use at the end of every fiscal quarter (March, June, September, December), or on request: \"run my quarterly review\". Often paired with decision-check before, career-narrative-refresh after."
license: MIT
metadata:
  variant: personal
---

# Quarterly Review Skill (Personal Variant)

Synthesize a quarter (12-13 weekly reviews + goal progress + decisions + projects shipped) into a quarterly review page. Theme detection across the quarter, goal-progress audit, decision-alignment check, and next-quarter intent.

## When to Use

- End of every fiscal quarter (March, June, September, December)
- On request: "Run my quarterly review"
- Before [[career-narrative-refresh]] — quarterly review surfaces what to update in the narrative

## Inputs

User provides:
- Optional: a specific focus or theme for the quarter
- Optional: explicit quarter (e.g., 2026-Q2) if not the most recent

Reads:
- All `wiki/reviews/weekly/*.md` from the quarter (typically 12-13)
- All `wiki/accomplishments/*.md` with `date:` in the quarter — grouped by dimension for the reflections section
- All `wiki/hobbies/{slug}/sessions/*.md` with `date:` in the quarter — for hobby-cadence audit; surface dormant candidates (active hobbies with 0 sessions in the quarter)
- All `wiki/fitness/sessions/*.md` with `date:` in the quarter — session counts per modality, PRs set, indicator-lift movement
- All `wiki/fitness/body/*.md` with `date:` in the quarter — body-weight + measurement trajectory
- `wiki/fitness/programs/*.md` with `status: active` — mesocycle progression, deload adherence, plan-vs-actual
- `wiki/goals/{quarter}.md` — declared goals for the period
- `wiki/decisions/*.md` modified during the quarter
- All `wiki/projects/*/overview.md` — projects active during the quarter
- Most recent quarterly review at `wiki/reviews/quarterly/` — for carry-over and trajectory
- The review template at `_templates/review.md`

## Algorithm

1. **Aggregate weekly reviews.** Read all 12-13 weeks; extract shipped items, themes, blocker patterns, learning highlights, energy trajectory.
2. **Aggregate accomplishments by dimension.** Read all `wiki/accomplishments/*.md` with `date:` in the quarter. Group by `dimension:` and sort within each by `impact:` (`major` → `significant` → `meaningful` → `micro`) then date.
3. **Goal progress audit.** For each goal in `wiki/goals/{quarter}.md`, classify: hit / progressed / stalled / dropped. Cite supporting weekly reviews and accomplishments (the accomplishment log is the strongest evidence for "actually hit").
4. **Theme detection.** Topics or domains appearing across 3+ weekly reviews are quarter-level themes worth promoting (to topic pages or skill development). Cross-check against per-dimension accomplishment patterns.
5. **Decision audit.** Read decisions made during the quarter. For each, evaluate: was the rationale right? Did expected consequences happen? Cross-link to accomplishments where the decision led to a captured win.
6. **Trajectory check.** Compare to previous quarterly review. Are themes recurring or shifting? Is goal-attainment ratio trending up or down? Which dimensions grew quarter-over-quarter? Which atrophied?
7. **Surface next-quarter intent.** Carry-over goals + new theme suggestions + skill-gap pointers + dimensions worth more attention.
8. **Mark accomplishments reviewed.** Bump `status: reviewed-quarterly` on every accomplishment included.

## Output

Write `wiki/reviews/quarterly/{YYYY}-Q{N}.md` using `_templates/review.md` with `review_cadence: quarterly`:

```yaml
---
type: review
review_cadence: quarterly
period: {YYYY-Qn}
created: {today}
modified: {today}
tags: [review, quarterly]
status: current
---
```

Body sections:
- `## Synopsis` — 2-3 sentences on the quarter, plus a count of accomplishments per dimension
- `## What I Shipped` — major completions (compress weekly granularity)
- `## Goal Progress` — per-goal audit with citations to weeklies and accomplishments
- `## Reflections by Dimension` — **one subsection per dimension that had accomplishments this quarter**:
    - `### Career` — list (significant + major elevated; meaningful summarized; micro counted), themes, carry-forward
    - `### Craft` — same structure
    - `### Learning` — same; cross-link books/courses
    - `### Network` — same; cross-link people pages
    - `### Health` — same
    - `### Finance` — same
    - `### Relationships` — same
    - `### Side-project` — same
    - `### Community` — same
    - `### Personal-growth` — same
    - Skip dimensions with zero accomplishments rather than rendering empty subsections.
- `## Themes` — patterns that recurred across weeks AND per-dimension accomplishment patterns; candidates for topic pages
- `## Decisions Audit` — were quarter's decisions right? Any to revisit? Cross-link to anchored accomplishments.
- `## What I Learned` — major learnings spanning the quarter
- `## Trajectory` — comparison to previous quarter; which dimensions grew, which atrophied
- `## Next Quarter Intent` — goal carry-over + new directions + dimensions to attend to
- `## Cross-References` — weekly reviews, accomplishments index, goals, decisions, projects, books

## Side-effects

1. **Update `wiki/reviews/quarterly/index.md`**.
2. **Mark accomplishments reviewed.** Bump `status: reviewed-quarterly` on every `wiki/accomplishments/*.md` included.
3. **Trigger consideration of [[career-narrative-refresh]]** — quarterly is the natural cadence for narrative updates; surface a recommendation.
4. **Update or close `wiki/goals/{quarter}.md`** — mark goals as hit / dropped / carried-over.
5. **Surface stale topic pages** that the quarter's themes suggest are due for [[knowledge-consolidation]].
6. **Surface uncaptured wins.** If weekly reviews mention shipped/completed items that lack a corresponding `wiki/accomplishments/` entry, surface them and offer to log via [[log-accomplishment]].
7. **Surface dormant-hobby candidates.** Active hobbies with zero sessions in the quarter are surfaced for the user to confirm `status: dormant` (parked) or `status: done` (no longer pursuing) — keeps the hobby graph honest.
8. **Append to `log/changelog.md`**.

## Interactive Review

```
Quarterly review for {YYYY-Qn}:

Goal progress (3 goals):
  ✓ Ship the Kafka talk — HIT
  ↻ Build personal site v2 — PROGRESSED (frontend done; design decisions outstanding)
  ✗ Read 12 books — STALLED at 4 (Q3 too busy)

Themes that recurred (3+ weekly mentions):
  - Event-driven architecture (across 5 weeks; 4 atomic notes; project + decision)
    → Candidate topic page: wiki/topics/event-driven-architecture
  - Career narrative reconsideration (across 4 weeks)
    → Recommend: run career-narrative-refresh

Decisions made this quarter (4):
  All four hold up against current goals. No decisions flagged for revisit.

Reflective prompts:
  1. Which goal is most worth carrying into next quarter?
  2. What's one thing you'd structurally change about how the quarter ran?
  3. New themes emerging that you'd commit to for next quarter?

Save the quarterly with your reflections?
```

## Failure Modes

- **Quarter has fewer than 8 weekly reviews.** Vault was inconsistently maintained. Note the gap explicitly; review covers what's there. Don't fabricate.
- **No goals page for the quarter.** Skip goal-progress audit; surface: "consider authoring goals at the start of next quarter to make the next review more useful."
- **First quarterly review.** No carry-over or trajectory comparison. Establish the baseline.

## Cadence

- **Manual:** Run within 2 weeks of quarter-end. Best done with the user reviewing recent goals + planning next-quarter intent.
- **Scheduled:** A Cowork task on the first Sunday after quarter-end can prompt.
