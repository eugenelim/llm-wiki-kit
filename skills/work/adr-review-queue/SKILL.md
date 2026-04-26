---
name: adr-review-queue
description: "Surface ADRs in status \"draft\" awaiting acceptance, ranked by age and downstream blocking (specs that depend on the draft ADR). Reminding operation; weekly cadence. Use weekly on the team's architecture-review cadence, on request \"what ADRs need review?\" / \"run the ADR queue\", or before sprint-planning if any planned specs depend on a draft ADR."
license: MIT
metadata:
  variant: work
---

# ADR Review Queue Skill

Surface ADRs in `status: draft` awaiting acceptance. Reminding operation; weekly cadence; output is a queue page for the team to work through during architecture review.

## When to Use

- Weekly, on the team's architecture-review cadence
- On request: "What ADRs need review?" / "Run the ADR queue"
- Before sprint planning if any planned specs depend on a draft ADR

## Inputs

1. **All ADRs across projects.** Files in `wiki/projects/*/decisions/*.md` with `type: decision`.
2. **Their statuses.** From frontmatter `status:` field — interested in `draft`.
3. **Their ages.** From `created:` and `modified:` fields. An ADR sitting in `draft` for >30 days is stale; one for >90 days is probably abandoned.
4. **Dependencies.** For each draft ADR, scan all specs to find which specs reference it. A draft ADR that blocks an in-progress spec is high-priority.
5. **Authors.** From `author:` frontmatter or the ADR's body — who proposed the decision.

## Algorithm

1. **Find all `draft` ADRs.** Across all projects.
2. **Annotate each.**
   - Age: days since `created`
   - Days since last edit: days since `modified`
   - Dependent specs: how many specs reference this ADR; how many are in-progress
   - Author: who's the responsible party
3. **Prioritize.**
   - **Blocking** — referenced by an in-progress spec; must be resolved or the spec stalls.
   - **Stale** — >30 days in draft; either accept, supersede, or archive.
   - **Open** — recent (<30 days), not blocking.
   - **Abandoned** — >90 days in draft with no edits in 60+ days; recommend archive.

## Output

Write `wiki/log/adr-queue.md` (overwrite each run):

```yaml
---
type: adr-queue
created: {today}
modified: {today}
tags: [adr, review-queue]
status: current
---
```

Body sections:

- **`## Synopsis`** — counts: total draft ADRs, of which blocking, stale, open, abandoned.
- **`## Blocking`** — ADRs blocking in-progress specs; resolve first. Per item: title, age, blocked specs (wikilinks), author, recommended action.
- **`## Stale`** — draft >30 days; review and resolve.
- **`## Open`** — recent, healthy queue.
- **`## Abandoned`** — recommend archiving with a brief reason.

Each item includes a wikilink, the age, and a "recommended action" in parentheses.

## Side-effects

1. **Update `wiki/log/index.md`** to point at this queue.
2. **Append to changelog** if any ADRs moved from draft to a new status during this run.
3. **Optionally:** tag the responsible authors in a team channel for the Blocking section.

## Interactive Review

Don't auto-resolve ADRs; surface them for human review. The team's architect or tech lead should walk the queue and either:

- Move blocking ADRs to `accepted` (with finalized rationale)
- Move stale ADRs to `accepted`, `superseded`, or `archived`
- Confirm open queue items remain in active discussion

After the human walks the queue, run again — the queue should shrink.

## Failure Modes

- **No draft ADRs.** Produce a digest saying so, briefly. Healthy state.
- **Many draft ADRs (>20).** Likely a process problem — the team isn't closing decisions. Flag in synopsis, suggest a focused review session.
- **Blocking ADR with no responsible author.** Surface the gap; the team should designate an owner.
- **ADR references missing specs.** Broken wikilinks; surface in Anomalies.

## Cadence

- **Manual:** Before architecture review meetings.
- **Scheduled:** A Cowork weekly task running Sunday evening so the queue is fresh for Monday review.
