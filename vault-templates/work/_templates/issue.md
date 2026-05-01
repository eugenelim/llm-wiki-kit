---
title: "ISSUE-{{PROJECT}}-{{NNN}}: {{Short imperative title — what's broken or blocked}}"
type: issue
id: ISSUE-{{PROJECT}}-{{NNN}}
project: {{project-slug}}
status: open                  # open | mitigated | resolved | wont-fix | duplicate
severity: medium              # critical | high | medium | low
owner: "[[../../people/{{slug}}]]"
escalation: null              # Required when severity: critical or high
eta: {{YYYY-MM-DD}}           # Target resolution date; use "TBD" only if genuinely unknown
opened: {{YYYY-MM-DD}}        # When first surfaced (may pre-date this page)
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
resolved: null                # ISO date when status → resolved | wont-fix
related_tasks: []
related_meetings: []
related_decisions: []
related_risks: []             # RISK-* pages this issue is the realized form of
supersedes: null              # ISSUE-* this page replaces (use for duplicates)
provenance: extracted         # extracted | synthesized | mixed
tags: [issue, {{project-slug}}]
---

## Synopsis

{{One-to-three sentences. The TL;DR a steering-committee reader needs without reading the rest of this page.}}

## Description

{{What's broken or blocked. Name the system, the failing action, and the surface where it manifests. Be specific about which workstream and artifact is affected. Avoid vague framing — state the concrete symptom.}}

## Impact

{{What does this block if unresolved past the ETA? Name affected milestones, deliveries, or downstream teams. Quantify where possible (e.g., "blocks 3 specs", "delays M2 by ~2 weeks").}}

## Mitigation

{{Current workaround or active plan to reduce impact while the root cause is addressed. Distinct from resolution. If none, state "None — working toward resolution directly."}}

## Owner & Escalation

- **Owner:** {{Who is accountable for driving resolution}}
- **Escalation path:** {{Who to escalate to if the owner is blocked or non-responsive}}
- **Escalation rule:** {{Optional. E.g., "1–2 day commitment-date rule per standing process."}}

## Timeline

Append-only event log. New entries go at the bottom.

- {{YYYY-MM-DD}} — surfaced in [[../meetings/{{...}}]] / {{callout location}}
- {{YYYY-MM-DD}} — promoted to formal Issue page

## Resolution

*(Fill in only when `status: resolved | wont-fix`.)* How the issue was resolved, or why it was closed without resolution. Link to the resolving artifact (commit, ADR, vendor response, decision).

## Related

- Tasks: [[...]]
- Meetings: [[...]]
- Risks: [[...]]
- Decisions: [[...]]
