# RFC-0009: Faceted ontology and the LYT organizing philosophy — page-kind facets, capture/synthesis split, emergent structure

- **Status:** Accepted <!-- Draft | Open | Final Comment Period | Accepted | Rejected | Withdrawn -->
- **Author:** eugenelim
- **Date opened:** 2026-06-16
- **Date closed:** 2026-06-16
- **Related:** **Builds on RFC-0008 (workspace-as-lens)** — which establishes the substrate/lens split and the multi-valued `workspaces:` area axis this RFC layers on. Also RFC-0001 (v2 architecture — primitive system + frontmatter schema), RFC-0005 (narrow charter mission to the author), RFC-0007 (primitive contribution model), ADR-0002 (journal as state truth), ADR-0003 (managed regions), ADR-0004 (drift detection & proposal flow), ADR-0005 (Pydantic for disk-bound schemas), `docs/specs/wiki-search/spec.md`, `docs/guides/explanation/organizing-philosophy.md`

## Summary

RFC-0008 (workspace-as-lens) gave the vault its *area* axis: one substrate,
many filtered `workspaces:`, realized through Obsidian Bases. It deliberately
left the **page-kind** axis on the existing fused `type` field, and left the
folder layout alone. This RFC completes the organizing model along the axes
RFC-0008 did not touch, and anchors the philosophy both already serve:

1. **Anchor LYT as the kit's stated organizing philosophy** (*link, don't
   file; map, don't bury; synthesize, don't hoard*), recorded as a new
   "Organizing philosophy" subsection in `docs/CHARTER.md` and as the
   produced vault's own `CORE.md`. (RFC-0008's lenses and Bases views are
   LYT in practice; this names the lineage.)
2. **Refine the page-kind axis.** Split the fused `type` (`medical-record`,
   `stakeholder-update`) into orthogonal facets — `genre` (generic document
   shape) and `subtype` (specific form). The *area* axis stays RFC-0008's
   `workspaces:`; this RFC introduces no parallel "domain" field.
3. **Replace entity-kind folders with role folders** — `people/` (nodes),
   `efforts/<type>/<instance>/` (bounded containers), `library/` (capture
   & reference), `atlas/` (synthesis). Folders key only *stable,
   single-valued roles*; lifecycle is the `status` facet, not a location.
4. **Protect the synthesis peak.** `library/` (high-volume, agent-filled)
   is structurally separated from `atlas/` (low-volume, human-gated), and
   LLM-authored synthesis is *proposed*, not silently committed.
5. **Grow the vocabulary emergently** — a fixed facet spine, with the LLM
   proposing new `subtype` values through the journal for human acceptance.

`workspaces:` answers *which area a page belongs to*; `genre`/`subtype`
answer *what kind of page it is*; the role folder answers *where it lives*.
The three are orthogonal and compose.

This is the kit's **single organizing model** — the kit is pre-release with
no vaults in the field, so there is no dual model, no opt-in, and no
back-compat to carry. It remains **folder-fallback-safe**: a vault stays
usable by a human in plain Obsidian with no plugins and no agent (folders
browse; queries enrich).

## Motivation

RFC-0008 solved area-membership (`workspaces:`) but two problems in the
page-kind axis and the folder layout remain. The current model still
conflates two things in one `type` string: every content-type primitive
contributes one fused value to the `frontmatter.schema.yaml` `types`
managed region (e.g.
`templates/content-types/medical-record/regions/frontmatter.schema.yaml.types`),
and each ontology primitive still seeds one entity-kind folder.

- **Page-kinds are not generic.** `medical-record` = *medical* (subject) ×
  *record* (shape); `stakeholder-update` = *stakeholder* × *update*.
  Because the subject is fused into the kind, the shape cannot be reused, so
  `family` and `work-os` end up with disjoint `type` vocabularies for what
  are often the same document shapes. (See `recipes/family.yaml` vs
  `recipes/work-os.yaml`.) `workspaces:` carries the *area*, but the *shape*
  is still trapped inside a fused enum.
- **Folders force single-home filing.** Entity-kind folders make a person
  who is also a vendor, or a trip that involves medical needs, pick one
  home — the classic single-home problem. Findability then depends on
  remembering the folder, the weakest retrieval path Obsidian offers — and
  it cuts against RFC-0008's premise that views, not folders, locate things.

Repo precedent argues *for* the change:

- **The journal + proposal flow already exists** (ADR-0002, ADR-0004).
  Emergent `subtype` promotion and gated LLM synthesis ride the same
  "propose-don't-apply → user accepts" rails we ship for page drift — a new
  event type, not a new mechanism.
- **The frontmatter-filtering mechanism already exists.** `wiki search`
  (`docs/specs/wiki-search/spec.md`, Implemented) filters pages by
  frontmatter fields over ripgrep, and RFC-0008's `.base` lenses filter the
  same frontmatter. Selecting by `genre`/`subtype` is the same mechanism.
  (Its current `--type` flag keys on the field this RFC splits; re-keying to
  `--genre`/`--subtype` is part of the all-at-once landing — see §H.)
- **A subtype precedent exists.** `docs/guides/reference/file-formats.md`
  already uses `asset_type: video` under `type: asset` — a secondary facet
  under a primary one is an accepted shape.
- **Managed regions already carry schema contributions** (ADR-0003,
  ADR-0006). Splitting the one `types` region into `genre`/`subtype`
  regions *extends* that mechanism — every content-type primitive rewrites
  its single fused contribution into per-facet contributions, part of the
  §H landing rather than a no-op.

The deeper motivation is that the kit ships an *LLM-maintained* vault yet
makes the kit author pre-declare every kind and folder up front. The LLM is
the one capability that makes a connection-first, emergent, synthesis-
protecting structure viable for a non-expert. RFC-0005 narrowed the mission
to "an author setting up a vault they and the people around them can use"; a
structure that only its author can navigate by folder fails that mission.
LYT names the philosophy that resolves it — and that RFC-0008 already
embodies.

## Proposal

### A. Anchor the organizing philosophy

Add an **"Organizing philosophy"** subsection to `docs/CHARTER.md` under
Mission, and make it the produced vault's `core/files/CORE.md`. The kit's
existing anchor — Karpathy's LLM-Wiki pattern (the *maintenance model*) — is
unchanged; LYT is layered as the *organization model* (the model RFC-0008's
lenses and Bases views already express). Proposed Charter text:

> **Organizing philosophy — link, don't file.** The vaults this kit
> produces are thinking spaces, not filing cabinets. Following Linking
> Your Thinking (Nick Milo), structure comes from *connection and
> synthesis*, not from where a file is filed: wikilinks, relations, and
> frontmatter facets are the primary structure; folders are a thin
> browsable convenience. Maps of Content are the navigation layer;
> structure is allowed to emerge from use rather than be designed up
> front; and the synthesis layer is protected from the volume of capture.
> We adopt LYT's vocabulary and principles and credit the lineage (the
> synthesis layer is `atlas/`, its maps are MOCs); we are not affiliated
> with LYT and take no dependency on its commercial tools. This governs the
> *vaults the kit produces* — it adds no ADR/RFC/spec ceremony to kit
> development, consistent with the Charter's existing carve-out under
> "Eat our own dogfood" that produced vaults do not inherit that ceremony.

The full exposition (including *what a MOC is*) lives in
`docs/guides/explanation/organizing-philosophy.md`.

### B. The facet model

Refine the page-kind axis: replace the fused `type` with `genre` +
`subtype`. The *area* axis is RFC-0008's `workspaces:`, reused unchanged —
**this RFC introduces no parallel "domain" field**.

| Field | Cardinality | Kind | Notes |
|---|---|---|---|
| `genre` | single | controlled, fixed | document shape; 9 values (below) |
| `subtype` | single | controlled, growable | specific form (canonical) |
| `workspaces` | **list** | controlled (RFC-0008) | area/lens membership — **unchanged here** |
| `status` | single | controlled | `active`, `draft`, `archived`, `someday` (deferred, not abandoned — excluded from active views, not archived) |
| `parent` | **list** | relation (wikilink) | container / hub membership |
| `provenance` | single | controlled (existing) | `extracted`, `synthesized`, `mixed` |
| `tags` | list | **open folksonomy** | free; promotion feeds controlled facets |
| `created`, `modified` | — | existing | unchanged |

Genre vocabulary (fixed spine, 9): `note`, `record`, `update`,
`decision`, `reference`, `profile`, `log`, `contract`, `moc`. `contract`
earns its place as a generic shape because agreements recur across areas (a
vendor MSA, a lease, an employment offer, a nanny agreement) — it is not
specific to any one workspace.

Existing type-specific lifecycle fields (`trip_status`, `update_status`,
`decision_status: proposed|accepted|superseded`) and the legacy
`status: upcoming` collapse in the crosswalk: generic lifecycle becomes the
`status` facet; a genre/subtype that needs finer states (e.g. a `decision`'s
proposed→accepted→superseded) keeps a subtype-scoped lifecycle field. The
crosswalk (§H) enumerates each mapping.

Orthogonality: knowing a page's `genre` must tell you nothing about its
`workspaces`; `subtype` refines `genre` (a `record` of subtype `meeting` or
`medical`). Faceted-classification design (Ranganathan/PMEST, Z39.19,
Flamenco): mutual exclusivity *within* an axis, free combination *across*;
every page carries every facet (use an explicit value, never omit, so
queries don't silently drop pages).

A content-type primitive stays exactly as specific as today (it still ships
its ingest SKILL, template, and fixtures) — only the frontmatter it *writes*
changes: `medical-record` → `genre: record, subtype: medical` (with
`workspaces:` stamped from the active lens per RFC-0008). Specificity moves
from a fused enum value into composable facets.

### C. Role folders, not kind folders

```
raw/                          # source files (immutable)
wiki/
  index.md                    # root MOC / dashboard
  people/                     # NODES: people, orgs, vendors, customers (query-hubs)
  efforts/<type>/<instance>/  # CONTAINERS: trips/, cases/, projects/, studies/
  library/                    # CAPTURE & REFERENCE (high-volume; agent-filled)
  atlas/                      # SYNTHESIS (low-volume; gated; the peak — LYT's term)
```

The diagram shows only `raw/` and the **reorganized `wiki/` content tree**.
The produced vault's other top-level folders — `outputs/`, `log/`,
`skills/`, `.wiki.journal/` (see `core/files/CORE.md`) — are **unchanged** by
this RFC; the reorg is scoped to what lives under `wiki/`. Workspaces
(RFC-0008) are filtered views that cut *across* these role folders — a
`library/` note can belong to the `research` workspace — so the two are
orthogonal.

Two rules keep this off the by-topic problem:

1. **No kind-keyed folders.** A meeting lives in `library/` with
   `subtype: meeting`, never in a `meetings/` folder. Kind is a facet.
2. **Folders key only a stable, single-valued role.** Lifecycle is the
   `status` facet, not an `archive/` folder; an "area" (Health) is a
   *workspace* (RFC-0008) with an optional `genre: moc` page, not an
   `areas/` folder. (A *changing* attribute as a folder causes churn; a
   *stable* one — role, capture-vs-synthesis — does not. That distinction is
   why the `library`/`atlas` split is a folder but `status` is not.)

These are *produced-vault* folders. The kit-repo convention that gates new
top-level directories behind an RFC governs the kit's own source tree, not
the layout the kit renders into a user's vault — the same kit-vs-vault scope
split AGENTS.md draws.

### D. Containers (instances, not kinds)

A **container** is a *bounded instance* with its own identity and lifecycle
that accumulates heterogeneous artifacts: a trip, a medical case, a research
study, an event. It is distinct from a *workspace* (RFC-0008): a workspace is
a standing, recipe-composed lens (an area like `research`); a container is
one bounded thing within it (`study_protein-folding`). A container is safe as
a folder — unlike a kind bucket — because membership is single-valued and
unambiguous.

- **Folder containers** for material mostly *exclusive* to one instance:
  `efforts/trips/japan-2026/`. Contents are **flat inside**, grouped by an
  `_index.md` MOC running `GROUP BY genre`. The only permitted subfolder is a
  non-semantic bulk sink (`_assets/`, `_working/`); never genre subfolders
  (`sources/`, `records/`, `drafts/`), which re-import the silo one level
  down.
- **Hub-file containers** for material mostly *shared* across instances (a
  work-coordination project whose meetings/people/decisions cross-cut):
  `efforts/projects/acme-migration.md` — no folder; member pages live in
  `library/`/`atlas/` and join via the `parent:` relation.

Membership is canonically the `parent:` frontmatter relation (so shared
pages and cross-cutting Bases views work uniformly); the folder is the *home*
for exclusive material. `container_mode` (folder | hub) is a declared
property of the concept/primitive. Containers are homed uniformly across all
recipes under one `efforts/` root, in nested per-type registries
(`efforts/trips/`, `efforts/cases/`, `efforts/projects/`) — their children
are instances, not attribute-buckets.

### E. Protect the synthesis peak

`library/` (capture/reference, high-volume, `provenance: extracted`) is
structurally separated from `atlas/` (synthesis, low-volume,
`provenance: synthesized`). A captured source and the synthesis drawn from it
are **two linked notes**, never one mixed document. (This is about *which
folder* a note lives in — distinct from the `provenance: mixed` value, which
legitimately tags a *single* page blending verbatim and inferred content.)
Creation-gating keeps the peak from eroding:

1. **Update/link before create** (reuse-first bias).
2. **Synthesis threshold** for `atlas/`: warranted only when a pattern
   recurs (≥2 sources, or central to one).
3. **LLM-authored `atlas/` pages are proposed**, via the journal `proposed`
   state (ADR-0004), and accepted by the human. The agent fills `library/`
   freely (cheap, prunable); it cannot silently grow `atlas/`.
4. **`library/` is prunable, `atlas/` is durable** — captures may age out
   (`status: someday`/`archived`, lint-flagged orphans).

### F. Emergent vocabulary growth

The facet *keys* are fixed; the LLM may propose new `subtype` *values* only.
(Workspaces are recipe-composed primitives per RFC-0008, not emergent facet
values — promoting a recurring theme to a full workspace means authoring a
workspace primitive, which is out of this RFC's scope.) Two-gate trigger:
(a) ≥N distinct sources (start N=3) **and** (b) no existing value passes a
reuse check; then an LLM-as-judge shortlist; then a journal
`facet_value.proposed` entry the user accepts. Reuse-first;
supersede-don't-delete; a periodic gardening pass consolidates near-
duplicates. **The reuse check is a stdlib string/normalization heuristic**
(case-fold, singularize, `difflib` ratio) — no new runtime dependency;
whether an embedding-based check is ever warranted is deferred to a separate
ADR. The human accepts every promotion, so the heuristic's misses degrade
gracefully (a near-dup is proposed, the human merges it) — see Drawbacks.

### G. Manual affordances — degrade gracefully without the agent

The model must not handcuff users to the LLM (Charter: offline-functional;
downstream readers use any editor). The kit ships, per recipe:

- **Content-type page templates that pre-stamp the facet fields** (empty
  `genre`/`subtype`/`parent`; `workspaces:` per RFC-0008) so a hand-created
  note is never an orphan; native Obsidian Properties autocomplete fills the
  values.
- **Starter Bases views** (`.base`) — alongside RFC-0008's workspace lenses,
  including container hub views — so grouping and inline editing work
  point-and-click on day one.
- **Frontmatter properties only** (no inline `field::`), for Bases
  compatibility.
- **A one-page setup checklist** (enable core Bases/Templates, set the
  template folder, optional plugins).

Optional plugins (Templater/QuickAdd auto-templating, Metadata Menu no-YAML
editing) are *documented, not bundled or required* (Charter:
dependency-minimal, not Obsidian-locked).

### H. Greenfield — one model, no compatibility layer

- **Faceting is the model.** Every recipe ships faceted; every shipped
  operation is re-keyed to facet-predicates in one pass. No dual model, no
  legacy `type:` read-tolerance, no per-recipe opt-out — nothing half done.
- **One-time kit re-authoring.** The kit's own catalog and starters are
  re-authored faceted-first. A fixed crosswalk maps each current fused `type`
  to facets (`medical-record → genre: record, subtype: medical`) as the
  authoring reference; content-type contributions and starter regeneration
  move together. RFC-0008's `type: source-note` examples likewise refine to
  `genre: note, subtype: source`. This is kit work, not a user-vault
  migration (there are no user vaults).
- **`wiki init --adopt` stays safe.** If a user later points the kit at their
  own pre-existing markdown folder, back-filling facets is an agent/manual
  job through `safe_write`, never a silent `wiki init` side effect.

## Alternatives considered

- **Do nothing (keep fused `type` + entity-kind folders).** Rejected: the
  two page-kind/folder problems persist and the kit keeps under-using the
  LLM. Pre-release, "do nothing" only locks in the weaker model before
  anyone depends on it.
- **Introduce a separate `domain` area axis (this RFC's earlier draft).**
  Rejected during reconciliation: RFC-0008's `workspaces:` already provides
  the multi-valued area axis. A second area field would duplicate it under a
  different name — the exact overload this model exists to avoid. The
  area axis is `workspaces:`; this RFC owns only the page-kind axis.
- **Pure-flat (no folders; everything in one directory + facets).** Rejected:
  unbrowsable in Obsidian's file explorer for the no-plugin user; the
  research is unanimous that large vaults want 5–10 shallow role folders.
- **Adopt PARA wholesale (Projects/Areas/Resources/Archive).** Rejected:
  PARA encodes lifecycle, responsibility, and reference as *folder
  locations* because it has no metadata layer — reproducing the
  Areas-vs-Resources fuzz, the Archive-strips-structure problem, and PARA's
  own silo critique. We keep PARA's *Project = bounded container* insight and
  drop its buckets in favor of facets. PARA also has no entity model, so it
  maps badly onto `people/` nodes.
- **Merge `library/` + `atlas/` into one folder.** Rejected on the
  value-tier/attention argument: mixing high-volume capture with low-volume
  synthesis buries the synthesis layer, worsened by LLM doc-generation. The
  Zettelkasten/LYT capture-vs-permanent split is load-bearing.
- **Typed relations (`project:`, `trip:`) instead of one `parent:`.**
  Rejected: the container's own `subtype` already says what kind it is, so a
  single `parent:` is simpler. (All relations are YAML frontmatter, never
  Dataview inline `field::` — Bases cannot read inline fields.)
- **Ship a dual / opt-in model (faceted *and* legacy folder model).**
  Rejected: with no vaults in the field there is no one to protect from a
  cutover, so opt-in is half-done complexity — two models to maintain — for
  zero migration benefit. Tier-3 friction is addressed by the manual
  affordances (§G) and the folder-fallback property, not by letting users
  avoid the model.

## Drawbacks

- **Couples to RFC-0008.** This RFC assumes the `workspaces:` axis and
  substrate/lens model from RFC-0008; if that proposal's follow-on specs
  change the axis name or shape, this RFC's facet set must track it. Mitigated
  by owning a disjoint axis (page-kind, not area) so the coupling is a
  reference, not an overlap.
- **Tier-3 residual friction is real and irreducible.** For a user with no
  community plugins and no agent, the two friction-killers — *auto-apply
  template on note creation* and *no-YAML dropdown editing* — are gated behind
  community plugins the kit cannot install. Core Obsidian Templates has no
  auto-apply-on-create. So faceting is heavier than folder-filing for that
  tier; the kit can only narrow the gap (templates + checklist + Bases).
- **Discipline cost.** Faceting pays off only if pages reliably carry their
  facets and relations. Off the template path (mobile, quick-capture,
  third-party apps) this is manual; only an agent re-scan backfills, and the
  linter only *detects* drift.
- **The runtime-dependency tension.** A robust emergent-promotion reuse check
  wants embedding similarity, which our pyyaml+pydantic-only runtime cannot
  provide without a new ADR-gated dependency. The initial string heuristic
  will over- or under-merge in cases an embedding check would catch.
- **One-time kit re-authoring is large.** Every operation contract re-keys
  from folder-globs to facet-predicates, and the catalog + starters are
  re-authored faceted-first, in one pass. The blast radius is contained to
  the kit (no user vaults), but it is a big single landing.
- **Naming and conceptual load.** `genre`, `subtype`, `moc`,
  capture-vs-synthesis, *plus* RFC-0008's `workspaces` — more vocabulary than
  "put it in a folder," and dependent on the explanation doc and READMEs.
- **Philosophy coupling.** Anchoring on LYT — a third-party, evolving,
  commercial framework — risks brand drift, and adopting its vocabulary
  (`atlas/`, MOC) raises the methodology-literacy bar. Accepted deliberately:
  the kit teaches the methodology regardless, so its real terms are more
  honest than half-crediting it. Mitigated by crediting the lineage and
  depending on no LYT *tool*.

## Prior art

- **Genre vs subject separation is established.** Dublin Core separates
  `Type` (genre) from `Subject` (aboutness)
  ([DCMI elements](https://www.dublincore.org/specifications/dublin-core/usageguide/elements/));
  DITA separates topic shape from subject; schema.org allows multi-typed
  entities + `additionalType`; FRBR layers content vs form. Our fused `type`
  is the enumerative trap
  [Ranganathan/PMEST](https://en.wikipedia.org/wiki/Faceted_classification)
  named in 1933.
- **Faceted design rules** — orthogonality, within-facet mutual exclusivity,
  small facet set, every-doc-every-facet —
  [Hearst/Flamenco](https://flamenco.berkeley.edu/papers/faceted-workshop06.pdf),
  [ANSI/NISO Z39.19](https://www.niso.org/publications/ansiniso-z3919-2005-r2010),
  [Hedden on polyhierarchy](https://www.hedden-information.com/polyhierarchy-in-taxonomies/).
- **PKM object-type models** confirm "kind separate from aboutness, surfaced
  in many views" (the same models RFC-0008 cites for `workspaces`):
  [Tana supertags](https://tana.inc/articles/intro-to-nodes-fields-and-supertags),
  [Anytype types + relations](https://doc.anytype.io/anytype-docs/basics/relations),
  [Notion multi-select + relations](https://www.notion.com/help/relations-and-rollups),
  [Capacities object types](https://docs.capacities.io/reference/content-types).
- **Organizing philosophy:** [LYT / ACE](https://blog.linkingyourthinking.com/notes/ace-folder-framework),
  [LYT Atlas + MOCs](https://notes.linkingyourthinking.com/Cards/MOCs+Overview),
  [Maps of Content guide](https://www.dsebastien.net/2022-05-15-maps-of-content/);
  capture-vs-synthesis from Zettelkasten (literature vs permanent notes).
  [PARA Projects vs Areas](https://fortelabs.com/blog/project-people-vs-area-people-are-you-running-a-sprint-or-a-marathon/)
  and its [known critiques](https://www.todoist.com/productivity-methods/para-method).
- **Manual maintenance in the Obsidian UI:** [Properties](https://obsidian.md/help/Editing+and+formatting/Properties)
  (native, autocomplete), [Bases](https://obsidian.rocks/getting-started-with-obsidian-bases/)
  (core, inline editing), [Metadata Menu](https://mdelobelle.github.io/metadatamenu/general/)
  (optional, no-YAML). Core Templates
  [has no auto-apply-on-create](https://obsidian.md/help/plugins/templates)
  (official help; [forum corroboration](https://forum.obsidian.md/t/automatic-template-when-create-a-new-note-templater/51717)).
- **Agent-grown schema (2024–26):** fixed-spine + emergent-leaves + two-gate
  human-accepted promotion — [EDC](https://arxiv.org/abs/2404.03868),
  [DIAL-KG](https://arxiv.org/abs/2603.20059) (validate-before-evolve),
  [AutoSchemaKG](https://arxiv.org/abs/2505.23628),
  [Mem0](https://arxiv.org/pdf/2504.19413) (supersede-don't-delete);
  promotion thresholds from [tag gardening](https://www.webology.org/2008/v5n3/a58.html).

## Unresolved questions

None outstanding. The questions raised during drafting (area axis → reuse
RFC-0008's `workspaces:`, drop the parallel `domain`; peak-folder name →
`atlas/`; container homing → uniform `efforts/<type>/<instance>/`; reuse
check → stdlib heuristic, embeddings deferred to an ADR; genre list → all 9
kept; operation re-keying → all-at-once, greenfield) were resolved in the
design phase and fold into the Proposal. Reviewers may still contest any.

## Follow-on artifacts

- **Charter amendment:** add the "Organizing philosophy" subsection to
  `docs/CHARTER.md` (this RFC is the required gate per the Charter-via-RFC
  rule).
- **ADR:** "Genre + subtype page-kind facets replace the fused `type`"
  (records the decision + the folders-key-stable-roles rule + the
  reuse-`workspaces`-not-`domain` reconciliation with RFC-0008).
- **ADR (deferred):** revisit an embeddings-based reuse check for emergent
  promotion (only if the stdlib heuristic proves insufficient).
- **Specs:** `docs/specs/faceted-frontmatter-schema/` (the new schema +
  managed regions + crosswalk, aligned to RFC-0008's `workspaces:` axis);
  `docs/specs/role-folders-and-containers/` (folder model, `container_mode`,
  `_index.md` MOC views); `docs/specs/capture-synthesis-gating/`
  (creation-gating + journal `facet_value.proposed`/synthesis-proposal
  events); `docs/specs/operations-and-search-rekey/` (re-key every operation
  contract **and** `wiki search`/`search.py` from folder-globs/`--type` to
  `--genre`/`--subtype`; `--tag` unchanged; `--status` retained but its
  accepted values shift per the §H crosswalk — `upcoming` dropped);
  `docs/specs/recipe-organization-model/` (all recipes faceted; uniform
  `efforts/` layout; coordinated with RFC-0008's workspace primitives).
- **Sequencing.** Follow-on specs land in dependency order: schema +
  crosswalk → role-folders/containers → operations-and-search re-key →
  recipe + starter regeneration. "Nothing half done" is the end-state, not a
  single PR; the first spec's plan owns the ordering.
- **Vault-side:** `core/files/CORE.md` rewrite to embody the philosophy;
  content-type template + Bases-view shipping; the setup checklist how-to.
- **Done:** `docs/guides/explanation/organizing-philosophy.md` (landed with
  this RFC).
