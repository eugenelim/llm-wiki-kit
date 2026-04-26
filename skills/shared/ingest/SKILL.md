---
name: ingest
description: "Unified entry point for ingesting any source (paste, URL, file, photo) into the wiki. Routes on two axes — source-type (clean the input via ingest-website / ingest-document / inline) and content-type (apply schema via ingest-recipe, ingest-meeting, ingest-application, ingest-receipt, ingest-medical-record, ingest-person, etc., decide where it lands) — then runs validation, contradiction check, and wiki update. Use whenever a user drops or pastes any source for ingestion."
license: MIT
metadata:
  variant: shared
---

# Ingest Skill

Unified entry point for ingesting any source into the wiki. The orchestrator routes on **two axes** — *source-type* (clean the input) and *content-type* (apply schema, decide where it lands) — then runs the shared validation, contradiction check, and wiki update flow.

## Architecture

```
Source arrives (paste, URL, file, photo)
        │
        ▼
┌──────────────────────────┐
│  Source-type ingester     │   "Clean it up."
│                           │
│  ingest-website   (URL)   │   URL  → defuddle / pure.md
│  ingest-document  (file)  │   PDF  → Docling
│  inline           (text)  │   text → direct
└────────────┬─────────────┘
             ▼
       clean markdown
             │
             ▼
┌──────────────────────────┐
│  Content-type ingester    │   "Apply schema, route."
│                           │
│  ingest-recipe            │   recipe  → wiki/food/{slug}.md
│  ingest-meeting           │   meeting → projects/{slug}/meetings/
│  ingest-medical-record    │   medical → wiki/health/{name}-medical.md
│  ingest-receipt           │   receipt → wiki/finances/...
│  ingest-trip              │   trip    → wiki/travel/upcoming/
│  ingest-school-doc        │   school  → wiki/education/{child}/
│  inline (generic)         │   article → wiki/research/{date}-{slug}.md
└────────────┬─────────────┘
             ▼
     structured wiki page
             │
             ▼
┌──────────────────────────┐
│  Shared Flow              │
│  scope check (purpose.md) │
│  contradiction detection  │
│  wiki update              │
│  task / fact extraction   │
│  index + changelog        │
└──────────────────────────┘
```

Source-type ingesters are *shared* across variants — every vault uses them. Content-type ingesters are *variant-specific* — they apply the variant's schema and routing rules. Most ingests compose both: a recipe URL routes through `ingest-website` (cleanup) → `ingest-recipe` (schema → `wiki/food/{slug}.md`). A meeting PDF routes through `ingest-document` → `ingest-meeting` (decisions, action items → `wiki/projects/{slug}/meetings/{date}.md`). The orchestrator picks both axes and dispatches accordingly.

## Routing

### Source-type detection (cleanup)

Identifies the *form* of the input.

| Signal | Source-type ingester |
|---|---|
| URL to a web page | [[ingest-website]] (defuddle / pure.md) |
| File: `.pdf`, `.docx`, `.pptx`, `.xlsx`, image | [[ingest-document]] (Docling) |
| File already in `raw/` (any markdown / binary) | none — already cleaned; route directly to content-type detection |
| File in `Clippings/` (Obsidian Web Clipper inbox) | none — already cleaned by the clipper; route to content-type detection, then relocate to `raw/web-clips/` (see "Web Clipper Inbox" below) |
| Pasted text starting with `http(s)://` | [[ingest-website]] |
| Pasted text (no URL, no speakers) | none — handle directly |
| File: `.csv` | none — plain text, handle directly |

### Content-type detection (schema)

Identifies *what kind of thing* the input represents — determines schema and target wiki location.

| Signal | Content-type ingester | Variant |
|---|---|---|
| User says "ingest this recipe" or URL matches a recipe-host pattern (food blog, NYT Cooking, Bon Appétit, AllRecipes, etc.) | [[ingest-recipe]] | family |
| Speaker-labeled transcript / AI-summary file (Granola, Otter, Fireflies) | [[ingest-meeting]] | work |
| Receipt photo / PDF / statement entry | [[ingest-receipt]] | family |
| EOB / lab result / visit summary | [[ingest-medical-record]] | family |
| Booking confirmation / itinerary email | [[ingest-trip]] | family |
| Report card / school newsletter / permission slip | [[ingest-school-doc]] | family |
| Book / course / podcast / paper notes (Kindle highlights, paper PDF, course transcript) | [[ingest-book-note]] | personal |
| Job posting URL / application form / recruiter email | [[ingest-application]] | personal |
| URL to "save / bookmark this" (vs. "ingest / summarize this") | [[ingest-bookmark]] | all |
| Person / contact — LinkedIn URL, business-card photo, vCard, email signature, intro email, "add this person" | [[ingest-person]] | all (routes to `wiki/people/` for work/family, `wiki/network/relationships/` for personal) |
| Interaction with an existing person — "log a coffee with @sarah", "after my 1:1 with @mark" | [[person-update]] | all |
| Tax form (W-2, 1099-*, 1098, K-1, 5498, 1095-*) — PDF or scan | [[ingest-tax-document]] | family / personal |
| Article / blog post / documentation page | (handled inline as a generic article) | all |
| Document with no obvious type | (handled inline; offer content type via interactive confirmation) | all |

When the user states the content type explicitly ("ingest this recipe"), the orchestrator routes directly to the content-type ingester, which composes the source-type ingester it needs. When the content type is ambiguous, the orchestrator runs the source-type ingester first, then offers a content type via interactive confirmation.

### Research-source routing

When the [[research]] orchestrator is invoked **or** when an active research project exists in `wiki/research/`, content-type detection routes through the **research-source** path: the source-type ingester cleans the input, then the research-source schema (`source_kind`, `pillar_contributions`, `verification_strength`, `published_at`, `events_described`) is applied and the output lands at `wiki/research/{active-project}/sources/{slug}.md` rather than the default location. The [[research]] orchestrator picks the API-backed provider (Perplexity, Semantic Scholar, Gemini Deep Research) based on question semantics and what's enabled in `.claude/research-providers.yaml`. If no active project exists, the orchestrator asks: *"Save as a one-off research brief, or start a new research project (run [[research-start]])?"* — don't silently default; the choice matters for downstream operations. See [`docs/design/research-layer.md`](../../docs/design/research-layer.md) for the architecture.

## Extraction Paths

### Specialized (delegated)

The orchestrator detects both axes, then hands off. Each ingester produces clean markdown (source-type) or a structured wiki page (content-type), then returns control to the orchestrator for the Shared Flow.

**Source-type ingesters** (shared across variants):

- **Web pages, articles, blog posts** → [[ingest-website]] (defuddle locally; pure.md fallback for JS-heavy / bot-blocked sites, behind a privacy gate)
- **PDF, DOCX, PPTX, XLSX, images** → [[ingest-document]] (Docling via `scripts/ingest_document.py`; `--fast` `pymupdf4llm` path for plain-text PDFs)

**Content-type ingesters** (variant-specific):

- **Recipes** → [[ingest-recipe]] *(family)* — composes `ingest-website` (URLs) or `ingest-document` (photos / scanned cards) for cleanup, then applies the recipe template's schema and cross-references dietary notes for per-person allergen flags
- **Meeting transcripts** → [[ingest-meeting]] *(work)* — handles paste directly, or composes `ingest-website` (Granola / Otter / Fireflies URLs) or `ingest-document` (PDF exports); extracts decisions, action items, key discussion, open questions; pushes action items to the project's `tasks.md`
- **Book / course / paper notes** → [[ingest-book-note]] *(personal)* — composes `ingest-document` (PDFs) or paste handling; creates structured book page + 2-5 atomic notes capturing standout ideas
- **Job applications** → [[ingest-application]] *(personal)* — composes `ingest-website` (postings) or `ingest-document` (PDFs); creates application page with stage tracking + tailored-material slots; surfaces network leverage at the company
- **Bookmarks** → [[ingest-bookmark]] *(all variants)* — lightweight URL save (no full content extraction); produces a small `bookmark` page with structured metadata that the [[bookmark-homepage]] operation renders as a multi-column dashboard via Obsidian Bases
- **Tax documents** → [[ingest-tax-document]] *(family / personal)* — composes `ingest-document` (Docling); extracts form type / year / issuer / key figures; redacts SSN; cross-references holdings for 1099-B / 1099-DIV; routes to `wiki/finances/tax/{year}/`
- **Medical records, EOBs, lab results** → [[ingest-medical-record]] *(family)* — composes `ingest-document`; appends dated entry to per-person medical summary; updates medications / providers; surfaces follow-ups for the [[follow-up-tracker]]
- **Receipts, statement entries** → [[ingest-receipt]] *(family)* — composes `ingest-document` (photos/PDFs) or paste; categorizes by domain (vehicle / home / medical / food / travel); routes output to the right page; surfaces warranty + tax-relevant items
- **Trip itineraries** → [[ingest-trip]] *(family)* — composes `ingest-website` (booking URLs) or `ingest-document` (PDFs); creates or appends to a trip page in `wiki/travel/upcoming/`; surfaces passport / readiness checks
- **School documents** → [[ingest-school-doc]] *(family)* — composes `ingest-document` or `ingest-website`; routes to per-child education folder; surfaces dates for family calendar and action-item callouts

After the specialized ingester returns, the orchestrator runs the type-appropriate **interactive review** with the user before final commit. Pattern: specialized ingester = mechanical extraction; orchestrator = judgment, scope, contradiction handling, final wiki write.

### Inline (handled by the orchestrator)

#### Pasted Text

Sources: user pastes content directly into chat.

**Detection heuristics:**
- Starts with `http` → route to [[ingest-website]]
- Has speaker labels (`Sarah:`, `@eugene:`, timestamps) → route to [[ingest-meeting]]
- Has YAML frontmatter → save as markdown and run extraction directly
- Otherwise → general text; ask the user for context

**Steps:**
1. Ask for context if ambiguous: "Is this from a meeting, an article, or something else?"
2. Save to `raw/<YYYY-MM-DD>-<slug>.md`.
3. Route to the matching specialized skill, or run the Shared Flow directly if no specialized skill applies.

#### CSV

CSV is plain text and small enough to handle inline:

1. Read the file structure (column headers, row count, data types).
2. Summarize the dataset: what does it contain, time range, key metrics.
3. Create a companion page with the summary.
4. If the data relates to an existing wiki topic, update that page with relevant data points.

#### Web Clipper Inbox (`Clippings/`)

The Obsidian Web Clipper extension defaults to saving to `Clippings/{title}.md` in the vault root. The kit treats this folder as a **transient inbox** — clippings are processed and relocated to the canonical `raw/web-clips/` store. Users can also configure the clipper to write directly to `raw/web-clips/`; see [`docs/guides/web-clipper.md`](../../../docs/guides/web-clipper.md) for the recommended template.

**Detection:** files matching `Clippings/*.md` with frontmatter `source_url:` (or, lacking that, an inferred source URL from the body's typical Web Clipper structure).

**Steps (per clipping):**

1. **Read.** Parse the clipping's frontmatter and body. The clipper has already cleaned the page — skip source-type cleanup.
2. **Backfill missing frontmatter** if needed (`fetched_via: obsidian-web-clipper`, `fetched_at:` from file mtime, `provenance: extracted`). If the recommended Web Clipper template was used, these are already present.
3. **Route to content-type detection.** Same content-type table as any other source (recipe / meeting / application / book-note / tax-document / generic article / etc.). The orchestrator surfaces the proposed routing for confirmation if ambiguous.
4. **Run the Shared Flow** (scope check → contradiction check → wiki update → task / fact extraction → index → changelog).
5. **Relocate on success.** Move `Clippings/{title}.md` to `raw/web-clips/<YYYY-MM-DD>-<slug>.md` where `YYYY-MM-DD` comes from the clipping's `fetched_at:` (or file mtime as fallback) and `slug` is a kebab-cased version of the title. The wiki page's source footnote uses the **post-relocation path**.
6. **Leave on failure.** If the user rejects the routing, the source falls out of scope (`purpose.md` skip), or routing is ambiguous and the user defers, the file stays in `Clippings/` for retry. Surface the reason inline and append a `log/changelog.md` entry noting the deferral.

**Batch processing:** "Process my clippings inbox" iterates every file in `Clippings/`, surfaces a routing plan per file, and processes after confirmation. Files that succeed relocate; files that fail stay put with a noted reason.

**Never delete `Clippings/` itself or any unprocessed file.** Per the safety rule — relocation is the only modification; deletion requires explicit user confirmation. If a user explicitly asks to discard a clipping ("delete that bookmark, don't ingest it"), the file moves to `Clippings/_archive/` (created on first use) rather than being hard-deleted, unless the user confirms a delete.

**De-duplication:** if `ingest-website` is invoked on a URL that already has a clipping in `Clippings/` matching `source_url:`, use the existing clipping rather than re-fetching. The relocation flow runs as normal.

## Shared Flow (All Source Types)

After extraction, every source type runs through the same steps:

1. **Scope check:** Read `purpose.md`. Skip out-of-scope content.
   Log the skip.
2. **Contradiction check:** Compare extracted claims against existing
   wiki content. Flag contradictions with `> [!danger]` callouts.
   Do not silently overwrite.
3. **Wiki update:** Create or update wiki pages with wikilinks,
   proper frontmatter, and synopsis sections.
4. **Task extraction:** If action items were found (meetings, decisions),
   add them to the project's `tasks.md`.
5. **Entity fact log:** If any fact-tracked entities were mentioned,
   append new facts to their fact logs.
6. **Index update:** Update `wiki/index.md` if new pages were created.
7. **Changelog:** Append an entry to `log/changelog.md`.

## Usage Examples

**Paste a transcript:**
```
User: [pastes 2000 words of meeting transcript]
Agent: I see this is a meeting transcript with 4 participants. Let me
extract the key points...
[runs transcript extraction → shared flow]
```

**Ingest a URL:**
```
User: Ingest this article: https://example.com/event-sourcing-patterns
Agent: [fetches with defuddle → runs article extraction with review →
       shared flow]
```

**Drop a file:**
```
User: I put the new requirements doc in raw/order-platform/requirements-v3.pdf
Agent: [reads PDF → runs document extraction → shared flow]
```

**Quick web clip (via defuddle):**
```
User: Clip this page and add it to our Kafka research:
      https://kafka.apache.org/documentation/#design
Agent: [defuddle → extract key concepts → add to wiki/tools/kafka and
       wiki/domains/event-driven-architecture]
```

**Ingest a recipe (content-type stated):**
```
User: Save this recipe: https://example.com/sheet-pan-tacos
Agent: [routes to ingest-recipe → ingest-website (defuddle cleanup) →
       schema extraction (ingredients, steps, prep time) →
       cross-reference dietary-notes for allergens →
       writes wiki/food/weeknight/sheet-pan-tacos.md]
```

**Ingest a meeting transcript:**
```
User: [pastes Granola summary of sprint review]
Agent: [routes to ingest-meeting → schema extraction (decisions,
       action items, key discussion, open questions) →
       writes projects/order-platform/meetings/2026-04-25-sprint-review.md
       and pushes action items to projects/order-platform/tasks.md]
```
