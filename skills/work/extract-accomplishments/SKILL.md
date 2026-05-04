---
name: extract-accomplishments
description: "Synthesize completed tasks from a time period into an accomplishments report covering key wins, volume by project and priority, and detected themes. Sources: wiki/projects/*/archive/tasks-YYYY-MM.md (primary) and wiki/projects/*/tasks.md Done sections (fallback for unarchived work). Output: wiki/team-status/accomplishments-{period}.md for team-wide, wiki/projects/{slug}/delivery/accomplishments-{period}.md for single-project scope. Use when asked \"what did we accomplish last month?\" / \"extract accomplishments for Q2\" / \"generate an accomplishments report\" / \"what did we ship this quarter?\" / \"show me what the team finished in April\". Not for forward-looking status (use team-status). Run archive-done-tasks first for best archive coverage."
license: MIT
metadata:
  variant: work
---

# Extract Accomplishments Skill (Work Variant)

Backward-looking synthesis operation. Reads completed tasks from monthly
archive files and live Done sections; produces a structured accomplishments
report with highlights, per-project breakdown, volume summary, and
Claude-detected themes.

Distinct from `team-status` (forward-looking: risks, issues, asks) and
`weekly-digest` (general activity log). This skill answers specifically:
"what did we *finish* over this period?"

## When to Use

- End-of-month or end-of-quarter retrospective
- Before a stakeholder update where you need to show what shipped
- Leadership asks "what did the team accomplish this quarter?"
- On request: "extract accomplishments for {period}" / "what did we
  ship last month?" / "generate an accomplishments report"

Pair with `archive-done-tasks` first when the Done sections in `tasks.md`
have not been recently archived — live Done tasks are included as a
fallback, but archived tasks are easier to query by date.

## Inputs

User provides:
- **Period** — one of:
  - `YYYY-MM` (e.g., `2026-04`) — a specific calendar month
  - `YYYY-QN` (e.g., `2026-Q2`) — a fiscal quarter (Q1 = Jan–Mar, Q2 = Apr–Jun,
    Q3 = Jul–Sep, Q4 = Oct–Dec)
  - `last-month`, `last-quarter`, `this-month`, `this-quarter` — relative shorthands
  - A custom date range: `{start} to {end}` (ISO dates)
  - If not provided, prompt the user.
- **Scope** — `team` (default, all projects) or a project slug
- **Audience** — `internal` (default), `leadership` (terser, highlights only)

Reads:
- `wiki/projects/*/archive/tasks-YYYY-MM.md` — primary source; filtered to
  months within the period
- `wiki/projects/*/tasks.md` — Done section; used as fallback for tasks with
  `Completed:` dates in the period that haven't been archived yet
- `wiki/projects/*/overview.md` — for project display names and goals context

## Algorithm

1. **Resolve period.** Convert relative shorthands to absolute date ranges
   (e.g., `last-month` from today 2026-05-04 → 2026-04-01..2026-04-30).
2. **Collect archive tasks.** Read `archive/tasks-YYYY-MM.md` files whose
   `period:` frontmatter falls within the resolved date range. Extract all
   `- [x]` blocks.
3. **Collect live Done tasks (fallback).** For each project in scope, read
   the `## Done` section of `tasks.md`. Include tasks whose `Completed: YYYY-MM-DD`
   falls in the period. Skip tasks that appear identical to an already-collected
   archive entry (match on title after stripping priority marker).
4. **Tag each task with its project.** Derive from the file path
   (`wiki/projects/{slug}/...`).
5. **Classify highlights.** Tasks with `**[HIGH]**` priority are candidates
   for the highlights list. From those, select up to 5 that had the highest
   apparent impact (infer from context links — tasks linking to specs or ADRs
   rank higher than standalone tasks).
6. **Detect themes.** Look for recurring keywords, assignees, or context links
   across tasks. Surface patterns that appear in 3+ tasks as themes.
7. **Compute volume summary.** Count tasks per project × priority level.
8. **Compose the report.** Write using the output format below.
9. **Write output.** Team-wide → `wiki/team-status/accomplishments-{period}.md`;
   project-scoped → `wiki/projects/{slug}/delivery/accomplishments-{period}.md`.
   Do not overwrite an existing file; append `-v2`, `-v3` if one already exists.
10. **Changelog.** Append to `log/changelog.md`:
    "Accomplishments report for {period}: [[{output path}]]. {N} tasks across
    {M} projects."

## Output Format

```markdown
---
type: review
review_cadence: monthly          # or quarterly
period: YYYY-MM                  # or YYYY-QN
scope: team                      # or {project-slug}
audience: internal               # or leadership
provenance: synthesized
created: YYYY-MM-DD
modified: YYYY-MM-DD
tags: [review, accomplishments, {period}]
status: active
---

## Synopsis

{N} tasks completed across {M} projects in {period}. {K} high-priority items
shipped. Dominant themes: {theme 1}, {theme 2}.

## Highlights

Top completions by impact:

- [x] **[HIGH]** Implement canonical model transformation (order-platform)
  Assignee: @eugene · Completed: 2026-04-22
  Context: [[../projects/order-platform/specs/order-ingestion-service]]

- [x] **[HIGH]** MFA rollout: SMS provider migration (auth-service)
  Assignee: @raj · Completed: 2026-04-28

## By Project

### Order Platform

- [x] **[HIGH]** Implement canonical model transformation — @eugene · 2026-04-22
- [x] **[HIGH]** Write integration tests for DLQ handling — @sarah · 2026-04-30
- [x] **[MED]** Add Schema Registry integration — @sarah · 2026-04-23

### Auth Service

- [x] **[HIGH]** MFA rollout: SMS provider migration — @raj · 2026-04-28
- [x] **[MED]** Rotate API keys in staging — @raj · 2026-04-15

## Volume Summary

| Project | High | Med | Low | Total |
|---|---|---|---|---|
| order-platform | 2 | 1 | 0 | 3 |
| auth-service | 1 | 1 | 0 | 2 |
| **Total** | **3** | **2** | **0** | **5** |

## Themes

Patterns detected across this period's completed work:

- **Schema infrastructure** — 3 tasks in order-platform touched schema
  validation or the Schema Registry. Suggests this is a foundational
  workstream worth tracking as a topic page.
- **Security hygiene** — 2 tasks (API key rotation, MFA migration) across
  different projects. Consider a cross-cutting checklist.

## Sources

- [[../projects/order-platform/archive/tasks-2026-04|order-platform archive — 2026-04]]
- [[../projects/auth-service/archive/tasks-2026-04|auth-service archive — 2026-04]]
```

### Leadership mode

When `audience: leadership`:
- Emit Synopsis + Highlights + Volume Summary only (skip By Project detail)
- Cap Highlights to 3 items
- Themes section replaced by a single "What this tells us" sentence in Synopsis

## Failure Modes

- **No tasks found for the period.** Surface: "No completed tasks found in
  {period} across {scope}. Either the period is before any tasks were logged,
  or tasks.md Done sections are empty and archives don't yet exist for this
  period." Do not write an output file.
- **Period partially covered by archives, rest in live Done.** Proceed with both
  sources; note in the Synopsis: "Some tasks sourced from unarchived Done sections
  — run archive-done-tasks for complete coverage."
- **Output file already exists.** Append a version suffix (`-v2`) and surface:
  "An accomplishments report for {period} already exists at {path}. Wrote new
  version as {path-v2}."
- **No projects in scope.** Surface: "No wiki/projects/ directories found." Exit.

## Pairs With

- **[[archive-done-tasks]]** — run first; this skill reads what it produces
- **[[team-status]]** — forward-looking complement; accomplishments is backward
- **[[weekly-digest]]** — weekly-digest is broader activity; this is completion-only
- **[[sprint-planning]]** — use an accomplishments report as input to velocity
  estimation in the next sprint plan

## Cadence

- **Monthly:** Run at month-end for a clean record before starting a new month.
- **Quarterly:** Roll up the quarter before a business review or team retrospective.
- **On-demand:** Any time a stakeholder asks "what did we ship?"
