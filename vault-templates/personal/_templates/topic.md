---
title: "{{Topic Name}}"
type: topic
status: active                # active | someday | done | outdated
provenance: synthesized       # synthesized if drawn from notes/sources; mixed if it also contains your own first-thought claims
created: {{YYYY-MM-DD}}
modified: {{YYYY-MM-DD}}
last_synthesis: {{YYYY-MM-DD}}  # bump whenever the topic is re-synthesized
tags: [topic, {{kebab-tags}}]
notes_consolidated: {{N}}     # count of atomic notes this synthesis pulls from
aliases: []                   # alternative names; Obsidian resolves these in search and wikilinks
---

## Synopsis

{{2-3 sentences: what this topic is, the angle this page takes on it, and why it's worth knowing. A reader should be able to decide from the synopsis alone whether the full page is relevant.}}

## Frame

{{The lens this topic is organized under. What question does it answer? What kind of problem is it a tool for thinking about? If the topic could be cut several ways, name the cut you've chosen so future-you doesn't fight the structure.}}

## Core Claims

<!--
The heart of the topic. Each claim:
  - Stands alone — readable without the surrounding prose.
  - Cites 2+ atomic notes, books, or sources via inline footnote.
  - Single-source claims are allowed but flagged with [single-source] so future synthesis can corroborate or retire them.
  - Claims should be defensible — something you could argue for or against.
Add or remove claim blocks as the topic grows; this is a living page.
-->

### Claim 1 — {{One-sentence claim}}

{{2-4 sentences elaborating the claim. State it in your own words, then explain the mechanism, evidence, or reasoning behind it. End with the implication: what does this claim let you do, predict, or decide?}}

Sources: [^c1a] [^c1b]

[^c1a]: [[notes/{{atomic-note-slug}}]]
[^c1b]: [[notes/{{atomic-note-slug}}]] *(or [[books/{{book}}]], [[raw/{{path}}]])*

### Claim 2 — {{One-sentence claim}}

{{Elaboration.}}

Sources: [^c2a] [^c2b]

[^c2a]: [[notes/{{atomic-note-slug}}]]
[^c2b]: [[notes/{{atomic-note-slug}}]]

### Claim 3 — {{One-sentence claim}} `[single-source]`

{{Elaboration. Mark as single-source until a second note corroborates it.}}

Sources: [^c3a]

[^c3a]: [[notes/{{atomic-note-slug}}]]

## Tensions & Open Questions

<!--
Where the input notes / sources disagree, or where the synthesis is honestly unresolved.
Don't pick a winner unless the evidence forces it. A tension surfaced is more valuable
than a tension hidden by false consensus.
-->

> [!question] {{Tension title}}
> **Position A:** {{claim}} — [[notes/{{slug}}]]
> **Position B:** {{conflicting claim}} — [[notes/{{slug}}]]
> **What would resolve it:** {{the evidence, experiment, or distinction that would settle this.}}

- {{Open question 1}} — {{why it matters; what would close it.}}
- {{Open question 2}}

## Inferred (Not Yet Validated)

<!--
Claims that are the synthesizer's own inference — not directly stated in any source note.
Keep these visible and labeled until corroborated. wiki-lint flags `> [!note] Inferred`
callouts for review.
-->

> [!note] Inferred
> {{An inference drawn across the source notes that no single note states. Spell out the leap.}}

## Sources

### Atomic Notes Consolidated

<!-- The input notes this topic synthesizes. Each note's frontmatter should have `cited_in: [[topics/{{this-slug}}]]` set. -->

- [[notes/{{atomic-note-slug}}]] — {{one-line gist}}
- [[notes/{{atomic-note-slug}}]] — {{one-line gist}}
- [[notes/{{atomic-note-slug}}]] — {{one-line gist}}

### Books / Papers / Talks

- [[books/{{slug}}]] — {{the chapter or argument that's load-bearing for this topic}}
- [[books/{{slug}}]] — {{...}}

### Projects, Decisions, Meetings

- [[projects/{{slug}}]] — {{how this topic shows up in the project}}
- [[decisions/{{YYYY-MM-DD}}-{{slug}}]] — {{decision shaped by or shaping this topic}}
- [[meetings/{{YYYY-MM-DD}}-{{slug}}]] — {{conversation that contributed}}

### External

<!-- URLs only when there's no internal source. Prefer ingesting first. -->

- [{{title}}]({{url}})

## Connections

- Related topics: [[topics/{{slug}}]], [[topics/{{slug}}]]
- Parent domain: [[domains/{{slug}}]]
- Builds on: [[topics/{{earlier-topic}}]]
- Contradicts: [[topics/{{other-topic}}]]
- Feeds into: [[topics/{{downstream-topic}}]]

## Practical Implications

{{What this topic lets you do, predict, or decide. If you can't name a concrete consequence, the topic may be too abstract — consider whether it should stay as scattered notes instead.}}

## Synthesis Log

<!--
Append-only log of synthesis passes. Each entry: date, what was added/changed, which new
notes were folded in. Lets you see the topic's evolution and decide when a deep
re-synthesis (vs. incremental update) is due.
-->

- {{YYYY-MM-DD}} — Initial synthesis from {{N}} atomic notes.
- {{YYYY-MM-DD}} — Added [[notes/{{slug}}]]; updated Claim 2; new tension surfaced.
