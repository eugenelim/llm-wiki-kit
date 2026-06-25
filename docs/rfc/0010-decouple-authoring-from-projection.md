# RFC-0010: Decouple authoring from projection — a projection port, a landing box, and externalized skill packs

- **Status:** Accepted <!-- Draft | Open | Final Comment Period | Accepted | Rejected | Withdrawn -->
- **Author:** eugenelim
- **Approver:** eugenelim
- **Date opened:** 2026-06-24
- **Date closed:** 2026-06-24
- **Related:** RFC-0008 (workspace-as-lens — the substrate this completes), RFC-0007 (primitive contribution model — entry-point sideload; this amends its scope), RFC-0009 (faceted ontology — `genre`/`subtype`, journal-gated emergent `subtype`: §`:34,254-256`), ADR-0004 (drift detection — centralized `safe_write`), ADR-0002 (journal as state truth), `docs/architecture/overview.md` (`ingest.py` routing), `core/files/skills/ingest/SKILL.md` (the prose "shared flow"). **External dependency:** the [eugenelim/agent-ready-repo](https://github.com/eugenelim/agent-ready-repo) `agentbundle`/`.apm` pack system (that repo's ADR-0021) — not an in-repo artifact.

## The ask

**Recommendation (BLUF):** Extract the vault's write pipeline into a single **projection port** (`wiki project`), reachable by any skill — kit-native or foreign. Pair it with a **landing box** (an inbox plus an `adopt` skill) that auto-routes externally-generated artifacts through the port, where the LLM maps each artifact onto the faceted schema and the port mechanically validates the result. Then **externalize the kit's workspace-type skills** (research, the content-type ingesters' synthesis halves, operations) as distributable `.apm` packs, leaving the kit as the **vault substrate** (port + drift/journal/lock + doctor/lint/bootstrap/search).

**Why now (SCQA):** *Situation* — RFC-0008 established the vault as a *substrate* under filtered lenses; RFC-0007 gave external primitives a sideload path; ADR-0004 centralized the write **primitive** (`safe_write`, reached through `render_tree`/`install`). *Complication* — ADR-0004 unified the *merge semantics*, not a way to *invoke* projection: `safe_write` is a private function with no porcelain verb, and each internal writer reaches it through bespoke wiring (`_cmd_research` for research, the prose "shared flow" in `ingest/SKILL.md` for ingest). The chain *around* the write — schema-mapping, scope/contradiction checks, fact/task propagation, changelog — lives only as SKILL prose. So a foreign, prompt-only skill (e.g. the agent-ready-repo research pack) has neither the bespoke wiring nor access to the private function — no seam at all — and writes Markdown directly, tripping the kit's own anti-pattern (`ingest/SKILL.md:183`). *Question* — how do we let skills from anywhere land managed state in the vault without each one re-implementing (or bypassing) the projection chain?

**Decisions requested:**

1. **Projection port.** Extract the write pipeline from `ingest`'s back half and expose it as `wiki project <artifact> --as <subtype>`; `ingest` then calls it. · *recommend: yes* · decide-by: RFC accept (default: yes).
2. **Landing box.** Ship an inbox convention + an `adopt` skill that auto-routes foreign artifacts through the port, modeled on the existing `Clippings/` inbox. · *recommend: yes* · decide-by: RFC accept.
3. **Mapping convention (the load-bearing one).** Translation is **open and LLM-determined** in the landing box; validation is **closed and mechanical** at the port. The LLM maps any artifact onto the fixed `genre` enum + a `subtype` (reusing one, or proposing a new one via RFC-0009's journal gate); the port rejects anything that fails the schema. · *recommend: yes* · decide-by: RFC accept.
4. **Externalization boundary.** Knowledge-work skills (research, ingester synthesis, operations) leave the kit; the substrate stays. · *recommend: yes* · decide-by: RFC accept.
5. **Distribution.** Externalized packs ship as `.apm` packs via `agentbundle`, hosted **in this repo as an agentbundle catalogue** (`packs/<pack>/.apm/…` + `pack.toml`), and **project to the wiki via the port while remaining usable elsewhere** (agentbundle's per-tool adapters). This **complements** RFC-0007's entry-point sideload now, with intent to **retire** the entry-point lane once `.apm` covers kit-native primitives too. · *recommend: `.apm`/agentbundle; complement now, retire entry-points later* · decide-by: RFC accept.
6. **Trust boundary.** The port is the only *sanctioned* write path; foreign writes that bypass it surface as drift in `wiki doctor` (detect, don't prevent), and the port input-validates at the boundary. · *recommend: yes* · decide-by: RFC accept.

The litmus test for the whole proposal: **we can delete the kit's own research skill and instead ship a how-to that says `agentbundle install --pack research git+https://github.com/eugenelim/agent-ready-repo`, and a user's research-pack output lands in the vault through the port with a clean journal baseline.**

## Problem & goals

**Diagnosis.** Two concerns are fused inside every vault-side skill:

- **Authoring** — what content to produce, its schema, where it lands. The domain logic; legitimately what a skill knows.
- **Projection (state-sync)** — drift check via `safe_write`, journal append, managed-region merge, schema validation, scope/contradiction checks, changelog. The invariant the kit exists to protect.

`ingest/SKILL.md` shows the fusion: lines 76–145 narrate "content-type ingester *produces* the page → shared flow *lands* it," and line 183 makes the flow law ("Don't write to `wiki/` outside the `wiki ingest` flow… a hand-written page bypasses drift detection"). The **merge primitive is already centralized** — every kit write routes through the one `write_helper.safe_write` (`render.py:166` walks and writes every file through it; `install.py` uses `safe_write_region`), exactly as ADR-0004 intended. What is *not* extracted is everything around that primitive: `safe_write` is a private function with no porcelain verb (`write_helper.py:78`); each writer reaches it through bespoke wiring (`_cmd_research`, the `ingest` prose flow); and the projection chain that should wrap it — schema-mapping, scope/contradiction checks, fact/task propagation, changelog — exists only as **SKILL prose**, reachable by a Claude session reading the skill but never as a command. A plumbing-free external skill has no command to call and cannot reach projection at all.

**Goals.**

- One callable projection path that owns the entire write contract; every other writer routes through it.
- A foreign, prompt-only skill can land managed vault state with **zero vault knowledge** — it emits a plain artifact; the vault adopts it.
- A mapping convention that scales to skills "from everywhere" without pre-declaring a per-source adapter.
- Shrink the kit to the substrate; move knowledge work to externally-maintained, separately-versioned packs.

**Non-goals.**

- **Not a sandbox or a foreign-code runtime.** `.apm` skills are files the agent reads; we detect bad writes, we do not jail the agent (preserves Charter Principle 5, library-not-application).
- **Not a sync/hosting service.** Out of scope per CHARTER ("does not host or sync vaults").
- **Not reversing RFC-0007 *now*.** Its entry-point sideload is retained as a complement for kit-native primitives while `.apm` is the foreign-skill lane; the decided direction is to **retire** the entry-point lane later once `.apm` covers kit-native primitives too. That retirement is a follow-on, not this RFC.
- **Not re-opening the faceted schema.** RFC-0009's `genre`/`subtype` and its emergent-subtype gate are reused as-is.

## Proposal

### D1 — The projection port (`wiki project`)

Refactor `ingest`'s terminal pipeline into one reusable path and expose it as a verb:

```
wiki project <artifact.md> --as <subtype> [--at <path>]
```

It takes frontmatter + body and runs, in one place: validate/map frontmatter against the faceted schema → resolve destination (subtype routing, or explicit `--at`) → scope + contradiction check → `safe_write` (drift detection) → journal event → fact/task propagation → changelog. This is the hexagonal **port**: a technology-agnostic entry point with many adapters and a single owned contract. `ingest` becomes "front half (clean + synthesize) → call the port"; `research --out` and the operations writer fold onto the same path. A finished foreign artifact is simply the *subset* that skips cleaning and synthesis.

We do **not** expose raw `safe_write` as the sole low-level verb: that pushes journal/schema knowledge back onto callers, re-coupling them.

### D2 — The landing box (inbox + `adopt` skill)

Manual `wiki project X --as Y` per artifact is the clunky path. Instead, ship a **landing box** modeled directly on the kit's existing `Clippings/` inbox (`ingest/SKILL.md:147–162`: transient inbox → route → relocate on success → leave on failure). A foreign pack writes its output into the inbox; a vault-side `adopt` skill sweeps it, classifies each artifact, projects it through the port, and relocates on success. Classification reuses the pure router in `ingest.py`. This is the "skill that automatically pipes external outputs through the right location."

**Inference is the floor, and the vault learns.** We cannot control foreign packs, so we never require them to hint — `adopt` *reasons out* genre+subtype by reading the artifact. To stop re-reasoning the same shape every time, a mapping the user **elicits or confirms** is recorded as **self-vault knowledge** (a learned classification memory: "artifacts shaped like this, from this source, → this genre/subtype/destination"). Next time, `adopt` consults that memory first and only re-elicits on a genuinely new shape. The hint the pack won't give us, the vault accumulates for itself — gated by user confirmation, and a *new* subtype still routes through RFC-0009's human-accept journal gate.

### D3 — The mapping convention: open translation, closed validation

The convention that makes "skills from everywhere" tractable:

- **Translation is open and LLM-determined.** In the landing box, the `adopt` skill reads the foreign artifact and maps it onto the schema by reasoning — it is not a pre-declared adapter per source (you cannot enumerate the unknowable). It picks a `genre` from the fixed enum (`note, record, update, decision, reference, profile, log, contract, moc`) and a `subtype`: an existing one if it fits, or a **new one proposed through RFC-0009's journal gate** for human acceptance.
- **Validation is closed and mechanical.** The port hard-validates the *result*: required facets present (`genre, subtype, status, provenance, created, …`), `genre` in the baseline enum, `subtype` known-or-proposed. This is the anti-corruption boundary's enforcement — the foreign model is translated to ours on the way in and never pollutes the schema.

This splits the anti-corruption layer cleanly: the *translation* is a reasoning task done by Claude (the kit stays the library — Charter Principle "Library-not-application"; handles arbitrary input), the *enforcement* is a schema gate (mechanical; protects the vault). It needs no fallback content-type — a research brief is `genre: reference` (already in the enum) + `subtype: research-brief`.

### D4a — The externalization boundary

| Stays (substrate — couples to journal/drift/lock/schema/search) | Leaves (knowledge-work packs) |
|---|---|
| wiki-lock, wiki-conflict, wiki-doctor, wiki-lint, wiki-bootstrap, wiki-search, wiki-agent; the `ingest` *router* + the projection port; init / add / upgrade / resolve | wiki-research; all **12** content-type ingesters' *synthesis halves* (`templates/content-types/`); all **10** operations (`templates/operations/` — action-item-rollup, follow-up-tracker, meal-planning, medical-summary, onboarding-pack, renewal-reminders, stakeholder-map-refresh, status-synthesis, trip-prep, weekly-digest) |

This is the hexagonal domain/infrastructure line, and it completes RFC-0008: the substrate gains a *write* boundary to match its read lenses.

### D5 — Distribution and trust

**This repo becomes an agentbundle catalogue.** The kit's own personal-focused packs live in-tree under agentbundle's pack layout — `packs/<pack>/.apm/{skills,agents,…}` plus `pack.toml` — installable with `agentbundle install --pack <name> git+https://github.com/eugenelim/llm-wiki-kit --scope user`. (Foreign packs the kit merely *recommends*, such as the research pack, are installed from their own catalogues, e.g. agent-ready-repo.) Packs are "files you own, no runtime" — prompt-only, so they **cannot** speak `safe_write`; they depend entirely on the port to land output. A deliberate consequence: a personal pack **projects into the wiki through the port *and* applies elsewhere** (any agentbundle target), so the catalog is not wiki-locked — it is portable knowledge work the wiki is one consumer of. Adding `packs/` is a new top-level directory; this RFC is its authorizing proposal (per the "propose new top-level directories via RFC" convention). RFC-0007's `wiki-primitive` entry-point sideload is **retained as a complement now and retired later**, once `.apm` packs cover kit-native primitives too; until then, entry-points serve primitives that already speak the contract and `.apm` serves prompt-only foreign packs. Trust: the port is the only sanctioned write path; a foreign write that bypasses it lands as an orphan `wiki doctor` already flags (detect, don't prevent — there is no way to stop a prompt-only skill from calling its Write tool). The port input-validates at the boundary, per the anti-corruption-layer trust guidance.

**Migration path.** Port + landing box + convention first (the enabler). Then the litmus test as the first migration: delete `wiki-research`, ship the `agentbundle install --pack research` how-to, confirm output lands through the port. Note `wiki-research` today is *not* prompt-only — `_cmd_research` already projects via `safe_write --out` — so this migration is about **ownership and distribution** (move the knowledge work out, replace a wired kit verb with an externally-owned pack), and the replacing pack, being prompt-only, is precisely what needs the port. The genuine "no seam at all" case is any other foreign pack. Then migrate remaining packs one at a time. `wiki run` *dispatch* is already shipped (`_cmd_run`, `cli.py:1682`; specs `task-17-wiki-run`, `wiki-run-exec`), and operation `outputs/*` are written today through `safe_write` from vault-side SKILL prose (`run.py`) — the same prose-to-port shape as `ingest`. So routing operations through the port carries the same migration cost as the ingest lane, not zero; the win is that one port serves both.

## Options considered

**Axis for D1 (where the write contract is exposed)** — exhausts "what form the seam takes," from none to fully extracted:

| Option | Trade-off | |
|---|---|---|
| Do nothing — prose shared flow, private `safe_write` | Foreign skills can't project (the blocker persists); ADR-0004's "one semantics" stays unrealized; every content-type re-narrates the flow | |
| New `wiki project` verb only | Clean port, but `ingest`'s existing back-half logic duplicated | |
| Generalize `wiki ingest` to take finished artifacts | Reuses routing, but overloads one verb with "raw source" and "finished artifact" modes | |
| **Extract the port from `ingest`; expose as `wiki project`; `ingest` calls it** | One implementation, two entry points; matches the hexagonal port + git plumbing/porcelain split | ★ |
| Expose raw `safe_write` as a low-level verb only | Re-couples callers to journal/schema knowledge | |

**Axis for D5 distribution (how packs install)** — do-nothing / Python-native / agent-native:

| Option | Trade-off | |
|---|---|---|
| Do nothing — keep skills bundled in `templates/` | No externalization; kit keeps growing | |
| RFC-0007 entry-point sideload for everything | Works for primitives that speak the contract; wrong shape for prompt-only foreign skills with no Python package | |
| **`.apm`/agentbundle for foreign packs; entry-points retained for kit primitives** | Two lanes matched to two classes; rides agent-ready-repo's accepted pack system; foreign packs depend on the port (D1) | ★ |
| New bespoke pack format | Reinvents a catalogue/manifest/adapter system agent-ready-repo already ships | |

Prior art grounds each: hexagonal ports & adapters (one port, many adapters, technology-agnostic), the DDD anti-corruption layer (translate-then-validate at a boundary between models), the kit's own `Clippings/` inbox, RFC-0007's Hugo/Sphinx-style extension surface, and agent-ready-repo's `pack.toml`/adapter projection model (that repo's ADR-0021 — external, not in-repo).

## Risks & what would make this wrong

**Pre-mortem.**

- *The port leaks abstraction* — callers still need to know subtypes/paths, so it isn't really decoupled. *Mitigation:* the landing box + LLM translation means foreign skills pass only `--as` (or nothing, letting `adopt` infer); the port owns the rest.
- *LLM mis-maps foreign artifacts*, silently corrupting the genre/subtype space. *Mitigation:* mechanical validation rejects out-of-enum genres; new subtypes go through RFC-0009's human-accept journal gate, not silent creation.
- *Two distribution lanes confuse contributors.* *Mitigation:* the boundary table (D4a) is the rule — couples-to-substrate → kit primitive; prompt-only knowledge work → `.apm` pack.
- *Externalized packs drift from the port contract* as the schema evolves. *Mitigation:* the port validates at the boundary, so drift surfaces as rejected projection, not silent bad state.

**Key assumptions (falsifiable).**

- The write pipeline is cleanly separable from synthesis in existing skills. *(Spiked — holds; see Evidence.)*
- The faceted schema + emergent-subtype gate can absorb arbitrary foreign artifacts without a new fallback genre. *(Spiked — holds: `reference` + journal-gated subtype.)*
- A prompt-only `.apm` skill, given the port, needs no other kit integration to land managed state. *(The litmus test falsifies this if it fails.)*

**Drawbacks.** A foreign write that bypasses the port still lands as an orphan until `wiki doctor` runs — we detect, we don't prevent. Two distribution mechanisms are more surface than one. The `adopt` skill adds an LLM step (and its latency/variance) between a pack's output and a clean baseline.

**Charter tension (named, and largely dissolved).** The Charter's "Common core, droppable primitives, composed by recipes" principle (`CHARTER.md:132`) frames the kit as "an engine plus a catalog." Mass-externalizing the catalog (D4a moves the synthesis halves of 12 content-types + 10 operations + research out of the tree) could *look* like narrowing the kit to engine-only. The resolution (D5): the catalog is **not destroyed, it is promoted to portable agentbundle packs** that project into the wiki via the port *and* apply elsewhere. The kit still composes recipes from a catalog; the catalog simply becomes separately-versioned, multi-target packs rather than in-tree primitives — so "common core, droppable primitives" is preserved in substance (droppable now means installable-and-portable, not bundled). A Charter-reconciliation follow-on still records this so the principle's wording tracks reality (the Charter's revision trigger, `CHARTER.md:173`, applies); the Approver confirms the wording, not the direction.

## Evidence & prior art

**Spike / de-risk.** The riskiest assumption is that projection is separable from synthesis. It holds: `ingest/SKILL.md` already structures itself as "content-type ingester *produces* the structured page" (76–88) → "shared flow *lands* it" (122–145), and `ingest.py` is "pure string parsing — no I/O" routing (`docs/architecture/overview.md`). The seam is already named in the design; this RFC makes it code. Two secondary spikes also cleared: the faceted schema's fixed genre enum already carries `reference` (`faceted-frontmatter-schema/spec.md:17`), and the journal-gated emergent-`subtype` mechanism — "the LLM proposing new `subtype` values through the journal for human acceptance" — is defined in `docs/rfc/0009-…:34,254-256` (it is *not* in the schema spec, which models `subtype` only as a build-time managed region), so no fallback content-type is needed. (One earlier assumption was *falsified* during review and is corrected here: `wiki run` is not a stub — its dispatch is shipped and operation outputs already write through `safe_write` in SKILL prose, so the operation lane is a real prose-to-port migration like `ingest`, not greenfield.)

**Repo precedent.** RFC-0008 (substrate/lens; this adds the substrate's write boundary); RFC-0007 (entry-point sideload, "same `safe_write` write contract"); ADR-0004 (rejects bespoke-per-command writes, mandates one semantics); RFC-0009 (`genre`/`subtype`, emergent-subtype gate); `ingest/SKILL.md` (shared-flow prose, `Clippings/` inbox, write anti-pattern).

**External prior art (fetched and confirmed).**

- Hexagonal architecture / ports & adapters — [AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html): "the application communicates with external components over interfaces called *ports*, and uses *adapters* to translate the technical exchanges"; "Ports are technology-agnostic entry points"; "A port can have multiple adapters without any risk to the port." Grounds the port = port, skills = adapters mapping.
- Anti-corruption layer — [Microsoft Learn / Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer): "This layer translates communication between the two systems"; the consumer side "always uses the data model and architecture of subsystem A"; and "Because the anti-corruption layer mediates systems that might have different trust levels, consider enforcing input validation … at this boundary." Grounds D3 (translate-then-validate) and D5/D6 (input-validate at the port).
- agent-ready-repo pack system — `pack.toml` as single source of truth projected lossily per tool, identity `@catalogue/pack`, canonical `.apm/{skills,agents,…}`. **External-repo artifact** (agent-ready-repo's own ADR-0021 and README, *not* in this repo's `docs/adr/`, which tops at 0011); confirmed against the [eugenelim/agent-ready-repo](https://github.com/eugenelim/agent-ready-repo) catalogue, which ships a `research` pack today. Grounds D5 distribution; relying on it requires that external system staying stable.

## Experiment / validation

- **Hypothesis.** A prompt-only external pack, given only the projection port + landing box, can land managed vault state with a clean journal baseline and no kit-specific integration.
- **What we measure.** Install the `.apm` `research` pack; run a research project; confirm its brief lands in the vault via the port with a valid faceted-schema mapping and a clean `wiki doctor`.
- **Success / failure criteria.** Success = the kit's own research skill is deleted, the how-to points at `agentbundle install --pack research`, and the round-trip is clean. Failure = the pack needs any kit-specific shim beyond the port to land output. Results go to a spike note created at implementation time (`docs/specs/landing-box/spike.md` — placeholder, not yet written); RFC stays `Open` until the round-trip passes.

## Open questions

1. **Form of the learned-mapping memory.** The decision is settled (inference floor + a vault-resident learned memory, gated by user confirmation — see D2); what the landing-box spec must still pin down is *how* that memory is stored and consulted: a managed region in a `mappings` page, a dedicated learned-mappings record, or frontmatter on an index — and the confirmation UX that writes to it. · *Default: a single human-readable learned-mappings record in the vault, written only on user confirmation and — like any managed page — **through the projection port itself**, consulted by `adopt` before re-reasoning.* · owner: eugenelim · decide-by: landing-box spec.

## Follow-on artifacts

<!-- Filled in when the RFC is accepted. -->

- ADR: the projection port as the single sanctioned write path (records the ADR-0004 realization).
- ADR: two-lane distribution — entry-point sideload vs `.apm` packs — and the class boundary.
- Follow-on RFC/spec: retire the RFC-0007 entry-point lane once `.apm` covers kit-native primitives (the decided end-state).
- Spec: `docs/specs/projection-port/` (`wiki project` contract + `ingest` refactor).
- Spec: `docs/specs/landing-box/` (inbox convention + `adopt` skill + LLM-map/port-validate convention).
- Spec: stand up the in-repo agentbundle catalogue — the `packs/` tree, `pack.toml`, and migration of the externalized skills from `core/`/`templates/` into `packs/<pack>/.apm/`.
- Spec: the research-pack externalization + how-to (the litmus test — recommends installing the external research pack from agent-ready-repo).
- Convention change: `docs/CONVENTIONS.md` — "all vault writes route through the projection port"; the kit-primitive vs `.apm`-pack contribution boundary.
- Charter reconciliation: a follow-on RFC (or Charter edit) resolving D4a against Principle "Common core, droppable primitives" — confirm the kit-as-substrate framing satisfies it or amend the principle.
