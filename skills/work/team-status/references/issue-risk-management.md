# Issue & Risk Management — Reference

Detailed conventions, field semantics, lifecycle state machines, and migration guidance for the structured issue and risk page types introduced in the `team-status` skill.

## Page layout

Each project's `wiki/projects/{slug}/` directory gains two new subfolders:

```
wiki/projects/{slug}/
├── issues/
│   ├── _index.md              # Lists open issues by severity; links to .base
│   ├── _issues.base           # Bases view (copy from skill assets/_issues.base)
│   ├── ISSUE-{ABBREV}-001.md
│   └── ISSUE-{ABBREV}-002.md
└── risks/
    ├── _index.md              # Lists open risks by impact×probability; links to .base
    ├── _risks.base            # Bases view (copy from skill assets/_risks.base)
    ├── RISK-{ABBREV}-001.md
    └── RISK-{ABBREV}-002.md
```

`{ABBREV}` is a 2–8 character uppercase abbreviation of the project slug with hyphens removed (e.g., `order-platform` → `ORDER`, `auth-service` → `AUTH`). Choose it once and never change it — IDs are stable.

When creating an `issues/` or `risks/` folder for a project, also create `_index.md` with the following structure:

```markdown
---
type: index
title: "{Project} Issues"
project: {project-slug}
created: YYYY-MM-DD
modified: YYYY-MM-DD
tags: [index, issue, {project-slug}]
---

## Open Issues

| ID | Severity | Title | Owner | ETA |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

*(Auto-populated by `_issues.base` view; list is a fallback for non-Bases environments.)*

## Recently Resolved (last 30 days)

*(List resolved issues here after closing them.)*
```

## Field semantics

### Issue fields

| Field | Required | Notes |
|---|---|---|
| `id` | yes | Stable. Format `ISSUE-{ABBREV}-{NNN}`, zero-padded counter per project. Never renumber. |
| `status` | yes | `open` (default). `mitigated` = workaround in place, root cause unresolved. `resolved` = root cause fixed. `wont-fix` = decision not to address. `duplicate` = `supersedes` must point to canonical issue. |
| `severity` | yes | `critical` = milestone in jeopardy / data loss / outage. `high` = workstream significantly blocked. `medium` = notable drag, workaround viable. `low` = nuisance, future cleanup. |
| `owner` | yes | Single accountable person. Wikilink to `people/` page. Avoid teams or "TBD" — ownerless issues stall. |
| `escalation` | conditional | Required when `severity: critical` or `high`. |
| `eta` | yes | ISO date. `TBD` is acceptable when genuinely unknown — do not guess. |
| `opened` vs `created` | both | `opened` = when the issue first surfaced (may predate the page). `created` = when this page was authored. The gap tells you capture latency. |
| `resolved` | conditional | Set when status moves to `resolved` or `wont-fix`. Used by `team-status` for delta counts. |
| `related_risks` | optional | RISK-* pages this issue is the realized form of. |

### Risk fields

| Field | Required | Notes |
|---|---|---|
| `id` | yes | Stable. Format `RISK-{ABBREV}-{NNN}`, zero-padded counter per project. |
| `status` | yes | `open` (default). `mitigated` = mitigation plan active, risk still possible. `closed` = risk no longer applicable. `realized` = risk materialized into an issue — set `realized_as`. |
| `probability` | yes | `high` / `medium` / `low`. |
| `impact` | yes | `high` / `medium` / `low`. |
| `proximity` | yes | Earliest date the risk could materialize. Distinct from `eta` — this is a horizon, not a deadline. |
| `realized_as` | conditional | Wikilink to the `ISSUE-*` page when `status: realized`. |

## Lifecycle

### Issue lifecycle

```
[inline callout]
     │
     │ persists > 1 week without formal page
     ▼
  open ──────────────────────────────────► resolved
     │                                       ▲
     │ workaround in place                   │ root cause fixed
     ▼                                       │
  mitigated ─────────────────────────────────┘
     │
     │ decision not to address
     ▼
  wont-fix
     │
     │ duplicate found
     ▼
  duplicate (supersedes → canonical ISSUE-*)
```

### Risk lifecycle

```
[inline callout]
     │
     │ persists > 1 week without formal page
     ▼
  open ──────────────────────────────────► closed (risk no longer applicable)
     │
     │ mitigation plan active
     ▼
  mitigated ──────────────────────────────► closed
     │
     │ risk materializes
     ▼
  realized → creates ISSUE-* page; set realized_as
```

## Callout quick-capture (preserved)

The existing callout conventions are **preserved as a low-friction inbox**:

- `> [!warning] Risk: {description}. Mitigation: {plan}.` — captures a risk anywhere in the wiki
- `> [!danger] Issue: {description}. Owner: @{person}. ETA: {date}.` — captures an issue anywhere

**Promotion rule:** any callout that persists across two consecutive `team-status` runs (approximately one week) without a corresponding formal page MUST be promoted. The `team-status` skill detects un-promoted callouts and surfaces them in the delta summary with an offer to auto-promote.

**Auto-promotion offer (team-status):**
> "N inline [issue|risk] callouts have persisted >1 week without a formal page. Want me to promote them to [ISSUE|RISK]-{ABBREV}-{NNN} pages? I'll pre-fill `opened`, `description`, `owner`, and `eta` from the callout text."

If the user accepts, `team-status` creates the pages using the template from `_templates/issue.md` or `_templates/risk.md`, then records the new IDs in the delta summary.

## Migration for existing vaults

For vaults currently using only inline callouts, run `team-status` and accept the promotion offer when it surfaces. The skill will:

1. Scan every `> [!warning] Risk:` and `> [!danger] Issue:` callout across the wiki.
2. Generate one candidate page per callout under `wiki/projects/{slug}/issues/` or `wiki/projects/{slug}/risks/`.
3. Counter starts at `001` per project.
4. Pre-fill fields from callout text; leave `severity`, `probability`, `impact`, `escalation`, and `related_*` for human review.

After migration, the original callouts can remain in place (they are recognized as already-promoted when their fingerprint matches a formal page) or be replaced with a wikilink to the formal page.

## Severity / probability color tokens

These tokens are used consistently across `team-status` markdown output and `status-slides` deck rendering:

| Level | Markdown icon | Slide swatch (RGB) |
|---|---|---|
| critical / high impact | 🔴 | `#D32F2F` |
| high probability | 🟠 | `#F57C00` |
| medium | 🟡 | `#FBC02D` |
| low | ⚪ | `#9E9E9E` |
