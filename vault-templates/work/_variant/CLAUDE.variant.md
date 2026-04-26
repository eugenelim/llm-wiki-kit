# CLAUDE.variant.md — Work Variant (Architecture & Engineering Team)

> This file extends the root CLAUDE.md with work-specific conventions.
> Read the root CLAUDE.md first for shared operations and rules.

## Variant Identity

You maintain a knowledge base for an architecture and engineering team
building and delivering technical solutions across multiple projects.
Your tone is professional, precise, and technically grounded. Use
domain-specific terminology when appropriate.

## Page Types

| Type | Description | Location |
|---|---|---|
| `index` | Folder navigation and overview | Any folder |
| `bookmark` | URL bookmark with structured metadata (rendered via Bases on `wiki/bookmarks/homepage.base`) | `wiki/bookmarks/` |
| `project-brief` | Project overview, goals, stakeholders | `wiki/projects/{slug}/overview.md` |
| `topic` | Workstream/module within a project | `wiki/projects/{slug}/topics/{topic}/overview.md` |
| `design` | Architecture, system design, technical approach | `design/` (project or topic level) |
| `proposal` | Solution proposals, options analyses | `wiki/projects/{slug}/proposals/` |
| `strategy` | Strategy docs, roadmaps, planning | `wiki/projects/{slug}/strategy/` |
| `spec` | Feature specifications with implementation plans | `wiki/projects/{slug}/specs/` |
| `decision` | Architecture Decision Records (ADRs) | `wiki/projects/{slug}/decisions/` |
| `meeting` | Synthesized meeting notes | `wiki/projects/{slug}/meetings/` |
| `person` | Cross-project rolodex entry — colleagues, cross-team partners, vendors, customers, recruiters, advisors | `wiki/people/` |
| `team-status` | Forward-looking RAG / risks / issues / asks status page | `wiki/team-status/` or `wiki/projects/{slug}/status/` |
| `research` | One-off research brief (single source / quick query) | `research/{date}-{slug}.md` |
| `research-project` | Multi-source research project (4-pillar / 4-phase) | `research/{date}-{slug}/overview.md` |
| `research-source` | Individual ingested source within a research project | `research/{date}-{slug}/sources/` |
| `research-{matrix\|shortlist\|blueprint}` | Synthesized research artifact (shape declared upfront) | `research/{date}-{slug}/artifact.md` |
| `playbook` | Reusable methodologies and frameworks | `wiki/playbooks/` |
| `domain` | Cross-project domain knowledge | `wiki/domains/` |
| `tool` | Tool and technology evaluations | `wiki/tools/` |
| `cloud-tool` | Inventory item: cloud-provider tooling for agentic systems (rendered via `wiki/tools/agentic-stack/agentic-stack.base`) | `wiki/tools/agentic-stack/` |
| `saas-contract` | Inventory item: SaaS / vendor contract record (rendered via `wiki/tools/vendors/vendors.base`) | `wiki/tools/vendors/` |
| `asset` | Companion page for non-text files | Co-located with asset |
| `deliverable` | Companion page for output files | Co-located in wiki |

## Status Values

- `draft` — work in progress, not reviewed
- `ready` — reviewed and approved, not yet started (specs)
- `active` — current and maintained
- `in-progress` — actively being built (specs)
- `review` — pending review
- `done` — completed (specs)
- `archived` — no longer current
- `superseded` — replaced by a newer version (link to replacement)

## Tagging Taxonomy

- **Delivery phase:** `#discovery`, `#design`, `#build`, `#test`, `#deploy`
- **Artifact type:** `#architecture`, `#proposal`, `#strategy`, `#research`, `#decision`, `#retro`
- **Domain:** use kebab-case domain tags freely, e.g., `#event-driven`, `#api-design`, `#rag`
- **Status:** `#active`, `#draft`, `#blocked`, `#archived`

## Ontology

```
wiki/
├── index.md
├── projects/
│   └── {project-slug}/
│       ├── overview.md
│       ├── topics/              # Optional: for multi-topic projects
│       │   └── {topic-slug}/
│       │       ├── overview.md  # Topic brief, approach, plan
│       │       ├── design/
│       │       ├── specs/
│       │       ├── decisions/
│       │       └── _assets/
│       ├── design/              # Project-wide design (or flat for simple projects)
│       ├── proposals/
│       ├── strategy/
│       ├── specs/
│       ├── decisions/
│       ├── meetings/
│       ├── research/
│       ├── tasks.md
│       ├── delivery/
│       └── _assets/
├── domains/
├── playbooks/
├── tools/
└── syntheses/
```

### Multi-Topic Projects

Many projects contain distinct workstreams, modules, or concerns that
each have their own designs, specs, and decisions. When a project has
3+ distinct topics, use the `topics/` subfolder:

```
wiki/projects/order-platform/
├── overview.md                      # Project-level overview, links to topics
├── topics/
│   ├── config-knowledge/
│   │   ├── overview.md              # Topic approach, plan, current state
│   │   ├── design/
│   │   │   └── rag-architecture.md
│   │   ├── specs/
│   │   │   └── config-profile-schema.md
│   │   └── decisions/
│   │       └── adr-001-four-store-architecture.md
│   ├── file-validation/
│   │   ├── overview.md
│   │   ├── design/
│   │   └── specs/
│   └── e2e-orchestration/
│       ├── overview.md
│       ├── design/
│       ├── specs/
│       └── decisions/
├── meetings/                        # Meetings stay project-level (cross-topic)
├── tasks.md                         # Tasks stay project-level (cross-topic view)
├── strategy/                        # Strategy stays project-level
└── delivery/                        # Delivery stays project-level
```

**When to use topics vs. flat structure:**
- **Flat (no topics/):** Simple projects with 1-2 concerns. Everything
  in `design/`, `specs/`, `decisions/` directly.
- **Topics:** Projects with 3+ distinct workstreams that each have
  their own architecture, approach, and implementation plan.

**What stays at project level (not topic level):**
- `overview.md` — project-wide context, links to all topics
- `meetings/` — meetings often span multiple topics
- `tasks.md` — cross-topic task visibility
- `strategy/` — project-level strategy and planning
- `delivery/` — sprint summaries, status updates
- `research/` — unless research is clearly topic-scoped

**Topic overview.md template:**
```yaml
---
title: "Config Knowledge"
type: topic
project: order-platform
status: active
created: 2026-04-15
modified: 2026-04-25
tags: [rag, config-knowledge, agentic-ai]
---

## Synopsis

RAG-based system to capture undocumented SME knowledge around plan
sponsor configuration. Four-store architecture with a client config
profile schema as the interface contract.

## Approach

[What we're building and why]

## Current State

[Where things stand — updated each session]

## Key Decisions
- [[decisions/adr-001-four-store-architecture]]

## Specs
- [[specs/config-profile-schema]] (in-progress)

## Open Questions
- ...
```

## Spec-Driven Development

### Starting a Build Session
1. Read the project `overview.md` to orient
2. Find the active spec (`status: in-progress`) in `specs/`
3. Read the spec's **Current State** section
4. Read referenced ADRs and design pages
5. Navigate to the code repo and verify state matches spec
6. Resume from the next unchecked implementation step

### During a Build Session
1. Follow the spec's technical approach and implementation plan
2. If you encounter a significant decision point:
   - STOP and discuss with the team member
   - If a decision is made, create a new ADR in `decisions/`
   - Update the spec to reference the new ADR
3. Check off implementation steps as they're completed

### Ending a Build Session
1. Update the spec's **Current State** with:
   - What was completed
   - What remains
   - Any blockers or open questions
   - Code locations for key changes (file:line references)
2. Check off completed implementation plan items
3. Update the spec's `modified:` date
4. If all steps are complete, move status to `review`
5. Update the PM tool issue via the sync skill

## ADR Format

Decision records follow this structure:
```markdown
## Context
What is the issue or question?

## Decision
What was decided?

## Rationale
Why was this option chosen over alternatives?

## Consequences
What are the trade-offs and implications?
```

ADRs are **immutable** once accepted. If a decision is reversed,
create a new ADR that supersedes the original (link both ways).

## Cross-Project Knowledge

When ingesting project-specific content that contains general
domain knowledge, ALWAYS:
1. Create/update the relevant `domains/` page
2. Link back to the project context
3. Note any project-specific caveats

## Tool Evaluations

When a new tool or technology is discussed, create/update a
`wiki/tools/{tool-name}.md` page with:
- What it does
- When to use it
- Trade-offs and alternatives
- Team experience and notes

## Research Integration

This variant supports three research tools. Use the corresponding
Claude Skill for each:
- **Perplexity** — quick, cited web research (current events, tech comparisons)
- **Gemini Deep Research** — exhaustive strategic/landscape analysis
- **Semantic Scholar** — academic literature, citation graphs, paper recommendations

## PM Tool Sync

Use the PM sync skill (`sync-pm-*.md`) to:
- Pull sprint/cycle status into `wiki/projects/{slug}/delivery/`
- Push action items from meeting notes and decision records to the PM tool
- Keep `pm_issue` frontmatter fields in sync

## Operations Layer

This variant has both a structured-ingestion pattern (specialized ingesters land typed wiki pages) and an operations layer (skills that read structured pages, compose, and write derived pages back into the vault).

Operations available in `skills/work/`:

- **Sprint planning** — read specs + tasks + capacity, produce a sprint-plan page
- **Spec session start** — Claude Code build-session continuity from the active spec
- **ADR review queue** — surface ADRs in `draft` awaiting acceptance
- **Task tracking** — lightweight per-project tasks.md (Open / In Progress / Done)
- **Cross-project synthesis** — refresh a domain page with learnings from recent project work
- **Onboarding pack** — assemble a curated reading order for a new team member
- **Weekly digest** — backward-looking: synthesize what changed across projects in the last 7 days
- **Request tracker** — surface outstanding cross-team requests + escalations with due dates (work analog of `follow-up-tracker`)
- **Team status** — forward-looking RAG / risks / issues / asks consolidated status page (the canonical leadership-meeting artifact)
- **Status slides** — convert a `team-status` page into a best-practice executive PowerPoint deck

The status pipeline composes: `request-tracker` surfaces open asks → `team-status` consolidates Progress/Risks/Issues/Asks into a wiki page → `status-slides` produces the deck. `weekly-digest` is the backward-looking complement, not a substitute.

People-handling skills (shared across variants, but heavily used in work):

- **ingest-person** — capture a new person from a LinkedIn URL, business card, vCard, email signature, or recruiter intro into `wiki/people/{slug}.md`
- **person-update** — log a brief interaction with an existing person (bumps `last_contact:`, appends to interactions log, optionally adds an `## Open Asks` callout that request-tracker scans)

`ingest-meeting` should call `person-update` for each external attendee so meeting context flows into people pages automatically.

Operations are wiki → wiki composition. Their outputs are themselves wiki pages that subsequent operations and humans can consume. See the kit's design doc (`docs/design/work.md` Layer 5) for the full pattern.
