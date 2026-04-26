---
name: team-status
description: "Produce a consolidated forward-looking team-status page covering Progress (against goals/milestones), Risks (forward-looking), Issues (current blockers/incidents), and Asks (escalations + cross-team requests + decisions needed). Reads sprint plans, tasks, meeting decisions, ADRs accepted, request-tracker output, and risk/issue callouts. Use weekly before status meetings, monthly for steering committees, before quarterly business reviews, or on request: \"produce the team status\" / \"run the team-status report\" / \"team status for {project}\". For backward-looking \"what changed last 7 days\" use weekly-digest instead. To convert the output to a deck use status-slides."
license: MIT
metadata:
  variant: work
---

# Team Status Skill

Synthesizing operation. Produce a consolidated forward-looking team status with the four standard sections — **Progress**, **Risks**, **Issues**, **Asks** — structured so `status-slides` can map directly to a deck.

Distinct from `weekly-digest` (backward-looking — what changed in the last 7 days). team-status is forward-looking: where we are vs. plan, what could go wrong, what's currently blocked, what we need from others.

## When to Use

- Weekly before status meetings (default cadence)
- Monthly for steering-committee reviews
- Before a quarterly business review
- On request: "produce the team status" / "team status for {project}"

## Inputs

User provides:
- Scope: `team` (default — all active projects in `wiki/projects/`) or specific project slug
- Audience: `internal` (default), `leadership`, `steering-committee`, `customer` — affects detail and tone
- Optional: explicit period (default = since last team-status, fallback 7 days)

Reads:
- `wiki/projects/*/overview.md` — briefs, frontmatter `goals:` / `milestones:` if present
- Latest `wiki/projects/*/delivery/sprint-{date}.md` — current sprint commitments and progress
- `wiki/projects/*/tasks.md` — open / in-progress tasks (volume + blocked >7 days)
- `wiki/projects/*/meetings/*.md` from the period — recent decisions and action items
- `wiki/projects/*/decisions/*.md` — ADRs `accepted` since last status
- `> [!warning] Risk: ...` callouts across the wiki
- `> [!danger] Issue: ...` callouts across the wiki
- request-tracker output (or scan inline) — open asks and escalations
- Last team-status page (if exists) — for delta comparison

## Conventions

The four sections are populated from these signals:

| Section | Signals |
|---|---|
| **Progress** | sprint progress vs. plan, milestones hit/slipped, specs shipped, ADRs accepted, RAG per workstream |
| **Risks** | `> [!warning] Risk: {description}. Mitigation: {plan}.` callouts, plus risks inferred from slipped milestones / capacity gaps |
| **Issues** | `> [!danger] Issue: {description}. Owner: @{person}. ETA: {date}.` callouts, plus open high-priority tasks blocked >7 days |
| **Asks** | request-tracker output: open requests-to-others, escalations, decisions needed from leadership |

## Algorithm

1. **Collect.** Per project in scope: sprint plan, tasks, recent meetings, decisions, callouts.
2. **Compute RAG per project / workstream.**
   - **🟢 Green** — on track, no critical blockers
   - **🟡 Amber** — slipping but recoverable; one or more material risks open
   - **🔴 Red** — milestone in jeopardy; unmitigated issue; capacity gap; external blocker not moving
3. **Synthesize Progress.** What shipped, what's in-flight, what slipped. Frame against declared goals/milestones.
4. **Surface Risks.** Top 3-5 risks ranked by impact × likelihood. Each with mitigation plan and owner.
5. **Surface Issues.** Current blockers / incidents. Each with owner, ETA, escalation status.
6. **Surface Asks.** Decisions needed from leadership; cross-team requests outstanding (from request-tracker); capacity asks.
7. **Tailor to audience.**
   - **leadership / steering-committee:** terse, RAG-led, asks-prominent. ~1-2 pages.
   - **internal:** full detail, transparent on tradeoffs.
   - **customer:** progress-led; risks framed as "watch items"; issues only if customer-affecting.
8. **Write the status page** to `wiki/projects/{slug}/status/{YYYY-MM-DD}-team-status.md` (per-project) or `wiki/team-status/{YYYY-MM-DD}.md` (team-wide).

## Output

A `type: team-status` page with the canonical structure (so status-slides can map it):

```markdown
---
type: team-status
period: 2026-04-19..2026-04-25
audience: leadership
provenance: synthesized
created: 2026-04-25
modified: 2026-04-25
tags: [status, weekly]
---

## Synopsis
RAG: 🟡 Amber. Two projects on track; order-platform slipping schema sign-off. One material risk; one open issue. Two asks for leadership.

## Progress
| Workstream | RAG | Update |
|---|---|---|
| order-platform | 🟡 | 6 of 8 specs in implementation; schema sign-off blocking 2 specs |
| auth-service | 🟢 | MFA rollout 60% complete, on track for May 15 |
| platform-foundation | 🟢 | Service-mesh adoption Phase 2 done |

## Risks
- **R1 (high impact, medium likelihood):** Schema-registry vendor lock-in if Confluent migration delays past Q3. Mitigation: parallel evaluation of Apicurio (PoC by 2026-05-15). Owner: @lead-arch.
- **R2 ...**

## Issues
- **I1:** Order-ingestion DLQ growing 5% per day in staging. Owner: @sarah. ETA: 2026-04-30. Root cause: mis-shaped messages from upstream pre-canonical-model rollout.

## Asks (Leadership)
- **A1:** Approval to bring on contractor for schema migration (~$80k, 8 weeks). Decision needed by 2026-05-01.
- **A2:** Resolve cross-team dependency: @data-platform schema sign-off owed since 2026-04-10.

## What's Next (next 2 weeks)
- Ship 4 specs in order-platform; close DLQ issue; conclude vendor evaluation.
```

## Side-effects

1. Each project page's frontmatter `last_status:` updated to the new status page wikilink.
2. A digest entry appended to `log/changelog.md`.
3. If a previous team-status exists, a delta summary surfaces: "{N} risks new, {M} issues new, {K} risks resolved since {prev-date}."

## Pairs With

- **request-tracker** — feeds the Asks section. Run first.
- **status-slides** — converts this page to a best-practice executive PowerPoint.
- **weekly-digest** — backward-looking complement; together they answer "what changed?" and "what's the state of play?"
- **sprint-planning** — team-status reads the latest sprint plan as the Progress source-of-truth.

## Cadence

- **Weekly:** Default for team-internal status.
- **Monthly:** Steering-committee version, longer horizon, more polish.
- **Quarterly:** QBR version, integrated with broader business-review materials.

## Failure Modes

- **No risk/issue callouts in the wiki.** Surface: "no `> [!warning] Risk:` or `> [!danger] Issue:` callouts found. Either the team isn't using the convention, or there really are none. Want me to infer from slipped milestones / blocked tasks?"
- **Last status was very recent.** If a team-status was generated <3 days ago and nothing has changed materially, propose updating the existing one rather than creating a new one.
- **Audience mismatch.** If `audience: customer` is requested but Issues contains internal-only language, flag for review before producing.
- **Many projects red.** If the majority of projects are RAG: red, surface a top-line "the team is overloaded" rather than burying it in workstream rows.
