# Charter

> The foundational document for this project. One page, read whole.
> Modeled on the [CNCF project charter pattern](https://contribute.cncf.io/maintainers/governance/charter/):
> mission, scope, and principles in a single place, kept stable and short.

Changes to this file go through an RFC. The rest of the docs in this repo
are scaffolding around it; this file is the why.

-----

## Mission

`llm-wiki-kit` makes it practical for one technically-comfortable author —
an engineer, an engineering-adjacent professional, or the tech-confident
member of a household — to set up and maintain an Obsidian wiki that they
and the people around them can use, and that an LLM can read, ingest into,
and operate on. The kit serves the author; the downstream readers (family
members, teammates, stakeholders) consume the resulting vault in whatever
editor or chat client they already use, and need no relationship with the
kit itself.

The kit ships a common core plus a catalog of droppable primitives,
composed by recipes, so each author gets a vault shaped to their actual
life or work without having to design one from scratch.

Audiences who cannot install the kit themselves — true non-engineers,
households or teams without a tech-comfortable maintainer — are a
Tier 2 audience served by *starter distributions*: pre-rendered vaults
producible from the kit but consumable without it (see RFC-0006 and
[`starters/README.md`](../starters/README.md)). The kit produces them; the
user clones one. The library boundary in Principle 5 is unchanged,
because a starter is a CI-generated projection of the library, not a
parallel application.

The project exists because the LLM Wiki pattern (Karpathy, 2025) is
genuinely valuable but currently lives in scattered, hand-rolled vaults
that only their authors can maintain. The kit’s job is to make that
pattern reproducible.

### Organizing philosophy — link, don’t file

The vaults this kit produces are thinking spaces, not filing cabinets.
Following Linking Your Thinking (Nick Milo), structure comes from
*connection and synthesis*, not from where a file is filed: wikilinks,
relations, and frontmatter facets are the primary structure; folders are a
thin browsable convenience. Maps of Content are the navigation layer;
structure is allowed to emerge from use rather than be designed up front;
and the synthesis layer is protected from the volume of capture. We adopt
LYT’s vocabulary and principles and credit the lineage (the synthesis layer
is `atlas/`, its maps are MOCs); we are not affiliated with LYT and take no
dependency on its commercial tools. This governs the *vaults the kit
produces* — it adds no ADR/RFC/spec ceremony to kit development, consistent
with the “Eat our own dogfood” carve-out under Principles. Karpathy’s
LLM-Wiki pattern remains the *maintenance* model; LYT is the *organization*
model layered over it. See [RFC-0009](rfc/0009-faceted-ontology-and-lyt-philosophy.md)
and [`docs/guides/explanation/organizing-philosophy.md`](guides/explanation/organizing-philosophy.md).

## Scope

What this project does:

- Provides a Python CLI (`wiki`) for creating, extending, and validating
  Obsidian-compatible vaults.
- Ships three audience-specific recipes that compose primitives into coherent
  vaults: `family` (household OS — meals, medical, trips, follow-ups),
  `work-os` (professional teams — stakeholders, decisions, customer feedback,
  vendor renewals), and `personal` (single-person knowledge base).
- Maintains an append-only JSONL journal in every vault as the single source
  of truth for what’s installed, what’s been ingested, and what operations
  have run.
- Ingests source material (meeting transcripts, recipes, medical records,
  documents) into structured wiki pages via Claude-driven content-type
  ingesters.
- Runs named operations (`weekly-digest`, `meal-planning`,
  `stakeholder-map-refresh`, etc.) defined as contracts, executed by Claude.
- Detects drift between the kit’s last known state and on-disk reality, and
  hands off conflicts to the user via a Claude-mediated `wiki-conflict` skill
  rather than silently overwriting.
- Optionally integrates research providers (Perplexity, Gemini Deep Research,
  Semantic Scholar) as opt-in infrastructure primitives.

What this project does **not** do:

- It does **not** host or sync vaults. The user’s vault is a folder on their
  machine, optionally backed by their own git or their own cloud sync. The kit
  is a tool, not a service.
- It does **not** ship engineering-team primitives (ADRs, RFCs, sprint
  planning, spec docs, code review). Those belong in a code repository
  alongside the code they describe, not in a wiki. The boundary is
  intentional: an engineer using both gets a wiki for
  stakeholders/decisions/customer-feedback and a separate repo for
  specs/ADRs/plans, not a fuzzy overlap.
- It does **not** include an LLM. Users bring their own Claude (or other
  agent) and run the kit’s vault-side skills inside it. The kit’s Python code
  is a tool layer, not an inference layer.
- It does **not** require API keys to get started. The default vault is fully
  functional offline; research providers are opt-in.
- It does **not** auto-write to user-edited content. Drift detection +
  proposal sidecars are non-negotiable — any change to a file the user has
  edited goes through a conflict review.
- It does **not** lock the user into Obsidian. The output is plain markdown
  in a normal folder structure. Obsidian Templater compatibility is
  intentional, but the vault works with any markdown editor.

The “does not” list is at least as important as the “does” list. It’s how
we — and AI agents working in the repo — know when a request is out of
bounds. If the project is being asked to do things that aren’t on either
list, that’s a signal to refine this section, not to drift.

## Principles

The values that resolve ties when reasonable people disagree. Six, no more.

1. **Honesty over capability.** It’s better to ship a small kit that does
   what it says than a large kit that requires asterisks. If a skill triggers
   at 60% in evals, that’s the number we publish. If drift detection has a
   case it can’t recover from, the docs say so. Marketing-flavored claims
   (“Claude never silently overwrites”) require a passing eval.
1. **The journal is the truth.** Vault state is whatever the JSONL journal
   says it is. If the journal and disk disagree, that disagreement is itself
   the user’s signal — not something to paper over. Every state-changing
   action appends an event before touching disk. No separate manifests, no
   parallel state.
1. **Dependency-minimal.** Runtime deps are `pyyaml` + `pydantic>=2` + stdlib.
   New runtime deps require an ADR. The single biggest reason: even the
   engineering-comfortable author the kit serves should not have to
   troubleshoot install failures, and the Tier 2 audience (who clones a
   starter without installing the kit at all) is best served by keeping
   the install path narrow if and when they later want kit upgrades.
   The kit must `pipx install` cleanly on a fresh Python 3.11 every time.
1. **Common core, droppable primitives, composed by recipes.** The kit is
   not one application — it’s an engine plus a catalog. Every audience-
   specific feature lives in a primitive that someone could remove without
   breaking the core. Recipes compose primitives; they don’t extend them.
1. **Library-not-application.** The kit is invoked by Claude as a set of
   primitives Claude can call. Claude is the application; the kit is the
   library. We don’t try to be the agent, the orchestrator, or the model.
   That’s why we ship Python modules and SKILL.md files, not an LLM wrapper.
1. **Eat our own dogfood.** This project follows the same `AGENTS.md` /
   charter / ADR / RFC / spec discipline it ships to its users. If the
   discipline doesn’t hold up under daily use here, it’s not ready to
   ship to anyone else. This discipline is for *kit development*; the
   vaults the kit produces do **not** inherit ADR/RFC/spec ceremony,
   per Charter §Scope's exclusion of engineering-team primitives.

## What’s NOT in this charter

To keep this file from becoming everything-and-the-kitchen-sink:

- **Decision history** lives in `adr/`. The charter is what we believe;
  ADRs are the choices we made because of those beliefs.
- **Current project state** lives in `ROADMAP.md` and `CHANGELOG.md`. The
  charter is direction; the roadmap is where we are and where we’re going.
- **Current architecture state** lives in `architecture/`.
- **Conventions for how we work** live in `CONVENTIONS.md`.
- **Governance** (maintainership, decision-making) — currently a single
  maintainer operating by consensus with contributors. If the project grows
  enough to need a `GOVERNANCE.md`, we’ll add it. Most small projects don’t
  — forcing governance ceremony on a project that doesn’t need it produces
  theater, not clarity.

## When to revise

Revise this charter when:

- The mission has actually changed (rare — usually means a fork). Example
  trigger: deciding to support code/spec primitives directly inside the
  kit rather than keeping them outside its scope.
- The scope has shifted enough that PRs are routinely landing for things
  the current scope doesn’t cover. Example trigger: every other PR adds
  engineering-team primitives.
- A principle has stopped resolving ties — it’s being ignored, or it
  contradicts another principle in ways we haven’t acknowledged. Example
  trigger: “dependency-minimal” and a primitive that would genuinely need
  Pandas — pick one and revise the other.

Revise via RFC. Editing the charter directly without discussion is the
single fastest way to lose the trust this document is meant to build.
