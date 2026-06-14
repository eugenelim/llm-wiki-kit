# RFC-0008: Workspace-as-lens — one knowledge bank, many filtered workspaces

- **Status:** Accepted <!-- Draft | Open | Final Comment Period | Accepted | Rejected | Withdrawn -->
- **Author:** eugenelim
- **Date opened:** 2026-06-13
- **Date closed:** 2026-06-13
- **Related:** Builds on RFC-0005 (narrow mission) and RFC-0001 (v2 primitives/recipes);
  uses RFC-0004 (agent identity) and RFC-0007 (primitive contribution model);
  constrained by ADR-0009 (headless `claude -p` invocation contract), ADR-0010
  (`--agent` passthrough), and Charter
  Principle 5 (library-not-application). Touches the one-recipe-per-vault invariant
  in `docs/specs/wiki-agents/spec.md` and the Tier-3 recipe-inheritance note in
  `docs/architecture/overview.md`. Spawns a follow-on UI RFC (see §Follow-on artifacts).

## Summary

Today the kit ships single-purpose recipes: one `wiki init --recipe <name>` produces
one vault shaped for one audience. A user who wants a content-creation area *and* a
home-projects area *and* a research area either crams them into one undifferentiated
knowledge bank or runs several disconnected vaults — and a fact known to two areas
(a person, a source document) has nowhere clean to live.

This RFC introduces **workspace-as-lens**: keep one knowledge bank (one vault, one
journal, one frontmatter schema) as the *substrate*, and express each area as a
**lens** over it — a filtered, named view with its own in-scope content, owning agent,
operations, and default Obsidian Bases view. A note can belong to several workspaces at
once. This is the substrate/lens split every leading tool converges on (Notion
teamspaces, Tana supertags, Obsidian Bases, Claude/ChatGPT Projects), expressed in the
kit's existing primitive/recipe vocabulary.

Concretely: a new `workspace` primitive kind, a multi-valued `workspaces:` frontmatter
axis realized through `.base` views, and a documented `claude -p` "enter-workspace"
prompt-scoping contract. **The kit stays a library** — it ships the schema axis, the
lenses, and the contracts; any GUI/document-viewer is a companion artifact carried by a
separate follow-on RFC, so this proposal does not reverse RFC-0005 or soften Principle 5.

Crucially, this **preserves the one-recipe-per-vault invariant**: the multiplicity moves
into the recipe (which now composes several workspace lenses), not into the vault.

## Motivation

### The single-purpose recipe forces a bad choice

The kit's composition model is "one recipe → one vault → one purpose." The architecture
states it plainly: recipes "compose primitives into audience-specific bundles — `family`,
`work-os`, `personal`" and "don't extend each other in v2.0" (`docs/architecture/overview.md:167-169`).
The journal hard-codes this: "the journal records exactly one recipe per vault"
(`docs/specs/wiki-agents/spec.md:443-444`).

That's the right call for *isolating a kit user's whole life from their whole job*. But it
gives no answer to the within-a-life structure the user actually has. A single person
running a `personal` vault wants distinct working areas — drafting blog/social content,
running home projects, doing research, weekly planning — that are **not** separate lives and
should **not** be separate stores. Splitting them into separate vaults fragments the
knowledge bank: a source you researched can't feed the blog you're drafting without
duplication, and the weekly-planning view can't see across areas. Cramming them into one
flat bank loses all the scoping that makes each area workable.

### The charter's "fuzzy overlap" concern is about the wrong axis

The charter warns against fuzzy overlap — "an engineer using both gets a wiki for
stakeholders/decisions/customer-feedback and a separate repo for specs/ADRs/plans, **not a
fuzzy overlap**" (`docs/CHARTER.md:71-75`). That boundary is about *wiki content vs. engineering-team
artifacts*, and it stands. It is not an argument against structuring life-areas *within*
a wiki. A person known to both your research and your blog is the opposite of fuzzy
overlap — duplicating them across two vaults is the real mess. Workspace-as-lens keeps the
charter's clean boundary (no engineering primitives in the wiki) while giving the
in-wiki areas a first-class shape.

### The substrate already exists; one field is missing

`frontmatter.schema.yaml` is contributed-to by every content-type primitive
(`docs/architecture/overview.md:155`) and is exactly what Obsidian Bases queries. The
journal is the single source of truth for vault state (`overview.md:171-193`). The only
thing missing to express lenses is a frontmatter axis that says *which areas a note
belongs to* — and a way to render the resulting views. Both are additive.

### Recipe inheritance is already parked — this is the cheaper unlock

The architecture notes that recipe inheritance "ships as a Tier 3 roadmap item" if it
becomes useful (`overview.md:169`). Workspace-as-lens delivers most of the value people
would want from recipe composition — several coherent areas in one vault — *without*
recipe inheritance, by composing workspace primitives inside a single recipe. The
one-recipe-per-vault invariant is untouched.

## Proposal

### The substrate/lens split

- **Substrate (exactly one per vault):** one folder, one `.wiki.journal/journal.jsonl`,
  one `frontmatter.schema.yaml`, one recipe recorded in `VaultInitEvent.recipe`. Unchanged.
- **Lens (zero or more per vault):** a *workspace* — a named, filtered view of the
  substrate with its own in-scope content, owning agent, operations, and default Bases
  view. Realized entirely through frontmatter + `.base` files; it owns no separate store.

A vault with no workspaces behaves exactly as today (one implicit "everything" view), so
existing vaults are unaffected.

### 1. A new `workspace` primitive kind

Add a sixth primitive kind alongside `ontology`, `content-type`, `operation`,
`infrastructure`, `agent`. A workspace primitive lives at
`templates/workspaces/<name>/` and ships:

```yaml
# templates/workspaces/content-studio/primitive.yaml
name: content-studio
kind: workspace
version: 0.1.0
description: Idea bank, drafts, and source notes for blog and social content.
requires:                       # bare names, matching existing primitive.yaml convention
  - draft
  - idea
  - idea-bank-refill
scope:                          # what the lens shows; compiled into the shipped .base
  workspaces: [content-studio]  # notes whose frontmatter `workspaces` contains this
agent: content-curator          # optional RFC-0004 agent that owns the lens
operations:                     # operations that run within this lens
  - idea-bank-refill
  - draft-pipeline-status
bootstrap: files/bootstrap.md    # lens context injected into a scoped claude -p session
# files/ ships: content-studio.base (the default view) + bootstrap.md
```

Names are bare (not `kind:name`-qualified) to match the existing `requires:` and recipe
`primitives:` convention. Because the catalog is a flat name lookup, a workspace name must be
unique across *all* primitive kinds — and the `research` infrastructure primitive already
exists, so a research lens would need a distinct name (e.g. `research-desk`). This
namespace pressure is noted in Unresolved questions.

The recipe composes workspace primitives like any other primitive — the recipe stays the
single composition unit, so the one-recipe-per-vault invariant holds. A multi-area recipe
simply lists several workspace primitives by bare name:

```yaml
# recipes/personal.yaml (illustrative future shape)
primitives:
  - content-studio
  - home-projects
  - research-desk
  - planning          # a cross-cutting lens that shows everything by status
```

**Reconciling lens `agent:`/`operations:` with the recipe `agents:` block.** Agent→operation
binding already lives at the recipe level, and `docs/specs/wiki-agents/spec.md:446-457` pins
*one-agent-per-operation-per-recipe* (CT-5) with a refuse-on-conflict resolution chain. The
workspace primitive's `agent:`/`operations:` fields must not fork that mechanism. The intended
shape: at compose time the kit **derives** recipe-level `agents:` bindings from the composed
workspace primitives, and a CT-5 violation across two lenses (the same operation owned by two
agents) is a **recipe validation error** — not a silent last-writer-wins. The exact derivation
rule is called out in Unresolved questions and is the first thing the follow-on spec must pin.

### 2. The `workspaces` frontmatter axis

Introduce a multi-valued `workspaces: list[str]` field on vault pages, sibling to `type:`
(page-kind stays on `type`; area-membership goes on `workspaces`). Whether this is a *schema
addition* or simply a *new convention* depends on whether vault-page frontmatter is
schema-validated today or free-form — an open point the follow-on spec must confirm against
`models.py` (see Unresolved questions). Either way the field is additive and optional.
Multi-valued is the load-bearing choice — it lets one note belong to several lenses (the
Tana-supertag move), e.g. a source note tagged `workspaces: [research, content-studio]`.

```yaml
---
type: source-note
workspaces: [research, content-studio]
status: active
---
```

Page-creation and ingest stamp `workspaces` from the active lens; the field is optional
(absent = belongs to the implicit default view only), so it is fully backward compatible.

### 3. Bases-realized views (documentation-verified)

Each workspace primitive ships a `<name>.base` Obsidian Bases file that filters the shared
markdown by list-membership. This is **verified against the Bases documentation** — `.base`
filters support `.contains()` on list properties ([Bases syntax][bases-syntax]).
Bench-confirmation in a live Obsidian build (≥1.9.10) that a multi-membership note renders in
both its lenses is still pending; the proof vault under `.context/workspace-as-lens-proto/`
exists to be opened for exactly that check (see Unresolved questions):

```yaml
# templates/workspaces/research/files/research.base
filters:
  and:
    - workspaces.contains("research")
views:
  - type: table
    name: Research
    order: [file.name, type, status, file.mtime]
```

`file.hasTag`, `file.inFolder`, and `file.hasLink` are also available for lenses that
prefer folder- or tag-scoping. This is the native "filterable views" mechanism — no
plugin, notes stay portable markdown (Charter §Scope `docs/CHARTER.md:84-86`, no Obsidian
lock-in: the `.base` file is additive metadata, the notes work in any editor).

### 4. The `claude -p` "enter-workspace" contract

Scoping an LLM session to a lens is **purely a prompt-body concern** and fits the pinned argv
shape — `claude -p --add-dir <vault> --permission-mode dontAsk --output-format json` (ADR-0009)
plus the `[--agent <name>]` passthrough (ADR-0010) — without modification. The kit injects the
lens's scope, agent, and
bootstrap into the prompt body; it points Claude at the `.base` view rather than
enumerating matching files (the kit has no query engine and must not grow one):

```
claude -p --add-dir <vault> --permission-mode dontAsk --output-format json \
  --agent content-curator \
  "You are operating in the 'content-studio' workspace of this vault. In-scope notes
   are those whose frontmatter `workspaces` contains 'content-studio' (live view:
   content-studio.base). Treat other notes as read-only context. Bootstrap: <bootstrap>.
   <task>."
```

This stays inside ADR-0009's boundary: the prohibition is *one-directional* — the kit must
not parse Claude's **stdout** for semantics (`adr/0009:71-77`). Injecting scope on the
**input** side is exactly the free-to-evolve prompt body the ADR sanctions. The kit's
visible surface is a read-only lister, `wiki workspaces` (mirroring `wiki agents` /
`wiki outcomes`), and lens-scoped dispatch reuses the existing `wiki run --exec` path.

### 5. Source-preservation contract (enables the document viewer)

Today ingest converts a source into a derived markdown page. To support a document
viewer, ingest gains a contract: **preserve the original binary and link it from the
derived page** (a `source_file:` frontmatter pointer to a stored attachment). This is a
library-shaped contract — the kit preserves and links; *rendering* the original is the
companion UI's job (§6). Obsidian renders PDF inline already; the real gap is DOCX/PPTX/XLSX,
which it cannot preview — that is what a viewer adds. (This dovetails with the pending
Docling ingest ADR, which would produce these derived pages in the first place.)

### 6. UI and document viewer — companion artifact, separate RFC

A local `claude -p`-powered UI (a workspace switcher + lens-scoped chat + a side-by-side
original↔derived document viewer, in the spirit of the Projects "Sources tab") is
explicitly **out of scope for the kit**. RFC-0005 placed a GUI "outside the kit and
probably outside this project entirely" (`rfc/0005:346-354`), and Principle 5
(library-not-application) is load-bearing. This RFC therefore ships only the *contracts* a
UI needs — the `workspaces` axis, the `.base` lenses, the enter-workspace prompt-scoping
contract, and the source-preservation contract — and routes the UI itself to a dedicated
follow-on RFC where its repo boundary, dependency footprint, and Principle 5 relationship
get argued on their own terms.

### Migration

Fully backward compatible. Existing vaults have no `workspaces` field and no workspace
primitives → one implicit default view, behaving exactly as today. No journal schema
change (`workspaces` is page frontmatter, not a journal event). Adopting workspaces is
opt-in per recipe; a `wiki add workspace:<name>` follows the existing `wiki add` path.

## Alternatives considered

### (A) Do nothing — keep single-purpose recipes, tell users to run multiple vaults

The status quo. *Rejected:* it forces the fragmentation the whole proposal exists to fix —
a fact known to two areas must be duplicated or orphaned, and no cross-area view (weekly
planning) is possible. The cost compounds as users accrete areas; the kit's own `personal`
recipe already gestures at multiple areas (identity, cooking, trips, decisions) with no way
to scope between them.

### (B) Multiple recipes per vault / recipe inheritance

Let a vault record several recipes, or let recipes extend each other. *Rejected:* breaks the
one-recipe-per-vault journal invariant (`wiki-agents:443-444`) — a load-bearing
simplification the agent-binding resolution chain depends on — and pulls forward the Tier-3
recipe-inheritance item (`overview.md:169`) with all its ambiguity (whose `agents:` block
wins? whose variables?). Workspace-as-lens gets the same user-facing outcome (many areas, one
vault) while keeping the recipe as the single composition unit. Strictly cheaper.

### (C) Folder-based areas (one top-level folder per workspace)

Use `wiki/<area>/` folders as the workspace boundary and filter by `file.inFolder(...)`.
*Rejected as the primary axis:* a file lives in exactly one folder, so folders cannot
express multi-membership — the source-note-shared-by-two-lenses case, which is the point.
PKM practice agrees: folders answer "where does this live," properties answer "what is this
about" ([PARA vs Johnny Decimal][para-jd]). Folder-scoping remains *available* as a lens
filter for areas that genuinely are folder-shaped; it just isn't the axis.

### (D) Tag-namespace lenses (`#ws/research`) instead of a `workspaces` property

Model membership as tags. *Rejected as primary:* pollutes the topical tag namespace and
conflates the lens axis with subject tags. We confirmed `.contains()` works on list
properties, so the cleaner `workspaces: []` property is viable; tags stay a documented
fallback only if a user's tooling can't query properties.

### (E) Ship the UI inside the kit

Build the workspace switcher + viewer as kit code. *Rejected:* directly reverses RFC-0005
and softens Principle 5, the kit's sharpest tiebreaker. The library/application split is
worth more than the convenience of one repo. The UI gets its own RFC and likely its own
repo, parallel to the starter-distribution precedent (RFC-0006).

## Drawbacks

- **A new primitive kind is a real surface-area increase.** Six kinds instead of five;
  `primitives.py`, discovery, the recipe resolver, and docs all grow a case. Mitigation: it
  reuses the existing primitive machinery (manifest, `files/`, `requires:`) and the existing
  `wiki add` path; it is not a new subsystem.
- **`workspaces` frontmatter must be stamped consistently or lenses leak.** A page created
  outside a lens won't carry the field and will fall out of every workspace view. Mitigation:
  page-creation/ingest stamp it from the active lens; `wiki doctor` can flag pages with no
  `workspaces` value as "unfiled" (a future check).
- **Lens scoping is advisory, not enforced.** A `claude -p` session is *told* to treat
  out-of-scope notes as read-only context; nothing prevents it reading or writing across the
  whole `--add-dir` vault. Mitigation: this is honest about the boundary (Principle 1) — the
  lens is an organizing convention, not a security boundary, and the RFC says so plainly.
- **Bases is Obsidian-specific.** The `.base` files only render in Obsidian; another editor
  sees inert markdown + an unused `.base` file. Mitigation: notes and the `workspaces`
  property stay fully portable; the lens *rendering* degrades gracefully to "all notes,"
  which is the pre-RFC behavior. No lock-in (Charter §Scope).
- **Splitting the UI out front-loads contract design with no visible payoff yet.** Users get
  schema + `.base` files but no switcher/viewer until the follow-on RFC ships. Mitigation:
  the `.base` lenses are independently useful inside Obsidian today; the UI is upside, not a
  prerequisite.

## Prior art

- **Notion** — workspace (billing/identity boundary) vs. **teamspace** (free, unlimited,
  scoped lens with its own content + permissions). Validates the substrate/lens split at
  scale; teamspaces being cheap-and-many is exactly the lens posture here.
  ([Notion docs][notion])
- **Tana** — supertags are retroactive, opt-in structure, and **one node can carry several
  supertags and appear in several databases at once**. Direct precedent for the multi-valued
  `workspaces` axis and multi-membership lenses. ([Tana supertags][tana])
- **Capacities** — object types defined upfront and **queryable across the whole
  workspace**; gentler than Tana. Argues for typed, queryable structure over freeform.
  ([Capacities][capacities])
- **Obsidian Bases** (core since 1.9.10) — `.base` files give database-like, filterable
  views over the same markdown's YAML; `.contains()` on list properties is supported. The
  native realization of "filterable views" this RFC depends on. ([Bases syntax][bases-syntax],
  [overview][bases-overview])
- **Claude / ChatGPT Projects** — a workspace = persistent instructions + scoped Sources +
  scoped history. The lens-as-context-scope model behind §4, and the "Sources tab" behind the
  document-viewer motivation in §5–6. ([Projects comparison][projects])
- **PARA vs. Johnny Decimal** — "folders answer *where does this live*; tags/properties
  answer *what is this about*." Argues for a frontmatter axis over folder-isolation
  (alternative C). ([PARA vs JD][para-jd])
- **Content-pipeline practice** — idea-bank → validate → outline → draft → edit → publish,
  one idea repurposed across formats; shapes the `content-studio` lens example.
  ([content pipeline][pipeline])
- **In-repo precedent:** RFC-0001 (primitives/recipes), RFC-0004 (agent identities the lens
  reuses), RFC-0007 (whose sideload model would extend to workspace primitives once this RFC
  adds the kind), ADR-0009 + ADR-0010 (the `claude -p` + `--agent` contract §4 rides on), and
  the Tier-3 recipe-inheritance note
  (`overview.md:169`) this RFC makes largely unnecessary.

## Unresolved questions

- **Is `workspace` a primitive kind, or a thin recipe-level block?** *Lean: primitive kind.*
  It keeps Principle 4 ("recipes compose, don't extend") intact and makes lenses sideloadable
  per RFC-0007. A recipe-level block would avoid the sixth kind but would make recipes carry
  composition logic they don't carry today. Reviewers should confirm the kind is worth it.
- **How are lens `agent:`/`operations:` fields reconciled into the recipe `agents:` block
  without breaking CT-5 (one-agent-per-op-per-recipe)?** *Lean: the kit derives recipe-level
  bindings from composed workspace primitives at compose time, and a cross-lens CT-5 conflict
  is a recipe validation error, not last-writer-wins.* The exact derivation rule must be pinned
  by the follow-on spec; it's the highest-risk design detail.
- **Workspace names share the flat primitive namespace — is that acceptable, or do workspaces
  need their own namespace?** *Lean: accept the flat namespace (workspace names must be unique
  across all kinds; `research` is already taken, so a research lens is `research-desk`).* A
  reviewer may prefer kind-scoped names to avoid surprising collisions.
- **Bench-confirmation of multi-membership `.base` rendering in a live Obsidian build.**
  *Lean: low risk — the syntax is documentation-verified — but open `.context/workspace-as-lens-proto/vault/`
  in Obsidian ≥1.9.10 before the spec relies on it.* Carried over from the proto's open item.
- **Where is `workspaces` validated, and how strict?** *Lean: add it to the page frontmatter
  schema as an optional list, validated leniently (unknown workspace names warn, don't fail).*
  Open question whether vault-page frontmatter is schema-validated at all today, or free-form —
  needs confirmation against `models.py` during spec.
- **Does `wiki doctor` gain an "unfiled note" check (pages with empty `workspaces`)?**
  *Lean: yes, as a warning, in a follow-up — not in the first spec.* Naming it now so the
  first spec doesn't preclude it.
- **How does a cross-cutting lens (e.g. `planning`) that should see *everything* express its
  scope?** *Lean: an empty/absent `scope.workspaces` means "all notes," with the `.base`
  filtering by status/recency instead of membership.* Reviewers may prefer an explicit
  `scope: all` marker for legibility.
- **UI repo boundary and dependency footprint** — deferred wholesale to the follow-on UI RFC.
  *Lean: separate repo, parallel to starters.* Not resolved here by design.

## Outcome

**Accepted 2026-06-13.** The substrate/lens model, the `workspace` primitive kind, the
multi-valued `workspaces:` frontmatter axis realized through Obsidian Bases, and the
library-only boundary (UI/viewer deferred to a follow-on RFC) are adopted. Implementation
proceeds via the follow-on artifacts below. The highest-risk detail to pin first is the
recipe-level agent-binding derivation rule (CT-5 across composed lenses); the load-bearing
mechanism (`.contains()` multi-membership) is documentation-verified and should be
bench-confirmed in Obsidian before the spec relies on it.

## Follow-on artifacts

Filled in on acceptance. Expected:

- **ADR:** record the substrate/lens decision and the `workspace` primitive kind (the
  architecturally significant choices), and the source-preservation ingest contract.
- **Spec:** `docs/specs/workspace-primitive/` — the `workspace` kind, the `workspaces`
  frontmatter axis, the shipped `.base` template, the `wiki workspaces` lister, and the
  enter-workspace prompt-scoping contract. TDD for the resolver/schema changes; integration
  tests for `wiki add workspace:<name>` and `wiki workspaces`.
- **Recipe update:** evolve `personal` (and optionally `work-os`) to compose workspace
  primitives, with a worked multi-lens example.
- **Architecture:** update `docs/architecture/overview.md` (sixth primitive kind; lens model;
  retire or downgrade the Tier-3 recipe-inheritance note).
- **Follow-on RFC (UI + document viewer):** a `claude -p`-powered local UI — workspace
  switcher, lens-scoped chat, side-by-side original↔derived document viewer — argued on its
  own terms (repo boundary, deps, Principle 5). Out of scope here.

[notion]: https://www.notion.com/help/guides/teamspaces-give-teams-home-for-important-work
[tana]: https://medium.com/@bah.lindt/supertags-in-tana-940a10e5a977
[capacities]: https://docs.capacities.io/migration/switching-from-tana
[bases-syntax]: https://obsidian.md/help/bases/syntax
[bases-overview]: https://obsidian.md/help/bases
[projects]: https://elephas.app/blog/claude-projects-vs-chatgpt-projects
[para-jd]: https://studio-obsidian.com/obsidian-folder-structure/
[pipeline]: https://www.successful-blog.com/1/build-content-pipeline/
