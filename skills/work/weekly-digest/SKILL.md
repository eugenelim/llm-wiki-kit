---
name: weekly-digest
description: "Backward-looking weekly digest. Synthesize what CHANGED across the team's wiki in the last 7 days — sprint plans active this week, meeting decisions, ADRs accepted, specs that shipped. Use Friday afternoon (or end-of-week per the team's cadence), or on request: \"what changed this week?\" / \"produce the weekly digest\". For FORWARD-looking RAG / risks / issues / asks status (the typical leadership-meeting artifact), use team-status instead — they pair: weekly-digest answers \"what happened?\", team-status answers \"where are we and what do we need?\"."
license: MIT
metadata:
  variant: work
---

# Weekly Digest Skill

Synthesize what changed across the team's wiki in the last 7 days. Friday afternoon operation; output is the team's "what happened this week" reference.

## When to Use

- Friday afternoon (or end-of-week, whenever the team's natural cadence allows)
- Before weekly leadership / status meetings
- On request: "What changed this week?" / "Produce the weekly digest"

This is the team-OS analog of the family weekly-digest and serves the same function: visible weekly payoff that keeps the capture loop alive.

## Inputs

Read across all active projects in `wiki/projects/`:

1. **Sprint plans active this week.** Each project's most-recent `delivery/sprint-{date}.md` whose sprint window includes the last 7 days.
2. **Meeting decisions.** Files in each project's `meetings/` modified in the last 7 days. Extract by reading the `## Decisions` and `## Action Items` sections.
3. **ADRs accepted this week.** ADRs with `modified:` in the last 7 days where `status` changed to `accepted`.
4. **Specs that shipped.** Specs whose `status` changed from `in-progress` to `review` or `done` in the last 7 days.
5. **Cross-project changelog.** `log/changelog.md` entries from the last 7 days.
6. **Domain page updates.** Pages in `wiki/domains/` modified in the last 7 days — the cross-project learnings.

## Algorithm

1. **Group by project.** Each active project gets its own subsection.
2. **Within each project, organize by category.** What shipped, what's in flight, what's blocked, key decisions, key meetings.
3. **Cross-project insights at the top.** Anything that touches multiple projects (a domain learning, a tool eval, a cross-cutting ADR) belongs in a "this week's themes" section.
4. **Surface anomalies.** Specs in-progress >2 weeks without updates, ADRs accepted without an associated spec change, action items that haven't been logged to tasks.md.
5. **Quantify.** Counts of: specs shipped, ADRs accepted, meetings held, decisions made, open action items.

## Output

Write `wiki/log/digest-{YYYY-WW}.md` (ISO year-week — e.g., `digest-2026-W17.md`):

```yaml
---
type: weekly-digest
week: {YYYY-WW}
created: {today}
modified: {today}
tags: [digest, weekly]
status: current
---
```

Body sections:

- **`## Synopsis`** — 2-3 sentences. Total counts (specs shipped, ADRs accepted, meetings, decisions). One sentence on the week's biggest theme.
- **`## This Week's Themes`** — cross-project patterns or insights worth highlighting.
- **`## By Project`** — per-project subsection (`### {Project Name}`):
  - Shipped: list of specs that completed
  - In flight: in-progress specs with current status
  - Blockers: anything stalling
  - Key decisions: ADRs accepted or major meeting decisions
  - Meetings: list with wikilinks and one-line summaries
- **`## Anomalies`** — surfaced issues (stale specs, missing actions, etc.). Don't fix; surface for human attention.
- **`## Counts`** — quantified rollup at the bottom: `Specs shipped: 3 / Specs in progress: 7 / ADRs accepted: 2 / Meetings: 5 / Decisions logged: 11`.

## Side-effects

1. **Update `wiki/log/index.md`** with link to this digest.
2. **Append to `log/changelog.md`**: "Weekly digest produced: see [[log/digest-{YYYY-WW}]]."
3. **Optionally:** post the synopsis paragraph to a Slack / team channel via a downstream operation.

## Interactive Review

The digest is mostly factual extraction; aggressive interactive review isn't usually needed. Present the synopsis + counts and ask: "Save digest, or adjust any framing?"

## Failure Modes

- **No project activity this week.** Produce a digest stating that explicitly. Don't fabricate activity.
- **Meeting page without decisions or actions.** The page may not have been processed yet by [[ingest-meeting]]. Note in the Anomalies section.
- **Project with no `delivery/index.md`.** Likely a young project; skip rather than error.
- **ADR with ambiguous status change.** Some ADRs may be edited without clean status transitions. Surface in Anomalies.

## Cadence

- **Manual:** Run Friday afternoon before EOW.
- **Scheduled:** A Cowork scheduled task running every Friday at 3pm. Output to the digest path; the team reads or skims at end-of-week.
