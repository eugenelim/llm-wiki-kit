# ADR-0011: Genre + subtype facets replace the fused `type`; folders key only stable roles

- **Status:** Accepted
- **Date:** 2026-06-16
- **Deciders:** maintainer
- **Related:** [RFC-0009](../rfc/0009-faceted-ontology-and-lyt-philosophy.md) (the proposal this ADR records); RFC-0008 (workspace-as-lens — establishes the `workspaces:` area axis this decision reuses); ADR-0002 (journal as state truth), ADR-0003 (managed regions), ADR-0004 (drift/proposal flow), ADR-0005 (Pydantic for disk-bound schemas).

## Context

Vault pages carry a single fused `type` frontmatter field (`medical-record`,
`stakeholder-update`, `vendor-contract`) and live in entity-kind folders
(`people/`, `medical/`, `projects/`). RFC-0009 found this conflates a
document *shape* with a *subject*, so shapes can't be reused across recipes,
and entity-kind folders force single-home filing — the weakest retrieval
path in Obsidian. RFC-0008 had already added the *area* axis (`workspaces:`),
deliberately leaving the page-kind on `type` and the folders alone. RFC-0009
completes the model along those untouched axes and is accepted; this ADR
records the architecturally significant decisions so they survive as
history independent of the RFC narrative.

## Decision

1. **Split the fused `type` into two orthogonal page-kind facets:**
   `genre` (a fixed, generic vocabulary of 9 document shapes — `note`,
   `record`, `update`, `decision`, `reference`, `profile`, `log`,
   `contract`, `moc`) and `subtype` (a controlled-but-growable specific
   form, the canonical source of truth). The fused `type` field is removed.

2. **The area axis is RFC-0008's `workspaces:`, reused unchanged.** This ADR
   introduces no parallel `domain` field; "which area a page belongs to" is
   answered by `workspaces:`, "what kind of page it is" by `genre`/`subtype`,
   "where it lives" by the role folder. The three are orthogonal.

3. **Folders key only a stable, single-valued role** (`people/`, `efforts/`,
   `library/`, `atlas/`). A *changing* attribute (lifecycle) is the `status`
   facet, never an `archive/` folder; an *area* is a workspace, never an
   `areas/` folder. Containers under `efforts/<type>/<instance>/` are bounded
   instances (single-valued membership), distinct from workspaces (standing
   lenses).

4. **Capture is structurally separated from synthesis.** `library/`
   (high-volume, agent-filled, `provenance: extracted`) is a different folder
   from `atlas/` (low-volume, human-gated, `provenance: synthesized`);
   LLM-authored `atlas/` pages are proposed through the journal, not silently
   committed.

5. **Greenfield, single model.** The kit is pre-release; faceting is the only
   model — no dual model, no opt-in, no legacy `type:` read-tolerance.

## Consequences

- **Positive.** Generic, reusable shapes across recipes; the single-home
  problem dissolves (a page is one `genre`, many `workspaces`, surfaced by
  query); the synthesis peak is protected; the model composes cleanly with
  RFC-0008 (orthogonal axes, shared Bases mechanism).
- **Breaking, against live code.** RFC-0008 is already shipped: the live
  `core/files/frontmatter.schema.yaml` carries both `type` and `workspaces`.
  Removing `type` ripples through the twelve content-type primitives — their
  `primitive.yaml` `contributes_to` manifests (`region: types`), their
  `.types` snippets, the `when: type == …` guards in their `.fields` snippets
  (64 occurrences), and their page templates — which must all change together
  (see the `faceted-frontmatter-schema` spec). The shipped
  `templates/workspaces/*/*.base` views do **not** reference the frontmatter
  `type` (their `type:` is the Bases view-type keyword), so they need no edit.
  *(Corrects this ADR's earlier draft, which wrongly said the `.base` views
  reference `type`.)*
- **Vocabulary cost.** More frontmatter concepts (`genre`, `subtype`, `moc`,
  capture-vs-synthesis) than "put it in a folder"; carried by the explanation
  doc and READMEs.
- **Philosophy coupling.** Adopting LYT's `atlas/`/MOC vocabulary raises the
  methodology-literacy bar; accepted deliberately (the kit teaches the
  methodology regardless) and bounded to no LYT *tool* dependency.
- **Reuse check stays stdlib.** Emergent `subtype` promotion uses a stdlib
  string/normalization heuristic — no new runtime dependency; an
  embeddings-based check is deferred to a separate ADR if ever warranted.
