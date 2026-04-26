---
name: research-sieve
description: "Phase-2 research operation. Read sources/*.md in an active research project; group each source's pillar_contributions into the four pillar pages (entities, attributes, mental-model, verdict). Sources that don't fit any pillar move to sources/_archive/. Use after 48-72 hours of capture, when research-verdict-check reports the source pool is rich enough to organize, or on request: \"sieve the sources for {project}\"."
license: MIT
metadata:
  variant: shared
---

# Research Sieve Skill

Phase-2 operation. Reads the project's `sources/*.md` and groups each source's `pillar_contributions:` into the four pillar pages (entities, attributes, mental-model, verdict). Sources that don't fit any pillar move to `sources/_archive/`.

## When to Use

- After 48-72 hours of capture (or when [[research-verdict-check]] reports the source pool is rich enough to organize)
- When the user explicitly invokes "sieve the sources for {project}"
- Mid-project when capture has accumulated enough material that browsing sources is harder than reading pillar pages

The discipline: *discard 90% of information that doesn't directly support or refute the central claim.* The sieve enforces that.

## Inputs

User provides:

- Project slug or path. If absent, defaults to the most-recently-modified research project (treated as active).

Reads:

- `wiki/research/{slug}/overview.md` — central claim, verdict shape, current phase
- `wiki/research/{slug}/sources/*.md` — all source pages (excluding `_archive/`)
- Existing pillar pages (entities.md, attributes.md, mental-model.md, verdict.md) — to layer onto, not overwrite

## Algorithm

1. **Validate phase.** If `phase != capture`, surface a warning: "This project is in {phase}, not capture — sieve typically runs after capture. Continue?"

2. **Read every source.** For each `sources/{slug}.md`:
   - Read frontmatter `pillar_contributions:` (list of pillar names)
   - Read body — extract content under the `## Pillar Contributions` subsections
   - Note `verification_strength`, `published_at`, `events_described` for chronology and weighting

3. **Cluster by pillar.** Group source contributions by pillar:
   - **Entities** — unique entity names mentioned across sources, with per-entity source citations
   - **Attributes** — measurable attributes with values per entity and source citations
   - **Mental Model** — rules / principles with the source(s) that asserted them
   - **Verdict** — candidate selections with the sources that recommend them

4. **Detect contradictions.** Within each pillar, look for sources that disagree about the same entity / attribute / rule. Surface with `> [!danger] Contradiction` callouts on the affected pillar page rather than silently picking.

5. **Identify orphan sources.** Sources whose `pillar_contributions:` is empty or whose body has no clear pillar assignments. Move these to `sources/_archive/{date}-{reason}/{filename}.md` after user confirmation.

6. **Compose pillar page updates.** For each pillar, write content layered onto existing material — *preserve any human-authored content; augment, don't overwrite.*

## Output

Updates these files:

- `wiki/research/{slug}/entities.md` — populated catalog with sub-headings per entity, each citing the sources that mention it
- `wiki/research/{slug}/attributes.md` — populated specs grouped by attribute, with values per entity and per-source citations
- `wiki/research/{slug}/mental-model.md` — rules / principles with sourced rationale
- `wiki/research/{slug}/verdict.md` — early candidates ranked, each with source-backed claim and verification status

Each pillar page's frontmatter:

```yaml
---
type: research-pillar
pillar: entities | attributes | mental-model | verdict
project: "[[research/{slug}/overview]]"
provenance: synthesized
modified: {today}
sources_count: {N}
contradictions: {0 | N}    # count of unresolved contradictions on this pillar
---
```

Updates `overview.md`:

- `phase: synthesize`
- Phase log appended: `{today}: research-sieve (sources sieved: {N}; archived: {M}; contradictions: {K})`

## Side-effects

1. **Move orphan sources** to `sources/_archive/{date}-archive/`.
2. **Append to `log/changelog.md`**: "Research project sieved: [[research/{slug}/overview]]."

## Interactive Review

Before writing, present a summary:

```
Sieve preview for {project}:

Sources reviewed: 12
Pillar contributions found:
  Entities: 6 unique (Cursor, Cline, Claude Code, Copilot, Aider, Continue)
  Attributes: 7 (speed, context window, accuracy, cost, IDE support, agentic, plugins)
  Mental Model: 3 rules (RAG vs long-context vs agentic)
  Verdict: 4 candidates ranked

Contradictions surfaced (2):
  - "Cursor's context window" — 3 sources say 200K, 1 source says 1M
  - "Claude Code's plugin ecosystem" — varies between sources

Orphan sources to archive (1):
  - sources/perplexity-2026-04-23-ai-history.md (no pillar contributions)

Apply sieve?
```

The user confirms or adjusts (e.g., keeps an orphan source for context, picks a contradiction resolution).

## Failure Modes

- **No sources captured yet.** Surface: "Project has 0 sources. Capture before sieving."
- **All sources orphan.** Indicates `pillar_contributions` weren't tagged during capture; ask the user to fix tagging before re-sieving.
- **Pillar pages have human-authored content.** Augment, don't overwrite. If structure conflicts, surface for review.
- **Verdict pillar empty.** Sieve doesn't fail — sources may not yet have produced verdict candidates. Flag in summary so the user knows more capture is needed for verdict-shape questions.

## Cadence

- **On demand:** Once after the bulk of capture is done; possibly again if substantial new sources arrive mid-Synthesize.
- **No scheduling:** Sieve is deliberate. Scheduled sieves would fight new captures and produce churn.
