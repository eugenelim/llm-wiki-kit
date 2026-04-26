---
name: ingest-book-note
description: "Capture book, course, podcast, or paper notes into a structured wiki/books/{slug}.md page plus 2-5 atomic notes for standout ideas. Use when the user says \"ingest this book / course / podcast / paper\", or the source is a Kindle highlights export, scanned book annotations, course transcript, podcast transcript, or paper PDF."
license: MIT
metadata:
  variant: personal
---

# Ingest Book Note Skill (Personal Variant)

Specialized content-type ingester for books, courses, podcasts, and papers. Composes a source-type ingester for cleanup, then applies book-note schema. Output: a structured `wiki/books/{slug}.md` page using the book template, plus 2-5 atomic notes capturing the standout ideas.

## When to Use

The orchestrator (`skills/shared/ingest.md`) routes here when:

- The user says "ingest this book / course / podcast / paper"
- The source is a Kindle highlights export, scanned book annotations, course transcript, podcast transcript, or paper PDF
- A pasted text identifies as book / course / paper notes (chapter / section structure)

## Composition (two-axis routing)

This is a content-type ingester. Common compositions:

| Source | Source-type cleanup | Result |
|---|---|---|
| Kindle highlights export | none — handle directly | raw text with chapter / location markers |
| Paper PDF / book PDF | [[ingest-document]] (Docling) | clean markdown |
| Course / podcast transcript | none if pasted; [[ingest-website]] if URL to transcript | raw text |
| Scanned book annotations | [[ingest-document]] (Docling with OCR) | OCR'd text |
| URL to course / podcast page | [[ingest-website]] (defuddle) | clean markdown of the page |

After cleanup, this skill applies the book-note schema regardless of source.

## Inputs

After source-type cleanup:

1. **The cleaned-up content** — highlights / transcript / annotations
2. **Existing `wiki/books/` library** — to detect duplicates by title + author
3. **Existing `wiki/topics/` and `wiki/notes/`** — for cross-referencing what this book extends or contradicts
4. The book template at `_templates/book.md` (currently a planned template; if absent, use the standard book schema described below)

## Algorithm

1. **Extract metadata.** Title, author(s), year, publisher / venue, ISBN if present.
2. **Identify content type.** Book, course, podcast, paper, conference talk. Each has slightly different schema (papers have abstracts; podcasts have hosts; courses have modules).
3. **Extract highlights / quotes.** Each highlight gets a chapter / section / location reference.
4. **Identify standout ideas.** From the highlight set, identify 2-5 ideas worth their own atomic notes (not every highlight; the ones the user marked or that advance the user's existing themes).
5. **Cross-reference.** Search `wiki/topics/` and `wiki/notes/` for related material. Identify what this book extends, contradicts, or deepens.

## Output

Two kinds of artifacts:

### 1. Book page

Write `wiki/books/{slug}.md`:

```yaml
---
title: "{Book Title}"
type: book
content_kind: book   # book | paper | podcast | course | talk
status: read         # someday | in-progress | read | abandoned
provenance: extracted
created: {today}
modified: {today}
tags: [book, {topic-tags}]
author: "{Author(s)}"
year: {YYYY}
venue: "{publisher / journal / podcast / course platform}"
finished: {today}
---
```

Body sections:
- `## Synopsis` — 2-3 sentences on what the book is about
- `## Why It Mattered to Me` — the angle that made this worth ingesting
- `## Standout Quotes` — direct quotes with chapter / section / location citation
- `## Key Claims` — the book's central arguments
- `## Connections` — wikilinks to related topics, notes, projects
- `## Atomic Notes Generated` — list of new notes produced from this ingest

### 2. 2-5 atomic notes

For each standout idea, write `wiki/notes/{idea-slug}.md` using `_templates/note.md`:
- `provenance: extracted` (with the book in `sources:`)
- `tags:` matching the book's domain
- `## The Idea` — single-claim atomic note
- `## Connections` linking to related notes
- `## Source` — wikilink back to the book page

## Side-effects

1. **Update `wiki/books/index.md`** with the new book.
2. **Update existing topic pages** if the book provides corroboration or contradiction. Don't auto-rewrite topics; flag for [[knowledge-consolidation]] to handle.
3. **Surface theme detection** — if the new book's tags overlap with 4+ existing notes, propose [[knowledge-consolidation]] for that theme.
4. **Update reading-status frontmatter** if the book was previously listed in `someday` or `in-progress`.
5. **Append to `log/changelog.md`**: "Book ingested: [[books/{slug}]] + {N} atomic notes."

## Interactive Review

```
Book ingested: "Designing Data-Intensive Applications" by Martin Kleppmann (2017)
Highlights: 47 captured

Standout ideas selected (4):
  1. "Eventual consistency isn't a bug; it's a model trade-off"
     → atomic note: notes/eventual-consistency-as-model-tradeoff
  2. "The duality of streams and tables"
     → atomic note: notes/streams-tables-duality
  3. "CRDTs as conflict resolution at the data layer"
     → atomic note: notes/crdts-as-data-layer-resolution
  4. "Saga pattern as distributed state machine"
     → atomic note: notes/saga-as-distributed-state-machine

Cross-references found:
  - Extends: [[topics/distributed-systems]] (consistency section)
  - Corroborates: [[notes/event-loops-vs-actor-models]] (different angle)
  - Theme detection: 6 existing notes on event-driven thinking + this book + 4 new notes
    → Strong signal for [[knowledge-consolidation]] on event-driven-architecture

Save book + 4 atomic notes? Trigger consolidation?
```

## Failure Modes

- **Duplicate book detected.** Surface; ask whether to overwrite (rare — usually just update reading-status), version, or merge new highlights into the existing page.
- **Highlights set is overwhelming (>200).** Don't try to atomize all of them; surface the top tier (highly-marked, central to user's themes) and ask the user which to atomize.
- **Source has no clear chapter / section markers.** Cite by page number or quote-context; flag the limited specificity.
- **Book is highly tangential to user's themes.** Surface: "This book has only weak overlap with your active themes — ingest anyway, or skip and revisit if relevance grows?"

## Cadence

- **On demand:** Run when finishing a book / course / paper.
- **No scheduling:** Reading is bursty; capture happens on completion.
- **Pairs with [[reading-queue]] and [[knowledge-consolidation]].**
