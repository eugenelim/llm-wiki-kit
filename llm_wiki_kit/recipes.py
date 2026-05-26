"""Load recipes from disk and compose them against the primitive catalog.

The migration plan (RFC-0001 Task 9) names three surfaces:

* :func:`load_recipe` reads a single ``recipes/<name>.yaml`` and validates
  it against the Pydantic :class:`~llm_wiki_kit.models.Recipe` model.
  Pydantic errors flow through
  :class:`~llm_wiki_kit.errors.ValidationError`; everything else (missing
  file, malformed YAML, non-mapping top level) flows through
  :class:`~llm_wiki_kit.errors.RecipeError`.

* :func:`discover_recipes` walks ``recipes_dir/*.yaml`` (top-level only,
  alphabetical) and loads each. A bad file is fatal — silent skips would
  hide typos.

* :func:`resolve_recipe_primitives` is the composition step. It takes a
  recipe plus a flat catalog of available primitives (typically the
  union of ``primitives.discover_primitives(templates_dir)`` and the
  ``core`` primitive loaded separately), walks the transitive closure of
  the recipe's ``primitives:`` list under ``requires:``, prepends
  ``core`` if the recipe didn't already name it, and hands the closed
  set to :func:`~llm_wiki_kit.primitives.resolve_dependencies` for
  install ordering.

**Why the always-include-core policy lives here.** ``primitives.py``
deliberately stays recipe-agnostic — its
:func:`~llm_wiki_kit.primitives.resolve_dependencies` operates on a
*closed* set and does not synthesize entries. The "every vault gets
``core``" rule is a recipe-layer policy, so it belongs in this module's
closure step. If a recipe explicitly lists ``core``, we don't double-add
it; if it omits ``core``, we prepend it before closure expansion.

**Why a missing catalog primitive is a hard error.** Recipes are
authored content. A recipe naming a primitive the catalog doesn't ship
is either a typo or a missing primitive — both of which a user should
hear about at ``wiki init`` time, not at first ``wiki run``. The closure
step raises :class:`~llm_wiki_kit.errors.RecipeError` rather than
reusing :class:`~llm_wiki_kit.errors.PrimitiveError` because the failure
is a recipe-vs-catalog mismatch, not a primitive-loader concern: the
primitives all loaded fine; the recipe asked for something that doesn't
exist.

**Variables.** :attr:`~llm_wiki_kit.models.Recipe.variables` is a flat
``dict[str, str]`` of render-context defaults (``vault_name``,
``recipe_name``, recipe-specific overrides). Recipes may declare
defaults here; the installer (Task 10) composes them with CLI arguments
to produce the final render context. This module reads the field but
does not interpret it — composition is the installer's job.

**Filename ↔ recipe.name coupling.** :func:`load_recipe` does not
enforce that ``recipes/family.yaml`` declares ``name: family``. Keeping
the loader lenient leaves the field authoritative; ``wiki doctor``
(Task 12) is where authoring drift like that gets surfaced.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.errors import RecipeError, ValidationError
from llm_wiki_kit.journal import read_events, replay_state
from llm_wiki_kit.models import Primitive, PrimitiveKind, Recipe, VaultState
from llm_wiki_kit.primitives import (
    discover_primitives,
    load_operation_contract,
    resolve_dependencies,
)

CORE_PRIMITIVE_NAME = "core"


def load_recipe(path: Path) -> Recipe:
    """Load and validate a single recipe file.

    ``path`` is the ``.yaml`` file itself (not a directory). The function
    does not cross-check the filename against the declared ``name``
    field — the field is authoritative.
    """

    if not path.exists():
        raise RecipeError(f"recipe file does not exist: {path}")
    if not path.is_file():
        raise RecipeError(f"recipe path is not a file: {path}")

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RecipeError(f"cannot read {path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise RecipeError(f"malformed YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise RecipeError(f"{path} must contain a YAML mapping, got {type(data).__name__}")

    try:
        return Recipe.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(f"recipe at {path}", exc) from exc


def discover_recipes(recipes_dir: Path) -> list[Recipe]:
    """Load every ``recipes_dir/*.yaml`` (top-level only).

    Returns an empty list when ``recipes_dir`` doesn't exist (a fresh
    repo before any recipe has been authored is not an error). Files
    that aren't ``.yaml`` are skipped; subdirectories are not recursed
    into. A malformed recipe is fatal: silent skips would hide typos.
    """

    if not recipes_dir.exists():
        return []

    recipes: list[Recipe] = []
    for entry in sorted(recipes_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix != ".yaml":
            continue
        recipes.append(load_recipe(entry))

    recipes.sort(key=lambda r: r.name)
    return recipes


def resolve_recipe_primitives(
    recipe: Recipe,
    catalog: list[Primitive],
) -> list[Primitive]:
    """Expand ``recipe.primitives`` to its install-ordered closure.

    Behavior in order:

    1. Always-include-core: ``core`` is added to the requested set if the
       recipe didn't already list it. ``core`` must exist in
       ``catalog``; otherwise :class:`RecipeError` is raised.
    2. Closure expansion: starting from the requested names, walk every
       primitive's ``requires:`` (looked up in ``catalog``) until the
       set is closed under transitive ``requires:``. Any name that
       isn't in ``catalog`` raises :class:`RecipeError`.
    3. Agent-binding validation: every key in ``recipe.agents`` and
       every operation in its ``runs:`` list must be in the closure
       with the matching kind, and no operation may appear in two
       agents' ``runs:`` lists. Delegated to
       :func:`_validate_agent_bindings`; a no-op when ``agents`` is
       empty. See ``docs/specs/wiki-agents/spec.md`` §Inputs §"Recipe
       surface".
    4. Install order: the closed primitive set is handed to
       :func:`~llm_wiki_kit.primitives.resolve_dependencies` for
       topological sort (alphabetical tiebreaker).
    """

    by_name: dict[str, Primitive] = {primitive.name: primitive for primitive in catalog}

    if CORE_PRIMITIVE_NAME not in by_name:
        raise RecipeError(
            f"recipe '{recipe.name}' cannot resolve: "
            f"primitive '{CORE_PRIMITIVE_NAME}' is missing from the catalog"
        )

    requested: list[str] = list(recipe.primitives)
    if CORE_PRIMITIVE_NAME not in requested:
        requested.insert(0, CORE_PRIMITIVE_NAME)

    closed: dict[str, Primitive] = {}
    pending: list[str] = list(requested)

    while pending:
        name = pending.pop()
        if name in closed:
            continue
        primitive = by_name.get(name)
        if primitive is None:
            raise RecipeError(
                f"recipe '{recipe.name}' references primitive '{name}' which is not in the catalog"
            )
        closed[name] = primitive
        for required in primitive.requires:
            if required not in closed:
                pending.append(required)

    _validate_agent_bindings(recipe, closed)

    return resolve_dependencies(list(closed.values()))


def _validate_agent_bindings(
    recipe: Recipe,
    closed: dict[str, Primitive],
) -> None:
    """Validate ``recipe.agents`` against the resolved closure.

    Three load-bearing checks per
    ``docs/specs/wiki-agents/spec.md`` §Inputs §"Recipe surface" — the
    error shapes are distinct (CT-3, CT-4, CT-5) and must not be
    consolidated:

    1. Every key in ``agents:`` is a primitive in the closure whose
       ``kind`` is ``agent``. "Not in closure" and "wrong kind" are
       reported separately so a typo never masquerades as a kind
       mismatch (and vice versa).
    2. Every operation in any ``runs:`` list is a primitive in the
       closure whose ``kind`` is ``operation``.
    3. No operation appears in two agents' ``runs:`` lists. Recipes
       compose primitives into bundles; binding the same operation to
       two agents is a recipe-author bug because schedule-install
       resolution can only freeze one agent per dispatched operation.

    ``recipe.agents`` is the empty dict on every pre-RFC-4 recipe; the
    function is a no-op in that case. Pydantic's ``min_length=1`` on
    ``AgentBinding.runs`` already pins CT-6 at recipe-load time —
    that check fires before this validator runs and is therefore not
    duplicated here.
    """

    if not recipe.agents:
        return

    seen_operations: dict[str, str] = {}
    for agent_name, binding in recipe.agents.items():
        primitive = closed.get(agent_name)
        if primitive is None:
            raise RecipeError(
                f"recipe '{recipe.name}' binds agent '{agent_name}' but the "
                f"primitive is not in the recipe's closure"
            )
        if primitive.kind is not PrimitiveKind.AGENT:
            raise RecipeError(
                f"recipe '{recipe.name}' binds agent '{agent_name}' but the "
                f"primitive resolves to kind: {primitive.kind.value} "
                f"(kind: agent expected)"
            )
        for operation_name in binding.runs:
            op_primitive = closed.get(operation_name)
            if op_primitive is None:
                raise RecipeError(
                    f"recipe '{recipe.name}' binds operation "
                    f"'{operation_name}' to agent '{agent_name}' but the "
                    f"operation primitive is not in the recipe's closure"
                )
            if op_primitive.kind is not PrimitiveKind.OPERATION:
                raise RecipeError(
                    f"recipe '{recipe.name}' binds operation "
                    f"'{operation_name}' to agent '{agent_name}' but the "
                    f"primitive resolves to kind: {op_primitive.kind.value} "
                    f"(kind: operation expected)"
                )
            if operation_name in seen_operations:
                first_agent = seen_operations[operation_name]
                raise RecipeError(
                    f"operation '{operation_name}' is bound to multiple "
                    f"agents in recipe '{recipe.name}': {first_agent}, "
                    f"{agent_name}; one operation may have at most one "
                    f"preferred agent per recipe"
                )
            seen_operations[operation_name] = agent_name


def installed_outcome_verbs(
    vault_root: Path,
    kit_root: Path,
) -> dict[str, tuple[str, str]]:
    """Return verb → (operation, skill) for every installed outcome-declaring op.

    The map is computed by:

    1. Resolving the journal path
       (``<vault_root>/.wiki.journal/journal.jsonl``); a missing
       journal yields ``{}`` (the helper is pure — PR-6's CLI
       dispatcher handles the "outside a vault" message per spec
       §Outputs §1).
    2. Reading the journal via :func:`journal.read_events`
       (strict). The lenient sibling is doctor-only by design (see
       ``docs/specs/journal-locking/plan.md`` §"lenient consumers")
       and silently swallows mid-journal corruption — a partial
       verb set is more dangerous than a hard failure here. The
       helper therefore raises :class:`JournalCorruptError` on
       corruption; PR-6's dispatcher catches it at the boundary
       and falls through to argparse without a verb-shaped
       rewrite (the user sees argparse's standard error, plus
       any ``wiki doctor`` complaint the next run surfaces).
    3. :func:`journal.replay_state` derives the currently-installed
       primitive set from the parsed events.
    4. For each installed primitive name, looking up
       ``<kit_root>/templates/operations/<name>/contract.yaml`` via
       :func:`primitives.load_operation_contract`. A primitive that
       is not an operation (no ``contract.yaml`` under
       ``operations/``) or is no longer in the kit catalog is
       silently skipped — matching ``wiki upgrade``'s
       ``plan.not_in_catalog`` handling in
       :func:`upgrade.plan_upgrade` (``upgrade.py`` ~line 109's
       installed-set vs. catalog-set diff).
    5. Emitting one entry per declared verb:
       ``verbs[verb] = (contract.name, contract.skill or contract.name)``.
       The ``contract.skill or contract.name`` fallback mirrors
       :func:`run._load_contract`'s resolution
       (``run.py:508`` / documented in ``wiki run --help`` at
       ``cli.py:1919`` as ``<contract.skill or operation>``) and
       the slash-stub writer (PR-3) so the discovery surface and
       the on-disk stub agree about ``{skill}``.

    The returned dict's **insertion order** mirrors the journal's
    event order — first install wins iteration order. Callers that
    surface verbs to a user (``wiki outcomes``) sort by key per
    spec §Outputs §4; iteration-order-sensitive callers should
    sort explicitly rather than rely on this contract.

    Helper reads the **current catalog**'s contract per installed
    primitive (the journal records the install version but not the
    verbs). A vault that was installed before its operation's
    contract declared ``outcomes:`` sees the new verbs as soon as
    the on-disk contract gains them — regardless of whether a
    ``PrimitiveUpgradeEvent`` ever fired. Spec AC "Backwards
    compatibility" depends on this.
    """

    journal_path = vault_root / ".wiki.journal" / "journal.jsonl"
    if not journal_path.is_file():
        return {}

    state = replay_state(read_events(journal_path))

    # Walk the *merged* catalog so sideloaded operation primitives
    # surface alongside bundled ones (``docs/specs/primitive-sideload/
    # spec.md`` §"Provenance decoration"). Each primitive's
    # ``_source_dir`` carries the on-disk directory the contract lives
    # in regardless of source, so a single per-primitive lookup handles
    # bundled and sideloaded uniformly.
    catalog = discover_primitives(kit_root / "templates")
    verbs, _sources = _resolve_installed_outcomes(state, catalog)
    return verbs


def installed_outcome_verbs_with_sources(
    vault_root: Path,
    kit_root: Path,
) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Return ``(verb→(op, skill), verb→source)`` from a single catalog walk.

    Used by ``wiki outcomes`` per ``docs/specs/primitive-sideload/
    spec.md`` §"Outputs ``wiki outcomes`` provenance column" to render
    the ``Source`` column without paying the discovery cost twice.
    Returns ``({}, {})`` when the vault has no journal.
    """

    journal_path = vault_root / ".wiki.journal" / "journal.jsonl"
    if not journal_path.is_file():
        return {}, {}

    state = replay_state(read_events(journal_path))
    catalog = discover_primitives(kit_root / "templates")
    return _resolve_installed_outcomes(state, catalog)


def _resolve_installed_outcomes(
    state: VaultState,
    catalog: list[Primitive],
) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Shared resolver for the two installed-outcome helpers above.

    Walks ``state.installed_primitives`` once, looks each name up in
    the catalog, and produces both the verb→(op, skill) map (existing
    contract) and the verb→source map (sideload addition) from the
    same per-primitive contract load. Single source of truth — the two
    public helpers (``installed_outcome_verbs`` and
    ``installed_outcome_verbs_with_sources``) cannot disagree by
    construction.
    """

    installed_primitives = state.installed_primitives
    catalog_by_name: dict[str, Primitive] = {p.name: p for p in catalog}
    verbs: dict[str, tuple[str, str]] = {}
    sources: dict[str, str] = {}
    for primitive_name in installed_primitives:
        primitive = catalog_by_name.get(primitive_name)
        if primitive is None or primitive.kind is not PrimitiveKind.OPERATION:
            continue
        source_dir = primitive._source_dir
        if source_dir is None:
            continue
        contract = load_operation_contract(source_dir)
        if contract is None or not contract.outcomes:
            continue
        skill = contract.skill or contract.name
        for verb in contract.outcomes:
            verbs[verb] = (contract.name, skill)
            sources[verb] = primitive.source
    return verbs, sources
