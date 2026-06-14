# Spec: workspace-primitive

- **Status:** Draft <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0008 (workspace-as-lens), RFC-0004 (agent identity primitives), ADR-0009 (headless `claude -p` invocation), ADR-0010 (`--agent` passthrough). The recipe agent-binding rules (CT-3/4/5) in `docs/specs/wiki-agents/spec.md` are a constraint this spec must **not** modify.

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

We are giving the kit a way to express **workspaces** — named, filtered *lenses* over a single
vault — so a technically-comfortable author can keep one knowledge bank (one vault, one journal,
one frontmatter schema) yet work inside distinct areas (e.g. content-studio, research, planning)
without fragmenting into multiple vaults. This implements the first follow-on artifact of
accepted RFC-0008.

A **workspace** is a new primitive kind composed by recipes like any other primitive. A workspace
declares: a `scope` (which notes the lens covers), a shipped Obsidian Bases `view` (`.base`) that
renders that scope, an optional set of `operations` surfaced in the lens, an optional `bootstrap`
note injected when a session is scoped to the lens, and an optional `agent` that **references an
existing** agent primitive (it does not mint a per-lens persona). Notes opt into lenses through a
new multi-valued `workspaces:` frontmatter field; because vault-page frontmatter is not
kit-validated, this field is a *discoverable convention* (declared in the shipped schema for
humans and Obsidian Bases), not a kit-enforced constraint.

Success, from the author's perspective:

- After `wiki add workspace:content-studio`, the vault contains a `content-studio.base` lens that,
  opened in Obsidian, shows exactly the notes whose `workspaces:` frontmatter contains
  `content-studio`, and nothing else.
- A note can carry `workspaces: [research, content-studio]` and appear in **both** lenses
  (multi-membership), with no duplication on disk.
- A workspace with an **empty or absent `scope`** is a *cross-cutting* lens: it covers all notes
  (e.g. a `planning` lens that surveys the whole bank by status), rather than filtering on
  membership.
- `wiki workspaces` lists the installed workspaces with their scope, agent, and operations —
  read-only. It mirrors `wiki agents`' *structure and behavior* (vault-scoped, header-then-rows, no
  journal write, empty→header-only→exit 0) but defines its **own** `NAME/SCOPE/AGENT/OPERATIONS`
  columns backed by a new row type (not `AgentRow`, which carries recipes).
- A recipe can compose several workspace primitives, and the existing one-recipe-per-vault
  invariant and CT-5 agent-binding rules are **unchanged** — workspaces never synthesize
  agent→operation execution bindings (Model A, per the agent-design investigation recorded in
  Assumptions).
- Scoping a `claude -p` session to a workspace is a **documented prompt-composition contract**
  that fits the ADR-0009/ADR-0010 argv with no new flag and no new CLI verb.

This spec ships the machinery plus **one** worked example workspace (`content-studio`). Wiring an
existing recipe (`personal`) to compose workspaces is deferred to a separate follow-up, per
RFC-0008's follow-on list.

## Boundaries

### Always do

- Wire `PrimitiveKind.WORKSPACE` at the sites that genuinely need it — the enum, the discovery
  catalog dir (`_CATALOG_DIRS`), the `wiki add` kind map (`_KIND_DIRS`), and the new lister — and
  **leave the exclusive kind-filter guards untouched** (e.g. `is PrimitiveKind.AGENT` /
  `is not PrimitiveKind.OPERATION` checks in `recipes.py`/`install.py`/`ingest.py`/`operations.py`/
  `doctor.py` correctly *exclude* a workspace and must not learn about it). Verify each exclusion is
  correct; do not add a WORKSPACE branch where the kind is legitimately irrelevant.
- Route every workspace file (the `.base` view, bootstrap note) into the vault through the
  existing render/`safe_write` path; `.base` files render **verbatim** (not interpolated).
- Keep the `workspaces:` frontmatter field a **convention**: declare it in the shipped
  `frontmatter.schema.yaml` for discoverability, but do not add kit-side page-frontmatter
  validation (the kit does not validate page YAML today).
- Make the five workspace manifest fields (`scope`, `agent`, `operations`, `bootstrap`, `view`)
  **optional** and reject them on non-workspace primitives via a model validator.

### Ask first

- Any change to the recipe agent-binding resolution chain or the CT-3/4/5 validators in
  `recipes.py` (this spec's Model A explicitly leaves them untouched — touching them is a scope
  change).
- Adding any CLI surface beyond the read-only `wiki workspaces` lister (e.g. a `wiki workspace
  enter` verb) — the enter-workspace contract is documentation-only in this spec.
- Generating a `.base` file from `scope` (rather than shipping it verbatim) — that introduces a
  view-renderer the kit doesn't have today.

### Never do

- **Never synthesize agent→operation execution bindings from a workspace's `agent:`/`operations:`
  fields, and never feed workspaces into CT-5.** Workspaces are lenses, not schedulers (Model A
  invariant). Execution bindings live only in the recipe `agents:` block.
- **Never add a runtime dependency** (Charter Principle 3 — requires an ADR) and **never add a new
  top-level directory** (`templates/workspaces/` is a catalog subdir, not a repo-root directory).
- Never make the kit parse `claude` stdout for semantics (ADR-0009), and never embed or inline an
  agent persona body (ADR-0010) — the kit passes an agent *name*, nothing more.

## Testing Strategy

- **`PrimitiveKind.WORKSPACE` + catalog/kind-map wiring** — *goal-based*: discovery picks up a
  `templates/workspaces/<name>/` primitive and `wiki add workspace:<name>` resolves the kind; a
  one-shot test asserts the workspace appears in the discovered catalog. (Enum-plumbing has no
  compressible invariant to TDD; the check is "it's wired everywhere.")
- **Five workspace-only manifest fields + reject-on-non-workspace validator** — *TDD*: pure
  Pydantic validation with a clear invariant (fields accepted on `kind: workspace`, rejected
  elsewhere), mirroring the existing routing-on-content-type validator.
- **Workspace reference validation at recipe-resolve time** (`agent` resolves to an installed
  `kind: agent`; each `operations:` entry resolves to an installed `kind: operation`; both must be
  in the closure) — *TDD*: a validation function with distinct error shapes, mirroring the
  CT-3/CT-4 tests in `test_recipes_agents.py`. **No CT-5-style uniqueness check** — that's the
  Model A invariant under test (two workspaces may surface the same operation).
- **`workspaces:` baseline schema field** — *goal-based*: the rendered `frontmatter.schema.yaml`
  in a fresh vault contains an optional `workspaces` list field; a grep/parse assertion suffices.
- **`.base` verbatim install** — *goal-based / integration*: after install, the vault's
  `content-studio.base` is byte-identical to the shipped template (Bases braces survive).
- **`wiki workspaces` lister** — *TDD + integration*: rows for installed workspaces with its own
  NAME/SCOPE/AGENT/OPERATIONS columns (a new row type, not `AgentRow`), empty set prints only the
  header and exits 0, non-vault exits with the standard error — mirroring `_cmd_agents`'s structure
  and empty/non-vault behavior, not its columns.
- **Enter-workspace contract** — *goal-based*: the documented argv is asserted byte-equal to the
  argv `wiki run --exec` builds today (pinned against `_build_argv`, `run.py:901`), so the doc fails
  if the real argv drifts — not "the doc agrees with itself." No new code path (it is a contract for
  a future UI / the user to drive `wiki run --exec`).
- **`content-studio` example workspace** — *goal-based*: installs cleanly into a temp vault and
  also serves as the integration fixture for the lister and `.base` tests.

## Acceptance Criteria

- [ ] `PrimitiveKind.WORKSPACE` exists; `discover_primitives` finds primitives under
      `templates/workspaces/`; `wiki add workspace:<name>` resolves and installs one.
- [ ] The `Primitive` model accepts `scope`, `agent`, `operations`, `bootstrap`, `view` on
      `kind: workspace` and raises a validation error if any appears on another kind.
- [ ] Recipe resolution raises a clear `RecipeError` when a workspace's `agent` is not an installed
      `kind: agent` in the closure, or an `operations:` entry is not an installed `kind: operation`
      in the closure; it raises **no** error when two workspaces list the same operation.
- [ ] `test_recipes_agents.py` passes **untouched** (regression proof the CT-3/4/5 validators and
      the `agents:` resolution chain are unchanged). *(Reviewer note: confirm the diff has no edits
      to `_validate_agent_bindings`.)*
- [ ] A workspace whose `scope` is empty or absent resolves and renders a `.base` that covers all
      notes (cross-cutting lens), rather than filtering on `workspaces` membership.
- [ ] A fresh vault's `frontmatter.schema.yaml` declares an optional multi-valued `workspaces`
      field; no kit code validates page `workspaces:` values.
- [ ] After `wiki add workspace:content-studio`, the vault contains `content-studio.base`
      byte-identical to the shipped template, and a `bootstrap.md`.
- [ ] `wiki workspaces` in a vault with the example installed prints a NAME/SCOPE/AGENT/OPERATIONS
      table; in an empty vault prints only the header and exits 0; outside a vault exits with the
      standard "not a wiki vault" error.
- [ ] `docs/` documents the enter-workspace `claude -p` prompt-scoping contract; the documented
      argv is byte-equal to the argv `wiki run --exec` actually builds today (pinned against
      `_build_argv`, `run.py:901` — where the `claude` argv is constructed; `wiki run --exec` enters
      via `_cmd_run_exec`, `cli.py:1724`), so it fails if the argv drifts — and adds no new flag.
- [ ] `ruff check`, `ruff format --check`, `mypy`, and `pytest -m 'not slow'` all pass over
      `llm_wiki_kit tests`.

## Assumptions

- Technical: `PrimitiveKind` is a 5-member `StrEnum` used via `is`/`is not` guards (no `match`
  statements). Only a few sites need WORKSPACE wiring (enum, `_CATALOG_DIRS`, `_KIND_DIRS`, lister);
  the rest are exclusive filters that must stay untouched (source: `llm_wiki_kit/models.py:53-58`;
  grep of `PrimitiveKind` usages — all `is`/`==`, zero `match`).
- Technical: `Primitive` is a strict model (`extra="forbid"`); new fields need first-class
  declaration + a kind-gated validator mirroring `_routing_only_on_content_types` (source:
  `llm_wiki_kit/models.py:45`, `:95-182`, `:174-180`).
- Technical: CT-3/4/5 agent-binding validation lives in `_validate_agent_bindings`, called from
  `resolve_recipe_primitives` after closure (source: `llm_wiki_kit/recipes.py:192-262`, `:187`).
- Technical: `.base` files render verbatim — not in `INTERPOLATED_FILES` — so Bases `{...}` syntax
  is safe (source: `llm_wiki_kit/render.py:47-55` — the `INTERPOLATED_FILES` frozenset; `.base`
  absent).
- Technical: vault-page YAML frontmatter is not kit-validated; `workspaces:` is convention +
  discoverable schema only (source: `render.py`/`install.py` write-through; no page-frontmatter
  validator found).
- Technical: `workspaces:` is a universal optional field, so it belongs in the **baseline**
  `fields:` of the shipped schema (next to `tags`/`source`), not a managed region (source:
  `core/files/frontmatter.schema.yaml:41-62`).
- Technical: catalog dirs are plural → new dir `templates/workspaces/`; add to `_CATALOG_DIRS`
  (`primitives.py:78-86`) and `_KIND_DIRS` (`cli.py:231-237`) (source: `ls templates/`).
- Technical: `wiki workspaces` mirrors the read-only `_cmd_outcomes`/`_cmd_agents` listers
  (source: `cli.py:1097-1147`, `:1156-1185`).
- Technical: `wiki run --exec` exists and rides the ADR-0009/0010 `claude -p` path (entry
  `_cmd_run_exec`, `cli.py:1724`; argv built in `_build_argv`, `run.py:901`); lens scoping is
  prompt-body only, so no new flag/verb is needed.
- Technical: the flat primitive namespace makes `research` collide (infrastructure primitive
  exists); a research lens uses a distinct name like `research-desk` (source: `ls
  templates/infrastructure/`; `templates/*/research-desk` absent).
- Process: agent-design decision — a workspace's agent is **optional and references an existing
  agent** (Model A), not a required per-lens persona; corroborated by Anthropic's skills-first
  guidance, the Claude-Cowork OSS cluster, and OpenLoomi's `skills/`-no-`agents/` structure
  (source: user confirmation 2026-06-14; web research in conversation).
- Process: ship machinery + one example workspace; defer wiring the `personal` recipe to a
  follow-up; one sequenced spec (precedent: `wiki-agents`/`wiki-run-exec`/`primitive-sideload`
  specs each bundle model+recipe+CLI) (source: user confirmation 2026-06-14).
- Process: no `wiki workspace enter` verb — the enter-workspace contract is doc-only (source: user
  confirmation 2026-06-14).
- Product: the user is the single technically-comfortable author structuring one vault into areas;
  downstream readers consume the vault in Obsidian (source: RFC-0005 mission; user confirmation
  2026-06-14).
