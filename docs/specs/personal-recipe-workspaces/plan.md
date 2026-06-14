# Plan: personal-recipe-workspaces

- **Spec:** [`spec.md`](spec.md)
- **Status:** Done <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

The change is **catalog + recipe + one latent-defect fix + regenerated projection** — still no
*new* kit Python. The workspace-primitive machinery (PR #125) already discovers
`templates/workspaces/<name>/`, renders `.base`/bootstrap verbatim through the install path,
validates workspace `agent`/`operations` references at recipe-resolve time, and lists installed
workspaces via `wiki workspaces`. This spec mostly *exercises* that machinery from the
`personal` recipe — but composing two workspaces surfaces a defect the single-workspace path
never hit: both ship `files/bootstrap.md`, which `render_tree` writes to the same vault-root
`bootstrap.md`, so the second-installed lens clobbers the first. The fix is to namespace the
bootstrap as `<name>.bootstrap.md` (symmetric with `<name>.base`), which forces a small
amendment to the already-shipped `content-studio` workspace and the workspace-primitive spec.

Shape and order: ship the new `planning` workspace primitive (T1) and namespace the bootstrap
path across workspaces (T2) — these are independent. Then compose `content-studio` + `planning`
into `recipes/personal.yaml` (T3), where recipe resolution and the Model A no-CT-5 invariant get
proven. Then regenerate the committed `personal`-rendered example (T4) so the projection check
stays green. Finally an end-to-end test that a fresh `wiki init --recipe personal` lands both
lenses (with both bootstraps coexisting) and `wiki workspaces` lists them (T5). T1–T3 carry the
compressible-invariant tests (manifest validation, closure resolution, no-CT-5); T4 and T5 are
goal-based / integration.

The riskiest part is **T3**: the `planning` lens surfaces `follow-up-tracker` and
`weekly-digest`, which the `personal-coordinator` `agents:` binding already runs. The Model A
invariant says this overlap must raise **no** error — the temptation is to "reconcile" it. The
guard is the unmodified `test_recipes_agents.py` plus a no-error resolution test *paired with a
positive check* that the operations still resolve in the closure (so the no-throw can't pass by
the operations being skipped). The second risk is the bootstrap clobber (T2) — caught by T5's
two-distinct-files assertion; the third is forgetting projection regeneration (T4) — caught by
the starters check.

## Constraints

- **RFC-0008** — this is its deferred "Recipe update" follow-on; substrate/lens split, the
  workspace kind, the `workspaces:` axis, Bases views, library-only.
- **`docs/specs/workspace-primitive/spec.md`** — the shipped machinery this consumes; its
  Model A invariant (workspaces never synthesize agent→operation bindings, never feed CT-5)
  and its CT-3/4/5 leave-untouched rule bind here.
- **`docs/specs/wiki-agents/spec.md` (CT-3/4/5, one-recipe-per-vault)** — **must not be
  modified.** The recipe `agents:` block and `_validate_agent_bindings` stay byte-unchanged.
- **Charter Principle 3** — no new runtime dependency; none needed. No new top-level directory;
  `templates/workspaces/planning/` is an existing-subtree catalog entry.
- **Knowledge K-0018** — a recipe change stales the committed `personal`-rendered projection;
  regenerate with `python starters/regenerate.py --apply` in the same PR, never hand-edit.

## Construction tests

Most construction tests live under **Tasks** below. Cross-cutting only:

**Integration tests:**
- End-to-end: `wiki init --recipe personal` into a `tmp_path` vault; assert `content-studio.base`
  and `planning.base` are byte-identical to the shipped templates, `content-studio.bootstrap.md`
  and `planning.bootstrap.md` both exist as distinct byte-identical files, and `wiki workspaces`
  prints exactly the `content-studio` + `planning` rows with the expected columns (planning
  SCOPE empty). (Mirrors existing `tests/integration` vault tests.)
- Regression guard: `tests/unit/test_recipes_agents.py` runs **unmodified** and green — proof
  CT-3/4/5 and the `agents:` resolution chain are untouched.
- Projection invariant: `python starters/regenerate.py --check` exits 0
  (`tests/integration/test_starters_regenerable.py::test_regenerate_check_mode_clean`).

**Reviewer-checklist items (not test artifacts — diff inspection):**
- The diff has **zero edits** to `_validate_agent_bindings` and **zero edits** to
  `tests/unit/test_recipes_agents.py` (CT-3/4/5 untouched). These are confirmed by reading the
  diff, not by a runnable test; AC-4 is satisfied when both hold.

**Manual verification:**
- Open the temp vault's `planning.base` in Obsidian ≥1.9.10; confirm it surveys all notes
  ordered by status (the empty-scope cross-cutting lens, first shipped artifact for that path).
  Not automated.

## Tasks

### T1: `planning` cross-cutting workspace primitive ships and validates

**Depends on:** none

**Tests:**
- *TDD*: the `planning` `primitive.yaml` parses as a `Primitive` with `kind == WORKSPACE`,
  empty/absent `scope`, `agent == "personal-coordinator"`,
  `operations == ["follow-up-tracker", "weekly-digest"]`. Verifies the AC-2 manifest shape.
- *Goal-based*: `discover_primitives(templates/)` returns `planning` as `kind: workspace`; its
  `files/planning.base` carries no `workspaces.contains(...)` line and `status` is the **first**
  entry in the view `order:` list (parse the YAML, assert `order[0] == "status"`). Verifies the
  cross-cutting-*by-status* semantic — status-primary is the machine-checkable part of "ordered
  by status".

**Approach:**
- Create `templates/workspaces/planning/primitive.yaml` mirroring
  `templates/workspaces/content-studio/primitive.yaml`: `name: planning`, `kind: workspace`,
  `version: 0.1.0`, a description, `requires: [follow-up-tracker, personal-coordinator,
  weekly-digest]`, **no** `scope:` (or empty), `agent: personal-coordinator`,
  `operations: [follow-up-tracker, weekly-digest]`, `view: planning.base`,
  `bootstrap: planning.bootstrap.md`.
- Create `files/planning.base`: a verbatim Bases table over *all* notes (no membership
  filter), ordered by `status` first then `modified` (`status` is `order[0]`), with a
  header comment explaining it's the cross-cutting lens and why there's no
  `workspaces.contains(...)`.
- Create `files/planning.bootstrap.md`: the enter-workspace context for a vault-wide planning
  session (it surveys everything by status; the `personal-coordinator` agent is the companion).

**Done when:** the manifest validates, discovery finds it as a workspace, and the `.base` has
no membership filter while its `order:` names `status`.

### T2: workspace bootstrap notes are namespaced per lens (no clobber)

**Depends on:** none

**Tests:**
- *TDD*: `load_primitive(content-studio)` has `bootstrap == "content-studio.bootstrap.md"` and
  the file `templates/workspaces/content-studio/files/content-studio.bootstrap.md` exists (the
  bare `files/bootstrap.md` is gone).
- *Goal-based*: `enumerate_rendered_paths` (or `_iter_files_relative`) over the two workspaces'
  `files/` trees yields two **distinct** vault-relative bootstrap paths — no shared
  `bootstrap.md`. This is the regression assertion for the clobber defect at the render layer.
  Together these verify AC-3 (the content-studio rename + amendment).

**Approach:**
- Rename `templates/workspaces/content-studio/files/bootstrap.md` →
  `content-studio.bootstrap.md`; update its manifest `bootstrap:` field
  (`bootstrap: bootstrap.md` → `bootstrap: content-studio.bootstrap.md`).
- Amend every **non-changelog** `bootstrap.md` reference in the workspace-primitive artifacts.
  `grep -n bootstrap.md docs/specs/workspace-primitive/{spec,plan}.md tests/integration/test_install_workspace.py`
  enumerates them; the concrete sites today are:
  - `workspace-primitive/spec.md:137` — the `After wiki add workspace:content-studio` checkbox
    ("and a `bootstrap.md`"). **Change.**
  - `workspace-primitive/plan.md` — `:176` (`bootstrap: bootstrap.md`) and `:181`
    (`files/bootstrap.md`) are the contractual T5 sites; `:19`, `:54`, `:169` are descriptive
    prose ("manifest + `.base` + `bootstrap.md`", "`bootstrap.md` exists", "a `bootstrap.md`").
    **Change all five** to the namespaced path for accuracy; **leave the historical Changelog
    bullet** (`:249-253`, recording the prior `files/bootstrap.md → bootstrap.md` correction)
    intact.
  - `tests/integration/test_install_workspace.py` — the `(vault / "bootstrap.md")` assertion
    (`:42`) **and** the module docstring (`:5`). **Change both.**
  - Add a one-line entry to `workspace-primitive/plan.md`'s Changelog recording this rename and
    why (the multi-lens clobber found here).
- Note: `wiki add workspace:<name>` (the install path the content-studio test uses) and
  `wiki init --recipe personal` (T5's path) both flatten `files/<name>.bootstrap.md` to the
  vault-root `<name>.bootstrap.md` through the **same** `render_tree`/`_iter_files_relative`
  walk (`install.py` → `render.py:151-166`), so the rename cannot pass one entry while breaking
  the other; T5 makes the recipe-path coverage explicit.

**Done when:** the content-studio install test (amended) passes against the namespaced path,
the render-layer test shows two distinct bootstrap paths, no `files/bootstrap.md` remains under
`templates/workspaces/`, and the only **bare** (un-namespaced) `bootstrap.md` matches from
`grep -rEn '(^|[^.[:alnum:]-])bootstrap\.md' docs/specs/workspace-primitive tests/integration/test_install_workspace.py`
— a pattern that excludes `content-studio.bootstrap.md` / `planning.bootstrap.md` — are
Changelog lines in `workspace-primitive/plan.md` (the prior-correction entry plus the new
rename entry; every contractual and prose reference outside the Changelog is namespaced).

### T3: `recipes/personal.yaml` composes both lenses and still resolves (Model A holds)

**Depends on:** T1, T2

**Tests:**
- *TDD*: resolving `recipes/personal.yaml` returns a closure containing `content-studio` and
  `planning`, raising no `RecipeError`. Verifies AC-4 (closure clause).
- *TDD (Model A guard, no-throw + positive)*: resolving `personal` raises **no** error even
  though `planning.operations` (`follow-up-tracker`, `weekly-digest`) overlap the
  `personal-coordinator` `agents:` binding — **and** the resolved closure contains
  `follow-up-tracker` and `weekly-digest` as `kind: operation` (so the no-throw can't pass by
  the workspace operations being silently skipped). Verifies AC-4's no-error + "surfaced, not
  skipped" clauses.

**Approach:**
- Add `content-studio` and `planning` to the `primitives:` list in `recipes/personal.yaml`
  (alphabetical placement: `content-studio` before `decision`, `planning` before `recipe`).
- Extend the closure-notes comment block with one bullet per lens explaining why it's in the
  default personal shape (content-studio = drafting/publishing lens; planning = cross-cutting
  survey-by-status lens) and noting both reuse `personal-coordinator` (Model A, no new
  binding).
- Leave the `agents:` block byte-unchanged. **Do not** touch `_validate_agent_bindings` or
  `tests/unit/test_recipes_agents.py` (reviewer-checklist item, AC-4).

**Done when:** the recipe resolves with both lenses in the closure, the Model A guard test is
green, and `test_recipes_agents.py` is untouched and passing.

### T4: committed `personal`-rendered projection is regenerated

**Depends on:** T1, T2, T3

**Tests:**
- *Goal-based*: `python starters/regenerate.py --check` exits 0 (CI gate
  `test_regenerate_check_mode_clean`). Verifies AC-7.

**Approach:**
- Run `python starters/regenerate.py --apply`; commit the regenerated `personal`-rendered tree
  under `docs/guides/how-to/_examples/conflict-pending/`. The current committed example has
  **no** workspace artifacts, so this regen is **not** a no-op: expect four net-new files in the
  example diff — `content-studio.base`, `planning.base`, `content-studio.bootstrap.md`,
  `planning.bootstrap.md` — plus the journal lines their install events produce. Do **not**
  hand-edit (K-0018).

**Done when:** `regenerate.py --check` is clean and the regenerated tree is committed.

### T5: a fresh `wiki init --recipe personal` lands both lenses (both bootstraps) and lists them

**Depends on:** T1, T2, T3

**Tests:**
- *Integration*: `wiki init --recipe personal` into `tmp_path`; assert `content-studio.base`
  and `planning.base` byte-identical to the shipped templates, `content-studio.bootstrap.md`
  and `planning.bootstrap.md` both present as **distinct** files each byte-identical to its
  shipped template (the clobber regression), and `wiki workspaces` output contains the
  `content-studio` and `planning` rows with expected SCOPE/AGENT/OPERATIONS (planning SCOPE
  empty). Verifies AC-6 (init/listing + bootstrap coexistence).

**Approach:**
- Add an integration test (new file or extend an existing `personal`-recipe init test) that
  drives `wiki init --recipe personal` and `wiki workspaces` against a temp vault and asserts
  the rendered lens files, both bootstrap files, and the two lister rows.

**Done when:** the integration test is green, both bootstraps coexist, and the lister shows
both rows out of the box.

## Rollout

Additive and reversible. No existing vault is affected — vaults are recreated from the recipe
on `wiki init`; the change only alters what a *new* `personal` vault lands with. No journal
schema change, no migration. Reverting is removing the two `primitives:` lines and the
`planning/` catalog entry, restoring content-studio's bare `bootstrap.md` (and its spec/test),
then regenerating. The content-studio bootstrap rename is the one change that touches an
already-shipped artifact; existing vaults are unaffected (they are not re-rendered).

## Risks

- **Bootstrap clobber (T2).** Two workspaces shipping `files/bootstrap.md` collide at the
  vault root; the prior single-workspace path never exercised it. Mitigation: T2 namespaces the
  bootstrap as `<name>.bootstrap.md` and amends the content-studio install test; T5's
  two-distinct-files assertion is the end-to-end regression guard.
- **Accidentally tripping CT-5 (T3).** The `planning.operations` ↔ `personal-coordinator`
  overlap is exactly the case Model A allows; an implementer "reconciling" it would break the
  invariant. Mitigation: the unmodified `test_recipes_agents.py` plus the no-error resolution
  test paired with the positive "operations still resolve" check, and the AC-4 "no edits to
  `_validate_agent_bindings`" reviewer check.
- **Forgetting the projection regeneration (T4).** A green feature test set with a stale
  committed example. Mitigation: T4 is a first-class task and the starters check is a CI gate.
- **`planning.base` brace/quote drift on render.** If `.base` were interpolated, the Bases
  syntax would break. Mitigation: T5's byte-identical assertion (the workspace-primitive spec
  already keeps `.base` out of `INTERPOLATED_FILES`).

## Changelog

- 2026-06-14: initial plan.
- 2026-06-14: spec-mode review surfaced a bootstrap path-collision (two workspaces both ship
  `files/bootstrap.md` → same vault-root path → second clobbers first). Added T2 to namespace
  the bootstrap as `<name>.bootstrap.md` (renaming content-studio's and amending the
  workspace-primitive spec AC-6 + its install test); re-classified the e2e task as integration
  and made it assert two distinct bootstrap files; paired the Model A no-throw test with a
  positive closure-resolution check; moved the "no diff to `_validate_agent_bindings`" item to a
  reviewer-checklist note. Tasks renumbered (was T1–T4, now T1–T5).
