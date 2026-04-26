---
title: "ADR-{{NNN}}: {{Decision Title}}"
type: decision
project: {{project-slug}}
status: draft   # draft | accepted | superseded
provenance: synthesized
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
tags: [decision, adr]
supersedes: ""      # ADR this decision replaces, if any
superseded_by: ""   # ADR that replaces this decision, if any
---

## Synopsis

{{One sentence: what was decided and why it matters.}}

## Context

{{What is the issue or question? Include relevant constraints, prior assumptions, and the trigger that forced a decision.}}

## Decision

{{What was decided, stated unambiguously.}}

## Rationale

{{Why this option over alternatives. Reference data, trade-off analyses, prototype results, source documents in `raw/`.}}

## Consequences

**Positive:**
- {{}}

**Negative:**
- {{}}

**Implications:**
- {{Downstream changes this decision forces.}}

## Alternatives Considered

- **{{Alternative A}}** — {{Why rejected}}
- **{{Alternative B}}** — {{Why rejected}}

---

> ADRs are immutable once `status: accepted`. To reverse a decision, create a new ADR and link both ways via `supersedes` / `superseded_by`.
