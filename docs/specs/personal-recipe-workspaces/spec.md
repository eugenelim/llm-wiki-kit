# Spec: personal-recipe-workspaces

- **Status:** Implementing <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0008 (workspace-as-lens — this is its deferred "Recipe update" follow-on); `docs/specs/workspace-primitive/spec.md` (the shipped machinery this consumes; its Model A invariant and CT-3/4/5 leave-untouched rule bind here too — and this spec **amends its AC-6 bootstrap path**, see below). The one-recipe-per-vault invariant and CT-3/4/5 agent-binding rules in `docs/specs/wiki-agents/spec.md` are a constraint this spec must **not** modify.

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

We are wiring the shipped `personal` recipe to **compose workspace primitives**, so that a
fresh `wiki init --recipe personal` lands a multi-area knowledge bank — with working lenses
and their `.base` views — out of the box, instead of one undifferentiated vault. This
delivers RFC-0008's deferred "Recipe update" follow-on, turning the workspace machinery
(shipped in `docs/specs/workspace-primitive/`) from "installable on demand" into "present by
default in the kit's reference personal vault."

The user is the single technically-comfortable author of a `personal` vault. Success, from
their perspective, after `wiki init --recipe personal <dir>`:

- The vault contains a **membership lens** `content-studio.base` (filtering notes whose
  `workspaces:` frontmatter contains `content-studio`) and a **cross-cutting lens**
  `planning.base` (an empty-scope lens that surveys *all* notes ordered by status), each with
  its own bootstrap note (`content-studio.bootstrap.md`, `planning.bootstrap.md`) — both
  rendered through the normal install path, the `.base` files byte-identical to the shipped
  templates, and the two bootstrap notes **coexisting** (no clobber).
- `wiki workspaces` run in that vault lists **both** rows —
  `content-studio` (scope `content-studio`, agent `personal-coordinator`, no operations) and
  `planning` (empty scope, agent `personal-coordinator`, operations `follow-up-tracker`,
  `weekly-digest`) — with no extra setup.
- `wiki agents` and the recipe's existing `agents:` block are **unchanged** — the two lenses
  reference the existing `personal-coordinator` agent and surface existing operations, but
  synthesize **no** new agent→operation execution binding (Model A). The CT-3/4/5 validators
  and the one-recipe-per-vault invariant are untouched.
- The recipe's closure grows by exactly two workspace primitives (`content-studio`,
  `planning`) and the dependencies they pull (all of which the personal closure already
  installs) — no new content-type or operation primitive enters the vault.

This spec ships a new cross-cutting `planning` workspace primitive (the first shipped
empty-scope lens — the path was only covered by synthetic fixtures before), composes it and
the existing `content-studio` into `recipes/personal.yaml`, and regenerates the committed
`personal`-rendered example so the projection invariant holds.

**One latent defect must be fixed for this to work.** Every workspace shipped to date used the
bare filename `files/bootstrap.md`, which `render_tree` writes to the same vault-root path
`bootstrap.md` (`llm_wiki_kit/render.py:151-166`). The workspace-primitive spec only ever
installed *one* workspace at a time, so the collision never surfaced. Composing two workspaces
into one recipe means the second-installed lens's bootstrap silently overwrites the first's
(`safe_write`'s no-drift `direct_write` disjunct, `write_helper.py:188-200`). This spec
therefore **namespaces the bootstrap note per lens** — `<name>.bootstrap.md`, symmetric with
the already-namespaced `<name>.base` — which requires renaming `content-studio`'s bootstrap and
**amending workspace-primitive spec AC-6 and its install test** (`tests/integration/test_install_workspace.py`)
in this same PR. Drift is a bug; the consuming spec fixes the contract it found broken.

## Boundaries

The three-tier guard that keeps an implementing agent inside the lines.
*Always do* applies without asking; *Ask first* requires human sign-off
before proceeding; *Never do* is a hard rule, even under time pressure.

### Always do

- Add `content-studio` and `planning` to `recipes/personal.yaml`'s `primitives:` list
  (alphabetical, one per line) and extend the closure-notes comment block to explain why each
  lens is in the default personal shape — matching the recipe's existing self-documenting
  style.
- Ship the new `planning` workspace under `templates/workspaces/planning/` mirroring the
  shape of `templates/workspaces/content-studio/`: a `primitive.yaml` (`kind: workspace`,
  empty/absent `scope`, `agent: personal-coordinator`, `operations: [follow-up-tracker,
  weekly-digest]`, `view: planning.base`, `bootstrap: planning.bootstrap.md`,
  `requires: [follow-up-tracker, personal-coordinator, weekly-digest]`), a verbatim
  `files/planning.base` cross-cutting view ordered by status (its `order:` block names
  `status`; no `workspaces.contains(...)` membership filter), and a
  `files/planning.bootstrap.md`.
- Namespace the bootstrap note per lens (`files/<name>.bootstrap.md`) so two workspaces in one
  recipe don't clobber a shared `bootstrap.md`. This means **renaming**
  `templates/workspaces/content-studio/files/bootstrap.md` →
  `content-studio.bootstrap.md` and updating its manifest `bootstrap:` field, then **amending**
  `docs/specs/workspace-primitive/spec.md` AC-6 (and `plan.md` T5) and
  `tests/integration/test_install_workspace.py` to assert the namespaced path — all in this PR.
- Run `python starters/regenerate.py --apply` in the same PR and commit the regenerated
  `personal`-rendered tree (the `conflict-pending` example) so
  `tests/integration/test_starters_regenerable.py::test_regenerate_check_mode_clean` stays
  green. The committed example is the source of truth's projection — regenerate it, don't
  hand-edit (K-0018).

### Ask first

- Adding any **new** content-type, operation, or agent primitive to satisfy a lens (the two
  lenses must resolve entirely within the existing personal closure; if one doesn't, that's a
  scope change to surface, not a quiet primitive addition).
- Wiring workspaces into any recipe **other than** `personal` (e.g. `work-os`) — RFC-0008
  lists that as "optional" and it is out of this spec's scope.
- Choosing a `planning.base` filter that hard-codes specific `status` values (the field is
  free-form, no enum) rather than ordering by status — a status-vocabulary assumption needs
  sign-off.
- Changing the bootstrap-naming scheme away from `<name>.bootstrap.md` at the vault root (e.g.
  to a `workspaces/<name>/` subfolder, which would also relocate the `.base` and is a larger
  amendment to the shipped workspace-primitive contract) — the per-lens-filename choice here is
  the minimal fix; a different layout needs sign-off.

### Never do

- **Never modify `recipes/personal.yaml`'s `agents:` block, `_validate_agent_bindings`, or
  any CT-3/4/5 validator.** The two lenses reference an existing agent and surface existing
  operations; they create **no** new execution binding (Model A). Two lenses (or a lens and
  the `agents:` block) naming overlapping operations is explicitly allowed and must raise no
  error.
- **Never add a new top-level directory or a runtime dependency.**
  `templates/workspaces/planning/` is a catalog entry under the existing `templates/`
  subtree; no new dep is needed (Charter Principle 3).
- **Never hand-edit the regenerated starter / example trees to patch a diff** — the
  regenerator is the source of truth; a hand-edited projection is drift waiting to break.

## Testing Strategy

- **Recipe composes both lenses (closure + resolution):** *goal-based / TDD.* Resolving
  `recipes/personal.yaml` includes `content-studio` and `planning` in the closure and raises
  no `RecipeError` — the existing recipe-resolution test surface (`test_recipes*.py`) plus a
  targeted assertion that both names land in the resolved closure. Why: the load-bearing
  outcome is "the recipe still resolves *with* the lenses," a compressible invariant.
- **No CT-5 regression from overlapping operations:** *TDD (regression + positive guard).*
  Resolving `personal` raises no error even though `planning.operations` (`follow-up-tracker`,
  `weekly-digest`) overlap the `personal-coordinator` `agents:` binding — *and* the resolved
  closure contains those two operations as `kind: operation` (a positive check that workspace
  reference validation actually ran, so the no-throw can't pass by the operations being skipped
  entirely). `tests/unit/test_recipes_agents.py` passes unmodified. Why: this is the Model A
  invariant under test — the one place this change could wrongly trip the agent-binding chain.
- **`planning` primitive validates, is the cross-cutting case, and is status-ordered:** *TDD.*
  The `planning` manifest passes `Primitive` validation with empty/absent `scope`,
  `list_workspaces` reports it with an empty scope, and its `.base` has no
  `workspaces.contains(...)` filter while `status` is the **first** entry in the view `order:`
  block. Why: the empty-scope lens had no shipped artifact before; this pins both its model
  shape and the cross-cutting-*by-status* semantic (status-primary ordering is the
  machine-checkable part of "ordered by status").
- **End-to-end `wiki init --recipe personal`:** *integration.* After init into a temp vault,
  `content-studio.base` and `planning.base` are byte-identical to their shipped templates, the
  two namespaced bootstrap notes (`content-studio.bootstrap.md`, `planning.bootstrap.md`) both
  exist as distinct files each byte-identical to its shipped template, and `wiki workspaces`
  prints exactly the two expected NAME/SCOPE/AGENT/OPERATIONS rows. Why: this is the
  user-visible "lands out of the box" outcome and the regression test for the bootstrap-clobber
  defect; it exercises render-through + journal + lister together.
- **Starters projection invariant:** *goal-based.*
  `python starters/regenerate.py --check` exits clean after the change is applied (CI gate
  `test_regenerate_check_mode_clean`). Why: the recipe change stales the committed projection;
  the check proves it was regenerated, not hand-patched.

## Acceptance Criteria

- [ ] **AC-1:** `recipes/personal.yaml` lists `content-studio` and `planning` in `primitives:`
      (alphabetical), with closure-note comments explaining each; its `agents:` block is
      byte-unchanged.
- [ ] **AC-2:** `templates/workspaces/planning/` ships `primitive.yaml` (`kind: workspace`,
      empty/absent `scope`, `agent: personal-coordinator`, `operations: [follow-up-tracker,
      weekly-digest]`, `view: planning.base`, `bootstrap: planning.bootstrap.md`, `requires:`
      resolving in the personal closure), `files/planning.base` (verbatim, cross-cutting — no
      `workspaces.contains(...)` filter, `status` is the **first** entry in the view `order:`
      block), and `files/planning.bootstrap.md`.
- [ ] **AC-3:** `content-studio`'s bootstrap is renamed to `files/content-studio.bootstrap.md`
      with its manifest `bootstrap:` updated, and every **non-changelog** `bootstrap.md`
      reference in the workspace-primitive artifacts is amended to the namespaced path:
      `workspace-primitive/spec.md` (the `After wiki add workspace:content-studio` checkbox that
      names "a `bootstrap.md`");
      `workspace-primitive/plan.md` (the T5 `bootstrap: bootstrap.md` and `files/bootstrap.md`
      lines, plus the Approach/Construction-tests/T5-test prose that names `bootstrap.md`);
      `tests/integration/test_install_workspace.py` (the `(vault / "bootstrap.md")` assertion
      **and** the module docstring). The **one** historical Changelog entry in
      `workspace-primitive/plan.md` (a single bullet recording the prior
      `files/bootstrap.md → bootstrap.md` correction) is left intact; a new Changelog entry
      records this rename.
- [ ] **AC-4:** Resolving `recipes/personal.yaml` includes both workspaces in the closure and
      raises no `RecipeError`; the `planning.operations` ↔ `personal-coordinator` operation
      overlap raises **no** error, and the resolved closure contains `follow-up-tracker` and
      `weekly-digest` as `kind: operation` (Model A: surfaced, not skipped).
- [ ] **AC-5:** `tests/unit/test_recipes_agents.py` passes **unmodified**, and
      `_validate_agent_bindings` has zero diff (reviewer-verified; see the plan's
      reviewer-checklist note).
- [ ] **AC-6:** After `wiki init --recipe personal` into a temp vault: `content-studio.base`
      and `planning.base` are byte-identical to the shipped templates; `content-studio.bootstrap.md`
      and `planning.bootstrap.md` both exist as distinct files, each byte-identical to its
      shipped template; `wiki workspaces` prints the `content-studio` and `planning` rows with
      the expected SCOPE/AGENT/OPERATIONS columns (planning's empty scope renders as
      `(all notes)`, the cross-cutting cell).
- [ ] **AC-7:** `python starters/regenerate.py --check` exits 0 (the committed
      `personal`-rendered `conflict-pending` example — which gains four net-new workspace
      artifacts: both `.base` files and both namespaced bootstrap notes — was regenerated in
      this PR).
- [ ] **AC-8:** `ruff check`, `ruff format --check`, `mypy`, and `pytest -m 'not slow'` all
      pass over `llm_wiki_kit tests`.

## Assumptions

- Technical: the full workspace-primitive machinery (kind, five model fields, verbatim `.base`
  install, recipe reference validation, `wiki workspaces` lister) is shipped on main (PR #125),
  so this task adds **no** kit Python code — only catalog + recipe + regenerated example
  (source: `llm_wiki_kit/models.py:94,166`, `primitives.py:1067,1086`, `cli.py:1196`).
- Technical: `wiki init --recipe <r>` records the recipe closure as installed in the journal,
  and `list_workspaces` derives its rows from that installed set, so composing the workspaces
  into `personal` suffices for `wiki workspaces` to list them (source:
  `primitives.py:1102-1126`).
- Technical: `content-studio` (`agent: personal-coordinator`) and the new `planning` lens
  (`agent: personal-coordinator`, operations `follow-up-tracker`/`weekly-digest`) resolve
  entirely inside the existing personal closure — `personal-coordinator` is `kind: agent`, the
  two operations are `kind: operation`, all already listed in `recipes/personal.yaml` (source:
  catalog `primitive.yaml` kinds).
- Technical: `planning` does not collide in the flat primitive *name* namespace (source:
  `find templates core -name 'planning*'` → empty).
- Technical: workspace `files/` render to the vault root by relative path, so a bare
  `files/bootstrap.md` *path*-collides across two workspaces in one recipe (the second clobbers
  the first via `safe_write`'s no-drift disjunct); bootstraps are therefore namespaced as
  `<name>.bootstrap.md`. The prior single-workspace installs never exercised this (source:
  `render.py:151-166`, `write_helper.py:188-200`; reviewer finding 2026-06-14).
- Technical: a cross-cutting lens is expressed by empty/absent `scope.workspaces`
  (`WorkspaceScope.workspaces` defaults to `[]`), its `.base` ordering by status rather than
  membership; `status` is a free-form string (no enum) so the `.base` orders rather than
  filters on it (source: `models.py:108`; `core/files/frontmatter.schema.yaml:50-52`;
  RFC-0008 §Unresolved "all notes" resolution).
- Process: changing `recipes/personal.yaml` stales the committed `personal`-rendered
  `conflict-pending` example, fixed by `python starters/regenerate.py --apply` in the same PR
  (source: knowledge entry K-0018; `starters/regenerate.py` docstring).
- Process: this is RFC-0008's explicitly deferred "Recipe update" follow-on; the
  one-recipe-per-vault invariant and CT-3/4/5 stay untouched — workspaces never feed CT-5
  (Model A) (source: `docs/specs/workspace-primitive/spec.md`; RFC-0008 §Follow-on artifacts).
- Product: ship a second, new cross-cutting `planning` lens alongside the existing
  `content-studio` and wire both into `personal` (rather than `content-studio` alone), with
  `planning` carrying `agent: personal-coordinator` and `operations: [follow-up-tracker,
  weekly-digest]` (source: user confirmation 2026-06-14).
