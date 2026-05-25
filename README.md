# LLM Wiki Kit

A kit for building LLM-maintained markdown wikis — Karpathy's LLM Wiki pattern, adapted. Two ways to use it:

- **Just use a vault.** Clone a [starter](starters/) (`family` or `work-os`), copy it into a folder of your own, open it in Claude Code. No Python install required.
- **Build, customize, or upgrade a vault.** `pip install llm-wiki-kit`. Then `wiki init` for a new vault from a recipe, or `wiki upgrade` inside an existing vault (including a cloned starter) to pull in the kit's newest primitives.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills Spec](https://img.shields.io/badge/skills-agentskills.io-blue.svg)](https://agentskills.io/specification)
[![Obsidian Skills](https://img.shields.io/badge/foundation-kepano%2Fobsidian--skills-purple.svg)](https://github.com/kepano/obsidian-skills)

---

## Use a starter (no install required)

Three steps, fresh repo to working vault — no Python, no `pip install`.

**1. Pick a starter.**

| Starter                    | Best for                                                         |
|----------------------------|------------------------------------------------------------------|
| [`starters/family/`](starters/family/)   | A household OS — meals, medical, trips, action items.          |
| [`starters/work-os/`](starters/work-os/) | A professional OS — stakeholders, customers, projects, decisions. |

**2. Copy it to a folder of your own.**

```bash
cp -r starters/work-os ~/my-vault
cd ~/my-vault
```

The vault is just markdown — works in any editor. For LLM-driven workflows, open it in Obsidian or Claude Code.

**3. Talk to Claude.** Open Claude Code (or any agent that reads `AGENTS.md`) at the vault root. It will read `AGENTS.md` and `CORE.md` to learn what the vault is and what skills it can run. Then try one of the [prompts below](#talking-to-claude).

See [`starters/README.md`](starters/README.md) for the full clone-and-go workflow, including how to pull in kit upgrades later with `wiki upgrade`.

---

## Build or maintain a vault (`pip install`)

For authors who want to scaffold a new vault from scratch, customize existing primitives, or upgrade a cloned starter against the kit's latest output. Requires Python 3.11+.

**1. Install.**

```bash
pip install llm-wiki-kit
# or, for an isolated CLI:
pipx install llm-wiki-kit
```

**2. Init a new vault** (or skip if you already cloned a starter).

```bash
wiki init my-vault --recipe personal
cd my-vault
```

Pick a recipe — `personal` (smallest, start here), `family`, or `work-os`. `wiki init` initializes a git repository by default and makes one initial commit covering the freshly-rendered tree; pass `--no-git` to opt out. The kit's `.gitignore` ships either way — it covers `*.proposed` sidecars, OS junk, and search-index runtime.

**3. Or upgrade an existing vault** — including a cloned starter.

```bash
cd ~/my-vault          # cloned from starters/, or built with wiki init
wiki upgrade
```

`wiki upgrade` re-renders managed regions, installs new primitives the recipe now ships, and routes any user-edited files through `safe_write`'s drift detection — conflicts land as `.proposed` sidecars, never as silent overwrites.

**4. Open it.** The vault is Obsidian-compatible: *File → Open vault* → pick the vault folder. Or just open the folder in any markdown editor.

**5. Talk to Claude.** Same as the starter path above.

A 20-minute walkthrough lives in [`docs/guides/tutorials/tutorial-1-first-vault.md`](docs/guides/tutorials/tutorial-1-first-vault.md), with a deeper `work-os` tour in [`tutorial-2-work-os-walkthrough.md`](docs/guides/tutorials/tutorial-2-work-os-walkthrough.md).

## Talking to Claude

Three things to try first, in escalating order. Paste any of these into Claude Code at the vault root:

**Read the journal.** Works on day one with no setup. The journal is the kit's source of truth — every state-changing action lands one line of JSON before touching disk.

```text
Read .wiki.journal/journal.jsonl and summarize what's happened in this
vault in the last seven days. Group by event type.
```

**Ingest a source.** Drop a file under `raw/` and route it through the kit first (this journals the ingest dispatch):

```bash
mkdir -p raw
printf '# Standup\n\nDiscussed Q3.\n' > raw/standup.md
wiki ingest --as meeting raw/standup.md
```

Then in Claude:

```text
Pick up the journaled ingest route for raw/standup.md and run the
ingest-meeting skill; write the synthesized page under wiki/meetings/.
```

**Run an operation.** Once you have a few meeting pages from this week in `wiki/meetings/`:

```text
Run the weekly-digest skill for the current ISO week. Write the digest
under outputs/digests/ at the path the skill specifies.
```

The default `wiki run weekly-digest` (with no args) targets the most recent *complete* ISO week; we pin the current week in the prompt above so you see output on day one.

If you get a `.proposed` sidecar next to a file, see [*How to fix a `.proposed` sidecar*](#how-to-fix-a-proposed-sidecar) below — the kit never silently overwrites your edits.

## What you'll see in week 1

After `wiki init my-vault --recipe personal`, you have:

```
my-vault/
├── AGENTS.md               # Contract the agent reads when you open the vault.
├── CORE.md                 # What this vault is, in plain English.
├── .gitignore              # Sensible defaults — commit the journal, ignore sidecars.
├── .wiki.journal/          # Append-only event log. The kit's source of truth.
├── _templates/             # Page templates the kit fills in.
├── frontmatter.schema.yaml # YAML-frontmatter contract for typed pages.
├── identity.md             # Seed page about you (personal recipe).
├── skills/                 # Vault-side skills your agent session runs.
│   ├── ingest-meeting/, weekly-digest/, ingest-recipe/, …
│   └── wiki-search/, wiki-doctor/, wiki-conflict/, …
└── wiki/                   # Typed pages land here.
    ├── meetings/, people/, decisions/, food/, trips/, …
```

Two directories `wiki init` doesn't create — they appear on first use:

- `raw/` — informal convention; you (or the agent) drop source material here before ingest.
- `outputs/` — prescribed by operation contracts (e.g. `weekly-digest` writes to `outputs/digests/<window>.md`). The directory shows up the first time an operation runs.

A typical first week:

- **Day 1–2:** ingest a handful of sources (meeting notes, recipes, a trip plan). `wiki/<thing>/` starts filling up with one typed page per source. The journal grows by one `page.write` event per page.
- **Day 3–7:** run the `weekly-digest` operation. The agent reads across your meetings and writes a summary the kit places by the skill's contract. Run `wiki doctor` whenever you want to sanity-check that on-disk reality still matches the journal.

The deeper a recipe you pick, the more ontology folders, content-types, and operations show up — `family` adds shared-household primitives (action items, follow-up tracking, meal planning), `work-os` adds stakeholder/customer/decision primitives plus the operations that read across them.

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
wiki init <path> --recipe <name>     Create a new vault from a recipe.
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

The kit never silently overwrites a file you have edited. If your edits drift from the kit's last known state, the next write lands as `<path>.proposed` next to the original, and `wiki doctor` flags it. The walkthrough — including a worked example against the committed `docs/guides/how-to/_examples/conflict-pending/` vault — is in [`docs/guides/how-to/resolve-a-conflict.md`](docs/guides/how-to/resolve-a-conflict.md).

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
