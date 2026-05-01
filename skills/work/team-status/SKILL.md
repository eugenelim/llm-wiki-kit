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
- `wiki/projects/*/issues/ISSUE-*.md` — formal Issue pages (`status: open | mitigated`) — primary source
- `wiki/projects/*/risks/RISK-*.md` — formal Risk pages (`status: open | mitigated`) — primary source
- `> [!warning] Risk: ...` callouts across the wiki — fallback / quick-capture inbox
- `> [!danger] Issue: ...` callouts across the wiki — fallback / quick-capture inbox
- request-tracker output (or scan inline) — open asks and escalations
- Last team-status page (if exists) — for delta comparison

## Conventions

The four sections are populated from these signals:

| Section | Signals |
|---|---|
| **Progress** | sprint progress vs. plan, milestones hit/slipped, specs shipped, ADRs accepted, RAG per workstream |
| **Risks** | Primary: `wiki/projects/*/risks/RISK-*.md` pages (`status: open | mitigated`), ordered by impact × probability then proximity. Secondary: `> [!warning] Risk:` callouts (treated as untriaged — flag for promotion). Plus risks inferred from slipped milestones / capacity gaps. |
| **Issues** | Primary: `wiki/projects/*/issues/ISSUE-*.md` pages (`status: open | mitigated`), ordered by severity then ETA. Secondary: `> [!danger] Issue:` callouts (treated as untriaged — flag for promotion). Plus open high-priority tasks blocked >7 days. |
| **Asks** | request-tracker output: open requests-to-others, escalations, decisions needed from leadership |

## Algorithm

1. **Collect.** Per project in scope: sprint plan, tasks, recent meetings, decisions, callouts.
2. **Compute RAG per project / workstream.**
   - **🟢 Green** — on track, no critical blockers
   - **🟡 Amber** — slipping but recoverable; one or more material risks open
   - **🔴 Red** — milestone in jeopardy; unmitigated issue; capacity gap; external blocker not moving
3. **Synthesize Progress.** What shipped, what's in-flight, what slipped. Frame against declared goals/milestones.
4. **Surface Risks.** Read formal Risk pages first (`RISK-*.md`, status: open | mitigated), ordered by impact × probability then proximity. Fall back to `> [!warning] Risk:` callouts for untriaged items. Cap 3-5 for leadership, 8 for internal.
5. **Surface Issues.** Read formal Issue pages first (`ISSUE-*.md`, status: open | mitigated), ordered by severity then ETA. Fall back to `> [!danger] Issue:` callouts for untriaged items.
6. **Surface Asks.** Decisions needed from leadership; cross-team requests outstanding (from request-tracker); capacity asks.
7. **Tailor to audience.**
   - **leadership / steering-committee:** terse, RAG-led, asks-prominent. ~1-2 pages.
   - **internal:** full detail, transparent on tradeoffs.
   - **customer:** progress-led; risks framed as "watch items"; issues only if customer-affecting.
8. **Triage unpromoted callouts.** For each inline callout, check whether a matching formal page exists (fingerprint by description + owner + ETA). Any callout that has persisted across two consecutive runs without a formal page surfaces in the delta summary with a promotion offer:
   > "N inline [issue|risk] callouts have persisted >1 week. Want me to promote them to formal pages?"
   If accepted, create pages from `_templates/issue.md` / `_templates/risk.md` (or `assets/issue-template.md` / `assets/risk-template.md` if the vault templates are missing).
9. **Write the status page** to `wiki/projects/{slug}/status/{YYYY-MM-DD}-team-status.md` (per-project) or `wiki/team-status/{YYYY-MM-DD}.md` (team-wide).

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
RAG: 🟡 Amber. Two projects on track; order-platform slipping schema sign-off. Risks: 1 open (1 unregistered). Issues: 1 critical / 1 medium (1 untriaged). Two asks for leadership.

<!-- Note: Synopsis names order-platform because it is the single principal signal of the period. The other two projects appear only via the "two on track" count. Do not write one sentence per project here. -->

## Progress
| Workstream | RAG | Update |
|---|---|---|
| order-platform | 🟡 | 6 of 8 specs in implementation; schema sign-off blocking 2 specs |
| auth-service | 🟢 | MFA rollout 60% complete, on track for May 15 |
| platform-foundation | 🟢 | Service-mesh adoption Phase 2 done |

## Risks

| ID | P×I | Title | Owner | Proximity | Status |
|---|---|---|---|---|---|
| [[../projects/order-platform/risks/RISK-ORDER-003\|RISK-ORDER-003]] | high×high | Schema-registry vendor lock-in if Confluent delays | @lead-arch | 2026-05-15 | open |

**Unregistered callouts:** 1 (persisted >1 week — recommend promotion)
- "Capacity gap if contractor not approved" — surfaced in tasks. Owner: @pm. Proximity: TBD.

## Issues

| ID | Severity | Title | Owner | ETA | Status |
|---|---|---|---|---|---|
| [[../projects/order-platform/issues/ISSUE-ORDER-007\|ISSUE-ORDER-007]] | 🔴 critical | Order-ingestion DLQ growing 5%/day in staging | @sarah | 2026-04-30 | open |
| [[../projects/auth-service/issues/ISSUE-AUTH-002\|ISSUE-AUTH-002]] | 🟡 medium | MFA SMS provider rate-limited after 100 req/min | @raj | 2026-05-10 | mitigated |

**Untriaged callouts:** 1 (persisted >1 week — recommend promotion)
- "Schema sign-off owed by data-platform" — surfaced in [[../projects/order-platform/tasks]]. Owner: @data-platform. ETA: TBD.

## Asks (Leadership)
- **A1:** Approval to bring on contractor for schema migration (~$80k, 8 weeks). Decision needed by 2026-05-01.
- **A2:** Resolve cross-team dependency: @data-platform schema sign-off owed since 2026-04-10.

## What's Next (next 2 weeks)
- Ship 4 specs in order-platform; close DLQ issue; conclude vendor evaluation.
```

### Synopsis vs Progress — no duplication

The Synopsis is a top-line roll-up consumed at-a-glance; the Progress table is the per-project detail layer. They must not duplicate content:

- **Synopsis MUST contain:** overall RAG, count of projects per RAG band (e.g., "2 green / 1 amber / 0 red"), counts of risks / issues / asks, and the single most-important top-line signal for the period.
- **Synopsis MUST NOT contain:** one sentence per project paraphrasing each project's Progress row. If you find yourself writing "A did X. B did Y. C did Z." in the Synopsis, that is the bug — move the detail into Progress and replace the Synopsis with a counts-and-RAG summary.
- **Synopsis MAY name a specific project** only when that project is the dominant signal of the period (the principal Amber driver, the project that resolved a major risk, the project newly red). One project max in a typical Synopsis.

What's Next is forward-looking and is expected to have per-project bullets — that is not duplication of Progress.

## Side-effects

1. Each project page's frontmatter `last_status:` updated to the new status page wikilink.
2. A digest entry appended to `log/changelog.md`.
3. If a previous team-status exists, a delta summary surfaces: "{N} risks new, {M} issues new, {K} risks resolved since {prev-date}."
4. **Triage delta.** The status page records structured counts in the Synopsis: `{open}` open issues, `{mitigated}` mitigated, `{resolved-this-period}` resolved, `{untriaged}` untriaged callouts. Same for risks (`{open}` / `{mitigated}` / `{realized}` / `{unregistered}`).

See `references/issue-risk-management.md` for field semantics, lifecycle state machines, Bases view setup, and migration guidance.

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

- **No formal issue/risk pages and no callouts.** Surface: "no `ISSUE-*.md` / `RISK-*.md` pages and no `> [!warning]` / `> [!danger]` callouts found. Either the team isn't using these conventions, or there genuinely are none. Want me to infer from slipped milestones / blocked tasks?"
- **Last status was very recent.** If a team-status was generated <3 days ago and nothing has changed materially, propose updating the existing one rather than creating a new one.
- **Audience mismatch.** If `audience: customer` is requested but Issues contains internal-only language, flag for review before producing.
- **Many projects red.** If the majority of projects are RAG: red, surface a top-line "the team is overloaded" rather than burying it in workstream rows.
