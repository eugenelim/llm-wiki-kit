# CLAUDE.md — LLM Wiki Kit

> This is the root CLAUDE.md for the vault. It defines the conventions,
> operations, and rules that Claude follows when maintaining the knowledge base.
> Variant-specific extensions are loaded from `_variant/CLAUDE.variant.md`.

## Vault Identity

<!-- CUSTOMIZE: Replace this section with your team/family identity -->
You maintain a structured knowledge base using the LLM Wiki pattern.
Your job is to ingest raw sources, synthesize them into structured
wiki pages, and keep the knowledge base current, cross-linked, and
navigable.

## Skill Authoring Rules

**All new skills in this vault MUST follow the [Agent Skills spec](https://agentskills.io/specification).** No exceptions.

When you author or modify a skill, the structure is:

```
.claude/skills/<skill-name>/
├── SKILL.md           # Required: YAML frontmatter + Markdown instructions
├── scripts/           # Optional: executable code owned by this skill
├── references/        # Optional: detailed reference material loaded on demand
├── assets/            # Optional: templates, schemas, lookup tables
└── evals/
    └── evals.json     # 2-3 representative activation prompts
```

`SKILL.md` frontmatter (required):

```yaml
---
name: <skill-name>             # Must match the parent directory; lowercase, hyphens, max 64 chars
description: "<what + when>"   # Max 1024 chars; double-quoted; covers BOTH what the skill does AND when to use it
license: MIT
metadata:
  variant: shared|work|family|personal|<custom>
---
```

Activation guidance:

- The `description` field is what the agent sees during skill discovery. Make it specific. Include disambiguation against neighboring skills (e.g., "for tonight's dinner — for weekly plans use meal-planning instead").
- Reference scripts/files with paths relative to the skill root: `scripts/foo.py`, not `.claude/scripts/foo.py`.
- Keep `SKILL.md` under 500 lines. Move detailed reference material to `references/`.
- Always add `evals/evals.json` with at least 2 prompts demonstrating canonical and edge-case activations.
- Before authoring a new skill, search existing skills for activation overlap. If two skills could plausibly match the same prompt, sharpen one description so the boundary is unambiguous.

## Required Skills

This vault uses [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills)
for Obsidian-native file operations. Before working with any file type,
load the relevant skill:

- **obsidian-markdown** — for all .md file creation and editing
  (wikilinks, embeds, callouts, properties, frontmatter)
- **obsidian-bases** — for .base files (database views, filters,
  formulas, summaries over wiki pages)
- **json-canvas** — for .canvas files (spatial maps, flowcharts,
  project boards)
- **obsidian-cli** — for vault operations via the Obsidian CLI
  (search, property management, backlinks, tasks)
- **defuddle** — for web clipping (strips pages to clean markdown,
  saves tokens)

Install: copy the `.claude` folder from obsidian-skills into the
vault root, or use the plugin marketplace:
```
/plugin marketplace add kepano/obsidian-skills
/plugin install obsidian@obsidian-skills
```

## Conventions

### File Naming
- File names use **kebab-case**: `meeting-notes-2026-04-25.md`
- Dates are **ISO 8601**: `2026-04-25`
- Tags use **kebab-case**: `#project-management`, `#event-driven`
- Internal links use **Obsidian wikilink syntax**: `[[note-name]]`
- Asset links use embed syntax: `![[filename.ext]]` or `[[filename.ext]]`

### Frontmatter
Every wiki page **must** have YAML frontmatter. Minimum required fields:

```yaml
---
type: <page-type>        # See variant for valid types
status: <status>         # See variant for valid statuses
provenance: <provenance> # extracted | synthesized | mixed (see Provenance)
created: YYYY-MM-DD
modified: YYYY-MM-DD
tags: [tag1, tag2]
---
```

Additional fields are defined per variant and per page type.
Never remove YAML frontmatter from existing notes.

### Linking
- Use `[[wikilinks]]` for all internal vault references
  (Obsidian tracks renames automatically)
- Use `[text](url)` for external URLs only
- Use `[[Note Name#Heading]]` to link to specific sections
- Use `[[Note Name#^block-id]]` to link to specific blocks
- Always link assets from notes; never reference them only by path in prose

### Callouts
Use Obsidian callouts for important information:
```markdown
> [!warning] Outdated Information
> This page has not been updated in 90+ days. Verify before relying on it.

> [!tip] Key Decision
> See [[ADR-003]] for the rationale behind this choice.
```

### Synopsis (Progressive Loading)

Every wiki page **must** include a `## Synopsis` section immediately after
the frontmatter. This is a 2-3 sentence summary of the page's content.

```markdown
---
(frontmatter)
---

## Synopsis

This page describes the event-driven architecture for the order
processing pipeline, including the Kafka topic design, consumer
group strategy, and dead-letter queue handling.

## (rest of content...)
```

**Progressive loading rule:** Query in three stages:
1. **Index scan** — Read `index.md` to identify candidate pages.
2. **Synopsis scan** — Read frontmatter + `## Synopsis` of candidates. Discard irrelevant.
3. **Full read** — Read complete content of confirmed-relevant pages only.

Never read full page content until relevance is confirmed via synopsis. Exception: user names a specific page.

### Provenance Tracking

Every wiki page must declare how its content was produced:

| Value | Meaning |
|---|---|
| `extracted` | Content is directly transcribed or closely paraphrased from a source in `raw/`. Minimal LLM interpretation. |
| `synthesized` | Content is LLM-generated: analysis, synthesis, recommendations, or connections drawn across sources. |
| `mixed` | Page contains both extracted and synthesized content (most common for wiki pages). |

**Rules for synthesized content:**

1. Every synthesized claim must include a footnote or inline link to
   its source(s) in `raw/`:
   ```markdown
   The system requires exactly-once delivery semantics[^1].

   [^1]: [[raw/order-platform/requirements/nfr-v2.pdf]], section 4.2
   ```

2. If a synthesized claim draws from multiple sources, cite all of them.

3. If a claim is the LLM's own inference (not directly stated in any
   source), mark it with a callout:
   ```markdown
   > [!note] Inferred
   > Based on the latency requirements in [[nfr-v2]] and the throughput
   > targets in [[capacity-plan]], a streaming architecture is likely
   > more appropriate than batch ETL. This inference has not been
   > validated by the team.
   ```

4. When the `wiki-lint` skill runs, it checks that:
   - Every page has a `provenance` field
   - Pages with `provenance: synthesized` or `mixed` have source footnotes
   - Source footnotes point to files that actually exist in `raw/`

## Vault Structure (Shared Across Variants)

```
vault-root/
├── CLAUDE.md                    # This file (root agent instructions)
├── purpose.md                   # Vault scope statement (read before every ingest)
├── _variant/
│   └── CLAUDE.variant.md        # Variant-specific extensions
├── _templates/                  # Page templates with `{{placeholder}}` fields
│   └── ...                      # Defined per variant
│
├── raw/                         # Immutable source documents
│   └── ...                      # Organized per variant
│
├── wiki/                        # LLM-generated + human-curated pages
│   ├── index.md                 # Master navigation (auto-maintained)
│   └── ...                      # Organized per variant ontology
│
├── outputs/                     # Claude-generated deliverables
│   └── ...                      # .docx, .pptx, .pdf with companion pages
│
├── research/                    # Deep research outputs
│   └── {date}-{topic-slug}.md
│
├── log/
│   └── changelog.md             # Change log maintained by the LLM
│
└── .claude/                     # Claude Code skills + obsidian-skills
    └── skills/                  # Each skill is a directory:
                                 #   <skill-name>/SKILL.md (+ scripts/, references/, evals/)
```

## Operations

### Ingest (Processing New Sources)

1. **Read `purpose.md`** at the start of any ingest session, or before the first ingest in a conversation. Cache for the session — do not re-read per item in batch operations. If the source falls outside scope, skip it and log the skip in `log/changelog.md`.
2. Accept raw source → copy to `raw/` in the appropriate subfolder
3. Identify the source type and determine which wiki pages it affects
4. Extract key information: entities, decisions, claims, dates, relationships
5. **Check for contradictions.** Before updating any wiki page, compare
   new claims against existing page content. If a contradiction is found:
   - Do NOT silently overwrite the existing content
   - Add a callout on the affected wiki page showing both claims:
     ```markdown
     > [!danger] Contradiction
     > **Existing claim:** Kafka requires ZooKeeper for broker coordination.
     > Source: [[raw/project-x/architecture-v1.pdf]]
     >
     > **New claim:** KRaft mode eliminates ZooKeeper dependency (Kafka 3.3+).
     > Source: [[raw/project-x/architecture-v2.pdf]]
     >
     > Resolve by verifying which is current, then update this page.
     ```
   - Flag the contradiction in `log/changelog.md` for human review
   - If the new information clearly supersedes the old (e.g., newer date,
     higher authority source), update the page and note the supersession.
     Otherwise, leave both claims visible until a human resolves it.
6. Create or update wiki pages with `[[wikilinks]]` to related pages
7. If the source is a non-text file, create a companion page (see Asset Management)
8. Update `wiki/index.md` navigation if new pages were created
9. Append to `log/changelog.md`

### Query (Answering Questions)

Use **progressive loading** — never read full pages until relevance is confirmed.

1. Read `wiki/index.md` to identify candidate sections/pages (depth 0)
2. Read frontmatter + Synopsis of candidate pages (depth 1)
3. Discard irrelevant pages based on synopsis
4. Read full content of only the relevant pages (depth 2)
5. Follow wikilinks to gather additional context (repeat depth 1→2)
6. Synthesize answer with inline `[[PageName]]` references
7. Note the `provenance` field — flag synthesized claims if they're
   driving a critical decision
8. If the answer would be useful to future queries, save to wiki

### Lint (Health Checks)

Run on request or on a scheduled basis. The `wiki-lint` skill automates
these checks; supporting Python scripts live inside each owning skill's
`scripts/` directory (per the Agent Skills spec).

**Structural checks:**
1. Find **orphan pages** (no inbound links)
2. Find **stale pages** (no updates in 30+ days on active items)
3. Check for **missing frontmatter** fields (type, status, provenance,
   created, modified, tags)
4. Find **broken wikilinks** (links to non-existent pages)
5. Check that all non-text files in `_assets/` have companion pages
6. Verify every page has a `## Synopsis` section

**Provenance checks:**
7. Verify every page has a `provenance` field
8. Check that `synthesized` and `mixed` pages have source footnotes
9. Verify source footnotes point to files that exist in `raw/`
10. Flag `> [!note] Inferred` callouts that haven't been validated

**Knowledge quality checks:**
11. Detect **contradictions** — pages that make conflicting claims about
    the same entity or decision. Report as:
    ```markdown
    > [!danger] Contradiction Detected
    > [[page-a]] states X, but [[page-b]] states Y.
    > Resolve by updating one or both pages, or create an ADR
    > documenting the decision.
    ```
12. Detect **convergence debt** — raw sources in `raw/` that have no
    corresponding wiki page referencing them (ingested but not synthesized)
13. Flag **outdated information** with `> [!warning]` callouts
    (medical >6mo, financial >1yr, technical >90 days)

**Tag hygiene checks (use `scripts/tag-lint.py`):**
14. Detect **tag synonyms** — tags that likely mean the same thing
    (e.g., `#event-driven` vs `#eda`, `#k8s` vs `#kubernetes`)
15. Find **underused tags** (used on only 1 page — consider removing)
16. Find **overused tags** (used on >50% of pages — too broad to be useful)
17. Report results as a `wiki/synonyms.md` page that maps canonical
    tags to their alternatives

**Output:** Lint results are saved to `log/lint-{date}.md` and
summarized in the changelog. Auto-fixable issues (adding missing
`> [!warning]` callouts, updating `modified` dates) can be applied
automatically. Structural changes (resolving contradictions, merging
synonyms) require human confirmation.

### Folder Index Maintenance

Each significant folder should maintain an `index.md` that:
- Provides an overview of the folder's purpose and scope
- Lists and briefly describes the main notes in the folder
- Shows relationships between notes (chronological, hierarchical, etc.)
- Tracks current state (for projects) or evolution (for ongoing areas)
- Links to key assets in `_assets/` if applicable
- Is updated whenever significant changes occur in the folder

```yaml
---
type: index
folder: folder-name
created: YYYY-MM-DD
modified: YYYY-MM-DD
tags: [relevant, tags]
status: active
---
```

## Asset Management (Non-Text Files)

Obsidian's graph view, search, and backlinks only work with markdown.
Non-text files (PDFs, images, spreadsheets, diagrams, scanned documents)
require special handling to remain discoverable in the knowledge graph.

### The Companion Page Pattern

**Every non-text file gets a markdown companion page.**

The companion page is the file's metadata record — it contains frontmatter,
a description, and wikilinks that make the asset visible to Obsidian's
graph, search, and backlink features.

### Where Non-Text Files Live

Non-text files go in an `_assets/` subfolder within their parent context:

```
wiki/projects/order-platform/
├── design/
│   ├── data-pipeline-architecture.md      # Wiki page
│   └── _assets/
│       ├── system-diagram.png             # The image file
│       └── system-diagram.png.md          # Companion page
├── proposals/
│   ├── approach-doc.md                    # Companion page
│   └── _assets/
│       └── approach-doc-v1.docx           # The deliverable
```

For Claude-generated deliverables (outputs from Claude Code/Cowork),
use the `outputs/` folder instead:

```
outputs/
├── order-platform/
│   ├── approach-doc-v1.docx
│   └── architecture-presentation-v1.pptx
```

With companion pages in the wiki:
```
wiki/projects/order-platform/proposals/
└── approach-doc.md    # frontmatter: deliverable: [[outputs/order-platform/approach-doc-v1.docx]]
```

### Companion Page Format

```yaml
---
type: asset
asset_type: image | pdf | spreadsheet | document | diagram | presentation | scan | video | audio
asset_path: "[[_assets/system-diagram.png]]"
title: "Order Platform System Architecture Diagram"
created: 2026-04-20
modified: 2026-04-20
tags: [architecture, diagram, order-platform]
source: meeting-2026-04-18      # Where this asset came from
---

## Description

High-level system architecture diagram showing the order ingestion
pipeline, event bus, and downstream consumers.

## Context

Created during the [[design/data-pipeline-architecture]] design session.
Reflects decisions in [[decisions/adr-003-kafka-over-rabbitmq]].

## Preview

![[_assets/system-diagram.png|600]]
```

**Key rules:**
- The companion page filename matches the asset: `system-diagram.png.md`
  (or use a clean name like `system-diagram.md` if preferred)
- The `asset_path` field in frontmatter points to the actual file
- Use `![[filename]]` to embed previewable assets (images, PDFs)
- For non-previewable assets (.docx, .xlsx), use `[[filename]]` as a link
- Always include at least a one-sentence description of what the asset contains
- Cross-link to the wiki pages that reference or produced this asset

### Asset Base Views

Use Obsidian Bases to create database views over companion pages.
Create a `.base` file to see all assets in a project, filter by type,
or find assets without companion pages:

```yaml
# wiki/projects/order-platform/_assets.base
filter:
  - property: type
    operator: is
    value: asset
  - folder: wiki/projects/order-platform
views:
  - name: All Assets
    type: table
    order:
      - property: title
      - property: asset_type
      - property: modified
      - property: tags
```

### Update Documents

For living documents that accumulate updates over time (e.g., project
status reports, running meeting notes), use an `_updates/` subfolder:

- Naming format: `YYYY-MM-DD-brief-description.md`
- Use kebab-case for the description portion
- Date prefix enables chronological sorting
- The parent page should link to updates: `See [[_updates/]]`

### Large Files

Files larger than 50 MB should stay external (cloud drive, S3, etc.).
Create a stub companion page with an `external_path` field in frontmatter:

```yaml
---
type: asset
asset_type: video
external_path: "https://drive.google.com/file/d/xxxxx"
title: "Q1 Architecture Review Recording"
created: 2026-04-01
tags: [recording, architecture-review]
---

Recording of the Q1 architecture review. 2h 15m.
Stored externally due to file size (1.2 GB).
```

## File Lifecycle

- New files enter through `raw/` (sources) or directly into `wiki/` (authored content)
- `Clippings/` is a **transient inbox** for the Obsidian Web Clipper extension's default
  output — process clippings via the [[ingest]] orchestrator, which routes them through
  content-type schema and **relocates** to `raw/web-clips/<YYYY-MM-DD>-<slug>.md` on
  success. Failed routings stay in `Clippings/` for retry. See
  [`docs/guides/web-clipper.md`](../docs/guides/web-clipper.md) for the recommended
  Web Clipper template that writes directly to `raw/web-clips/` (skipping the relocation step).
- Active work lives in `wiki/` under the appropriate ontology section
- Completed, superseded, or obsolete items move to `wiki/` with `status: archived`
  (or to a dedicated `90-archive/{year}/` folder if the vault uses PARA archival)
- Raw sources are **immutable** — never modify anything in `raw/` (this includes `raw/web-clips/`
  after relocation)

## Safety Rules

- **Never delete files without asking** — move to archive instead
- **Never restructure top-level folders** without explicit instruction
- **Never modify `_templates/`** without explicit instruction
- **Never remove YAML frontmatter** from existing notes
- **Never overwrite** a deliverable version — create a new version file
- **Never rename wiki page files.** Filenames are canonical slugs. If a
  topic needs a new name, update the `title:` in frontmatter and add an
  `aliases:` field. Obsidian resolves aliases in search and wikilinks.
  If two pages cover the same topic, keep one as canonical and convert
  the other to a redirect (frontmatter only, with `redirects_to:` field).
- **Never silently overwrite contradicting content.** If new information
  contradicts existing wiki content, flag it with a `> [!danger]` callout
  rather than replacing. See the Ingest operation for the full protocol.
- **Always read `purpose.md`** before ingesting new sources
- **Always update `log/changelog.md`** when making significant changes
- **Always create companion pages** for non-text files

## Variant Extensions

The variant-specific CLAUDE.md is located at `_variant/CLAUDE.variant.md`.
Read it after this file for:
- Variant identity and tone
- Ontology-specific page types and statuses
- Variant-specific operations (spec management, medical records, etc.)
- Variant-specific tagging taxonomy
- Variant-specific skills and integrations
