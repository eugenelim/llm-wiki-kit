---
title: "{{YYYY-MM-DD}} — {{Decision Title}}"
type: decision
status: active            # active | revisited | reversed | archived
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [decision, {{domain}}]
expected_outcome: ""
revisit_by: ""            # date when to evaluate; decision-check operation reads this
---

## Synopsis

{{One sentence: what you decided.}}

## Context

{{What was the situation that forced or enabled the decision? Constraints, options on the table, time pressure.}}

## Options Considered

- **{{Option A}}** — {{trade-offs}}
- **{{Option B}}** — {{trade-offs}}
- **{{Option C}}** — {{trade-offs}}

## The Choice

{{The option you chose, stated unambiguously.}}

## Reasoning

{{Why this option over the others. Be honest — what was the load-bearing reason?}}

## Expected Outcome

{{What you expect to happen as a result. The decision-check operation will compare this to actual outcomes later.}}

## Revisit When

{{Trigger or date for revisiting. "After 6 months." "If X happens." "When I next see Sarah."}}

## Cross-References

- Related goals: [[goals/{{...}}]]
- Related projects: [[projects/{{...}}]]
- Informed by: [[books/{{...}}]], [[notes/{{...}}]]
- Conversations that shaped this: [[meetings/{{...}}]]
