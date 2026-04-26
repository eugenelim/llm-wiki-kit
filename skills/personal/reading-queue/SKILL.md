---
name: reading-queue
description: "Read books/courses/papers with status \"someday\" or \"in-progress\"; prioritize against current goals and active projects. Inline ranked recommendation — does NOT write a wiki page. Use when considering what to read next and the queue exceeds 5 items, before a focused-learning week (vacation, sabbatical, project sprint), after skill-gap-analysis surfaces priorities, or on request: \"what should I read next?\"."
license: MIT
metadata:
  variant: personal
---

# Reading Queue Skill (Personal Variant)

Read books / courses / papers with `status: someday` or `status: in-progress`. Prioritize against current goals and active projects. Output is an inline ranked recommendation, not a wiki page (the queue is a planning lens, not a permanent artifact).

## When to Use

- When considering what to read next and the queue is more than 5 items long
- Before a focused-learning week (vacation, sabbatical, sprint at the start of a project)
- After [[skill-gap-analysis]] surfaces priorities that the queue might serve
- On request: "What should I read next?"

## Inputs

User provides:
- Optional: a focus area or skill to prioritize for
- Optional: time budget (e.g., "books I can finish in 4 weeks")

Reads:
- All `wiki/books/*.md` with `status: someday` or `status: in-progress`
- `wiki/goals/*.md` — current goals as the prioritization lens
- `wiki/projects/*/overview.md` — active projects with topic relevance
- Recent `wiki/career/skills/*.md` — skill gaps surfaced from `skill-gap-analysis`
- Recent atomic notes in `wiki/notes/` — themes the user is already working on

## Algorithm

1. **Inventory the queue.** All books / courses / papers / podcasts in someday or in-progress.
2. **Score each item against current goals + projects.**
   - **Direct goal alignment** (3 points) — book directly serves a declared goal
   - **Active project relevance** (2 points) — book informs a project in flight
   - **Skill-gap match** (2 points) — book targets a skill flagged as underdeveloped
   - **Theme alignment** (1 point) — book extends a theme appearing in recent atomic notes
   - **Reading-time fit** (penalty for overlong books when budget is tight)
3. **Surface tradeoffs.** If two items score similarly, note what each emphasizes differently so the user can choose.
4. **Recommend top 3-5.** Don't dump the whole queue; the recommendation is the value-add.

## Output

Inline markdown report (does NOT write a wiki page):

```
Reading queue (priority, given current goals + projects):

1. [[books/designing-data-intensive-applications]] — IN PROGRESS
   Score: 7 (goal alignment + 2 active projects + theme match)
   Why: directly serves the "deepen distributed-systems thinking" goal AND
        informs the order-platform side project AND extends recent atomic
        notes on event-driven thinking
   Reading time: ~3 weeks at current pace

2. [[books/staff-engineer]] — SOMEDAY
   Score: 5 (skill-gap match + goal alignment)
   Why: skill gap surfaced last quarterly review (technical leadership);
        serves the "explore IC vs management track" goal

3. [[books/the-pragmatic-programmer]] — SOMEDAY
   Score: 4 (active project relevance + theme)
   Why: timeless craft; extends recent notes on technical writing as a
        practice
   Reading time: ~2 weeks

Tradeoff: items 2 and 3 both fit; pick based on which mode you're in next
month — leadership-track exploration vs. craft-deepening.

Lower priority (in queue but not recommending now):
  - [[books/{...}]] — interesting but unrelated to current goals
  - [[books/{...}]] — was relevant 6 months ago; reconsider scope of someday
```

## Side-effects

- **None by default.** This is a passive recommendation. The user reads and decides.
- *Optionally*, when user picks a book: update its frontmatter from `status: someday` to `status: in-progress` and the date.

## Interactive Review

The output IS the review — concise, sorted, with reasoning. The user reads it and either picks something or asks to re-rank with different weights.

If the user asks for a re-rank:
```
Re-ranked by reading-time-budget priority (assuming 4-week window):

1. [[books/the-pragmatic-programmer]] — fits the budget; high enough score
2. [[books/designing-data-intensive-applications]] — stretch fit; could continue past window
3. {next item}
```

## Failure Modes

- **Queue is empty.** Surface: "No books in someday or in-progress. Consider what would move you forward and add a few."
- **Queue is overflowing (50+ items).** Surface: "Queue has 50+ items. Many are likely aspirational rather than actionable. Consider archiving the oldest with `status: outdated` rather than carrying them indefinitely."
- **No goals page.** Score against active projects + recent atomic notes only; flag that goal-alignment scoring is unavailable.

## Cadence

- **On demand:** Run when picking what to read next.
- **No scheduled runs:** This is a pull-based recommendation, not a push.
- **Pairs with [[skill-gap-analysis]]:** Run skill-gap analysis quarterly; the gaps inform what's worth adding to the queue in the first place.
