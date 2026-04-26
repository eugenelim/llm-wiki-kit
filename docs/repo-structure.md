# Repo Structure

```
llm-wiki-kit/
├── README.md
├── LICENSE
├── .gitignore
├── docs/                     # Documentation
│   ├── README.md             #   Docs index
│   ├── design/               #   Architecture narratives — one per variant + research-layer
│   ├── guides/               #   Operational walkthroughs (setup, sync, file-formats, customizing, inventories)
│   ├── research-providers/   #   Per-provider docs for the research dispatch layer
│   ├── repo-structure.md     #   This file
│   └── comparison.md         #   Variant comparison
├── shared/                   # Canonical CLAUDE.md, variant extensions, purpose template
├── vault-templates/          # Per-variant vault skeletons (copy one to your cloud drive)
│   ├── work/                 #   Engineering team variant
│   ├── family/               #   Household variant
│   └── personal/             #   Solo knowledge + career variant
└── skills/                   # Agent Skills (agentskills.io spec)
    ├── shared/               #   Cross-variant: ingest orchestrator, research layer, lint, search, bookmarks
    ├── work/                 #   Variant-specific operations + ingesters
    ├── family/
    └── personal/
```

Each skill is a directory following the [Agent Skills spec](https://agentskills.io/specification):

```
skills/{variant}/{skill-name}/
├── SKILL.md          # Required: YAML frontmatter (name, description, license, metadata)
│                     #           + Markdown instructions
├── scripts/          # Optional: executable scripts owned by the skill (relative path: scripts/foo.py)
├── references/       # Optional: longer reference material loaded on demand
├── assets/           # Optional: templates, schemas, lookup tables
└── evals/
    └── evals.json    # Activation prompts demonstrating when the skill should fire
```

Bundled scripts (`tag-lint.py`, `convergence-debt.py` → wiki-lint; `wiki-search.py` → wiki-search; `ingest_document.py` → ingest-document; `research.py` → research) live inside their owning skill's `scripts/` directory.

## Inside each vault-template

```
vault-templates/{variant}/
├── CLAUDE.md                 # Copy of shared/CLAUDE.md (root agent contract)
├── purpose.md                # Copy of shared/purpose.md (vault scope; customize per-vault)
├── _variant/
│   └── CLAUDE.variant.md     # Variant-specific extension (page types, operations, tone)
├── _templates/               # Page templates with {{placeholder}} fields, per page type
├── .claude/
│   ├── skills/               # Empty in repo; populated during Quick Start step 3
│   │                         #   (each skill is a directory with SKILL.md + scripts/ + evals/)
│   └── research-providers.yaml   # API providers for the research dispatch script
├── raw/                      # Immutable source documents (your input)
├── wiki/                     # Structured knowledge — ontology per variant
│   ├── index.md              #   Dashboard / entry point
│   ├── bookmarks/            #   URL bookmarks + homepage.base
│   └── ...                   #   Variant-specific folders (see CLAUDE.variant.md ontology)
├── outputs/                  # Claude-generated deliverables (.docx, .pptx, .pdf)
├── research/                 # Research projects (4-pillar / 4-phase; see docs/design/research-layer.md)
└── log/
    └── changelog.md
```

## Conventions

- **Skills** follow an **orchestrator + specialized** pattern: `skills/shared/ingest/SKILL.md` detects source type and content type, then delegates to specialized siblings (`ingest-document`, `ingest-website`, `ingest-recipe`, `ingest-meeting`, `ingest-bookmark`, `ingest-tax-document`, etc.). The orchestrator stays small and routing-focused; specialized files own per-type extraction logic.
- **Inventories** use the same pattern as bookmarks — small per-item files in a typed folder + a `.base` file rendering the collection. See [`guides/inventories.md`](guides/inventories.md).
- **Research projects** live at `wiki/research/{date}-{slug}/` per the 4-pillar / 4-phase pattern in [`design/research-layer.md`](design/research-layer.md).

The detailed ontology and page-type table per variant lives in each variant's `CLAUDE.variant.{work,family,personal}.md`.
