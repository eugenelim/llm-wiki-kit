# Plan: workspace-primitive

- **Spec:** [`spec.md`](spec.md)
- **Status:** Executing <!-- Drafting | Executing | Done -->

> **Plan contract:** this is the implementation strategy. Unlike the spec, this
> document is allowed to change as you learn. When it changes substantially
> (a different approach, not just a re-ordering), note why in the changelog
> at the bottom.

## Approach

The change is **additive plumbing plus one example primitive** — no existing behavior changes.
The shape: introduce `PrimitiveKind.WORKSPACE` and a `templates/workspaces/` catalog dir, extend
the strict `Primitive` model with five optional workspace-only fields, add a recipe-resolve-time
validator that checks a workspace's `agent`/`operations` references resolve in the closure (a
sibling to the existing CT-3/CT-4 checks, deliberately **without** any CT-5-style uniqueness rule),
declare a universal optional `workspaces:` field in the shipped baseline schema, ship one
`content-studio` example workspace (manifest + `.base` + `bootstrap.md`), add a read-only `wiki
workspaces` lister modelled on `wiki agents`, and document the enter-workspace `claude -p` contract.

Order of operations: the enum + catalog wiring (T1) is the foundation; the model fields (T2) and
the schema field (T3) are independent of each other; reference validation (T4) needs the fields;
the example primitive (T5) needs the fields + schema; the lister (T6) needs the enum + the example
as a fixture; the doc contract (T7) is standalone. **The riskiest part is T1** — `PrimitiveKind` is
read via `is`/`is not` guards at ~12 sites (there are **no `match` statements**, so `mypy` can't
flag a missed site); most are *exclusive filters* that must stay untouched, and the danger is
editing one that should be left alone or missing the few that need wiring. The audit is an explicit
behavioral test, not a compiler check. The Model A discipline (T4) is the second risk: the temptation under EXECUTE
will be to "helpfully" derive agent bindings — the spec's Never-do and a negative test guard it.

The testing story: TDD for the model validators and the reference validator (compressible
invariants); goal-based checks for enum wiring, the schema field, and verbatim `.base` install;
TDD+integration for the lister; doc-consistency check for the enter-workspace contract.

## Constraints

- **RFC-0008** — the accepted design this implements; substrate/lens split, workspace primitive
  kind, `workspaces:` axis, Bases views, library-only (UI deferred).
- **RFC-0004 + ADR-0010** — agents are vault-side identity files referenced by *name*; the kit
  never embeds personas. A workspace `agent:` references an *existing* agent primitive.
- **ADR-0009** — the headless `claude -p` argv; the enter-workspace contract adds no flag and the
  kit never parses stdout.
- **`docs/specs/wiki-agents/spec.md` (CT-3/4/5)** — **must not be modified.** Workspaces never feed
  CT-5; execution bindings stay in the recipe `agents:` block.
- **Charter Principle 3** — no new runtime dependency (would need an ADR); none is needed here.

## Construction tests

Most construction tests live under **Tasks** below. Cross-cutting only:

**Integration tests:**
- End-to-end: `wiki init` a temp vault, `wiki add workspace:content-studio`, assert
  `content-studio.base` is byte-identical to the shipped template and `bootstrap.md` exists, then
  `wiki workspaces` prints the expected NAME/SCOPE/AGENT/OPERATIONS row. (Mirrors
  `tests/integration/test_install_agent.py`.)
- Regression guard: `tests/unit/test_recipes_agents.py` runs **unmodified** and green — proof CT-5
  is untouched.

**Manual verification:**
- Open the temp vault's `content-studio.base` in Obsidian ≥1.9.10; confirm a note with
  `workspaces: [content-studio]` appears and one without it does not. (One-time bench-confirm of
  the Bases `.contains()` mechanism RFC-0008 left pending; not automated.)

## Tasks

### T1: `PrimitiveKind.WORKSPACE` exists and is wired at the sites that need it

**Depends on:** none

**Tests:**
- *Goal-based*: a fixture `kind: workspace` primitive written into a **`tmp_path` catalog dir**
  (not the real `templates/`) is returned by `discover_primitives`, and `wiki add workspace:<name>`
  resolves the kind via `_KIND_DIRS`. Verifies AC-1. (Uses a temp catalog so T1 doesn't depend on
  the T5 example existing.)
- *Goal-based (enumerated audit)*: an explicit test that, for a `kind: workspace` primitive,
  asserts the correct behavior at each **exclusive filter** named below — a workspace is *excluded*
  from ingest routing, operation-contract enumeration, and `list_agents`, and is *not* mistaken for
  an agent or operation. (There are **no `match` statements on `PrimitiveKind`** — all usages are
  `is`/`is not` guards — so `mypy` exhaustiveness cannot catch a missed site; the audit must be an
  explicit behavioral test.)

**Approach:**
- Add `WORKSPACE = "workspace"` to `PrimitiveKind` (`models.py:53-58`).
- **Sites that must learn about WORKSPACE:** `_CATALOG_DIRS` (`primitives.py:78-86`, add
  `"workspaces"`); `_KIND_DIRS` (`cli.py:231-237`, add `workspace → "workspaces"`); the new lister
  (T6). That is the whole "add a branch" set.
- **Sites that must stay untouched (verify, don't edit):** the exclusive guards
  `recipes.py:232/246/381`, `install.py`, `doctor.py`, `ingest.py`, `operations.py`,
  `primitives.py` agent/operation filters — these `is`/`is not` checks correctly *exclude* a
  workspace. Confirm each still does the right thing for the new kind; add no WORKSPACE branch.
- Ship the catalog dir empty via `templates/workspaces/.gitkeep` until T5 adds the example.

**Done when:** discovery + `wiki add` resolve a workspace from a temp catalog, the enumerated-audit
test confirms the exclusive filters still exclude workspaces, and gates pass.

### T2: `Primitive` accepts the five workspace fields, rejects them elsewhere

**Depends on:** T1

**Tests:**
- *TDD*: `scope`, `agent`, `operations`, `bootstrap`, `view` validate on `kind: workspace`.
- *TDD*: each of the five raises a `ValidationError` on a `kind: content-type` (and one other kind)
  primitive — mirroring `_routing_only_on_content_types`.
- *TDD*: all five are optional (a minimal `kind: workspace` manifest with none of them validates).
  Verifies AC-2.
- *TDD*: a workspace with empty or absent `scope` validates (the cross-cutting-lens case; the
  "covers all notes" semantic is exercised by the lister in T6 and the contract in T7). Supports
  the cross-cutting-scope AC.

**Approach:**
- Add to `Primitive` (`models.py:95-182`): `scope: WorkspaceScope | None = None`,
  `agent: str | None = None`, `operations: list[str] = []`, `bootstrap: str | None = None`,
  `view: str | None = None`. Define a small `WorkspaceScope` model (`workspaces: list[str] = []`;
  empty/absent ⇒ "all notes", per RFC-0008's cross-cutting-lens resolution).
- Add a model validator `_workspace_fields_only_on_workspaces` mirroring
  `_routing_only_on_content_types` (`models.py:174-180`).

**Done when:** the model tests pass and the validator rejects misuse with a clear message.

### T3: Baseline `frontmatter.schema.yaml` declares an optional `workspaces` field

**Depends on:** none

**Tests:**
- *Goal-based*: render a fresh vault's schema; assert the parsed YAML's `fields.workspaces` is
  `{type: list, items: string, optional: true}`. Verifies AC-5.
- *Goal-based*: assert no kit code path validates a page's `workspaces:` value (grep/structural —
  the field is convention-only).

**Approach:**
- Add `workspaces:` to the baseline `fields:` block in `core/files/frontmatter.schema.yaml`
  (after `source:`, `:57-59`), as an optional string-list. No managed region (it is universal).
- Add a one-line comment in the schema header noting `workspaces:` opts a note into lenses.

**Done when:** a freshly rendered schema declares the field and tests confirm it is unvalidated.

### T4: Recipe resolution validates workspace `agent`/`operations` references — without CT-5

**Depends on:** T2

**Tests:**
- *TDD*: a recipe whose closure includes a workspace with `agent: X` where `X` is not an installed
  `kind: agent` raises `RecipeError` (distinct message). Mirrors the CT-3/CT-4 tests.
- *TDD*: a workspace `operations:` entry that is not an installed `kind: operation` raises
  `RecipeError`.
- *TDD (the Model A guard)*: **two** workspaces listing the **same** operation resolve with **no**
  error. Verifies AC-3 and the AC-4 invariant.
- *Regression*: `test_recipes_agents.py` passes unmodified.

**Approach:**
- Add `_validate_workspace_references(recipe, closed)` in `recipes.py`, called from
  `resolve_recipe_primitives` right after `_validate_agent_bindings` (`recipes.py:187`).
- For each `kind: workspace` primitive in the closure: if `agent` set, assert it's in the closure
  with `kind == AGENT`; for each `operations` entry, assert it's in the closure with
  `kind == OPERATION`. Reuse the CT-3/CT-4 error-shape style. **Do not** track a
  `seen_operations` map — there is no uniqueness constraint for workspaces.
- Leave `_validate_agent_bindings` untouched.

**Done when:** the reference tests pass, the same-operation-two-workspaces test passes, and the
diff shows zero edits to `_validate_agent_bindings`.

### T5: `content-studio` example workspace installs cleanly

**Depends on:** T2, T3

**Tests:**
- *Goal-based / integration*: `wiki add workspace:content-studio` into a temp vault produces
  `content-studio.base` byte-identical to the shipped template and a `bootstrap.md`. Verifies AC-6.
- *Goal-based*: the example's manifest passes `Primitive` validation and recipe-reference
  validation (its `agent`, if set, resolves).

**Approach:**
- Create `templates/workspaces/content-studio/`:
  - `primitive.yaml`: `kind: workspace`, `scope: {workspaces: [content-studio]}`,
    `view: content-studio.base`, `bootstrap: bootstrap.md`, `operations: []`, and
    `agent: personal-coordinator` with `requires: [personal-coordinator]` (demonstrates Model A's
    *reuse an existing agent* — `personal-coordinator` already exists).
  - `files/content-studio.base`: a Bases view filtering `workspaces.contains("content-studio")`
    (verbatim; braces safe).
  - `files/bootstrap.md`: the lens context for an enter-workspace session.

**Done when:** the example installs and the `.base` lands byte-identical in the vault.

### T6: `wiki workspaces` lists installed workspaces (read-only)

**Depends on:** T1, T5

**Tests:**
- *TDD/integration*: with `content-studio` installed, prints a NAME/SCOPE/AGENT/OPERATIONS table
  including its row.
- *TDD*: empty vault prints only the header and exits 0; run outside a vault exits with the
  standard "not a wiki vault" error. Verifies AC-7. Mirrors `_cmd_agents` tests.

**Approach:**
- Add `_cmd_workspaces` in `cli.py` mirroring `_cmd_agents`'s *structure* (`:1156-1185`):
  vault-scoped, read the journal-derived installed set, walk the catalog for `kind: workspace`,
  print a header + rows, empty→header-only→exit 0. Wire the subparser via `build_parser` like
  `agents`/`outcomes`.
- Define a **new** row type (e.g. `WorkspaceRow(name, scope, agent, operations)` in
  `primitives.py`) and `NAME\tSCOPE\tAGENT\tOPERATIONS` columns — do **not** reuse `AgentRow`
  (`primitives.py:867`), which carries `recipes` not `scope`.

**Done when:** the lister tests pass and output matches the documented columns.

### T7: Enter-workspace `claude -p` contract is documented and consistent with ADR-0009/0010

**Depends on:** T2

**Tests:**
- *Goal-based*: a test asserts the argv string in the doc is byte-equal to the argv
  `wiki run --exec` builds today (compared against `_build_argv`, `run.py:901` — the actual argv
  builder; `_cmd_run_exec` at `cli.py:1724` is the delegating entry point), so it fails if the argv
  drifts — not "doc agrees with doc." No new flag. Verifies AC-8.

**Approach:**
- Add a short section to `docs/architecture/` (or a `docs/guides/explanation/` note) describing how
  a workspace scopes a `claude -p` session: inject the workspace's `bootstrap` + scope
  (`workspaces contains <name>`, pointing at the `.base`) into the prompt body, pass the optional
  `agent` via `--agent`, reuse the existing `wiki run --exec` path. State explicitly: no new CLI
  verb, no stdout parsing, prompt-body only.

**Done when:** the doc exists and its argv matches the ADRs (no new flag), confirmed by the
doc-consistency check.

## Rollout

Additive and reversible. No existing vault is affected (no `workspaces` field, no workspace
primitives ⇒ unchanged behavior). Ships in the kit; users opt in via `wiki add workspace:<name>`.
No migration, no journal schema change. Wiring the `personal` recipe to compose workspaces is a
separate follow-up PR.

## Risks

- **Wrong-site edit or missed wiring (T1).** Since the kind is read via `is`/`is not` guards (no
  `match`), `mypy` can't help. The danger is two-sided: adding a WORKSPACE branch to an exclusive
  filter that should ignore it, or missing one of the few sites that need wiring. Mitigation: T1's
  enumerated-audit test asserts the exclusive filters still *exclude* workspaces, and the
  must-wire set is explicitly enumerated (enum, `_CATALOG_DIRS`, `_KIND_DIRS`, lister).
- **Model A drift (T4).** The implementer may be tempted to derive agent bindings "for
  convenience." Mitigation: the spec's Never-do, the negative test (two workspaces, same op, no
  error), and the AC-4 "diff shows no edits to `_validate_agent_bindings`" check.
- **`.base` not byte-identical after render.** If `.base` were ever added to `INTERPOLATED_FILES`,
  brace syntax would break. Mitigation: T5's byte-identical assertion catches it.

## Changelog

- 2026-06-14: initial plan.
- 2026-06-14: T5 example `bootstrap` value corrected from `files/bootstrap.md`
  to `bootstrap.md` — both `view` and `bootstrap` reference the *installed*
  vault-relative path (where the `files/` tree flattens to), so the
  enter-workspace driver this spec documents finds the note where it actually
  lands. The two declarative references are now consistent.
