---
name: request-tracker
description: "Scan project pages, meetings, decisions, and task boards for outstanding requests-to-others, cross-team dependencies, and escalations; surface what's owed back to the team and what we're waiting on, with due dates and original-ask context. Use weekly, before status meetings, before sprint-planning (asks owed back affect what we can commit), after a meeting that generated cross-team action items, or on request: \"what are we waiting on?\" / \"run the escalation tracker\" / \"open requests across projects\". The work-variant analog of follow-up-tracker (family) — same shape, work-domain triggers."
license: MIT
metadata:
  variant: work
---

# Request Tracker Skill

Reminding operation. Walk every active project's pages, meetings, decisions, and task board for outstanding requests-to-others; surface items due in the next 30 days, items overdue, and stale escalation candidates.

The work-variant analog of `follow-up-tracker` (family): a passive scanner that keeps the team ahead of cross-team dependencies rather than waiting for a status meeting to surface them.

## When to Use

- Weekly (default cadence)
- Before status meetings
- Before sprint planning (asks owed back affect what we can commit)
- After a meeting that generated cross-team action items
- On request: "what are we waiting on?" / "run the escalation tracker"

## Inputs

User provides:
- Optional: window (default 30 days)
- Optional: filter (e.g., "blocking the order-platform project," "owed BY @sarah," "stale only")
- Optional: project slug to scope to a single project

Reads:
- `wiki/projects/*/overview.md` — frontmatter `waiting_on:` field if present
- `wiki/projects/*/meetings/*.md` — `## Action Items` sections; flag items assigned to people outside the team's roster
- `wiki/projects/*/decisions/*.md` — "blocked on X" callouts
- `wiki/projects/*/tasks.md` — Open + In Progress tasks with assignees outside the project team
- Any page with `> [!important] Waiting on @{person|team} by {date}: {ask}` callouts
- All `wiki/people/*.md` — `## Open Asks` section callouts (both directions: waiting-on and owed-back)
- `wiki/projects/*/team.md` — internal-vs-external roster (links into `wiki/people/`)

## Conventions

The skill scans for this callout pattern across the wiki:

```markdown
> [!important] Waiting on @{person|team} by {date}: {ask}
> Originally asked: {date}. Context: [[meetings/...]] or [[decisions/...]]
```

Plus frontmatter on project overviews:

```yaml
waiting_on:
  - { who: "@data-platform", ask: "schema sign-off", asked: 2026-04-10, due: 2026-04-30 }
```

## Algorithm

1. **Collect.** Walk each project's overview, meetings, decisions, tasks. Extract every "Waiting on" callout, externally-assigned action item, and `waiting_on:` frontmatter entry.
2. **Normalize.** For each item: project, source-page, ask, owed-by, originally-asked, due, status.
3. **Classify.**
   - **Due this week** — due ≤7 days
   - **Due this month** — due 8-30 days
   - **Stale** — asked >14 days ago, no due date, no recent meeting reference
   - **Escalation candidate** — past due, or stale-and-blocking
4. **Group.** By project (default), or by owed-by person/team (`--by-person`).
5. **Surface.** Inline ranked report; offer to update each project's `waiting_on:` frontmatter.

## Output

Inline markdown report; optionally appended to `wiki/projects/{slug}/status/{date}-requests.md` if asked.

```markdown
## Open Requests — week of 2026-04-25

### Due this week
- **order-platform**: Schema sign-off from @data-platform — asked 2026-04-10, due 2026-04-30. [[meetings/2026-04-10-schema-review]]
- **auth-service**: Security review from @secops — asked 2026-04-15, due 2026-04-26. [[decisions/2026-04-15-mfa-rollout]]

### Due this month
- ...

### Stale (>14 days, no movement)
- **order-platform**: Q3 capacity from @platform-leadership — asked 2026-04-01, no due date. **Escalation candidate.**

### Escalations recommended
- ...
```

## Side-effects

1. Optionally update `waiting_on:` in each project's `overview.md` frontmatter with the current open list.
2. Append to `log/changelog.md`: "Request tracker run: {N} open requests across {M} projects, {K} escalation candidates."

## Pairs With

- **team-status** — request-tracker output feeds the **Asks** section. Run request-tracker first; team-status reads the result (or scans inline).
- **sprint-planning** — sprint-planning should account for asks owed back; run request-tracker first to surface them.
- **ingest-meeting** — meeting captures are the primary source of new requests; encourage adding `> [!important] Waiting on @X` callouts during synthesis.

## Failure Modes

- **No "Waiting on" callouts captured.** Surface: "no open requests detected. Either nothing is pending, or the team isn't using the `> [!important] Waiting on @X by {date}` callout. Want me to scan meeting transcripts heuristically for 'waiting on' / 'blocked by' prose?"
- **Owed-by name unresolved.** If `@person|team` doesn't match the project's `team.md` or shared roster, flag as "external — verify name."
- **Many stale items.** Surface: "{N} items stale (>14 days, no movement). Run team-status to surface as risks, or escalate to leadership."

## Cadence

- **Weekly:** Default. Run before the team's status meeting.
- **Pre-sprint:** Before sprint-planning so the team accounts for asks owed back.
- **Per-project:** Before any external-stakeholder review.
