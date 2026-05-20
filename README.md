# LLM Wiki Kit

A Python package and template catalog for building LLM-maintained markdown wikis — Karpathy's LLM Wiki pattern, adapted. The kit ships a common core plus a catalog of droppable primitives, composed by recipes, so a non-engineer can `pip install llm-wiki-kit`, run one command, and get an Obsidian-compatible vault wired up for Claude (or any agent that reads `AGENTS.md`) to ingest into and operate on.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills Spec](https://img.shields.io/badge/skills-agentskills.io-blue.svg)](https://agentskills.io/specification)
[![Obsidian Skills](https://img.shields.io/badge/foundation-kepano%2Fobsidian--skills-purple.svg)](https://github.com/kepano/obsidian-skills)

---

## Install

```bash
pip install llm-wiki-kit
# or, for an isolated CLI:
pipx install llm-wiki-kit
```

Requires Python 3.11+. Runtime deps are `pyyaml` and `pydantic>=2`; everything else is stdlib. `pipx install` works out of the box — the wheel bundles the recipe catalog and template assets so no source checkout is needed (see [`docs/specs/wheel-bundled-assets/spec.md`](docs/specs/wheel-bundled-assets/spec.md)).

## Quick start

```bash
# Pick a recipe: family, work-os, or personal.
wiki init --recipe family my-vault

# Sanity check.
cd my-vault
wiki doctor
```

Then point Claude Code (or any agent that reads `AGENTS.md`) at `my-vault/`. The kit lays down the journal, the skills, the schema, and the seed pages; the agent reads the vault-side `AGENTS.md` to learn what to do next.

A 20-minute walkthrough lives in [`docs/guides/tutorials/tutorial-1-first-vault.md`](docs/guides/tutorials/tutorial-1-first-vault.md), with a deeper `work-os` tour in [`tutorial-2-work-os-walkthrough.md`](docs/guides/tutorials/tutorial-2-work-os-walkthrough.md). Browse `examples/family-mini/` and `examples/work-os-mini/` to see what a rendered vault looks like before installing.

## The two loops

A wiki without operations is a filing cabinet. The capture loop runs at first, then dies because nobody sees a visible weekly payoff.

This kit is designed around **two reinforcing loops**:

- **Capture loop** — ingest a source → typed wiki page lands in the right place.
- **Operate loop** — operation reads structured pages → produces a derived artifact (a sprint plan, a meal plan, a weekly review) that subsequent operations and humans both consume.

Every feature — progressive loading, synopses, structured ingestion, the operations layer — exists to make both loops fast and useful.

**Human curation is non-negotiable.** Research on LLM-maintained documentation shows that fully unsupervised LLM management degrades quality over time. The kit enforces curation through provenance tracking, contradiction detection, an append-only journal, and drift detection (any change to a file you have edited goes through a proposal sidecar rather than a silent overwrite). The LLM proposes; you review.

## Composition model

Three layers compose into one vault:

1. **Common core** (`core/`) — always installed. The vault-side `AGENTS.md` contract, the journal, the frontmatter-schema baseline, and the cross-cutting skills (`wiki-search`, `wiki-conflict`, `wiki-lock`, `wiki-lint`, `wiki-doctor`, `ingest`, `wiki-research`).
2. **Primitives** (`templates/`) — independently versioned, droppable building blocks. Four kinds: *ontology* (folder shapes — `people/`, `food/`, `projects/`), *content-type* (an ingester + page template + frontmatter contribution — `meeting`, `recipe`, `medical-record`), *operation* (contract + skill + eval fixture — `weekly-digest`, `meal-planning`, `stakeholder-map-refresh`), and *infrastructure* (cross-cutting — `research`, `research-perplexity`, `research-gemini`, `research-semantic-scholar`).
3. **Recipes** ([`recipes/`](recipes/)) — named YAML files that compose primitives for one audience. v2.0 ships three: [`family`](recipes/family.yaml), [`work-os`](recipes/work-os.yaml), [`personal`](recipes/personal.yaml).

The deep dive — module map, journal events, write-safety layers — lives in [`docs/architecture/overview.md`](docs/architecture/overview.md). Foundational decisions (stdlib rendering, journal-as-truth, managed regions, drift detection, Pydantic schemas, additive contributions, vault-root config files) are captured as ADRs under [`docs/adr/`](docs/adr/).

## CLI surface

```
wiki init --recipe <name> <path>     Create a new vault from a recipe.
wiki add <kind>:<name>               Install a primitive into the current vault.
wiki upgrade [--primitive <name>]    Upgrade installed primitives to latest.
wiki doctor                          Validate vault state against the journal.
wiki ingest <source>                 Route source material to the right ingester.
wiki run <operation>                 Run a named operation.
wiki research <query>                Dispatch to a configured research provider.
wiki search <query>                  Ripgrep over the vault.
wiki journal {tail,grep,explain}     Read the vault journal.
```

`wiki resolve` and `wiki lock` round out the surface for proposal merges and multi-event sessions. Run `wiki <command> --help` for argument detail; the canonical contract is RFC-0001 §"CLI surface (target)".

## How to fix a `.proposed` sidecar

The kit never silently overwrites a file you have edited. If your edits drift from the kit's last known state, the next write lands as `<path>.proposed` next to the original, and `wiki doctor` flags it. The walkthrough — including a worked example against the committed `examples/conflict-pending/` vault — is in [`docs/guides/how-to/resolve-a-conflict.md`](docs/guides/how-to/resolve-a-conflict.md).

## Where the docs live

- **Mission and scope** — [`docs/CHARTER.md`](docs/CHARTER.md).
- **Tutorials and how-tos** — [`docs/guides/tutorials/`](docs/guides/tutorials/) and [`docs/guides/how-to/`](docs/guides/how-to/).
- **Architecture map** — [`docs/architecture/overview.md`](docs/architecture/overview.md).
- **Decisions** — [`docs/adr/`](docs/adr/).
- **Roadmap** — [`docs/ROADMAP.md`](docs/ROADMAP.md).
- **Shipped work** — [`CHANGELOG.md`](CHANGELOG.md).

## License

[MIT](LICENSE)

## Acknowledgments

- **Andrej Karpathy** — for the LLM Wiki concept that inspired this system.
- **Steph Ango (kepano)** — for [obsidian-skills](https://github.com/kepano/obsidian-skills) and Obsidian itself.
- **Anthropic** — for Claude Code, which makes the LLM Wiki pattern practical.
