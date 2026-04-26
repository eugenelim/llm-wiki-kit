---
name: knowledge-consolidation
description: "Find atomic notes accumulating around a theme; when 5+ notes share a theme, propose a synthesis to a topic page in wiki/topics/. Atomic notes remain as inputs; the topic is a new layer above. Use after weekly-review surfaces a theme appearing across 3+ notes, when wiki/notes/ has grown past ~50 notes without corresponding topic pages, on request \"consolidate notes on {topic}\", or quarterly."
license: MIT
metadata:
  variant: personal
---

# Knowledge Consolidation Skill (Personal Variant)

Find atomic notes accumulating around a theme. When 5+ notes share a theme, propose a synthesis to a topic page in `wiki/topics/`. Atomic notes remain as inputs; the topic is a new layer above. The Zettelkasten dual-layer in operation.

## When to Use

- After [[weekly-review]] surfaces a theme appearing across 3+ notes
- When `wiki/notes/` has grown past ~50 notes without a corresponding topic page
- On request: "Consolidate notes on {topic}"
- Periodically — quarterly is a reasonable cadence to sweep for under-synthesized themes

## Inputs

User provides:
- Optional: explicit theme / topic to consolidate around
- Optional: minimum note threshold (default: 5)

Reads:
- All `wiki/notes/*.md` — for theme detection across atomic notes
- All `wiki/topics/*.md` — to detect existing topic pages and avoid duplicate creation
- Tagged content in `wiki/books/` — books on the same theme become candidate references
- `wiki/projects/` — projects related to the theme are cross-references
- `wiki/decisions/` — decisions related to the theme add weight to consolidation worthwhileness

## Algorithm

1. **Detect theme clusters.** Scan atomic notes' frontmatter `tags:` and body content. Find tags or wikilink patterns appearing in 5+ notes.
2. **Filter candidates.** Already has a topic page? Skip (or propose update instead). Theme is too narrow (e.g., one project's specifics rather than cross-cutting)? Skip.
3. **Per candidate cluster:**
   - Identify the 5+ atomic notes
   - Identify supporting books, projects, decisions
   - Surface: which claims are ready for synthesis (corroborated across notes), which are open questions
4. **Propose topic page.** Working title, structure (sections), included notes, supporting evidence.
5. **Compose the synthesis.** Use atomic notes as building blocks; preserve their atomic form (don't bloat them); the topic page synthesizes WITHOUT swallowing the source notes.

## Output

Write `wiki/topics/{slug}.md`:

```yaml
---
title: "{Topic}"
type: topic
status: active
provenance: synthesized
created: {today}
modified: {today}
tags: [topic, {kebab-tags}]
notes_consolidated: 7    # count of atomic notes this synthesizes
last_synthesis: {today}
---
```

Body sections:
- `## Synopsis` — 2-3 sentences on what this topic is and why it's worth knowing
- `## Core Claims` — synthesized claims, each citing 2+ atomic notes
- `## Tensions / Open Questions` — claims that conflict between notes or that are unresolved
- `## Sources` — atomic notes consolidated, books / projects / decisions that inform the topic
- `## Connections` — wikilinks to related topic pages and domain pages

Each claim cites the atomic notes that established it via inline footnotes:
```markdown
Event loops are best understood as a cooperative scheduling primitive[^1].

[^1]: From [[notes/event-loops-vs-actor-models]] and [[notes/cooperative-vs-preemptive-scheduling]].
```

## Side-effects

1. **Update each consolidated note's frontmatter** — add `cited_in: [[topics/{slug}]]` so the source notes know they participate in a synthesis.
2. **Update `wiki/topics/index.md`** with the new topic listed.
3. **Update `wiki/domains/{domain}.md`** if the topic falls within an existing domain — domain page links to the new topic.
4. **Append to `log/changelog.md`**: "Knowledge consolidated: [[topics/{slug}]] from {N} atomic notes."

## Interactive Review

```
Consolidation candidate: "Event-Driven Architecture"

Atomic notes detected (7):
  [[notes/event-loops-vs-actor-models]]
  [[notes/cooperative-vs-preemptive-scheduling]]
  [[notes/cqrs-and-event-sourcing-as-peers]]
  [[notes/eventual-consistency-isnt-a-bug]]
  [[notes/saga-pattern-as-distributed-state-machine]]
  [[notes/dead-letter-queue-as-system-design-signal]]
  [[notes/event-store-vs-message-broker]]

Supporting evidence:
  Books: [[books/designing-data-intensive-applications]], [[books/enterprise-integration-patterns]]
  Projects: [[projects/order-platform-side-project]]
  Decisions: [[decisions/2026-03-12-kafka-over-rabbitmq]]

Proposed topic: wiki/topics/event-driven-architecture.md

Claims to synthesize (5):
  1. Event loops as cooperative scheduling — corroborated by 2 notes
  2. Eventual consistency as a feature not a bug — corroborated by 3 notes + book
  3. Sagas as distributed state machines — single-note claim; flag as single-source
  4. CQRS and event sourcing as peers, not parent-child — corroborated by 2 notes
  5. DLQ presence as a system-design quality signal — single-note claim; flag

Open question detected:
  - Notes disagree on whether event sourcing requires immutable events.
    Surface as `## Tensions` section with both positions.

Author topic page?
```

## Failure Modes

- **Theme is too narrow** — only spans one project. Decline; propose adding to the project's design page instead.
- **Theme is too broad** — like "engineering" or "AI." Decline; suggest a more specific sub-theme.
- **Notes contradict each other extensively.** Surface as tensions in the topic page. Don't pick a winner.
- **Existing topic page already covers the theme.** Propose update (incremental synthesis) rather than new topic.

## Cadence

- **On demand:** When weekly review surfaces a theme.
- **Periodic:** Quarterly sweep for under-synthesized themes.
- **No scheduled runs:** Consolidation is a deliberate creative act; scheduled runs would produce mechanical syntheses.
