# LLM Wiki Kit

A configurable knowledge **operating system** built on the LLM Wiki pattern. An LLM captures raw sources into a structured Obsidian-vault wiki, then runs operations that produce derived artifacts — plans, reviews, digests, dashboards, itineraries, typed inventories. Three first-class variants ship: **work** (engineering team), **family** (household), **personal** (solo knowledge + career). Capture and operate, both grounded in the same vault.

This repo provides **vault templates**, **CLAUDE.md schemas**, **Claude Skills**, **Python scripts**, and **page templates** for different use cases. Pick a variant, clone the template, customize your ontology, and start using your wiki with Claude Code or Claude Cowork.

---

## How It Works

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

**Capture.** Raw sources flow through specialized ingesters that produce *structured* wiki pages. A recipe URL becomes a recipe page in `food/` with ingredients, steps, and dietary tags. A meeting transcript becomes a synthesis in `projects/{slug}/meetings/` with decisions and action items. A PDF becomes markdown via Docling and lands in the right wiki location. The orchestrator (`skills/shared/ingest/SKILL.md`) routes by *source-type* (URL, PDF, paste) and *content-type* (recipe, meeting, EOB, receipt).

**Operate.** Operations are skills that read structured wiki pages, compose, and write derived pages back into the wiki. Five classes: planning, reminding, synthesizing, recommending, crisis-responding. Sprint planning, meal planning, weekly digest, follow-up tracker, ADR review queue, onboarding pack. The output of an operation is itself a wiki page that subsequent operations can read.

A wiki without operations is a filing cabinet. The capture loop runs at first, then dies because nobody sees visible weekly payoff. Operations provide that payoff — every Sunday's meal plan, every Friday's digest, every sprint's auto-prepared planning page. Capture and operate reinforce each other: better capture produces better operations; better operations create demand for better capture.

Humans guide the agent, review its output, and browse the wiki in Obsidian. Over time, the vault becomes institutional memory — for a team, a family, or you personally — searchable, navigable, always current, and *operational*.

### Design Philosophy

**Human-guided, not autonomous.** This system is a digital secretary, not an autopilot. You do the thinking — reading sources critically, building mental models, making judgment calls. The LLM does the grunt work — summarizing, cross-referencing, filing, and maintaining the structure that makes a knowledge base useful over time. You can jot down rough thoughts and the agent helps structure them, ask follow-up questions, and relate them to other ongoing work. But the human stays in the loop for every quality-critical decision.

**Human curation is non-negotiable.** Research on LLM-maintained documentation shows that fully unsupervised LLM management degrades quality over time. The sweet spot is human curation with LLM assistance — the LLM proposes, the human reviews. This kit enforces that through provenance tracking (so you know what's LLM-generated), contradiction detection at ingest time (so the LLM never silently overwrites), interactive review during article ingestion, and lint checks that surface quality issues for human resolution. If nobody reviews what the LLM writes, the wiki will drift. Build the review habit early.

**A wiki nobody operates from is waste.** The most common failure mode isn't bad content — it's content nobody composes against. An LLM can generate enormous volumes of structured notes, but if no operation reads them weekly, the capture loop dies and the wiki becomes expensive filing. This kit is designed around two reinforcing loops: the *capture loop* (ingest a source → wiki updates) and the *operate loop* (operation reads wiki → produces a derived page → derived page becomes input to the next operation). Every feature — progressive loading, synopses, search, structured ingestion, operations layer — exists to make both loops fast and useful. If you find yourself only ingesting and never operating, stop and ask whether the wiki is serving its purpose.

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

Without these skills, Claude may produce invalid wikilink syntax, broken `.base` files, or malformed `.canvas` output. **Install them in every vault where you use Claude Code.**

---

## Core Architecture

### CLAUDE.md — Two-Layer Schema

```
vault-root/
├── CLAUDE.md                     # Shared: conventions, progressive loading,
│                                 #   provenance, operations, asset management
└── _variant/
    └── CLAUDE.variant.md         # Variant-specific: identity, ontology,
                                  #   page types, tone, domain operations
```

### Key Patterns

**Progressive loading** — Every wiki page has a `## Synopsis` section (2-3 sentences). Claude reads pages in three stages: index scan (depth 0) → synopsis scan (depth 1) → full read (depth 2). This is a 100-300x reduction in tokens compared to reading every page in full.

**Provenance tracking** — Every page declares `provenance: extracted | synthesized | mixed` in frontmatter. Synthesized claims require source footnotes back to `raw/`. LLM inferences get marked with `> [!note] Inferred` callouts.

**Companion pages** — Non-text files (PDFs, images, .docx, .xlsx) get a markdown companion page with metadata, making them visible in Obsidian's graph and search.

**Structured ingestion** — Specialized ingesters with two axes: source-type (cleans the input — URL, PDF, paste, image) and content-type (applies schema — recipe, meeting, EOB, receipt). The orchestrator (`skills/shared/ingest/SKILL.md`) routes by both axes; specialized ingesters like `ingest-recipe`, `ingest-meeting`, `ingest-document` produce typed wiki pages that operations can mechanically consume.

**Operations layer** — Skills that read structured wiki pages, compose, and write derived pages back. Five classes: planning, reminding, synthesizing, recommending, crisis-responding. Sprint planning (work), meal planning (family), and weekly review (personal) are the canonical examples; each reads structured pages, applies variant-specific logic, and writes a new dated page that subsequent operations and humans both consume.

**Research projects** — Multi-source investigations toward a verdict. Each project lives in `wiki/research/{date}-{slug}/` with the **4-pillar ontology** (Entities, Attributes, Mental Model, Verdict) and progresses through the **4-phase workflow** (Capture, Sieve, Synthesize, Feedback). The artifact shape (`matrix`, `shortlist`, or `blueprint`) is declared upfront at research-start time. Verdicts require ≥2 corroborating sources (Two-Source Rule). Both variants instantiate the same architecture; only the domain examples differ. See [`docs/design/research-layer.md`](docs/design/research-layer.md).

**Lint with scripts** — Python scripts handle deterministic checks (tag synonyms, convergence debt, missing fields). Claude handles semantic checks (contradictions, orphan analysis, synonym review).

---

## Variants

### Work — Engineering Team

For multi-project engineering teams. Spec-driven development with Claude Code session continuity, ADRs, structured meeting ingest, sprint planning, weekly digest, cross-project synthesis, ADR review queue, onboarding pack, PM sync (Linear / Jira / Plane). Research integrations: Perplexity + Gemini + Semantic Scholar.

[Design narrative →](docs/design/work.md)

### Family — Household

Person-first ontology with structured ingest of recipes, medical records, receipts, school documents, trips. Operations: meal planning, follow-up tracker, trip prep, weekly digest, medical summary, recipe recommender. Inventories: restaurants, subscriptions, holdings, tax records, POIs. Trip planner integrates with the research layer.

[Design narrative →](docs/design/family.md)

### Personal — Knowledge & Career OS

Zettelkasten-style atomic notes plus career-progression artifacts. Operations: weekly / quarterly / annual reviews, career narrative refresh, job-search prep, knowledge consolidation, networking digest, reading queue, decision check, skill-gap analysis. Inventories: advisors, role-tooling, holdings, tax records.

[Design narrative →](docs/design/personal.md)

---

## Repo Structure

The high-level layout: `docs/` (documentation), `shared/` (canonical agent contracts), `vault-templates/` (one folder per variant), `skills/` (Agent Skills per [agentskills.io](https://agentskills.io/specification) — each is a directory with `SKILL.md`, owning `scripts/`, and `evals/evals.json`).

Skills follow an **orchestrator + specialized** pattern: `skills/shared/ingest/SKILL.md` detects source type and content type, then delegates to specialized siblings (`ingest-document`, `ingest-website`, `ingest-recipe`, `ingest-meeting`, `ingest-bookmark`, `ingest-tax-document`, etc.). The orchestrator stays small and routing-focused; specialized files own per-type extraction logic.

Full directory tree (top-level + per-vault structure): [`docs/repo-structure.md`](docs/repo-structure.md).

---

## Quick Start

### 1. Clone and Copy a Vault Template

```bash
git clone https://github.com/eugenelim/llm-wiki-kit.git
cd llm-wiki-kit

# Copy the variant template to your cloud drive folder
cp -r vault-templates/work ~/OneDrive/my-team-wiki
# or
cp -r vault-templates/family ~/GoogleDrive/my-family-wiki
# or
cp -r vault-templates/personal ~/Dropbox/my-personal-wiki
```

### 2. Install Obsidian Skills

```bash
cd ~/OneDrive/my-team-wiki   # (or wherever you put the vault)

# Clone kepano/obsidian-skills and copy into .claude/
git clone https://github.com/kepano/obsidian-skills.git /tmp/obsidian-skills
cp -r /tmp/obsidian-skills/.claude/* .claude/
rm -rf /tmp/obsidian-skills
```

### 3. Copy Kit Skills

Each skill is a directory (`SKILL.md` + `scripts/` + `evals/`) per the Agent Skills spec; copy whole directories.

```bash
# From the llm-wiki-kit repo root:

# Shared skills (every variant)
cp -r skills/shared/* ~/OneDrive/my-team-wiki/.claude/skills/

# Variant-specific skills
cp -r skills/work/* ~/OneDrive/my-team-wiki/.claude/skills/
# or for family:
# cp -r skills/family/* ~/GoogleDrive/my-family-wiki/.claude/skills/
# or for personal:
# cp -r skills/personal/* ~/Dropbox/my-personal-wiki/.claude/skills/
```

Bundled Python scripts ship inside their owning skills' `scripts/` directory — no separate copy step.

### 4. Customize

Edit `_variant/CLAUDE.variant.md` to set your team or family identity. The root `CLAUDE.md` works as-is.

### 5. Open in Obsidian and run your first canonical operation

Open the vault folder in Obsidian. `wiki/index.md` is your starting point.

Then run your variant's **canonical operation** — the gateway that establishes the rhythm that keeps the vault alive:

| Variant | Canonical operation | Cadence |
|---|---|---|
| Work | `sprint-planning` | Sprint kickoff (typically Monday morning) |
| Family | `meal-planning` | Sunday afternoon |
| Personal | `weekly-review` | Sunday evening or Monday morning |

The canonical operation produces a derived artifact (sprint plan, meal plan, weekly review) you'll consume the next week. **Without it, the capture loop dies; with it, the vault stays operational.** Resist the temptation to capture lots of content first — the canonical operation is what gives captures a purpose.

---

## Comparison

A side-by-side comparison of how the three variants differ — organizing unit, page types, operations, tone, shipped inventories — lives at [`docs/comparison.md`](docs/comparison.md).

---

## Creating a Custom Variant

See [docs/guides/customizing.md](docs/guides/customizing.md) for the five-step walkthrough: ontology design, `CLAUDE.variant.md`, templates, skills, and integration into the repo.

---

## Scaling Notes

The kit scales in stages. Start simple and add infrastructure only when you hit the limits of the current stage.

| Vault size | Retrieval method | What to do |
|---|---|---|
| **<100 pages** | Progressive loading only | Claude reads index.md, scans synopses, reads full pages. No infrastructure needed. |
| **100-500 pages** | Progressive loading | Still manageable. Keep synopses concise. Ensure index.md is well-maintained. |
| **500-2,000 pages** | **BM25 search** (optional skill) | Install the `wiki-search` skill. `pip install bm25s[core] PyStemmer`. Claude searches before navigating. ~5 second index build. |
| **2,000-10,000 pages** | BM25 search + sharded index | Split the index by project or domain. Rebuild nightly. Consider separate vaults per major area. |
| **10,000+ pages** | Dedicated search service | Move to Typesense, MeiliSearch, or SQLite FTS5 as an external index. The wiki remains markdown; only the search layer changes. |

**The default is no index.** Progressive loading (index.md → synopsis scan → full read) works for the vast majority of team and family vaults. The BM25 search skill (`skills/shared/wiki-search/`) is included as an optional scaling layer that Claude Code can call when the vault grows large enough to warrant it. It's pure Python with no server process — just a script that builds a local index file and queries it.

**Why BM25, not vectors?** At wiki scale, keyword search with stemming handles the retrieval problem well — most wiki queries lean on keyword overlap, proper-noun lookups, and domain terms, all of which BM25 indexes efficiently. Vectors add embedding infrastructure, chunking tuning, and a database — none of which are justified until you're well past 10,000 pages or need semantic similarity search across languages. BM25 is the right middle step between "Claude reads files" and "deploy a search cluster."

**Deployment and security.** For teams handling sensitive documents, the shared drive approach (OneDrive, Google Drive, Dropbox) inherits your organization's existing access controls, encryption, and compliance posture — no new infrastructure to secure. If using Git, keep the repository private and avoid pushing to public hosts. The vault runs entirely on your machines; no data leaves unless you configure external research integrations (Perplexity, Gemini, Semantic Scholar), and those are opt-in per query.

**Future consideration: intent-context routing.** The current retrieval model (progressive loading or BM25 keyword search) routes queries based on the query text. Community experience with agent-driven wikis suggests that the agent's operating context — "am I fact-checking?" vs. "am I doing open research?" — is a stronger routing signal than the query string itself. An agent in a fact-check context may emit long, well-formed sentences that want exact-match retrieval, while an open-research context produces short queries that need broader narrative search. If a future version adds a query router, it should accept an optional intent hint alongside the query text rather than relying on text-shape heuristics alone.

---

## Agent Flexibility

The kit is designed for Claude Code and Claude Cowork today, but the architecture is **agent-agnostic by design**. Nothing in the system depends on Claude-specific features:

- **CLAUDE.md is just a markdown file.** Rename it to `AGENTS.md` for OpenAI Codex, or `INSTRUCTIONS.md` for any other agent framework. The content — conventions, operations, safety rules — applies to any LLM that reads files and follows instructions.
- **Skills follow the open [Agent Skills spec](https://agentskills.io/specification).** Each skill is a directory with a `SKILL.md` (YAML frontmatter + Markdown instructions), optional `scripts/` and `references/`, and `evals/evals.json`. The format is portable across Claude Code, Codex, Cursor, OpenHands, Goose, Gemini CLI, and any other agentskills.io-compatible client.
- **Scripts are standard Python.** `tag-lint.py`, `convergence-debt.py`, `wiki-search.py`, `ingest_document.py`, `research.py` — these don't call Claude APIs. They parse markdown and YAML, or dispatch to research providers via configured API keys. Any agent or human can run them. They live inside their owning skill's `scripts/` folder per the spec.
- **Obsidian is the UI, not the agent.** The vault is just a folder of markdown files. Obsidian provides graph view and backlinks for humans. Agents work on the files directly.

**Multi-agent setups:** If you run multiple agents (e.g., Claude Code for engineering, a different model for research synthesis), they can share the same vault. The safety rules — particularly slug stability, contradiction detection at ingest, and the append-only fact log pattern — are designed to prevent conflicts when multiple writers operate on the same knowledge base. The `purpose.md` scope check helps prevent agents from writing outside their domain.

**Non-Claude agent tools:** The kit works with any tool that gives an LLM agent read/write access to a local filesystem. This includes OpenAI Codex CLI, Cursor Agent Mode, Cline, Aider, Continue, or any future agent framework. The CLAUDE.md schema is the interface contract — as long as the agent reads and follows it, the system works.

---

## What's Still Coming

The kit ships in stages. This release includes three variant schemas + four design narratives (work, family, personal, research-layer), the four operational guides, the shared skills (`ingest` orchestrator with two-axis routing, `ingest-website`, `ingest-document`, `ingest-person`, `person-update`, `wiki-lint`, `wiki-search`, `fact-tracking`, `task-tracking`), all variant content-type ingesters (`ingest-meeting` for work; `ingest-recipe` / `ingest-medical-record` / `ingest-receipt` / `ingest-school-doc` / `ingest-trip` for family; `ingest-book-note` / `ingest-application` for personal), the work-variant operation skills (`sprint-planning`, `weekly-digest`, `spec-session-start`, `adr-review-queue`, `cross-project-synthesis`, `onboarding-pack`, `task-tracking`, `request-tracker`, `team-status`, `status-slides`), the family-variant operation skills (`meal-planning`, `follow-up-tracker`, `trip-prep`, `weekly-digest`, `medical-summary`, `recipe-recommender`), the personal-variant operation skills (`weekly-review`, `quarterly-review`, `annual-review`, `career-narrative-refresh`, `job-search-prep`, `knowledge-consolidation`, `networking-digest`, `reading-queue`, `decision-check`, `skill-gap-analysis`, `log-accomplishment`, `log-hobby-session`, `log-fitness-session`, `log-body-metric`), the full research layer (orchestrator skill `research`, four phase operations `research-start` / `research-sieve` / `research-synthesize` / `research-verdict-check`, dispatch script `skills/shared/research/scripts/research.py`, provider config schema `.claude/research-providers.yaml`, and per-provider docs `docs/research-providers/{perplexity,semantic-scholar,gemini}.md`), the Python scripts (`tag-lint`, `convergence-debt`, `wiki-search`, `ingest_document`, `research`, `build_slides`), starter content for all three vault templates including the `meeting-synthesis` template (work) and `note` / `project` / `review` / `application` templates (personal), and the full research-layer template set in all three variants. Open work tracked for the next milestone:

**Vault templates** — additional `_templates/*.md` page templates per ontology (each variant ships starter templates; the full set listed in each variant's CLAUDE.variant.md page-types table is in progress).

**Skills**
- Work — sync: `sync-pm-{linear,jira,plane}.md`

---

## License

[MIT](LICENSE)

## Acknowledgments

- **Andrej Karpathy** — for the LLM Wiki concept that inspired this system
- **Steph Ango (kepano)** — for [obsidian-skills](https://github.com/kepano/obsidian-skills) and Obsidian itself
- **Anthropic** — for Claude Code and Cowork, which make the LLM Wiki pattern practical
