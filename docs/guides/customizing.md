# Creating a Custom Variant

The kit ships with `work` and `family` variants. To create your own — for, say, a research lab, a podcast, a consultancy, or a personal-knowledge system with a different ontology than family — follow this five-step path.

## 1. Define your ontology

The ontology is the most important decision: how knowledge is organized so it compounds across captures rather than siloing into dead folders.

- **Primary organizing unit.** Work uses *projects*. Family uses *people + domains*. What's yours? — clients, courses, episodes, customers, research areas?
- **Page types.** What kinds of pages will you create? Specs, ADRs, meeting notes (work)? Medical records, recipes, trips (family)? List 5-15 distinct types.
- **Relationships.** What links to what? In the work variant, projects link to ADRs link to specs link to delivery. Sketch the graph before you write any markdown.

Reference: the work and family ontologies are documented in [`design/work.md`](../design/work.md) (Layer 2) and inside `vault-templates/{work,family}/_variant/CLAUDE.variant.md`.

## 2. Write your CLAUDE.variant.md

Every variant has a `_variant/CLAUDE.variant.md` file that extends the root `CLAUDE.md` with:

- **Variant identity** — who maintains this vault, what it covers, how Claude should sound (tone, technical level, age-appropriateness)
- **Page types** — table mapping each `type` value to a description and default location
- **Status values** — the lifecycle states a page can have (`draft`, `active`, `archived`, etc.)
- **Tagging taxonomy** — categories of tags (delivery phase, artifact type, person, domain, urgency)
- **Ontology** — the directory structure under `wiki/`
- **Variant-specific operations** — workflows that differ from the shared root (e.g., medical records, ADRs, meeting syntheses)
- **Research integration** — which research tools this variant uses

Use `shared/CLAUDE.variant.work.md` and `shared/CLAUDE.variant.family.md` as references. They're sized at ~5-9KB each — your variant should be similar.

## 3. Create your templates

For each page type in your ontology, create a `_templates/<type>.md` file. Required:

- YAML frontmatter with all required fields (`type`, `status`, `provenance`, `created`, `modified`, `tags`) plus any variant-specific fields
- A `## Synopsis` section (2-3 sentences) for progressive loading
- Section headers reflecting the typical structure of that page type
- `{{placeholder}}` fields where the user fills in content

References: `vault-templates/work/_templates/project-brief.md`, `vault-templates/work/_templates/adr.md`, `vault-templates/family/_templates/person.md`, `vault-templates/family/_templates/recipe.md`.

## 4. Build your skills

Skills follow the [Agent Skills spec](https://agentskills.io/specification): each skill is a directory with `SKILL.md` (YAML frontmatter + Markdown instructions), optional `scripts/` and `references/`, and `evals/evals.json`. The kit ships with shared skills (`ingest` orchestrator, `ingest-website`, `ingest-document`, `wiki-lint`, `wiki-search`, `fact-tracking`, `bookmark-homepage`, `trip-planner`, `ingest-bookmark`, `ingest-tax-document`) plus a research layer (`research`, `research-start`, `research-sieve`, `research-synthesize`, `research-verdict-check`).

For your variant, consider:

- **Specialized ingesters** for the source types unique to your domain — podcast transcripts, scientific paper PDFs, customer ticket exports, etc. Follow the orchestrator + specialized pattern: register the type signal in `skills/shared/ingest/SKILL.md`'s detection table, then author the specialized skill alongside.
- **Sync skills** if you need to push or pull from external systems (PM tools, Slack, calendar, your CRM).
- **Domain operations** that automate routine work — "extract action items from meeting", "produce weekly status digest", "summarize this week's medical visits".

Skill directories live at `skills/<scope>/<skill-name>/` where `<scope>` is `shared`, your variant name (e.g., `lab`), or another variant. The `SKILL.md` frontmatter declares `name` (must match the directory name), `description` (max 1024 chars; covers what it does AND when to use it — this is what the agent sees during discovery), `license`, and `metadata.variant`. Author 2-3 representative activation prompts in `evals/evals.json` so the skill's trigger semantics are testable.

## 5. Add to the repo

Drop your variant into the kit's structure:

- `vault-templates/<your-variant>/` — full vault skeleton with `_variant/CLAUDE.variant.md`, `_templates/`, `wiki/index.md`, `log/changelog.md`, and `.gitkeep`s in empty dirs
- `skills/<your-variant>/` — variant-specific skills

Then run through the [setup guide](setup.md) on your new vault-template to verify the Quick Start works end-to-end.

## Examples to study

- **Work variant** — multi-project engineering team. See [`design/work.md`](../design/work.md) for the rationale on every choice. Spec-driven build sessions, ADRs, PM sync.
- **Family variant** — household. See `vault-templates/family/_variant/CLAUDE.variant.md` for the full schema. Sensitive-info handling, low-friction capture, person-first ontology.

If your variant is reusable beyond your own use, consider opening a PR on the kit so others can adopt it.
