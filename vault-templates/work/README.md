# Work Vault — Engineering Team Knowledge OS

A wiki + agent-driven operating layer for an architecture and engineering team. Specs, ADRs, meeting notes, sprint plans, status decks — all written as plain markdown your team owns, kept current by Claude.

This README is **self-contained**. You don't need any other documentation to set up the vault and start using it.

---

## Table of Contents

- [What this vault gives you](#what-this-vault-gives-you)
- [Prerequisites](#prerequisites)
- [Setup — pick one path](#setup--pick-one-path)
- [Your first session](#your-first-session)
- [Capturing new content](#capturing-new-content)
- [Producing deliverables](#producing-deliverables)
- [Querying the vault](#querying-the-vault)
- [Folder map](#folder-map)
- [Authoring rules in 30 seconds](#authoring-rules-in-30-seconds)
- [Health checks](#health-checks)
- [Going further](#going-further)

---

## What this vault gives you

When set up, this vault becomes:

- **A spec-driven build environment** — every feature has a `spec` with current state, implementation plan, and ADR links. Claude can resume a build session by reading the spec.
- **A team rolodex** — colleagues, partners, vendors, recruiters in one searchable place with last-contact dates and open asks.
- **A meeting record that actually gets used** — drop a transcript, get a synthesis with decisions, action items, and people-page updates.
- **A weekly rhythm**: sprint planning Monday, weekly digest Friday, team-status + slides for leadership reviews.
- **Cross-project synthesis** — domain pages (`event-driven`, `rag`, `api-design`) refresh from project-specific learnings.

The **wiki is the source of truth**, not the agent. Claude proposes, you review.

---

## Prerequisites

| Required | Why |
|---|---|
| [Obsidian](https://obsidian.md) (free) | Browse the vault, graph view, backlinks |
| [Claude Code](https://claude.com/code) or Claude Cowork with file-system access | The agent that maintains the vault |
| Python 3.10+ *(optional)* | Lint scripts, BM25 search, document ingest |
| Node + npm *(optional)* | Web clipping with `defuddle` |

You can skip the optional dependencies and add them only when you need them.

---

## Setup — pick one path

You have two ways to set up the vault. Both end with the same result.

### Path A — Edit `purpose.md` yourself (5 minutes, no agent)

1. **Move this folder** to a synced location (OneDrive / Google Drive / Dropbox / Git):
   ```bash
   # You're currently inside this folder. Move the whole thing:
   mv . ~/OneDrive/my-team-wiki
   cd ~/OneDrive/my-team-wiki
   ```

2. **Install [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills)** (Obsidian's official agent skills — wikilinks, Bases, Canvas):
   ```bash
   git clone https://github.com/kepano/obsidian-skills.git /tmp/obsidian-skills
   mkdir -p .claude
   cp -r /tmp/obsidian-skills/.claude/* .claude/
   rm -rf /tmp/obsidian-skills
   ```

3. **Copy this kit's skills** from your `llm-wiki-kit` checkout into `.claude/skills/`:
   ```bash
   cp -r /path/to/llm-wiki-kit/skills/shared/* .claude/skills/
   cp -r /path/to/llm-wiki-kit/skills/work/* .claude/skills/
   ```

4. **Edit `purpose.md`** — replace the placeholders with your team's scope. 3-7 sentences, in-scope and out-of-scope bullets. Claude reads this before every ingest, so anything outside scope gets skipped rather than polluting the wiki.

5. **Edit `_variant/CLAUDE.variant.md`** — top sections only: team name, tone preferences, any tag conventions specific to your org. The rest works as-is.

6. **Open the folder in Obsidian** as a vault. `wiki/index.md` is your starting point.

You're done. Skip to [Your first session](#your-first-session).

### Path B — Let Claude walk you through setup (10 minutes, conversational)

Do steps 1, 2, and 3 from Path A (move folder, install obsidian-skills, copy kit skills), then start Claude in the vault directory:

```bash
cd ~/OneDrive/my-team-wiki
claude
```

Paste this prompt:

> Set up this work vault for me. Read `CLAUDE.md` and `_variant/CLAUDE.variant.md` first to understand the schema, then ask me one question at a time to fill in:
>
> 1. **Team identity** — team name, what we build, tech stack at a high level.
> 2. **Active projects** — names + 1-line description for each. Create a stub `wiki/projects/{slug}/overview.md` for each from the `_templates/project-brief.md` template.
> 3. **In-scope topics** — what kinds of sources I want ingested (e.g., meeting transcripts, ADRs, design docs, vendor evaluations, research papers).
> 4. **Out-of-scope topics** — what I want skipped (e.g., personal HR docs, payroll, customer PII).
> 5. **Tone** — formal-engineering, casual-startup, or somewhere in between.
> 6. **Tagging conventions** — any taxonomies my org already uses (e.g., `#client-acme` per-client tags, `#cost-center-X`).
> 7. **PM tool** — Linear, Jira, Plane, or none.
>
> When done, write the result to `purpose.md` (replacing the placeholder) and update the identity / tone sections of `_variant/CLAUDE.variant.md`. Don't change anything else. Show me the diffs before saving.

Claude will ask one question at a time and write `purpose.md` plus a few project stubs at the end.

---

## Your first session

Run the **canonical operation** before capturing anything else. It's what makes the vault feel alive — the rhythm that gives captures a purpose.

For the work variant, that's **sprint-planning**:

```
Run the sprint-planning skill for the {project-slug} project.
Sprint starts Monday {YYYY-MM-DD}. Capacity is {N} engineer-days.
```

Claude will:
1. Read the project's `overview.md`, active specs, and recent decisions.
2. Pull open tasks from `tasks.md`.
3. Produce a `wiki/projects/{slug}/delivery/sprint-{YYYY-MM-DD}.md` page with goals, scope, risks, and a checklist.
4. Update the project overview's "Current State" section.

Open the new sprint page in Obsidian. That's your reference for the week.

> [!tip] If you don't have an active project yet
> Run `Capture a new project: {one-paragraph brief}.` Claude will scaffold `wiki/projects/{slug}/overview.md`, `tasks.md`, and the standard subfolders.

---

## Capturing new content

The pattern: tell Claude what kind of artifact you're producing, paste or point to source material, and let it land in the right place with the right frontmatter.

Below are the most common moves. Each prompt assumes you're in a Claude session inside the vault.

### Designs and architecture docs

```
Write a design doc for {topic} in the {project-slug} project.
Approach: {your sketch — bullet points are fine}.
Cross-link relevant ADRs and any prior designs.
```

Lands at `wiki/projects/{slug}/design/{topic-slug}.md` (or under `topics/{topic}/design/` for multi-topic projects). Use `_templates/` if a relevant template exists.

### ADRs (Architecture Decision Records)

```
Capture an ADR for the {project-slug} project: we decided to {choice}
over {alternative(s)}. Context: {why this came up}. Trade-offs:
{what we accept}.
```

Lands at `wiki/projects/{slug}/decisions/adr-{NNN}-{slug}.md` using `_templates/adr.md`. ADRs are immutable — to reverse a decision, create a new ADR that supersedes the old one.

### Specs (feature specifications with implementation plans)

```
Start a new spec in {project-slug} for {feature}. The goal is
{user-facing outcome}. Include implementation plan as a checklist.
Status starts at draft.
```

Lands at `wiki/projects/{slug}/specs/{feature-slug}.md`. The spec carries a **Current State** section that build sessions update — that's how Claude resumes work across sessions.

### Resuming a build session (spec-session-start)

```
Resume the build session on the active spec in {project-slug}.
```

Claude reads the spec's Current State, the referenced ADRs, the code repo, and picks up from the next unchecked implementation step. End the session with `Update the spec's Current State with what we completed and what remains.`

### Meeting notes

Drop a transcript or notes into `raw/{project-slug}/meetings/` (or paste them inline), then:

```
Ingest this meeting for {project-slug}: {paste or path to file}.
Surface decisions, action items with owners and dates, and any open questions.
```

Lands at `wiki/projects/{slug}/meetings/{YYYY-MM-DD}-{topic}.md` using `_templates/meeting-synthesis.md`. Person-pages get updated with `last_contact:` automatically for any external attendees.

### Tasks (lightweight per-project)

```
Add to {project-slug} tasks: {task description}. Owner: {name}. Due: {date}.
```

Appended to `wiki/projects/{slug}/tasks.md` under "Open". Move tasks between Open / In Progress / Done as work moves.

### Discovery and research notes

For a quick single-source brief:

```
Save a research brief: {topic}. Source: {URL or paste}.
Key takeaways and how they apply to {project-slug}.
```

Lands at `research/{YYYY-MM-DD}-{slug}.md`.

For multi-source investigations:

```
Start a research project: {question}. Artifact shape: matrix |
shortlist | blueprint. Sources I have so far: {URLs / paths}.
```

Scaffolds `research/{YYYY-MM-DD}-{slug}/` with the 4-pillar / 4-phase structure (capture, sieve, synthesize, verdict). Verdicts require ≥2 corroborating sources.

### People (rolodex)

From a LinkedIn URL, business card photo, vCard, or email signature:

```
Add this person to the people directory: {paste URL or details}.
Context: met at {event}, working on {project-slug}.
```

Lands at `wiki/people/{slug}.md`. After future interactions, log a touch with:

```
Log a touch with {name}: {what was discussed}. Surface any open asks they raised.
```

This bumps `last_contact:` and feeds the **request-tracker** skill.

### Bookmarks

```
Bookmark {URL} with note: {why it's useful}.
```

Lands at `wiki/bookmarks/{slug}.md`. Render the collection via `wiki/bookmarks/homepage.base`.

### Web clips

If you use the [Obsidian Web Clipper](https://obsidian.md/clipper), clips land in `Clippings/` or `raw/web-clips/`. Then:

```
Process pending clippings.
```

Claude routes each through the right ingester (recipe / article / paper / etc.) and relocates it.

### Documents (PDF, .docx, .xlsx, .pptx)

Drop the file into `raw/{project-slug}/`, then:

```
Ingest this document: raw/{project-slug}/{filename}.
```

The `ingest-document` skill (uses Docling under the hood) extracts to clean markdown, creates a companion page co-located with the asset, and links it from the relevant project.

---

## Producing deliverables

Operations read structured wiki pages and write derived pages back. The output is itself a wiki page subsequent operations can consume.

### Sprint plan
```
Plan the next sprint for {project-slug}. Capacity: {N} engineer-days. Sprint dates: {start}–{end}.
```

### Weekly digest (backward-looking)
```
Produce this week's digest across all active projects.
```
Lands at `wiki/syntheses/weekly-{YYYY-MM-DD}.md`. Reads recent changelogs, decisions, and meeting syntheses.

### Team status (forward-looking RAG / risks / issues / asks)
```
Refresh the team-status page for the leadership review.
```
Lands at `wiki/team-status/{YYYY-MM-DD}.md`.

### Status slides (PowerPoint deck)
```
Convert today's team-status page into a status deck.
```
Reads the latest `wiki/team-status/*.md`, builds a `.pptx` in `outputs/team-status/`, and creates a companion page in the wiki. Uses `python-pptx` under the hood; install with `pip install python-pptx`.

### ADR review queue
```
Show me ADRs awaiting acceptance.
```
Surfaces all `decisions/*.md` with `status: draft`.

### Cross-project synthesis (refresh a domain page)
```
Refresh the wiki/domains/{domain-name}.md page with learnings
from the last quarter of project work.
```

### Onboarding pack (curated reading order for a new hire)
```
Produce an onboarding pack for {name}, joining {project-slug} as {role}.
```
Lands at `wiki/onboarding/{name}-{YYYY-MM-DD}.md` with a guided reading order.

### Request tracker (cross-team asks + escalations)
```
List outstanding cross-team requests with due dates.
```
Reads `## Open Asks` callouts on people pages and meeting syntheses.

---

## Querying the vault

Just ask. Claude uses **progressive loading** — it scans `wiki/index.md`, then page synopses, and only reads full pages once it's confirmed relevance. That keeps token use low even on a large vault.

Examples:

- `What did we decide about message deduplication on the order-platform?`
- `Find all designs that touch RAG in the last 90 days.`
- `Who owns the Acme account and when did we last talk to them?`
- `What's the current state of the config-profile-schema spec?`
- `What's blocking the sprint?`

If a query would be useful to future questions, ask Claude to save the answer:

```
Save that as a synthesis page in wiki/syntheses/.
```

---

## Folder map

```
{your-vault}/
├── CLAUDE.md                    # Root agent contract (don't edit)
├── purpose.md                   # Your scope statement (you edit this)
├── _variant/
│   └── CLAUDE.variant.md        # Work-variant schema (edit identity sections only)
├── _templates/                  # Page templates with {{placeholder}} fields
│   ├── project-brief.md
│   ├── adr.md
│   ├── meeting-synthesis.md
│   ├── ...
├── raw/                         # Immutable source documents (drop files here)
├── wiki/                        # Structured pages (your source of truth)
│   ├── index.md                 #   Dashboard / entry point
│   ├── projects/{slug}/         #   Per-project: overview, design, specs, decisions, meetings, tasks, delivery
│   ├── people/                  #   Rolodex
│   ├── domains/                 #   Cross-project domain knowledge
│   ├── playbooks/               #   Reusable methodologies
│   ├── tools/                   #   Tool/vendor evaluations + agentic-stack inventory
│   ├── team-status/             #   Forward-looking status pages
│   ├── bookmarks/               #   URL bookmarks + homepage.base
│   └── syntheses/               #   Weekly digests, cross-project syntheses
├── research/                    #   Multi-source research projects (4-pillar / 4-phase)
├── outputs/                     #   Claude-generated deliverables (.docx, .pptx, .pdf)
├── log/
│   └── changelog.md             #   Append-only change log
└── .claude/
    ├── skills/                  #   Agent skills (you populated this in setup)
    └── research-providers.yaml  #   API keys for research dispatch
```

### Multi-topic projects

When a project has 3+ distinct workstreams (each with its own architecture, specs, decisions), use a `topics/{topic-slug}/` subtree:

```
wiki/projects/order-platform/
├── overview.md                  # Project-level
├── topics/
│   ├── config-knowledge/
│   │   ├── overview.md
│   │   ├── design/
│   │   ├── specs/
│   │   └── decisions/
│   ├── file-validation/
│   └── e2e-orchestration/
├── meetings/                    # Stay project-level (cross-topic)
├── tasks.md                     # Cross-topic task view
└── delivery/                    # Sprint plans, status updates
```

---

## Authoring rules in 30 seconds

These are enforced by `CLAUDE.md` and the `wiki-lint` skill:

- **Filenames are kebab-case** (`event-driven-architecture.md`), dates are **ISO 8601** (`2026-04-25`).
- **Every page has YAML frontmatter** (`type`, `status`, `provenance`, `created`, `modified`, `tags`).
- **Every page has a `## Synopsis` section** — 2-3 sentences. This is what enables progressive loading.
- **`provenance:`** is `extracted` (transcribed from a source) | `synthesized` (LLM-generated, needs source footnotes) | `mixed`.
- **Internal links are wikilinks**: `[[page-name]]`, not relative paths.
- **Non-text files get a markdown companion page** in an `_assets/` folder — that's how they show up in the graph and search.
- **Filenames are canonical slugs — never rename them.** Update `title:` and `aliases:` in frontmatter instead.
- **Never silently overwrite contradicting content** — Claude flags it with a `> [!danger] Contradiction` callout.

---

## Health checks

Run on demand or weekly. Detects orphans, stale pages, broken wikilinks, missing synopses, contradictions, convergence debt (raw sources never synthesized), and tag synonyms.

```
Lint the vault and write the report to log/lint-{today}.md.
```

Underlying scripts (Python 3.10+):
```bash
pip install pyyaml
# Tag synonyms + usage analysis
python .claude/skills/wiki-lint/scripts/tag-lint.py .
# Raw sources without wiki coverage
python .claude/skills/wiki-lint/scripts/convergence-debt.py .
```

For a 500+ page vault, install BM25 search:
```bash
pip install bm25s[core] PyStemmer pyyaml
```
Then ask Claude `Search the vault for {query}.` It runs `wiki-search.py` instead of progressive scanning.

---

## Going further

- **Add custom skills** — drop a new directory under `.claude/skills/{skill-name}/` with `SKILL.md`, `scripts/`, `evals/evals.json` per the [Agent Skills spec](https://agentskills.io/specification). Claude discovers it on next session start.
- **Add custom page templates** — drop `_templates/{type}.md` and add the type to `_variant/CLAUDE.variant.md`'s page-types table.
- **Connect a PM tool** — install the corresponding sync skill (`sync-pm-linear`, `sync-pm-jira`, `sync-pm-plane`) and configure with your API key.
- **Customize tone or ontology** — edit `_variant/CLAUDE.variant.md`. Don't restructure top-level folders without considering downstream.

---

## Safety reminders

- **Never delete files without asking** — archive instead (`status: archived`).
- **Never overwrite a deliverable version** — create a new version file.
- **`raw/` is immutable** — never modify ingested source documents after the fact.
- Review what Claude proposes before you accept. The wiki only stays trustworthy if a human curates the LLM's writes.
