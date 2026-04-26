---
title: "{{Meeting Title}}"
type: meeting
project: {{project-slug}}
date: {{YYYY-MM-DD}}
participants: []
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
provenance: synthesized
sources:
  - raw/{{project-slug}}/meeting-transcripts/{{YYYY-MM-DD}}-{{topic}}.md
tags: [meeting, {{meeting-type}}, {{project-slug}}]
related_specs: []
related_adrs: []
---

## Synopsis

{{One- to two-sentence summary: meeting type, key decisions or themes, scope.}}

## Decisions

<!-- Each decision: what was decided, who decided, why. Cross-link to an ADR if the decision was elevated. -->

- {{Decision}} — {{rationale or context}}
  - Cross-ref: [[decisions/adr-{{NNN}}-{{slug}}]] *(if applicable)*

## Action Items

<!-- Format: assignee · due date · context. Each item becomes a task in the project's tasks.md. -->

- [ ] **{{Owner}}** — {{Action}} (due {{YYYY-MM-DD}})
- [ ] **{{Owner}}** — {{Action}} (due {{YYYY-MM-DD}})

## Key Discussion

<!-- Topics debated but not yet decided. Capture the contour of the conversation. -->

### {{Topic 1}}

{{What was discussed; positions taken; trade-offs surfaced; alternatives considered.}}

### {{Topic 2}}

{{...}}

## Open Questions

<!-- Things that surfaced during the meeting that need follow-up before they can be decided. -->

- {{Question}}
- {{Question}}

## Information Shared

<!-- Facts, data points, references mentioned during the meeting. These feed fact-tracking and may surface in cross-project synthesis. -->

- {{Fact or data point}}
- {{Reference: [[domain or tool page]]}}

## Cross-References

- Project overview: [[projects/{{project-slug}}/overview]]
- Active sprint: [[projects/{{project-slug}}/delivery/sprint-{{YYYY-MM-DD}}]]
- Related design: [[projects/{{project-slug}}/design/{{...}}]]
