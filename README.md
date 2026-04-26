# LLM Wiki Kit

> A configurable knowledge **operating system** built on the LLM Wiki pattern. Pick a variant, drop it in a synced folder, and start using your wiki with Claude Code.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills Spec](https://img.shields.io/badge/skills-agentskills.io-blue.svg)](https://agentskills.io/specification)
[![Obsidian Skills](https://img.shields.io/badge/foundation-kepano%2Fobsidian--skills-purple.svg)](https://github.com/kepano/obsidian-skills)

The kit captures raw sources into a structured Obsidian-vault wiki, then runs operations that produce derived artifacts — sprint plans, weekly reviews, meal plans, status decks, ADR queues, networking digests. Three first-class variants ship: **work**, **family**, **personal**. Capture and operate, both grounded in the same vault.

---

## Table of Contents

- [Why this exists](#why-this-exists)
- [Pick a variant](#pick-a-variant)
- [Quick Start](#quick-start)
- [How it works](#how-it-works)
- [Adding new content (cheatsheet)](#adding-new-content-cheatsheet)
- [Foundation: Obsidian Skills](#foundation-obsidian-skills)
- [Architecture in one minute](#architecture-in-one-minute)
- [Scaling notes](#scaling-notes)
- [Agent flexibility](#agent-flexibility)
- [Documentation](#documentation)
- [License](#license)

---

## Why this exists

A wiki without operations is a filing cabinet. The capture loop runs at first, then dies because nobody sees a visible weekly payoff.

This kit is designed around **two reinforcing loops**:

- **Capture loop** — ingest a source → typed wiki page lands in the right place.
- **Operate loop** — operation reads structured pages → produces a derived artifact (a sprint plan, a meal plan, a weekly review) that subsequent operations and humans both consume.

Every feature — progressive loading, synopses, structured ingestion, the operations layer — exists to make both loops fast and useful.

**Human curation is non-negotiable.** Research on LLM-maintained documentation shows that fully unsupervised LLM management degrades quality over time. The kit enforces curation through provenance tracking, contradiction detection, interactive review, and lint checks that surface quality issues for human resolution. The LLM proposes; you review.

---

## Pick a variant

Each variant is a complete vault skeleton with its own ontology, page types, templates, operations, and a fully-self-contained README. Pick one and read its README — that's all the documentation you need to set it up.

| Variant | For | Canonical operation | README |
|---|---|---|---|
| **Work** | Architecture & engineering teams. Spec-driven build sessions, ADRs, meeting syntheses, sprint planning, weekly digests, team-status decks, cross-project synthesis, PM-tool sync. | `sprint-planning` (Mon) | [`vault-templates/work/README.md`](vault-templates/work/README.md) |
| **Family** | A household. Person-first ontology with structured ingest of recipes, medical records, school documents, trips, receipts, tax forms. Operations: meal-planning, follow-up tracker, trip prep, weekly digest, medical summary, recipe recommender. | `meal-planning` (Sun) | [`vault-templates/family/README.md`](vault-templates/family/README.md) |
| **Personal** | One person's mind + career. Atomic notes + topic syntheses, books, decisions, weekly/quarterly/annual reviews, hobby + fitness logs, accomplishment ledger, applications, network rolodex. | `weekly-review` (Sun) | [`vault-templates/personal/README.md`](vault-templates/personal/README.md) |

Side-by-side comparison: [`docs/comparison.md`](docs/comparison.md).

Don't see your shape? Build a custom variant: [`docs/guides/customizing.md`](docs/guides/customizing.md).

---

## Quick Start

Three steps. Picks the work variant for the example — swap the path for `family` or `personal` as needed.

### 1. Clone the kit and copy a variant template

```bash
git clone https://github.com/eugenelim/llm-wiki-kit.git
cd llm-wiki-kit

# Copy your chosen variant to a synced folder (OneDrive / iCloud / Dropbox / Git)
cp -r vault-templates/work ~/OneDrive/my-team-wiki
```

### 2. Install agent skills

From inside the new vault folder:

```bash
cd ~/OneDrive/my-team-wiki

# Foundation: kepano/obsidian-skills (wikilinks, Bases, Canvas, defuddle)
git clone https://github.com/kepano/obsidian-skills.git /tmp/obsidian-skills
mkdir -p .claude
cp -r /tmp/obsidian-skills/.claude/* .claude/
rm -rf /tmp/obsidian-skills

# This kit's skills (shared + your variant)
cp -r /path/to/llm-wiki-kit/skills/shared/* .claude/skills/
cp -r /path/to/llm-wiki-kit/skills/work/* .claude/skills/   # or family / personal
```

### 3. Set up your `purpose.md` — pick one path

You have **two ways** to fill in your vault's scope. Both end with the same result.

#### Path A — Edit `purpose.md` directly (5 minutes, no agent)

Open `purpose.md` in your editor and replace the placeholder with your real scope (3-7 sentences, in-scope and out-of-scope bullets). Then optionally tweak the identity sections of `_variant/CLAUDE.variant.md` (team/family name, tone). The rest works as-is.

#### Path B — Let Claude walk you through setup (10 minutes, conversational)

Start Claude in the vault directory and paste the variant-specific reference prompt. Claude reads the schema, asks you one question at a time, and writes `purpose.md` plus relevant stub pages at the end.

```bash
cd ~/OneDrive/my-team-wiki
claude
```

The full reference prompt is in your variant's README:

- [Work setup prompt](vault-templates/work/README.md#path-b--let-claude-walk-you-through-setup-10-minutes-conversational)
- [Family setup prompt](vault-templates/family/README.md#path-b--let-claude-walk-you-through-setup-10-minutes-conversational)
- [Personal setup prompt](vault-templates/personal/README.md#path-b--let-claude-walk-you-through-setup-10-minutes-conversational)

### 4. Open in Obsidian and run your canonical operation

Open the vault in Obsidian. `wiki/index.md` is your dashboard.

Then run your variant's **canonical operation** — the gateway that establishes the rhythm that keeps the vault alive. Your README has the exact prompt:

| Variant | Canonical operation | Cadence |
|---|---|---|
| Work | `sprint-planning` | Sprint kickoff (Mon) |
| Family | `meal-planning` | Sun afternoon |
| Personal | `weekly-review` | Sun evening / Mon morning |

The canonical operation produces a derived artifact you'll consume the next week. **Without it, the capture loop dies; with it, the vault stays operational.** Resist the temptation to capture lots of content first — the canonical operation is what gives captures a purpose.

---

## How it works

The kit runs two flows over the same vault:

```
  CAPTURE                                              OPERATE

  raw sources   →   specialized   →   structured  ↔   operations    →   derived
  (URLs, PDFs,      ingesters         wiki pages       (planning,        pages
   pastes,          (orchestrator     (typed,           reminding,       (sprint plans,
   photos,          routes by         cross-linked      synthesizing,    meal plans,
   transcripts,     source-type +     markdown)         recommending,    digests,
   recipes, …)      content-type)                       crisis-          schedules,
                                                         responding)     packing lists)
```

**Capture.** Raw sources flow through specialized ingesters that produce *structured* wiki pages. A recipe URL becomes a recipe page in `food/`. A meeting transcript becomes a synthesis in `projects/{slug}/meetings/` with decisions and action items. A PDF becomes markdown via Docling and lands in the right wiki location. The orchestrator (`skills/shared/ingest/SKILL.md`) routes by *source-type* (URL, PDF, paste) and *content-type* (recipe, meeting, EOB, receipt).

**Operate.** Operations are skills that read structured wiki pages, compose, and write derived pages back. Five classes: planning, reminding, synthesizing, recommending, crisis-responding. The output of an operation is itself a wiki page that subsequent operations can read.

Humans guide the agent, review its output, and browse the wiki in Obsidian. Over time, the vault becomes institutional memory — for a team, a family, or you personally — searchable, navigable, always current, and *operational*.

---

## Adding new content (cheatsheet)

Each variant's README has the full content-authoring guide with copy-paste prompts. Quick lookup:

| You want to add… | Variant | Prompt pattern |
|---|---|---|
| **A design or architecture doc** | work | `Write a design doc for {topic} in {project-slug}. Approach: {sketch}.` |
| **An ADR** | work | `Capture an ADR for {project-slug}: we decided {choice} over {alternative}. Context: {why}.` |
| **A feature spec with implementation plan** | work | `Start a new spec in {project-slug} for {feature}. Goal: {outcome}.` |
| **A meeting synthesis** | work / family / personal | `Ingest this meeting: {paste or path}. Surface decisions and action items.` |
| **A task** | work | `Add to {project-slug} tasks: {task}. Owner: {name}. Due: {date}.` |
| **A research project** (multi-source) | any | `Start a research project: {question}. Artifact shape: matrix \| shortlist \| blueprint.` |
| **A discovery / research note** (single source) | any | `Save a research brief: {topic}. Source: {URL or paste}.` |
| **A status deck** (PowerPoint) | work | `Convert today's team-status page into a status deck.` |
| **A recipe** | family | `Save this recipe: {URL or paste}. Family adjustments: {tweaks}.` |
| **A medical record** | family | `Ingest this medical document for {name}: {file path}. Surface follow-ups.` |
| **A trip plan** | family | `Start trip planning: {destination}, {dates}, traveling with {who}.` |
| **An atomic note** | personal | `Save an atomic note: {one idea}. Link to: {related notes/topics}.` |
| **A book record + standout-idea notes** | personal | `Save a book: {title} by {author}. Standout ideas: {bullets}.` |
| **A decision** | personal / work | `Log a decision: {what}. Context: {why}. Options: {bullets}. Why this one: {reasoning}.` |
| **An accomplishment** | personal | `Log an accomplishment: {what}. Dimension: {career\|craft\|learning\|...}.` |
| **A hobby session** | personal | `Log a hobby session: {hobby}, {duration}. What worked: {bullets}. Next time: {breadcrumb}.` |
| **A fitness session** | personal | `Log a workout: {sets×reps×weight or distance/pace}. Auto-detect PRs.` |
| **A weekly review** | personal | `Run my weekly review for the week ending {YYYY-MM-DD}.` |
| **A meal plan** | family | `Plan meals for next week. Constraints: {who's around, dietary, what's in fridge}.` |
| **A sprint plan** | work | `Plan the next sprint for {project-slug}. Capacity: {N} days.` |
| **A weekly digest** | work / family | `Produce this week's digest.` |
| **An onboarding pack** | work | `Produce an onboarding pack for {name}, joining {project-slug}.` |
| **A target-tailored resume** | personal | `Tailor a resume for {company} {role}. Use the application page at {path}.` |
| **A bookmark** | any | `Bookmark {URL} with note: {why useful}.` |
| **A new person in the rolodex** | any | `Add this person: {LinkedIn URL or details}. Context: {how we met}.` |
| **A document (PDF/.docx/.xlsx)** | any | `Ingest this document: raw/{path}.` |

For the full set with location, template, and what auto-updates downstream, jump into your variant's README.

---

## Foundation: Obsidian Skills

This kit is designed to work with [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills), the official agent skills for Obsidian created by Steph Ango (Obsidian's CEO). These skills teach Claude the correct syntax for every Obsidian file type:

| Skill | What It Does |
|---|---|
| **obsidian-markdown** | Correct Obsidian Flavored Markdown — wikilinks, embeds, callouts, properties, frontmatter, block IDs, tags |
| **obsidian-bases** | Obsidian Bases (`.base` files) — database-like views over wiki pages with filters, formulas, and summaries |
| **json-canvas** | JSON Canvas (`.canvas` files) — spatial maps, flowcharts, project boards |
| **obsidian-cli** | Obsidian CLI — read, create, search, manage notes, tasks, and properties from the command line |
| **defuddle** | Web clipping — strips pages to clean markdown, removes ads/nav/chrome, saves tokens |

Without these skills, Claude may produce invalid wikilink syntax, broken `.base` files, or malformed `.canvas` output. **Install them in every vault where you use Claude Code** (the per-variant READMEs include the install commands).

---

## Architecture in one minute

### CLAUDE.md — Two-Layer Schema

```
vault-root/
├── CLAUDE.md                     # Shared: conventions, progressive loading,
│                                 #   provenance, operations, asset management
└── _variant/
    └── CLAUDE.variant.md         # Variant-specific: identity, ontology,
                                  #   page types, tone, domain operations
```

### Key patterns

- **Progressive loading** — Every page has a `## Synopsis` section (2-3 sentences). Claude reads in three stages: index scan → synopsis scan → full read. ~100-300x token reduction.
- **Provenance tracking** — Every page declares `provenance: extracted | synthesized | mixed`. Synthesized claims need source footnotes back to `raw/`.
- **Companion pages** — Non-text files (PDFs, images, .docx, .xlsx) get a markdown companion page with metadata, making them visible in Obsidian's graph and search.
- **Structured ingestion** — Specialized ingesters with two axes: source-type (URL, PDF, paste, image) and content-type (recipe, meeting, EOB, receipt). The orchestrator routes by both.
- **Operations layer** — Skills that read structured wiki pages, compose, and write derived pages back. Five classes: planning, reminding, synthesizing, recommending, crisis-responding.
- **Research projects** — Multi-source investigations toward a verdict. Each lives at `research/{date}-{slug}/` with the **4-pillar ontology** (Entities, Attributes, Mental Model, Verdict) and **4-phase workflow** (Capture, Sieve, Synthesize, Feedback). The artifact shape (`matrix`, `shortlist`, or `blueprint`) is declared upfront. Verdicts require ≥2 corroborating sources.
- **Lint with scripts** — Python scripts handle deterministic checks (tag synonyms, convergence debt, missing fields). Claude handles semantic checks (contradictions, orphan analysis).

For the full design narratives: [`docs/design/work.md`](docs/design/work.md), [`docs/design/family.md`](docs/design/family.md), [`docs/design/personal.md`](docs/design/personal.md), [`docs/design/research-layer.md`](docs/design/research-layer.md).

---

## Scaling notes

The kit scales in stages. Start simple and add infrastructure only when you hit the limits of the current stage.

| Vault size | Retrieval method | What to do |
|---|---|---|
| **<100 pages** | Progressive loading only | Claude reads index.md, scans synopses, reads full pages. No infrastructure needed. |
| **100-500 pages** | Progressive loading | Still manageable. Keep synopses concise. Ensure `index.md` is well-maintained. |
| **500-2,000 pages** | **BM25 search** (optional skill) | Install the `wiki-search` skill. `pip install bm25s[core] PyStemmer`. ~5 second index build. |
| **2,000-10,000 pages** | BM25 search + sharded index | Split the index by project or domain. Rebuild nightly. Consider separate vaults per major area. |
| **10,000+ pages** | Dedicated search service | Move to Typesense, MeiliSearch, or SQLite FTS5 as an external index. The wiki remains markdown; only the search layer changes. |

**Why BM25, not vectors?** At wiki scale, keyword search with stemming handles retrieval well. Vectors add embedding infrastructure, chunking tuning, and a database — none of which are justified until you're well past 10,000 pages or need cross-language semantic similarity.

**Deployment + security.** The shared-drive approach (OneDrive / iCloud / Dropbox / Git) inherits your existing access controls, encryption, and compliance posture. The vault runs entirely on your machines; nothing leaves unless you opt into research integrations per query.

---

## Agent flexibility

The kit is designed for Claude Code and Claude Cowork today, but the architecture is **agent-agnostic by design**:

- **CLAUDE.md is just a markdown file.** Rename it to `AGENTS.md` for OpenAI Codex, or `INSTRUCTIONS.md` for any other agent framework. The content applies to any LLM that reads files and follows instructions.
- **Skills follow the open [Agent Skills spec](https://agentskills.io/specification).** The format is portable across Claude Code, Codex, Cursor, OpenHands, Goose, Gemini CLI, and any other agentskills.io-compatible client.
- **Scripts are standard Python.** They don't call Claude APIs — any agent or human can run them.
- **Obsidian is the UI, not the agent.** The vault is just a folder of markdown files.

**Multi-agent setups:** The safety rules (slug stability, contradiction detection at ingest, append-only fact log) are designed to prevent conflicts when multiple writers operate on the same knowledge base. The `purpose.md` scope check helps prevent agents from writing outside their domain.

---

## Documentation

- **Per-variant READMEs** (the primary entry point, fully self-contained):
  - [`vault-templates/work/README.md`](vault-templates/work/README.md)
  - [`vault-templates/family/README.md`](vault-templates/family/README.md)
  - [`vault-templates/personal/README.md`](vault-templates/personal/README.md)
- **Design narratives** (the rationale behind every choice):
  - [`docs/design/work.md`](docs/design/work.md)
  - [`docs/design/family.md`](docs/design/family.md)
  - [`docs/design/personal.md`](docs/design/personal.md)
  - [`docs/design/research-layer.md`](docs/design/research-layer.md)
- **Operational guides**:
  - [`docs/guides/setup.md`](docs/guides/setup.md) — the full setup walkthrough (per-variant READMEs are the recommended path)
  - [`docs/guides/sync-options.md`](docs/guides/sync-options.md) — shared drive vs. Git tradeoffs
  - [`docs/guides/file-formats.md`](docs/guides/file-formats.md) — companion-page rules for non-text files
  - [`docs/guides/web-clipper.md`](docs/guides/web-clipper.md) — Obsidian Web Clipper template
  - [`docs/guides/customizing.md`](docs/guides/customizing.md) — building a custom variant
  - [`docs/guides/inventories.md`](docs/guides/inventories.md) — the bookmarks-style inventory pattern (subscriptions, holdings, restaurants, …)
- **Reference**:
  - [`docs/comparison.md`](docs/comparison.md) — variants side-by-side
  - [`docs/repo-structure.md`](docs/repo-structure.md) — full directory tree
  - [`docs/research-providers/`](docs/research-providers/) — per-provider docs (Perplexity, Gemini, Semantic Scholar)

---

## License

[MIT](LICENSE)

## Acknowledgments

- **Andrej Karpathy** — for the LLM Wiki concept that inspired this system
- **Steph Ango (kepano)** — for [obsidian-skills](https://github.com/kepano/obsidian-skills) and Obsidian itself
- **Anthropic** — for Claude Code and Cowork, which make the LLM Wiki pattern practical
