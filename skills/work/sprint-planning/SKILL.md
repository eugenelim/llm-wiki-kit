---
name: sprint-planning
description: "Produce a dated sprint-plan page for a project, reading specs (status ready/in-progress), tasks, last sprint plan, and capacity. The canonical work-OS operation. Use at sprint kickoff (typically Monday morning before the team starts the new sprint), mid-sprint after a major blocker or scope change, or on request: \"plan the next sprint for {project}\"."
license: MIT
metadata:
  variant: work
---

# Sprint Planning Skill

The canonical work-OS operation. Read the project's specs, tasks, and capacity; produce a dated sprint plan page that becomes the input to the sprint, the next sprint's planner, and the weekly digest.

## When to Use

- Sprint kickoff (typically Monday morning before the team starts the new sprint)
- Mid-sprint replan after a major blocker, scope change, or capacity shift
- On request: "Plan the next sprint for {project}"

This skill operates per-project. If the team runs unified sprints across multiple projects, run the skill for each project and consolidate manually, or extend the skill with a multi-project mode.

## Inputs

Read the following from the wiki:

1. **Specs ready or in-progress.** All `.md` files in `wiki/projects/{project-slug}/specs/` filtered to `status: ready` or `status: in-progress`. For each: title, status, point estimate (frontmatter `points:` field if present), assignee, dependencies (frontmatter `depends_on:` field), and the spec's Current State section.
2. **Project tasks.** `wiki/projects/{project-slug}/tasks.md` — open and in-progress tasks with priorities and assignees.
3. **Last sprint plan.** Most recent file in `wiki/projects/{project-slug}/delivery/` matching `sprint-{date}.md`. Identify what was committed, what shipped (`status: done`), what carried over (`status: in-progress`), what got deferred.
4. **Capacity.** Either pulled from the PM-sync skill if active (Linear / Jira / Plane), or read from `wiki/projects/{project-slug}/team.md` if maintained, or asked of the user if absent. Use story points, days, or hours — whatever the team uses.
5. **Recent meeting decisions.** Files in `wiki/projects/{project-slug}/meetings/` modified in the last 14 days, scanning for new spec needs or scope changes.
6. **Blocking ADRs.** Any ADR referenced by a candidate spec where the ADR's `status` is `draft` (not yet `accepted`).

## Algorithm

1. **Build the candidate list.** Specs with `status: ready` or `status: in-progress`, plus carry-over items from the last sprint that didn't ship.
2. **Honor dependencies.** If spec A depends on spec B, schedule B (or a meaningful slice of B) first, or surface as a blocker.
3. **Surface blocking ADRs.** Any ADR in `draft` that gates a candidate spec must be either resolved this sprint or the dependent spec must be deferred. Add ADR resolution as an explicit committed item with a point estimate.
4. **Match to capacity.** Default buffer: 25-30% of total capacity for bugs, meetings, code review. Don't fill the buffer with optional work; leave it empty.
5. **Carry-over policy.** In-progress items from last sprint carry by default unless flagged for reset (frontmatter `reset_on_carry: true` on the spec).
6. **Stretch list.** Optional items the team can promote if early-sprint progress allows. Keep small (1-2 items).

## Output

Write `wiki/projects/{project-slug}/delivery/sprint-{YYYY-MM-DD}.md` (date is the sprint start) with frontmatter:

```yaml
---
type: sprint-plan
project: {project-slug}
sprint: {YYYY-MM-DD}
created: {today}
modified: {today}
tags: [sprint-plan, {project-slug}]
status: active
---
```

Body sections:

- **`## Synopsis`** — 2-3 sentences. Sprint dates, total committed points, stretch points, key dependencies / blockers.
- **`## Sprint Goal`** — 1-2 sentences capturing the strategic objective of the sprint.
- **`## Committed`** — list each item with point estimate, wikilink to its spec (or ADR), assignee, and a one-line rationale or status note.
- **`## Stretch`** — same format, flagged optional.
- **`## Blockers and dependencies`** — explicit list of what could derail the sprint, with wikilinks.
- **`## Capacity`** — per-person committed vs. available; total committed and stretch with buffer percentage.
- **`## Notes for next sprint's planner`** — anything the next planner needs to know (scope-refinement hints, ADR resolution status, planned-but-deferred items).

## Side-effects

After writing the sprint plan:

1. **Update each committed spec's frontmatter** to set `sprint: {YYYY-MM-DD}`.
2. **Push committed items to the PM tool** via [[sync-pm-linear]] / [[sync-pm-jira]] / [[sync-pm-plane]] if PM sync is active.
3. **Update `wiki/projects/{project-slug}/delivery/index.md`** with the new sprint entry.
4. **Append to `log/changelog.md`** with one line summarizing what shipped from last sprint and what's committed for this one.

## Interactive Review

Before writing, present the proposed sprint plan to the user:

```
Proposed sprint 2026-04-26 → 2026-05-09 for order-platform:

Sprint goal: ship canonical-model transformation + Schema Registry
integration so order-ingestion service can move draft → review.

Committed (23 / 38 pts, ~26% buffer):
  [8 pt] specs/order-ingestion-service (continued, Eugene)
  [5 pt] specs/schema-registry-integration (new, Sarah)
  [5 pt] specs/dlq-monitoring (new, Jake)
  [3 pt] adr-007-schema-evolution (blocker, whole team week 1)
  [2 pt] integration tests for DLQ (carry-over)

Stretch (5 pts):
  [5 pt] specs/error-budget-dashboard (Q3 commitment)

Blockers:
  adr-007-schema-evolution must be accepted before
  schema-registry-integration moves to review.

Save sprint plan to delivery/sprint-2026-04-26.md and push to Linear?
```

The user can adjust scope, swap items between committed / stretch, mark items as deferred, or request a different capacity assumption. Don't write the page until the user confirms.

## Failure Modes

- **No specs are ready.** The team needs to author specs before sprint planning. Surface this as: "No specs in `ready` status. Run a spec-refinement session before sprint planning, or pull from `draft` specs with explicit user approval."
- **Capacity unknown.** Ask the user. Don't invent capacity numbers.
- **Last sprint plan missing.** First sprint of the project — proceed without carry-over logic, note in the plan that no prior sprint exists.
- **Spec dependency cycle.** Two specs depend on each other (likely an authoring error). Surface to the user; don't try to resolve automatically.
- **Stretch dwarfs committed.** Means the team is hedging; ask the user to firm up commitment.

## Cadence

- **Manual:** Run before each sprint kickoff.
- **Scheduled:** A Cowork scheduled task could run this every 2 weeks on Monday morning, then ping the manager for review.
