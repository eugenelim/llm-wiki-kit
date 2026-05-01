---
title: "RISK-{{PROJECT}}-{{NNN}}: {{Short risk title — what could go wrong}}"
type: risk
id: RISK-{{PROJECT}}-{{NNN}}
project: {{project-slug}}
status: open                  # open | mitigated | closed | realized
probability: medium           # high | medium | low
impact: high                  # high | medium | low
owner: "[[../../people/{{slug}}]]"
proximity: {{YYYY-MM-DD}}     # Earliest date this risk could materialize; use "TBD" if unknown
opened: {{YYYY-MM-DD}}
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
closed: null                  # ISO date when status → closed | realized
realized_as: null             # ISSUE-* wikilink if status = realized
related_tasks: []
related_meetings: []
related_decisions: []
related_issues: []            # Issues that would be resolved if this risk is mitigated
supersedes: null
provenance: extracted         # extracted | synthesized | mixed
tags: [risk, {{project-slug}}]
---

## Synopsis

{{One-to-three sentences. What could go wrong, and why it matters now.}}

## Description

{{What is the risk? Describe the scenario: what event or condition must occur for this risk to materialize. Include any leading indicators currently visible.}}

## Impact

{{If this risk materializes: which milestones, workstreams, or dependencies are affected? Quantify: cost estimate, delay duration, scope loss.}}

## Mitigation

**Preventive** (reduces probability):
{{Actions that lower the likelihood of materialization. Include owner and target date for each.}}

**Contingent** (limits damage if it materializes):
{{Response plan — who does what, by when.}}

## Trigger Conditions

{{Concrete signals indicating this risk is materializing. E.g., "If {event} by {date}, escalate immediately." Used for week-over-week monitoring in team-status.}}

## Owner & Escalation

- **Owner:** {{Who watches this risk and drives mitigation}}
- **Escalation path:** {{Who to escalate to if the mitigation plan stalls}}

## Timeline

Append-only event log. New entries go at the bottom.

- {{YYYY-MM-DD}} — identified in [[../meetings/{{...}}]] / {{context}}
- {{YYYY-MM-DD}} — promoted to formal Risk page

## Closure

*(Fill in only when `status: closed | realized`.)* How the risk was resolved (closed without materializing), or what Issue it became (realized). Link to the resolving artifact or the realized `ISSUE-*` page.

## Related

- Issues: [[...]]
- Meetings: [[...]]
- Decisions: [[...]]
- Tasks: [[...]]
