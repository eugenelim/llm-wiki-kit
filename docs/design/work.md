# Team Knowledge Management System Design

## Architecture: LLM Wiki Pattern → Team Scale

This system adapts Karpathy's LLM Wiki pattern — where an LLM compiles and maintains a structured markdown knowledge base from raw sources — into a multi-project, multi-user team operating system for an architecture and engineering team. The core insight stays the same: **knowledge is synthesized at ingest time, not query time**. But we extend it with shared infrastructure, external research integration, project management sync, and non-technical user access via Claude Cowork.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    TEAM KNOWLEDGE SYSTEM                         │
│                                                                  │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────────┐    │
│  │  Shared   │   │   Research   │   │   Project Mgmt       │    │
│  │  Drive /  │◄─►│   Layer      │   │   Sync Layer         │    │
│  │  Git Repo │   │              │   │                      │    │
│  │          │   │  Perplexity  │   │  Linear / Jira /     │    │
│  │  Obsidian │   │  Gemini Deep │   │  Plane               │    │
│  │  Vault    │   │  Semantic    │   │  (via MCP + Skills)  │    │
│  │          │   │  Scholar     │   │                      │    │
│  └─────┬────┘   └──────┬───────┘   └──────────┬───────────┘    │
│        │               │                       │                 │
│        └───────────┬───┴───────────────────────┘                 │
│                    │                                             │
│         ┌──────────▼──────────┐                                  │
│         │   CLAUDE.md Schema  │  ← Ontology + Conventions       │
│         │   (per-project +    │                                  │
│         │    team-global)     │                                  │
│         └──────────┬──────────┘                                  │
│                    │                                             │
│     ┌──────────────┼──────────────┐                              │
│     │              │              │                               │
│  ┌──▼───┐   ┌─────▼────┐  ┌─────▼──────┐                       │
│  │Claude │   │ Claude   │  │ Claude     │                       │
│  │Code   │   │ Cowork   │  │ Chat +     │                       │
│  │(devs) │   │(everyone)│  │ Web Search │                       │
│  └───────┘   └──────────┘  └────────────┘                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: The Vault (Storage & Sync)

The team wiki lives as a single Obsidian vault. Every team member syncs it. The vault is the **single source of truth** — all AI-generated wiki pages, raw sources, research outputs, and project artifacts live here as plain markdown.

### Recommended: Shared Drive (default for most teams)

For teams that include non-technical members, a shared cloud drive (OneDrive / Google Drive / Dropbox) is the recommended default. Zero setup beyond installing Obsidian and pointing it at the synced folder, and every team member already understands how cloud drive sync works. Adoption matters more than governance for the first 6-12 months of a wiki's life.

### Alternative: Git Repository (when governance matters)

For larger teams or when wiki changes need formal review, a Git-backed vault provides version history with author attribution, branch-per-feature workflows for parallel work, pull-request review gates on AI-generated wiki updates, deterministic merge resolution, and a real audit trail for compliance.

The full operational comparison — including hybrid setups, when to switch, and the Google Workspace caveats around `.docx`/`.xlsx`/`.pptx` — lives in [`guides/sync-options.md`](../guides/sync-options.md). The format compatibility matrix is in [`guides/file-formats.md`](../guides/file-formats.md).

### Project Isolation

For teams working across multiple projects with confidentiality boundaries, use **separate vaults per project**. This ensures Claude cannot cross-pollinate knowledge between engagements. Each vault gets its own `CLAUDE.md` schema and its own Cowork Project context. Separate vaults enforce data isolation at the filesystem level — Claude cannot cross-reference content it cannot see, which is the simplest, most auditable confidentiality model.

---

## Layer 2: The Ontology (Knowledge Organization)

This is the most important design decision. The ontology defines how knowledge compounds across projects rather than siloing into dead project folders.

### Vault Directory Structure

```
team-wiki/
├── CLAUDE.md                    # Global schema: conventions, workflows, roles
├── _templates/                  # Page templates for consistency
│   ├── project-brief.md
│   ├── design-decision.md
│   ├── solution-proposal.md
│   ├── research-brief.md
│   ├── strategy-note.md
│   └── meeting-synthesis.md
│
├── raw/                         # Immutable source documents (Layer 1 of LLM Wiki)
│   ├── {project-slug}/          # Per-project raw materials
│   │   ├── requirements/
│   │   ├── meeting-transcripts/
│   │   ├── emails/
│   │   └── reference-materials/
│   └── research/                # Academic papers, reports, industry sources
│       ├── papers/
│       └── reports/
│
├── wiki/                        # LLM-generated + human-curated pages (Layer 2)
│   ├── index.md                 # Master navigation (auto-maintained)
│   │
│   ├── projects/                # One folder per active project
│   │   └── {project-slug}/
│   │       ├── overview.md      # Project brief, status, key decisions
│   │       ├── design/          # Architecture, system design, ADRs
│   │       ├── proposals/       # Solution proposals, options analyses
│   │       ├── strategy/        # Strategy docs, roadmaps, planning
│   │       ├── research/        # Project-specific research syntheses
│   │       ├── meetings/        # Synthesized meeting notes (not raw transcripts)
│   │       ├── decisions/       # Decision log with rationale
│   │       └── delivery/        # Sprint notes, status updates, retros
│   │
│   ├── domains/                 # Cross-project domain knowledge
│   │   ├── {domain-slug}.md     # e.g., "event-driven-architecture.md"
│   │   └── ...                  # Entities, concepts, technologies, standards
│   │
│   ├── playbooks/               # Reusable methodologies & frameworks
│   │   ├── system-design-review.md
│   │   ├── agentic-architecture-patterns.md
│   │   ├── rag-pipeline-design.md
│   │   ├── discovery-to-delivery.md
│   │   └── performance-engineering.md
│   │
│   ├── tools/                   # Tool & technology evaluations
│   │   ├── docling.md
│   │   ├── langgraph.md
│   │   └── ...
│   │
│   └── syntheses/               # Cross-project insights, Q&A archives
│       └── ...
│
├── outputs/                     # Claude-generated deliverables (.docx, .pptx, .pdf)
│   ├── {project-slug}/          # Per-project deliverables
│   │   ├── approach-doc-v1.docx
│   │   ├── architecture-overview.pptx
│   │   └── research-report-eda.pdf
│   └── team/                    # Cross-project deliverables
│       ├── quarterly-review.pptx
│       └── technology-radar.pdf
│
├── research/                    # Deep research outputs
│   ├── {date}-{topic-slug}.md
│   └── ...
│
└── log/                         # Change log maintained by the LLM
    └── changelog.md
```

### Deliverables Convention (Word, PowerPoint, PDF)

Obsidian's graph view, search, and backlinks work only on markdown. But Claude Code and Cowork routinely produce deliverables in Office formats — approach documents, research reports, architecture overviews, slide decks — that become important context for subsequent work. The convention: **every deliverable gets a markdown companion page**. The binary file lives in `outputs/`; the companion `.md` page lives alongside the wiki content it relates to, contains the frontmatter and a summary, and links to the file. The deliverable participates in the knowledge graph through its companion page even though Obsidian can't render its contents.

This pattern bridges two layers: the wiki markdown layer where knowledge lives and compounds, and the `outputs/` layer where polished deliverables live for consumption. The companion page extracts the knowledge from the deliverable back into the wiki graph so nothing is trapped in a binary file that only Claude can read.

The full companion-page rules — frontmatter fields, naming conventions, version handling, large-file handling, and when to produce markdown vs. an Office format — are in [`guides/file-formats.md`](../guides/file-formats.md).

### Ontology Design Principles

1. **Projects are the primary organizing unit**, but domain knowledge is extracted and cross-linked. When you learn something about event-driven architecture on one project, that knowledge lives in `domains/event-driven-architecture.md` with a backlink to the project context where it was learned.

2. **Playbooks capture reusable methodology.** System design review processes, architecture assessment frameworks, discovery workshop designs — these are team intellectual property that compounds. Every project should feed back into playbook refinement.

3. **Decisions are first-class objects.** Each project has a `decisions/` folder with lightweight ADRs (Architecture Decision Records). The LLM maintains these as it ingests meeting notes and design docs.

4. **The wiki layer is LLM-owned, human-reviewed.** Team members mostly read the wiki and guide the LLM. Direct human edits are fine but should be flagged in the changelog.

5. **Raw sources are immutable.** Never modify anything in `raw/`. The LLM reads from raw and writes to wiki.

### Frontmatter Standard

Every wiki page uses YAML frontmatter for structured metadata:

```yaml
---
title: "Event-Driven Architecture for Order Processing"
type: design          # project-brief | design | proposal | strategy | research
                      # decision | spec | playbook | domain | tool
project: order-platform
status: active        # draft | active | archived | superseded
created: 2026-04-15
updated: 2026-04-23
author: claude        # claude | {team-member}
sources:
  - raw/order-platform/requirements/system-requirements-v2.pdf
  - raw/order-platform/meeting-transcripts/2026-04-10-discovery.md
tags: [event-sourcing, cqrs, kafka, microservices]
pm_issue: ORD-142     # Links to PM tool (Linear/Jira/Plane issue key)
---
```

### Tagging Taxonomy

Use a controlled but extensible tag vocabulary:

- **Delivery phase:** `#discovery`, `#design`, `#build`, `#test`, `#deploy`
- **Artifact type:** `#architecture`, `#proposal`, `#strategy`, `#research`, `#decision`, `#retro`
- **Domain:** `#event-driven`, `#api-design`, `#rag`, `#agentic-ai`, `#data-pipeline`, `#security`
- **Status:** `#active`, `#draft`, `#blocked`, `#archived`

---

## Layer 3: The Schema (CLAUDE.md)

The CLAUDE.md file is the operating manual that turns Claude into a disciplined wiki maintainer. It lives at the vault root and defines all conventions.

### Key Sections for CLAUDE.md

```markdown
# Team Wiki Schema

## Identity
You maintain a team knowledge base for an architecture and
engineering team building and delivering technical solutions
across multiple projects.

## Vault Structure
[Reference the directory structure above]

## Operations

### Ingest (processing new sources)
1. Accept raw source → copy to raw/{project}/
2. Extract key information: entities, decisions, claims, relationships
3. Check existing wiki pages for conflicts or updates needed
4. Create or update wiki pages with [[wikilinks]] to related pages
5. Update index.md navigation
6. Append to log/changelog.md

### Query (answering questions)
1. Read wiki/index.md to identify relevant pages
2. Navigate via wikilinks to gather context
3. Synthesize answer with inline [[PageName]] references
4. Optionally save synthesis to wiki/syntheses/

### Lint (health checks)
1. Find orphan pages (no inbound links)
2. Find stale pages (no updates in 30+ days on active projects)
3. Check for missing frontmatter fields
4. Identify contradictions across pages
5. Flag decision records without rationale

## Page Conventions
- Every page has YAML frontmatter [as defined above]
- Use [[wikilinks]] for all cross-references
- Cite sources with footnotes linking to raw/ files
- Summaries go at the top, detail below
- Decision records follow: Context → Decision → Rationale → Consequences

## Cross-Project Knowledge
When ingesting project-specific content that contains general
domain knowledge, ALWAYS:
1. Create/update the relevant domains/ page
2. Link back to the project context
3. Note any project-specific caveats

## Tool Evaluations
When a new tool or technology is discussed, create/update a
wiki/tools/{tool-name}.md page with:
- What it does, when to use it, trade-offs, team experience
```

---

## Layer 3B: Spec-Driven Development & Claude Code Continuity

This section addresses a critical question: how does Claude Code pick up work across sessions, and how do wiki artifacts translate into executable engineering work?

### The Continuity Problem

Claude Code has no persistent memory between sessions. Every time you start a new session, Claude reads the CLAUDE.md file and starts fresh. This means the vault itself must contain everything Claude needs to understand where things stand and what to do next. If the context only existed in a prior conversation, it's lost.

This is where spec-driven development becomes essential — not as a methodology preference, but as a **mechanical requirement** for Claude Code continuity. A well-structured spec page in the wiki is how you "save your game." When Claude starts a new session and reads the spec, it knows what's being built, what's been decided, what's done, and what's next.

### How Claude Code Navigates a Build Session

Here's what actually happens when you open Claude Code to continue engineering work:

```
Session Start
    │
    ▼
┌──────────────────────────────────────────────┐
│  1. Claude reads CLAUDE.md                    │
│     → Learns vault structure, conventions,    │
│        and how to navigate                    │
│                                               │
│  2. You say: "Continue work on the order      │
│     ingestion service"                        │
│                                               │
│  3. Claude navigates:                         │
│     wiki/projects/order-platform/overview.md  │
│     → Finds links to active specs and ADRs    │
│                                               │
│  4. Claude reads the feature spec:            │
│     specs/order-ingestion-service.md          │
│     → Current status, completed work,         │
│        implementation plan, open questions     │
│                                               │
│  5. Claude reads referenced design pages:     │
│     design/data-pipeline-architecture.md      │
│     decisions/adr-003-kafka-over-rabbitmq.md  │
│                                               │
│  6. Claude reads the actual codebase          │
│     (in the code repo, separate from wiki)    │
│     → Reconciles spec intent with code state  │
│                                               │
│  7. Claude resumes implementation             │
│     → Updates spec status as work progresses  │
└──────────────────────────────────────────────┘
```

The spec is the bridge between "what we planned" and "what Claude builds." Without it, you'd spend the first 10 minutes of every session re-explaining context that should have been written down.

### Feature Specs as a Wiki Artifact Type

Feature specs get their own location in the vault structure. Add a `specs/` folder to each project:

```
wiki/projects/{project-slug}/
├── overview.md
├── design/
├── proposals/
├── strategy/
├── research/
├── meetings/
├── decisions/          # ADRs live here
├── specs/              # Feature specs live here
│   ├── order-ingestion-service.md
│   ├── schema-validation-pipeline.md
│   └── admin-dashboard-v2.md
└── delivery/
```

### Feature Spec Template

```markdown
---
title: "Order Ingestion Service"
type: spec
project: order-platform
status: in-progress     # draft | ready | in-progress | review | done
created: 2026-04-15
updated: 2026-04-24
author: {team-member}   # Specs are human-authored, Claude-refined
owner: {team-member}
tags: [kafka, event-sourcing, ingestion]
pm_issue: ORD-88
---

## Objective

One paragraph: what this feature does and why it matters.
Link to the project overview for broader context:
see [[wiki/projects/order-platform/overview]].

## Background & Decisions

Reference the ADRs and design pages that inform this spec.
These are not parent documents — they're context.

- [[decisions/adr-003-kafka-over-rabbitmq]] — why Kafka
- [[decisions/adr-007-avro-schema-registry]] — serialization choice
- [[design/data-pipeline-architecture]] — where this service fits
  in the overall system

## Requirements

### Functional
- Accept order events on the `orders.raw` Kafka topic
- Validate against the Order schema (v3) in Schema Registry
- Transform to canonical order model
- Write to `orders.validated` topic and PostgreSQL sink
- Dead-letter invalid events to `orders.dlq` with error metadata

### Non-Functional
- P99 latency < 200ms end-to-end
- Handle 5,000 events/sec sustained throughput
- Exactly-once delivery semantics

## Technical Approach

Describe the implementation approach at enough detail for Claude
Code to execute without ambiguity. Include:
- Service structure and key modules
- Key libraries and frameworks
- Data models / schemas
- API contracts (if applicable)
- Error handling strategy
- Testing approach

## Implementation Plan

Break the work into ordered steps. Claude Code uses this to know
what to work on next.

- [x] Scaffold service with project template
- [x] Implement Kafka consumer with consumer group config
- [x] Add Schema Registry integration and validation
- [ ] Implement transformation to canonical model  ← CURRENT
- [ ] Add PostgreSQL sink with idempotent writes
- [ ] Add dead-letter queue handling
- [ ] Write integration tests with embedded Kafka
- [ ] Load test at target throughput
- [ ] Document operational runbook

## Current State

Updated each session. This is what Claude reads to understand
where things stand.

**Last session (2026-04-23):** Completed Schema Registry
integration. Validation is working for happy path. Edge case:
nested array schemas throw a deserialization error that needs
investigation. See `src/validation/schema_validator.py:L142`.

**Open questions:**
- Should invalid events be retried before DLQ routing?
  → Raised in [[meetings/2026-04-22-standup]], pending answer
- Need to confirm PostgreSQL connection pooling config with
  the platform team

## Acceptance Criteria

- [ ] All functional requirements pass integration tests
- [ ] Load test confirms throughput target
- [ ] Runbook documented in wiki/projects/order-platform/delivery/
- [ ] ADR created if any significant decisions were made during build
```

### The Relationship Between ADRs and Feature Specs

ADRs and feature specs are **peers, not parent-child.** They serve different purposes and have different lifecycles:

```
                    ┌─────────────────────┐
                    │   Project Overview   │
                    │   (overview.md)      │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌──────────┐    ┌──────────┐    ┌──────────────┐
       │   ADRs   │    │  Design  │    │   Feature    │
       │          │◄──►│  Pages   │◄──►│   Specs      │
       │ decisions│    │  design/ │    │   specs/     │
       └──────────┘    └──────────┘    └──────────────┘
              ▲                                │
              │                                │
              └──── new ADR if significant ─────┘
                    decision made during build
```

**ADRs (Architecture Decision Records):**
- Capture *why* a decision was made
- Are immutable once accepted (superseded, never edited)
- Have a long shelf life — remain relevant across project phases
- May predate any feature spec (decisions made during discovery/design)
- May have no associated spec (infrastructure decisions, tool selections)
- A single ADR can inform multiple specs

**Feature Specs:**
- Capture *what* to build and *how*
- Are living documents — updated as implementation progresses
- Have a bounded lifecycle (draft → done → archived)
- Reference ADRs as context, not as parents
- May reference zero ADRs (simple feature, no significant decisions)
- May trigger new ADRs (significant decision discovered during build)

**Design Pages:**
- Capture the *system architecture* and *how components relate*
- Live between ADRs and specs conceptually
- Updated less frequently than specs, more than ADRs
- Both ADRs and specs reference design pages

**Practical examples of the relationship:**

| Scenario | ADR | Spec | Relationship |
|---|---|---|---|
| Team decides to use Kafka during design phase | ADR-003: Kafka over RabbitMQ | Order Ingestion spec references ADR-003 as background | ADR predates and informs spec |
| During build, team discovers they need a circuit breaker pattern | ADR-011: Circuit breaker for downstream calls | Order Ingestion spec references ADR-011 in technical approach | Spec triggers creation of ADR |
| Simple CRUD endpoint with no significant decisions | None | User Profile API spec | Spec exists without any ADR |
| Team decides on a deployment strategy | ADR-005: Blue-green deployment | Referenced by many specs across the project | One ADR informs many specs |
| Feature is purely UI with no architecture impact | None | Admin Dashboard v2 spec | No ADR needed |

**The rule:** A spec should reference any ADR that provides context for *why* things are built the way they are. But specs don't *derive from* ADRs — they derive from requirements, user needs, and project goals. ADRs constrain and inform the technical approach section of a spec.

### How Claude Code Uses Specs During Build Sessions

**Starting a session:**
```
You: "Pick up where we left off on the order ingestion service"

Claude reads:
  1. CLAUDE.md → vault conventions
  2. wiki/projects/order-platform/overview.md → project context
  3. wiki/projects/order-platform/specs/order-ingestion-service.md
     → Current State tells Claude exactly where things stand
     → Implementation Plan shows the next unchecked item
     → Open Questions flags blockers
  4. Referenced ADRs and design pages → technical constraints
  5. The actual code repo → reconcile spec with code
```

**Ending a session:**
```
Claude (or you) updates the spec:
  - Check off completed implementation steps
  - Update "Current State" with what was accomplished
  - Note any new open questions or blockers
  - If a significant decision was made, create a new ADR
  - Update the pm_issue in the PM tool via the sync skill
```

**This is the "save game" mechanic.** The spec's Current State section is a session journal. It should be updated at the end of every Claude Code session so the next session (whether it's you, a teammate, or a future Claude instance) can pick up without loss.

### Adding Spec Operations to CLAUDE.md

Add these operations to the CLAUDE.md schema:

```markdown
## Spec-Driven Development

### Starting a build session
1. Read the project overview.md to orient
2. Find the active spec (status: in-progress) in specs/
3. Read the spec's Current State section
4. Read referenced ADRs and design pages
5. Navigate to the code repo and verify state matches spec
6. Resume from the next unchecked implementation step

### During a build session
1. Follow the spec's technical approach and implementation plan
2. If you encounter a significant decision point (technology
   choice, architecture trade-off, pattern selection):
   - STOP and discuss with the team member
   - If a decision is made, create a new ADR in decisions/
   - Update the spec to reference the new ADR
3. Check off implementation steps as they're completed
4. Note any deviations from the spec in Current State

### Ending a build session
1. Update the spec's Current State with:
   - What was completed
   - What remains
   - Any blockers or open questions
   - Code locations for key changes (file:line references)
2. Check off completed implementation plan items
3. Update the spec's `updated:` date in frontmatter
4. If all steps are complete, move status to `review`
5. Update the PM tool issue via the sync skill

### Creating a new spec
1. Use the feature spec template
2. Link to relevant ADRs and design pages (if any exist)
3. Break implementation into small, ordered steps
4. Set status to `draft` until the team reviews
5. Create a corresponding issue in the PM tool
```

### The Code Repo and the Wiki: Two Separate Concerns

An important architectural note: **the code repo and the wiki vault are separate.** The wiki describes *what* to build and *why*; the code repo contains *the code itself*. They reference each other but don't live in the same Git repository or folder.

```
┌─────────────────────┐          ┌─────────────────────┐
│   Obsidian Vault     │          │    Code Repository   │
│   (shared drive      │          │    (Git)             │
│    or Git)           │          │                      │
│                      │          │  src/                │
│  wiki/specs/         │ ────────►│  tests/              │
│    references code   │          │  docs/               │
│    locations         │◄──────── │    may link back     │
│                      │          │    to wiki specs     │
│  CLAUDE.md tells     │          │  CLAUDE.md tells     │
│  Claude how to       │          │  Claude how to       │
│  maintain the wiki   │          │  write code          │
└─────────────────────┘          └─────────────────────┘
```

Claude Code works across both simultaneously — reading specs from the vault and writing code in the repo. The spec's file:line references in Current State help Claude locate exactly where it left off in the codebase.

If the code repo also has its own CLAUDE.md (which it should for coding conventions, linting rules, test patterns, etc.), that's separate from the wiki's CLAUDE.md. Claude reads both when working on a build session.

---

## Layer 4: Structured Ingestion

Sources don't just become "wiki pages." They become *structured* wiki pages — typed records that downstream operations can mechanically consume. The kit's ingest pipeline routes on two axes: source-type and content-type.

### Two-axis routing

**Source-type ingesters** (shared across variants) clean the input:

- [[ingest-website]] — URL → defuddle (local) → markdown; pure.md fallback for JS-rendered or bot-blocked pages
- [[ingest-document]] — PDF / DOCX / PPTX / XLSX / image → Docling (local) → markdown; pymupdf4llm fast-path for plain-text PDFs

**Content-type ingesters** (variant-specific) apply schema. For the work variant:

- [[ingest-meeting]] — speaker-labeled transcripts → meeting synthesis with decisions, action items, key discussion, open questions; frontmatter capturing project, date, participants, related ADRs

A meeting transcript URL routes through `ingest-website` to clean the page, then `ingest-meeting` to extract decisions and action items into a meeting page. A meeting transcript PDF routes through `ingest-document` for cleanup, then the same `ingest-meeting` for structuring. The cleanup is reused across content types; the structuring is variant-specific.

### Why structured ingestion matters for the operate loop

The work variant's operations — sprint planning, weekly digest, cross-project synthesis — assume meeting pages have consistent shape: dated frontmatter with `project:` field, a `## Decisions` section, an `## Action Items` section, links to related ADRs and specs. Without structured ingestion, every operation has to re-extract these fields from prose, which is expensive and fragile. With structured ingestion, operations become queries: *which open action items are assigned to Sarah?*; *which decisions affect the order-platform project this sprint?*

Spec-driven development (Layer 3B) is itself enabled by structured ingestion. Specs have consistent frontmatter, a Current State section, an Implementation Plan with checkboxes — that schema is what lets `spec-session-start` find the right spec, read its state, and resume work.

### Adding new content-type ingesters

When the team encounters a recurring source type the existing ingesters don't handle well — RFP responses, customer interviews, vendor proposals, security reviews — the path is:

1. Decide the schema for the target wiki page type.
2. Create or repurpose a template in `_templates/`.
3. Author `skills/work/ingest-{type}/SKILL.md` describing extraction, schema mapping, cross-links, and side-effects.
4. Register the trigger signal in the orchestrator's source-type-detection table.

Same pattern as the family variant's content-type ingesters — different domain content.

---

## Layer 5: The Team OS — Operations

This is the layer that turns the wiki from filing cabinet into operating system for the team.

### What an operation is

An **operation** is a skill that:

1. Reads a defined set of structured pages from the wiki.
2. Applies a domain-specific algorithm.
3. Writes a new structured page back into the wiki as the result.

The result page is itself queryable, linkable, and consumable by subsequent operations. A sprint plan is a wiki page; a weekly digest reads sprint plans and meeting decisions to synthesize what shipped; a quarterly review reads weekly digests.

Operations are explicitly different from ingest in two ways:

- Ingest: external source → wiki. Operation: wiki → wiki.
- Ingest: triggered by a captured artifact. Operation: triggered by a request (user-driven) or a schedule (e.g., every Monday at sprint kickoff).

### The five operation classes

| Class | What it does | Team examples |
|---|---|---|
| **Planning** | Compose a forward-looking artifact from current wiki state | Sprint planning; quarterly roadmap update; capacity planning |
| **Reminding** | Surface time-sensitive items from dated metadata | Specs in-progress for >2 weeks without updates; ADRs awaiting acceptance; tasks not synced to PM |
| **Synthesizing** | Compress a wide span of wiki content into a digest | Weekly digest of what changed across projects; cross-project synthesis on a domain; quarterly review |
| **Recommending** | Apply ranking/filtering to a library given a context | Tool evaluation summary for a current need; playbook suggestion for a project phase; similar past projects |
| **Crisis-responding** | Rapid composition of relevant info under time pressure | Incident retrospective prep; outage runbook assembly; onboarding pack for a new team member |

The same wiki content participates in multiple operation classes. ADR pages feed sprint planning *and* the ADR review queue *and* cross-project synthesis. Spec pages feed the staleness check *and* sprint planning *and* the weekly digest.

### Walkthrough: sprint planning

The canonical work-OS operation. An engineering manager on Monday morning: *"Plan the next 2-week sprint for the order-platform project."*

The `sprint-planning` skill runs roughly this:

1. **Read the inputs.**
   - All specs in `wiki/projects/order-platform/specs/` filtered to `status: ready` or `status: in-progress`.
   - `wiki/projects/order-platform/tasks.md` — open and in-progress tasks with priorities.
   - The most recent sprint plan in `wiki/projects/order-platform/delivery/` — what was committed last sprint, what shipped, what carried over.
   - Capacity from PM sync skill, or `wiki/projects/order-platform/team.md` if maintained.
   - Recent meeting decisions from `wiki/projects/order-platform/meetings/` that introduce new spec needs.

2. **Apply the algorithm.**
   - Honor spec dependencies (don't schedule a downstream spec before its dependency).
   - Match story points to capacity, with buffer for bugs and meetings.
   - Carry over in-progress items from last sprint unless flagged for reset.
   - Prefer specs with active stakeholder pressure (PM-priority tags or recent escalation).
   - Surface ADRs that should be resolved before related specs can finalize.

3. **Compose the output.** Write `wiki/projects/order-platform/delivery/sprint-2026-04-26.md`:

   ```markdown
   ---
   type: sprint-plan
   project: order-platform
   sprint: 2026-04-26
   created: 2026-04-25
   modified: 2026-04-25
   tags: [sprint-plan, order-platform]
   status: active
   ---

   ## Synopsis
   Sprint plan for 2026-04-26 → 2026-05-09. 23 points committed,
   5 stretch. Two specs continuing from last sprint, three new
   specs starting. One blocking ADR to resolve in week 1.

   ## Sprint Goal

   Ship the canonical-model transformation and the Schema Registry
   integration so the order-ingestion service can move from
   draft → review by sprint end.

   ## Committed (23 pts)

   - **[8 pt]** [[specs/order-ingestion-service]] — implement
     canonical-model transformation. Continuing from sprint
     2026-04-12. Eugene, in-progress.
   - **[5 pt]** [[specs/schema-registry-integration]] — replace
     local schema validation with Schema Registry. New this sprint.
     Sarah, ready.
   - **[5 pt]** [[specs/dlq-monitoring]] — observability for
     dead-letter queue. New this sprint. Jake, ready.
   - **[3 pt]** Resolve [[decisions/adr-007-schema-evolution]] —
     blocks both schema-registry and canonical-model specs.
     Whole team, week 1.
   - **[2 pt]** Carry over: integration tests for DLQ handling.
     From [[specs/order-ingestion-service]] step 7.

   ## Stretch (5 pts)

   - **[5 pt]** [[specs/error-budget-dashboard]] — Q3 commitment;
     promote if room.

   ## Blockers and dependencies

   - [[decisions/adr-007-schema-evolution]] must be `accepted`
     before schema-registry-integration can move to `review`.
   - [[wiki/tools/kafka-schema-registry]] page is out of date;
     update during the schema-registry spec.

   ## Capacity

   Eugene: 18 / 20 pts (with 10% buffer for the
     order-ingestion crossover work).
   Sarah: 7 / 10 pts.
   Jake: 5 / 8 pts.
   Total: 23 / 38 pts committed; 5 / 38 stretch; ~26% buffer.

   ## Notes for next sprint's planner

   - DLQ monitoring spec is small but had unclear success criteria;
     worth a 30-minute scoping refinement before next sprint.
   - Schema-registry spec depends on ADR-007 — track that ADR's
     acceptance to assess any spec-rescope risk.
   ```

4. **Side-effects.**
   - Update each spec's frontmatter to set `sprint: 2026-04-26`.
   - Push committed items to the PM tool via [[sync-pm-linear]] (or jira / plane).
   - Update `wiki/projects/order-platform/delivery/index.md` with the new sprint entry.
   - Append to `log/changelog.md`.

5. **Interactive review.** The agent presents the plan to the manager. Adjustments propagate — if the manager moves the dlq-monitoring spec to stretch, the capacity recompute and the PM-tool push both reflect the change.

### What makes this different from "Claude can write a sprint plan"

Anyone with an LLM can ask for a sprint plan. What makes the Team-OS version distinct:

- **The spec library is the source.** No invented scope. Every sprint item is a real wikilink to a spec the team has already authored.
- **Constraints come from the wiki.** Capacity isn't re-explained each sprint — it lives in `team.md` or the PM sync, and updates once when it changes. ADR-driven blockers are surfaced from the actual ADR pages.
- **Outputs feed back in.** The sprint plan page is the input to the next sprint's planner ("what carried over"), the weekly digest ("what shipped this week"), and the quarterly review ("what did we commit, what landed").
- **The operation is reusable.** A second engineering team using the same kit can drop their own specs into the same vault structure and run the same sprint-planning operation; no re-implementation per team.

### Other operations worth authoring

These are the high-leverage ones for an engineering team. P2 in the kit's roadmap; not all need to ship at MVP.

| Operation | Inputs | Output | Cadence |
|---|---|---|---|
| **Weekly digest** | All projects' delivery pages, meeting decisions of the last 7 days, changelog | `wiki/log/digest-{week}.md` | Friday afternoon |
| **Spec staleness check** | All specs with `status: in-progress` and their `modified:` dates | `wiki/log/spec-staleness-{date}.md` | Run weekly during sprint |
| **ADR review queue** | All ADRs with `status: draft`; their context dependencies | `wiki/log/adr-queue.md` | Run weekly |
| **Cross-project synthesis** | All wiki pages tagged with a topic (e.g., `#kafka`, `#rag`); the topic's domain page | Refresh of `wiki/domains/{topic}.md` with new learnings | Run on demand or after major project milestones |
| **Onboarding pack** | A new team member's role; relevant playbooks, domains, current projects | `wiki/people/{name}/onboarding.md` with a curated reading order | Run on demand at team join |
| **Incident retrospective prep** | An incident; relevant ADRs, design pages, playbooks, on-call notes | `wiki/projects/{slug}/incidents/{date}.md` (draft) | Run on demand after an incident |

Spec-driven development (Layer 3B) is itself a constellation of operations: `spec-session-start` is a planning operation; `spec-session-end` is a synthesizing operation that captures what changed in a build session. The build-session pattern is the work variant's most-used operation.

### Operations as the wiki's heartbeat

A team wiki without operations dies. The capture loop runs at first (someone enthusiastic about the new system files everything for two weeks), the operation loop never starts, the team stops getting visible value from the wiki, capture tapers off, and the wiki becomes a graveyard of half-filled records.

The cure is the same as for the family variant: ship one operation as soon as the wiki is populated enough to support it. Sprint planning is the gateway for engineering teams because it has the highest weekly visibility — every sprint starts with one, every team feels the pain when planning is bad. Once sprint planning works, the weekly digest follows naturally because the patterns are the same.

---

## Layer 6: Research Integration

The team needs external research capabilities — academic papers, market intelligence, technology landscape analysis — flowing into the wiki. Three tools serve different research profiles.

### 4A: Perplexity (Real-Time Research & Current Intelligence)

**What it provides:** AI-powered web search with inline citations, source links, and structured synthesis. Particularly strong for current events, technology comparisons, competitive intelligence, and fast factual lookups.

**Why it fits:**
- Citation-backed answers with source links — critical for engineering credibility
- Sonar API is OpenAI-compatible, easy to integrate into Claude Skills or automation
- Deep Research mode produces multi-source synthesis reports
- No ads, so research results are unbiased
- $20/mo Pro per user, or API at ~$1/M tokens for Sonar

**Integration pattern:**
- Build a **Claude Skill** (markdown instruction file) that calls the Perplexity API via a wrapper script
- Skill accepts a research question → calls Perplexity Sonar Pro → writes output to `research/{date}-{slug}.md` with citation metadata
- From Cowork: "Research the current state of vector database benchmarks for RAG pipelines" → triggers the skill → deposits a cited research brief in the vault
- Perplexity Spaces can also be used for ongoing topic monitoring (create a Space per domain area)

**Example Claude Skill (`skills/research-perplexity/SKILL.md`):**
```markdown
# Perplexity Research Skill

When asked to research a topic:
1. Formulate 2-3 targeted search queries
2. Call the Perplexity Sonar Pro API for each
3. Synthesize results into a research brief with:
   - Executive summary (3-5 sentences)
   - Key findings with inline citations
   - Source quality assessment
   - Implications for our work
4. Save to research/{YYYY-MM-DD}-{slug}.md
5. Create/update relevant wiki/domains/ pages
6. Link to any active project wiki pages
```

### 4B: Gemini Deep Research (Long-Form Strategic & Academic Research)

**What it provides:** Autonomous research agent that consults hundreds of sources and produces comprehensive, cited reports with native charts and infographics. Available via the Gemini API (Interactions API).

**Why it fits:**
- Deep Research Max (built on Gemini 3.1 Pro) is designed for exhaustive, long-form synthesis
- Native Google Workspace integration — results export to Google Docs, can pull from team Drive
- Supports MCP, so it can access internal data sources alongside web research
- Interactions API allows programmatic triggering of research tasks
- Produces native charts and infographics — presentation-ready
- Can run asynchronously (submit overnight, report by morning)

**Integration pattern:**
- Use Gemini Deep Research via the **Interactions API** for heavy research tasks
- Trigger from a Claude Skill or directly from the Gemini app
- Export markdown output into the `research/` folder
- Best for: technology landscape analyses, architecture pattern surveys, academic literature reviews, due diligence reports

### 4C: Semantic Scholar (Academic & Scientific Literature)

**What it provides:** Semantic Scholar is a free, AI-powered academic search engine developed by the Allen Institute for AI (AI2). It provides structured access to scientific literature through a comprehensive REST API covering papers, authors, citations, venues, and vector embeddings.

**Scale and coverage:**
- **225M+ papers**, 100M+ authors, 650M+ authorship edges, 2.8B+ citation edges
- Covers **all fields of science** with particular depth in the areas listed below
- Completely free, no subscription required, non-profit mission

**Fields of Study covered by Semantic Scholar:**

| Category | Example Disciplines |
|---|---|
| **Computer Science** | AI/ML, NLP, computer vision, distributed systems, software engineering, HCI, cybersecurity, databases, programming languages |
| **Engineering** | Electrical, mechanical, civil, chemical, systems engineering, robotics, control systems, signal processing |
| **Mathematics** | Statistics, applied math, optimization, computational mathematics, discrete math |
| **Physics** | Condensed matter, quantum computing, optics, materials science, astrophysics |
| **Biology & Medicine** | Genomics, neuroscience, pharmacology, epidemiology, clinical research, bioinformatics |
| **Chemistry** | Organic, inorganic, computational chemistry, materials chemistry, biochemistry |
| **Environmental Science** | Climate science, ecology, sustainability, geoscience, atmospheric science |
| **Economics & Business** | Econometrics, operations research, management science, finance |
| **Social Sciences** | Psychology, sociology, political science, linguistics, education |
| **Humanities** | Philosophy, history, law (growing coverage, less exhaustive than sciences) |

**Key API capabilities:**
- **Paper Search:** Query by keywords, return structured metadata (title, abstract, authors, venue, year, citation count, fields of study, open access PDF links)
- **Citation Graph:** Traverse citations and references for any paper — both inbound (who cited this) and outbound (what this paper cites). Citations are classified by type (background, methods, results) and influence level.
- **Author Profiles:** Structured data on researchers including publication history, h-index, affiliation, and co-author networks
- **TLDR Summaries:** AI-generated single-sentence summaries for papers, enabling rapid screening during literature review
- **SPECTER2 Embeddings:** Vector embeddings for papers, useful for semantic similarity search and clustering within your own systems
- **Recommendations API:** Given a paper (or set of papers), returns related recent publications — useful for staying current in a domain
- **Bulk Datasets:** Monthly snapshots of the entire knowledge graph for offline analysis
- **Rate limits:** 100 requests per 5 minutes unauthenticated; free API key available for higher limits (no cost)

**Why it matters for an architecture and engineering team:**
- Technology evaluation research: find the academic foundations behind tools and patterns you're evaluating
- Architecture decision support: ground design decisions in published research (e.g., event sourcing trade-offs, consensus algorithm comparisons)
- Staying current: the Recommendations API surfaces new papers related to your areas of interest
- Citation graphs reveal influence networks — which papers and researchers are foundational vs. derivative

**Integration pattern:**
- Build a **Claude Skill** that queries the Semantic Scholar API
- Accepts a research topic → searches for relevant papers → retrieves abstracts, citation counts, TLDRs, and PDF links
- Writes a structured literature review into `research/{date}-{slug}.md`
- Cross-references with existing wiki domain pages
- Optionally downloads open-access PDFs into `raw/research/papers/` for deeper ingestion

**Example Claude Skill (`skills/research-semantic-scholar/SKILL.md`):**
```markdown
# Semantic Scholar Research Skill

When asked to find academic sources on a topic:
1. Query the Semantic Scholar API /paper/search endpoint
   - Use fieldsOfStudy filter when appropriate
   - Request fields: title, abstract, tldr, citationCount,
     influentialCitationCount, year, authors, openAccessPdf,
     fieldsOfStudy, externalIds
2. Sort by relevance and citation count
3. For top 10-15 results, retrieve citation context:
   - How many highly influential citations?
   - What fields cite this work?
4. Compile into a literature review with:
   - Summary of the research landscape
   - Key papers table (title, year, citations, TLDR, PDF link)
   - Identified research clusters/themes
   - Gaps or contradictions in the literature
   - Recommendations for further reading
5. Save to research/{YYYY-MM-DD}-{slug}.md
6. Update relevant wiki/domains/ and wiki/tools/ pages
7. Download open-access PDFs to raw/research/papers/
```

### When to Use Which Research Tool

| Research Need | Tool | Rationale |
|---|---|---|
| Quick factual lookup, current events | Perplexity Sonar | Fast, cheap, well-cited web search |
| Multi-source synthesis, market research | Perplexity Deep Research | Good depth, reasonable latency |
| Exhaustive strategic/landscape review | Gemini Deep Research Max | Hundreds of sources, async, native visuals |
| Academic literature review | Semantic Scholar + Claude | Structured metadata, citation graphs, free |
| Specific paper lookup by DOI/title | Semantic Scholar API | Direct structured access |
| Internal knowledge + external context | Claude web search + wiki | Already in the workflow |

### Complementary Academic APIs (Optional)

For teams that need even broader academic coverage, these can supplement Semantic Scholar:

- **OpenAlex** (openalex.org): Open catalog of 250M+ works, fully free, with institutional and funder metadata. Good for bibliometric analysis.
- **Crossref**: Authoritative DOI metadata for 150M+ records. Best for citation verification and linking.
- **PubMed E-utilities**: Essential if biomedical/clinical research is relevant.
- **arXiv API**: Preprints in physics, math, CS, and related fields. Often has the latest papers weeks before formal publication.

---

## Layer 7: Project Management Integration

The choice of PM tool depends heavily on what's already in use at the organization. Below are three options with integration architectures for each.

### Option A: Linear

**Best for:** Teams that want a modern, opinionated, AI-native PM tool with minimal configuration overhead. Particularly strong for software-focused teams and startups.

**Why Linear fits:**
- AI-native: Linear Agent auto-assigns, triages, and generates project updates using AI
- Triage Intelligence applies historical patterns to incoming work items
- Speed and UX: dramatically less overhead than traditional PM tools
- Built-in cycles (sprints), projects, milestones, and initiatives
- MCP support is actively in development (confirmed by Linear team); a well-maintained community MCP server already exists
- GitHub/GitLab integration for dev work
- Slack and Microsoft Teams integration
- $8/user/mo (Standard) or $16/user/mo (Business with automations and AI agent features)

**Integration architecture:**

```
┌─────────────┐     MCP Server      ┌──────────┐
│  Claude Code │◄───────────────────►│  Linear  │
│  / Cowork    │     (bidirectional) │  API     │
└──────┬──────┘                      └────┬─────┘
       │                                  │
       │  Claude Skill:                   │
       │  "sync-pm"                       │
       │                                  │
       ▼                                  ▼
┌──────────────────────────────────────────────┐
│              Obsidian Vault                    │
│  wiki/projects/{slug}/delivery/               │
│  - sprint-notes.md (auto-generated)           │
│  - status-update.md (pulled from Linear)      │
│  - blockers.md (synced issues)                │
│                                               │
│  Frontmatter: pm_issue: ORD-142               │
│  (bidirectional linking)                      │
└──────────────────────────────────────────────┘
```

**Trade-offs:**
- Optimized for software development workflows; less flexible for non-dev project types
- Opinionated — great if you align with its conventions, frustrating if you don't
- Smaller ecosystem than Jira (fewer third-party integrations)

---

### Option B: Jira (Atlassian)

**Best for:** Organizations that already use the Atlassian ecosystem (Confluence, Bitbucket, Jira Service Management), enterprise teams requiring deep customization, compliance, and extensive reporting.

**Why Jira fits:**
- Ubiquitous in enterprise: already deployed in many organizations, reducing adoption friction
- Atlassian Intelligence (Rovo) provides AI-powered features: natural language to JQL, AI summaries, work breakdown suggestions, triage automation
- Agents in Jira (open beta since Feb 2026): teams can assign tasks to Rovo agents and third-party agents, @mention agents in comments, and embed agents in workflows
- **Rovo MCP Server is now generally available** — provides MCP-compatible AI clients (including Claude) with a single authenticated connection into Jira and Confluence
- Massive integration ecosystem: 3,000+ marketplace apps
- Deep customization: workflows, custom fields, schemes, screens — can model nearly any process
- Confluence integration for documentation alongside project tracking
- Jira Service Management for IT/support workflows if needed
- Pricing: Free (10 users), Standard ($8.15/user/mo), Premium ($16/user/mo)

**Integration architecture:**

```
┌─────────────┐   Rovo MCP Server    ┌──────────┐
│  Claude Code │◄────────────────────►│  Jira    │
│  / Cowork    │   (GA, OAuth 2.1)   │  Cloud   │
└──────┬──────┘                      └────┬─────┘
       │                                  │
       │  Also connects to:               │
       │  Confluence (via same MCP)       │
       │                                  │
       │  Claude Skill:                   │
       │  "sync-pm"                       │
       │                                  │
       ▼                                  ▼
┌──────────────────────────────────────────────┐
│              Obsidian Vault                    │
│  wiki/projects/{slug}/delivery/               │
│  - sprint-notes.md (auto-generated)           │
│  - status-update.md (pulled from Jira)        │
│  - blockers.md (synced issues)                │
│                                               │
│  Frontmatter: pm_issue: PROJ-142              │
│  (bidirectional linking)                      │
└──────────────────────────────────────────────┘
```

**Additional Jira advantage — Confluence bridge:** If the organization uses Confluence for documentation, the Rovo MCP Server provides Claude with access to both Jira issues and Confluence pages through a single connection. This means Claude can pull from Confluence content when building the wiki, creating a bridge between the Atlassian ecosystem and the LLM Wiki vault.

**Trade-offs:**
- Significantly more configuration overhead than Linear — requires deliberate setup to avoid complexity sprawl
- AI features (Atlassian Intelligence, Rovo) require Cloud plans; Data Center support ends March 2029
- Heavier UX — more powerful but slower day-to-day experience
- Per-user pricing with AI credits system can get expensive at scale

---

### Option C: Plane (Open Source, Self-Hosted)

**Best for:** Teams that need full data control, operate in air-gapped or highly regulated environments, or want to avoid vendor lock-in and per-user SaaS fees.

**Why Plane fits:**
- **Open source** (AGPL-3.0) with 48,000+ GitHub stars and active development
- Modern UX inspired by Linear — clean, fast, keyboard-first
- Self-hostable via Docker Compose, Kubernetes, or Podman (deploys in under 10 minutes)
- **Official MCP server** (plane-mcp-server) — Claude Code and Cowork can connect directly
- REST API with OAuth 2.0, webhooks, and typed SDKs in Node.js and Python
- Native AI agent support with @mention and Agent Run lifecycle tracking
- Cycles (sprints), modules, pages (built-in wiki), intake (triage), and analytics
- Slack integration with @Plane bot for creating work items from channel conversations
- GitHub and GitLab integration for dev workflows
- SOC 2, ISO 27001, GDPR, CCPA compliance
- **Community Edition is completely free** with unlimited users, projects, and core features
- Commercial Edition adds governance: workflows, approvals, SSO/SAML/LDAP, audit trails, epics

**Integration architecture:**

```
┌─────────────┐  plane-mcp-server    ┌──────────┐
│  Claude Code │◄────────────────────►│  Plane   │
│  / Cowork    │   (official MCP)    │  (self-  │
└──────┬──────┘                      │  hosted) │
       │                              └────┬─────┘
       │  Claude Skill:                    │
       │  "sync-pm"                        │
       │                                   │
       ▼                                   ▼
┌──────────────────────────────────────────────┐
│              Obsidian Vault                    │
│  wiki/projects/{slug}/delivery/               │
│  - sprint-notes.md (auto-generated)           │
│  - status-update.md (pulled from Plane)       │
│  - blockers.md (synced issues)                │
│                                               │
│  Frontmatter: pm_issue: PROJ-142              │
│  (bidirectional linking)                      │
└──────────────────────────────────────────────┘
```

**Cost comparison:**

| | Plane CE | Plane Commercial | Linear Standard | Jira Standard |
|---|---|---|---|---|
| Per-user/mo | **Free** | Contact sales | $8 | $8.15 |
| Self-host | Yes | Yes | No | No (DC EOL 2029) |
| AI agents | Yes (native) | Yes | Yes (Beta) | Yes (Rovo, Beta) |
| MCP server | Official | Official | Community | Official (Rovo) |
| Max users (free) | Unlimited | — | 250 (free plan) | 10 |

**Trade-offs:**
- Smaller ecosystem than Jira or Linear (fewer third-party integrations)
- Self-hosting means you manage infrastructure (though the footprint is small: 2 CPU, 4GB RAM)
- Commercial features (SSO, audit trails, epics) require the paid edition
- Younger product — some enterprise features are still maturing

---

### Shared PM Sync Skill (Works with Any Option)

Regardless of which PM tool you choose, the Claude Skill for syncing follows the same pattern:

```markdown
# PM Sync Skill

## Pull: PM Tool → Wiki
When asked for project status or sprint summary:
1. Query the PM tool via MCP for project issues, cycle progress, blockers
2. Generate a status update in wiki/projects/{slug}/delivery/
3. Update the project overview.md with current velocity/blockers
4. Flag any issues that need decisions → create decision records

## Push: Wiki → PM Tool
When a wiki page creates a new task or action item:
1. Parse action items from meeting syntheses or decision records
2. Create issues in the PM tool with appropriate labels, assignees, priority
3. Add the PM issue key to the wiki page frontmatter
4. Post a summary to the project's Slack channel

## Scheduled Sync
Run weekly (or per-sprint):
1. Pull all active cycle/sprint data
2. Generate wiki/projects/{slug}/delivery/sprint-{N}-summary.md
3. Cross-reference with decision records and design pages
4. Flag stale issues (no updates in 7+ days)
```

---

## Layer 8: User Access Patterns

### For Technical Team Members: Claude Code

- Direct terminal access to the vault
- Run ingest, query, and lint operations via CLAUDE.md commands
- Build and maintain Claude Skills
- Git-based workflow for wiki changes (if using Git approach)
- Full control over the research and sync pipelines

### For Non-Technical Team Members: Claude Cowork

Claude Cowork is the critical piece that makes this accessible to everyone. It brings Claude Code's agentic architecture to the desktop app without any terminal interaction.

**How it works for knowledge management:**
- Team member opens Cowork, points it at the local vault folder (synced via shared drive)
- Natural language: "Ingest the meeting notes from today's design review and update the project wiki"
- Cowork reads the raw file, follows the CLAUDE.md schema, creates/updates wiki pages
- "What do we know about event-driven architecture patterns across our projects?" → Cowork queries the wiki and synthesizes
- "Research how other teams handle schema evolution in event-sourced systems" → triggers the Perplexity or Semantic Scholar skill
- Scheduled tasks: "Every Monday at 8am, pull project status for all active projects and update the wiki"

**Cowork Projects feature** (launched March 2026) is particularly relevant:
- Create a Cowork Project per engagement or workstream
- Each project has its own files, instructions, and scoped memory
- Memory persists across sessions — Cowork learns each team member's patterns
- Project context doesn't leak across boundaries

**Key Cowork capabilities for this system:**
- File access: reads and writes directly to the Obsidian vault via the synced local folder
- MCP connectors: connects to Linear/Jira/Plane, Google Drive, Slack
- Scheduled tasks: automated wiki maintenance, status syncs
- Sub-agents: complex tasks like "research + synthesize + create PM issues" can run in parallel
- Plugin marketplace: install pre-built plugins or build custom ones for team workflows

### For Quick Queries: Claude Chat with Web Search

For team members who just need a quick answer from the knowledge base, regular Claude Chat (with vault context provided via memory or file upload) works for simple Q&A. Web search handles real-time verification.

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

1. **Set up the vault structure** — Create the directory tree, templates, CLAUDE.md schema
2. **Configure shared drive sync** — Choose cloud drive provider, create the synced vault folder, install Obsidian on all machines
3. **Seed with existing knowledge** — Ingest key documents from current projects into raw/, run initial wiki compilation
4. **Install Cowork** — Get all team members set up with Claude Desktop + Cowork pointing at the vault

### Phase 2: Research Layer (Week 3-4)

5. **Set up Perplexity** — API key, build the research Claude Skill
6. **Set up Semantic Scholar skill** — Build the academic research skill for literature reviews and technology evaluations
7. **Set up Gemini Deep Research** — API access via Interactions API, build the deep research skill for exhaustive strategic analysis
8. **Test the ingest → wiki → research cycle** on a real project question

### Phase 3: Project Management Sync (Week 5-6)

9. **Configure PM tool** — Set up Linear, Jira, or Plane based on organizational context
10. **Install/configure MCP server** for the chosen PM tool
11. **Build the sync skill** — bidirectional PM ↔ wiki synchronization
12. **Set up scheduled Cowork tasks** — weekly status pulls, sprint summaries

### Phase 4: Operational Maturity (Ongoing)

13. **Run weekly lint passes** — orphan pages, stale content, missing metadata
14. **Playbook extraction** — after each project milestone, extract reusable methodology into playbooks
15. **Onboarding new projects** — standardize the project kickoff → vault setup → PM tool setup flow
16. **Measure** — track wiki size, query patterns, research usage, time-to-insight

---

## Cost Estimate (Per Month, Team of ~5)

| Component | Cost | Notes |
|---|---|---|
| Obsidian | Free | Plugins are free. Sync is $5/user/mo if used. |
| Cloud Drive | Free-$12/user | Most orgs already have OneDrive or Google Drive. |
| Claude Pro/Max | $20-100/user | Cowork included. Max recommended for heavy use. |
| PM Tool | $0-16/user | Plane CE free; Linear/Jira Standard ~$8/user. |
| Perplexity Pro | $20/user | Or API-only at ~$1/M tokens. |
| Gemini Deep Research | Pay-per-use | Via Gemini API. Costs vary by research depth. |
| Semantic Scholar | Free | No cost. Free API key for higher rate limits. |
| Git hosting (if used) | Free-$4/user | GitHub/GitLab free tier usually sufficient. |
| **Total (5 users, mid-tier)** | **~$250-500/mo** | Scales linearly with team size. |

---

## Key Design Decisions & Rationale

**Why markdown over Notion/Confluence?**
The LLM Wiki pattern fundamentally depends on the LLM being able to read and write files directly. Markdown in a folder is the simplest, most LLM-friendly format. No API translation layer, no proprietary block format. Claude Code and Cowork read .md files natively. Git gives you version history for free. Obsidian gives you graph view, backlinks, and a beautiful reading experience on top.

**Why shared drive as default over Git?**
Adoption. Non-technical team members understand cloud drive sync intuitively — they already use it daily. Git requires learning commits, pulls, pushes, and conflict resolution, which creates friction that kills adoption. The shared drive approach gets the team using the wiki on day one. Switch to Git when you outgrow it (8+ people, need review gates, need audit trails).

**Why Office formats (.docx/.xlsx/.pptx) for Claude-generated deliverables?**
Claude Cowork and Claude's file creation tools work natively with Office formats. They cannot write directly to Google Docs, Sheets, or Slides format. If your team uses Google Workspace, the workflow is: Claude creates .docx → file syncs via Google Drive → team member opens in Google Docs (auto-converts for viewing/editing). This adds a small conversion step but is the most reliable path. The wiki itself (markdown files) has no format issues on any platform.

**Why three research tools instead of one?**
They serve different research profiles. Perplexity excels at fast, well-cited web research. Gemini Deep Research Max excels at exhaustive, long-form synthesis from hundreds of sources. Semantic Scholar provides structured academic metadata, citation graphs, and paper recommendations that the other two don't offer. For an architecture and engineering team, the combination means you can ground design decisions in both current industry practice (Perplexity) and published research (Semantic Scholar), and produce comprehensive landscape analyses when needed (Gemini). Start with Perplexity + Semantic Scholar; add Gemini when you need the heavy analysis.

**Why a separate outputs/ folder with companion pages?**
Obsidian's graph view, search, and backlinks only work on markdown. If you drop a .docx into a wiki folder, it becomes invisible to the knowledge graph — team members can't find it through normal navigation, and it can't participate in cross-linking. The companion page pattern solves this: the markdown page is the "index card" that Obsidian sees, while the binary file in `outputs/` is the polished deliverable. This also means Claude always has a markdown breadcrumb to find the file when it needs to read or update it in a future session. The separation of `outputs/` from `wiki/` also keeps the wiki clean — binary files don't clutter the markdown-native knowledge layer, and they can have different backup/sync/versioning policies if needed.

**Why spec-driven development?**
This isn't a methodology preference — it's a mechanical requirement. Claude Code has no memory between sessions. The spec is how you "save your game." Without a structured spec that records what's been decided, what's been built, what's next, and what's blocked, every new Claude Code session starts from scratch and you spend the first 10 minutes re-explaining context. The spec's Current State section is the session journal; the Implementation Plan is the task list. Together they give Claude everything it needs to resume work instantly.

**Why are ADRs and feature specs peers, not parent-child?**
ADRs capture *why* decisions were made. Specs capture *what* to build. These are different concerns with different lifecycles. An ADR can predate any spec (decisions made during discovery), inform multiple specs (a Kafka decision affects every service that uses it), or have no spec at all (a deployment strategy decision). A spec can reference zero ADRs (simple feature, no significant decisions) or trigger new ADRs (team discovers an architectural trade-off during build). Making specs "derive from" ADRs would create artificial coupling — you'd need an ADR before writing any spec, even for straightforward features. Instead, they cross-reference each other as peers in the knowledge graph. Design pages sit between them as the system-level context both reference.

**Why not a custom RAG system?**
At team scale (hundreds to low thousands of wiki pages), the LLM Wiki pattern — where Claude reads index.md and navigates via wikilinks — outperforms RAG. No embeddings pipeline, no vector database, no chunking tuning. The kit's `wiki-search` skill ships with a two-tier backend (ripgrep on day 1, SQLite FTS5 with BM25 ranking auto-enabled past ~1000 pages) so the lexical search layer scales to 50,000+ pages without infrastructure. Beyond that, swap in an external service (Typesense, Meilisearch). Embeddings stay out of scope — they solve a different problem (semantic mismatch like `pricing strategy` ↔ `go-to-market plan`) that authored vaults rarely hit.

**Why separate vaults per project when confidentiality matters?**
Separate Obsidian vaults with separate CLAUDE.md schemas and separate Cowork Projects enforce data isolation at the file system level. Claude cannot cross-reference content it cannot see. This is the simplest, most auditable way to maintain confidentiality boundaries.
