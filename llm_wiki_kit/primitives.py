"""Load primitives from disk and order them for install.

The migration plan (RFC-0001) names three surfaces:

* :func:`load_primitive` reads a single ``primitive.yaml`` and validates it
  against the Pydantic :class:`~llm_wiki_kit.models.Primitive` model. Pydantic
  errors flow through :class:`~llm_wiki_kit.errors.ValidationError` so the
  CLI prints one human-readable line per field; everything else (missing
  directory, missing manifest, malformed YAML) flows through
  :class:`~llm_wiki_kit.errors.PrimitiveError`.

* :func:`discover_primitives` walks ``templates_dir/<kind>/<name>/`` and
  loads every primitive it finds, sorted alphabetically by name. The catalog
  layout pinned in ``docs/architecture/overview.md`` is the schema this
  module assumes.

* :func:`resolve_dependencies` is a pure function over a closed list of
  primitives. It topologically sorts by ``requires:`` and raises on cycles
  or on a ``requires:`` target that isn't in the input set. Composing the
  closed set — adding ``core``, adding everything a recipe references and
  everything those things transitively require — lives in
  ``recipes.py`` (Task 9) and the installer (Task 10), not here.

**Why ``core`` isn't special-cased.** The ``core/`` directory at the repo
root has the same shape as a templates entry. The installer's
always-include-core policy is a recipe-level concern, not a loader-level
one, so :func:`load_primitive` treats ``core/`` like any other path.
:func:`discover_primitives` only walks ``templates/``; the caller passes
``core`` to :func:`load_primitive` separately.

**Tiebreaker is alphabetical by name.** When two primitives have no
dependency relationship, install order falls back to ``sorted(by name)``
rather than declaration order so re-running ``wiki init`` against the
same recipe produces the same journal, which keeps drift detection
honest in CI fixtures.
"""

from __future__ import annotations

import importlib.metadata
import importlib.resources
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.errors import PrimitiveError, ValidationError, WikiError
from llm_wiki_kit.models import OperationContract, Primitive, PrimitiveKind, VaultState

# Entry-point group used by sideload packages to advertise primitives
# (``docs/specs/primitive-sideload/spec.md`` §"The entry-point group").
# This is the kit's public extension contract; renaming it requires
# coordinated release-note guidance for every published sideload
# package. Defined as a module-level constant so tests reference the
# same string the loader does.
SIDELOAD_ENTRY_POINT_GROUP = "wiki-primitive"

# Dotted-root module names that a ``wiki-primitive`` entry-point value
# is not allowed to claim — refused at the discovery boundary to keep
# a malicious wheel from pointing the resolver at the kit's own
# ``templates/`` tree. The check matches the first dotted segment of
# ``entry_point.value`` (after stripping any ``:attr`` selector).
_RESERVED_ENTRY_POINT_VALUE_ROOTS: frozenset[str] = frozenset({"llm_wiki_kit"})

# Catalog directory names per ``docs/architecture/overview.md``. The kit ships
# the kind subdirectories pluralized (``ontologies/`` for the ``ontology``
# kind, etc.); ``infrastructure`` is uncountable and matches its kind value
# directly. The mapping is one-way (directory → expected kind) — discovery
# does not enforce that a primitive in ``ontologies/`` declares ``kind:
# ontology``: the declared kind in ``primitive.yaml`` is the source of truth,
# and cross-checking the parent directory name is a primitive-author concern,
# not a kit-side runtime check at v1. (No corresponding ``wiki doctor`` check
# ships today either; if a future RFC tightens this, it tightens for every
# kind together — see ``docs/specs/wiki-agents/spec.md`` CT-1.)
_CATALOG_DIRS: frozenset[str] = frozenset(
    [
        "ontologies",
        "content-types",
        "operations",
        "infrastructure",
        "agents",
        "workspaces",
    ]
)


# ---------------------------------------------------------------------------
# Outcome-named entry points (per
# ``docs/specs/outcome-named-entry-points/spec.md`` §Inputs §2).
#
# Constants live in ``primitives.py`` rather than ``cli.py`` because the
# validator below reads them and the kit's dependency graph is
# ``cli.py -> primitives.py``; reversing the direction would introduce a
# circular import. The *enumeration source* — which subcommands are
# reserved — is ``cli.build_parser()``;
# ``tests/unit/test_outcome_verbs.py::test_reserved_outcome_verbs_matches_subcommand_set``
# pins the two against each other so a new subcommand added to
# ``cli.py`` without an update here trips CI.
# ---------------------------------------------------------------------------

#: Verbs an outcome may never equal. Matches the set of registered
#: top-level ``wiki`` subcommands plus standard discovery aliases.
#: ``tests/unit/test_outcome_verbs.py::test_reserved_outcome_verbs_matches_subcommand_set``
#: pins this set against ``cli.build_parser()`` so a new subcommand
#: added in `cli.py` without an update here trips the test.
RESERVED_OUTCOME_VERBS: frozenset[str] = frozenset(
    {
        "init",
        "add",
        "upgrade",
        "doctor",
        "ingest",
        "resolve",
        "lock",
        "run",
        "research",
        "search",
        "journal",
        "schedule",
        "agents",
        "workspaces",
        # Discovery aliases — never registered as subparsers but
        # reserved so a primitive cannot claim them.
        "help",
        "version",
        "outcomes",
    }
)


#: Permitted verb stems. A well-formed verb either equals a bare-verb
#: entry (no trailing hyphen) outright, OR starts with one of the
#: prefix entries (trailing hyphen) followed by ``<object>``. Extend
#: this set in the same PR that adds an operation needing a new stem.
OUTCOME_VERB_STEMS: frozenset[str] = frozenset(
    {
        # Bare verbs.
        "digest",
        "roll-up",
        # Prefix forms (``<stem>-<object>``).
        "plan-",
        "refresh-",
        "log-",
        "summarize-",
        "prep-",
        "review-",
        "track-",
        "synthesize-",
        "pack-",
        "remind-",
        "map-",
    }
)


_OUTCOME_VERB_SHAPE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def is_well_formed_outcome_verb(verb: str) -> None:
    """Raise :class:`WikiError` if ``verb`` violates any naming rule.

    Returns ``None`` on success. Encodes spec §Inputs §2 rules 1, 2,
    3, 4, and 6 (rule 5 — catalog uniqueness — needs the full catalog
    and lives in :func:`check_outcome_verb_uniqueness`). Each rejection
    message names the rule that triggered it so the eventual
    error renders something the primitive author can act on.
    """

    # Rule 1 (length) and rule 2 (ASCII / locale). Length comes first
    # because the shape regex assumes a non-empty value.
    if not 3 <= len(verb) <= 24:
        raise WikiError(
            f"outcome verb '{verb}' length {len(verb)} is outside the "
            "3-24 character range (spec §Inputs §2 rule 1)"
        )
    if not verb.isascii():
        raise WikiError(
            f"outcome verb '{verb}' contains non-ASCII characters; "
            "outcome verbs are English-only ASCII per spec §Inputs §2 "
            "rule 2"
        )

    # Rule 1 (shape).
    if not _OUTCOME_VERB_SHAPE.fullmatch(verb):
        if any(ch.isupper() for ch in verb):
            raise WikiError(
                f"outcome verb '{verb}' must be ASCII lowercase "
                "kebab-case matching ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ "
                "(spec §Inputs §2 rule 1)"
            )
        if "--" in verb:
            raise WikiError(
                f"outcome verb '{verb}' contains consecutive hyphens (spec §Inputs §2 rule 1)"
            )
        if verb.endswith("-"):
            raise WikiError(f"outcome verb '{verb}' has a trailing hyphen (spec §Inputs §2 rule 1)")
        if verb[:1].isdigit():
            raise WikiError(
                f"outcome verb '{verb}' starts with a digit; verbs "
                "must start with [a-z] (spec §Inputs §2 rule 1, "
                "leading digit)"
            )
        raise WikiError(
            f"outcome verb '{verb}' does not match the kebab-case "
            "shape ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ (spec §Inputs §2 "
            "rule 1)"
        )

    # Rule 6 — belt-and-braces ``wiki-`` prefix block (rule 4 already
    # rejects it because no `wiki-` stem is allowlisted, but a future
    # maintainer adding a `wiki-` stem to ``OUTCOME_VERB_STEMS`` would
    # bypass that check).
    if verb.startswith("wiki-"):
        raise WikiError(
            f"outcome verb '{verb}' starts with the reserved 'wiki-' "
            "prefix (spec §Inputs §2 rule 6)"
        )

    # Rule 3 — reserved-word block.
    if verb in RESERVED_OUTCOME_VERBS:
        raise WikiError(
            f"outcome verb '{verb}' collides with a reserved wiki "
            "subcommand (spec §Inputs §2 rule 3)"
        )

    # Rule 4 — verb-form. Either the whole verb is a bare-verb entry,
    # or it starts with an allowlisted prefix entry (``<stem>-``)
    # followed by a non-empty ``<object>``.
    if verb in OUTCOME_VERB_STEMS:
        return
    for stem in OUTCOME_VERB_STEMS:
        if stem.endswith("-") and verb.startswith(stem) and len(verb) > len(stem):
            return
    raise WikiError(
        f"outcome verb '{verb}' does not start with an allowlisted "
        "verb-stem from primitives.OUTCOME_VERB_STEMS (spec §Inputs "
        "§2 rule 4); extend the constant in the same PR that needs a "
        "new stem"
    )


def check_outcome_verb_uniqueness(
    contracts: Iterable[OperationContract],
    *,
    source_by_operation: dict[str, str] | None = None,
) -> None:
    """Raise :class:`WikiError` on catalog-level outcome-verb collisions.

    Two passes over ``contracts``:

    1. **Verb uniqueness** (spec §Inputs §2 rule 5) — a verb appears at
       most once across every operation primitive.
    2. **Verb-vs-operation-name disjointness** (spec Invariants 8 +
       Acceptance criterion "Verb does not shadow any operation
       name") — a verb may not equal any operation's ``name``,
       including the declaring operation's own name.

    The function consumes the iterable once, so callers passing a
    one-shot generator do not need to materialize it twice.

    ``source_by_operation`` is the optional per-operation source map
    (``operation_name → "bundled" | "sideload:<package>"``) used in
    the pass-1 error message so a user with two packages each shipping
    the same verb sees the contributing source attribution and can
    decide which package to uninstall (``docs/specs/primitive-sideload/
    spec.md`` §"Error cases"). Bundled-only callers may pass ``None``;
    the message degrades gracefully to operation-name-only.
    """

    contracts_list = list(contracts)
    operation_names: set[str] = {contract.name for contract in contracts_list}

    def _attrib(operation_name: str) -> str:
        if source_by_operation is None:
            return f"'{operation_name}'"
        source = source_by_operation.get(operation_name, "bundled")
        return f"'{operation_name}' ({source})"

    seen_verbs: dict[str, str] = {}
    for contract in contracts_list:
        for verb in contract.outcomes:
            # Pass 1: verb uniqueness across the catalog.
            owner = seen_verbs.get(verb)
            if owner is not None:
                raise WikiError(
                    f"outcome verb '{verb}' is declared by both "
                    f"{_attrib(owner)} and {_attrib(contract.name)}; "
                    "verbs must be unique across the operation catalog "
                    "(spec §Inputs §2 rule 5)"
                )
            seen_verbs[verb] = contract.name

            # Pass 2: verb-vs-operation-name shadow.
            if verb in operation_names:
                raise WikiError(
                    f"outcome verb '{verb}' declared by "
                    f"{_attrib(contract.name)} shadows the operation name "
                    f"'{verb}'; outcome verbs and operation names "
                    "must occupy disjoint sets (spec Invariant 8)"
                )


def load_primitive(path: Path) -> Primitive:
    """Load and validate a single primitive directory.

    ``path`` is the primitive root — the directory that contains
    ``primitive.yaml``. The function does not look at ``path.parent`` to
    cross-check the kind: a primitive's declared ``kind`` is the source of
    truth, and discovery is responsible for placing primitives in the
    right kind subdirectory.
    """

    if not path.exists():
        raise PrimitiveError(f"primitive directory does not exist: {path}")
    if not path.is_dir():
        raise PrimitiveError(f"primitive path is not a directory: {path}")

    manifest_path = path / "primitive.yaml"
    if not manifest_path.exists():
        raise PrimitiveError(f"primitive.yaml not found in {path}")

    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimitiveError(f"cannot read {manifest_path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise PrimitiveError(f"malformed YAML in {manifest_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise PrimitiveError(
            f"{manifest_path} must contain a YAML mapping, got {type(data).__name__}"
        )

    try:
        primitive = Primitive.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(f"primitive.yaml at {path}", exc) from exc
    # The bundled load path always tags ``source="bundled"`` and records
    # the on-disk directory so consumers building a ``sources`` mapping
    # for the install pipeline can read it uniformly across bundled and
    # sideloaded primitives. ``source`` is a Field with ``exclude=True``
    # rather than a PrivateAttr per ``docs/specs/primitive-sideload/
    # spec.md`` §"Contracts with other modules"; the post-validate
    # override here guarantees a hand-edited ``primitive.yaml`` cannot
    # impersonate a sideload package by declaring ``source: sideload:…``.
    primitive.source = "bundled"
    primitive._source_dir = path
    return primitive


def _load_sideload_primitive(path: Path, *, source: str) -> Primitive:
    """Sideload sibling of :func:`load_primitive`.

    Loads a single ``primitive.yaml`` from a sideload package's
    ``templates/<kind>/<name>/`` directory under the source-scoped
    extra-field policy from ``docs/specs/primitive-sideload/spec.md``
    §"Source-scoped extra-field policy": top-level (and nested
    ``contributes_to`` / ``routing``) unknown fields are dropped, not
    rejected; the dropped names are captured on the instance for
    ``wiki doctor`` to surface. ``source`` is the
    ``"sideload:<package-name>"`` label written into the
    :attr:`Primitive.source` field.

    Distinct error attribution: malformed YAML or missing files in a
    sideload package prepend the package name to the error message
    so the user can navigate to the offending file in someone else's
    code rather than a kit-internal path.
    """

    if not path.exists():
        raise PrimitiveError(
            f"sideload primitive directory does not exist: {path} (source={source})"
        )
    if not path.is_dir():
        raise PrimitiveError(
            f"sideload primitive path is not a directory: {path} (source={source})"
        )

    manifest_path = path / "primitive.yaml"
    if not manifest_path.exists():
        raise PrimitiveError(f"sideload primitive.yaml not found in {path} (source={source})")

    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimitiveError(f"cannot read {manifest_path} (source={source}): {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise PrimitiveError(f"malformed YAML in {manifest_path} (source={source}): {exc}") from exc

    if not isinstance(data, dict):
        raise PrimitiveError(
            f"{manifest_path} must contain a YAML mapping, got "
            f"{type(data).__name__} (source={source})"
        )

    try:
        primitive = Primitive.from_sideload(data, source=source)
    except PydanticValidationError as exc:
        raise ValidationError(f"sideload primitive.yaml at {path} (source={source})", exc) from exc
    primitive._source_dir = path
    return primitive


def _discover_sideloaded_template_dirs() -> list[tuple[str, str, Path]]:
    """Resolve the ``wiki-primitive`` entry-point group to templates paths.

    Returns one ``(package_name, version, templates_path)`` triple per
    entry point, sorted by package name. An empty entry-point group
    returns ``[]``; an installation with no sideload packages therefore
    sees byte-equivalent loader output to today's kit.

    The function uses :func:`importlib.metadata.entry_points` to
    enumerate the group and :func:`importlib.resources.files` to
    resolve each entry-point value (a Python package's importable
    module path) into a filesystem-traversable ``Path`` pointing at the
    package's bundled ``templates/`` directory. This is the
    regular-wheel-install requirement from ``docs/specs/primitive-
    sideload/spec.md`` §"Sideload package installation" — a zipped-
    wheel or zipapp layout would not satisfy ``Path``'s
    ``iterdir`` / ``open`` contracts and the kit raises a
    :class:`PrimitiveError` naming the package at the first filesystem
    operation.

    The helper does NOT raise on a missing ``templates/`` directory
    (that surfaces from the merge call site in
    :func:`discover_primitives` with the exact spec-pinned error
    message). It does raise from :func:`importlib.metadata.entry_points`
    itself if the Python runtime cannot load the metadata; that's a
    runtime-infrastructure failure the kit lets propagate.
    """

    entry_points = importlib.metadata.entry_points(group=SIDELOAD_ENTRY_POINT_GROUP)
    triples: list[tuple[str, str, Path]] = []
    for entry_point in entry_points:
        # Defence: refuse any entry point whose dotted-root names the
        # kit's own package. A malicious or sloppy sideload package
        # could otherwise declare ``wiki-primitive = "llm_wiki_kit"``
        # and the resolver would obediently walk *the kit's own*
        # ``templates/`` directory, attributing those primitives to the
        # attacker's package name in every collision/error message.
        # The hard refusal here makes the confused-deputy report shape
        # impossible at the boundary.
        ep_root = entry_point.value.split(":", 1)[0].split(".", 1)[0]
        if ep_root in _RESERVED_ENTRY_POINT_VALUE_ROOTS:
            raise PrimitiveError(
                f"sideload entry-point value '{entry_point.value}' names "
                f"the kit's own package '{ep_root}'; refusing to resolve. "
                "A sideload package must point its 'wiki-primitive' "
                "entry-point value at its own module path."
            )
        # Prefer the *distribution* name and version recorded on the
        # entry point itself — that's the PyPI-visible identity a user
        # would see in ``pip list`` or ``pip install`` and the label the
        # spec contracts on (``docs/specs/primitive-sideload/spec.md``
        # §Outputs "the distribution name from
        # ``importlib.metadata``"). The module name a project ships
        # under ("wiki_primitive_pod") often differs from its
        # distribution name ("wiki-primitive-pod"), so deriving the
        # label from ``entry_point.value`` would render the wrong
        # identifier across every user-visible affordance the
        # provenance decoration touches.
        dist = entry_point.dist
        if dist is not None:
            package_name = dist.name
            version = dist.version
        else:
            # Fallback: an entry point produced without an attached
            # distribution (rare; some editable-install paths on older
            # Python versions). Derive a best-effort label from the
            # importable module path and look up the version
            # separately. ``"unknown"`` is the signal the spec's
            # provenance decoration uses for "metadata didn't resolve".
            package_name = entry_point.value.split(":", 1)[0].split(".", 1)[0]
            try:
                version = importlib.metadata.version(package_name)
            except importlib.metadata.PackageNotFoundError:
                version = "unknown"
        try:
            templates_traversable = importlib.resources.files(entry_point.value) / "templates"
        except (ModuleNotFoundError, TypeError) as exc:
            raise PrimitiveError(
                f"sideload package '{package_name}' declares entry-point "
                f"value '{entry_point.value}' but the kit cannot resolve "
                f"its package root: {exc}"
            ) from exc
        # Sideload packages MUST install such that
        # ``importlib.resources.files`` returns a filesystem-traversable
        # Path; zipped layouts return a different Traversable subclass
        # that the rest of the kit (which uses ``pathlib`` operations)
        # cannot consume. The cast below is the contract; the
        # PrimitiveError fires at the first ``iterdir`` / ``open`` call
        # if the contract is violated.
        templates_path = Path(str(templates_traversable))
        triples.append((package_name, version, templates_path))
    triples.sort(key=lambda triple: triple[0])
    return triples


def load_operation_contract(primitive_dir: Path) -> OperationContract | None:
    """Load ``<primitive_dir>/contract.yaml`` if present; else ``None``.

    **Return-None on missing file is intentional**, not an oversight.
    The spec's catalog-time-failures invariant (Invariant 5) covers
    *verb naming rules* — it does not require that every operation
    primitive ship a ``contract.yaml`` at catalog-load time. Two
    behaviors depend on this:

    1. ``tests/unit/test_primitives.py::test_discover_primitives_walks_kind_subdirectories``
       constructs an operation primitive without a contract to
       verify the kind-subdirectory walk; tightening here would
       break that contract.
    2. ``wiki run`` raises a dedicated ``WikiError`` against the
       missing file at its own boundary (``run.py:225``:
       ``raise WikiError(f"operation {operation!r}: no contract.yaml at {path}")``)
       with the absolute path included, which is the user-actionable
       message — the catalog-load path duplicating it would be noise.

    Pydantic schema errors and YAML parse errors are still fatal
    (mirroring :func:`load_primitive`'s handling of ``primitive.yaml``
    failures) — a typo in a contract that *is* on disk does not
    silently degrade.
    """

    contract_path = primitive_dir / "contract.yaml"
    if not contract_path.is_file():
        return None

    try:
        raw = contract_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PrimitiveError(f"cannot read {contract_path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise PrimitiveError(f"malformed YAML in {contract_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise PrimitiveError(
            f"{contract_path} must contain a YAML mapping, got {type(data).__name__}"
        )

    try:
        return OperationContract.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(f"contract.yaml at {primitive_dir}", exc) from exc


def _walk_templates_tree(
    templates_dir: Path,
    *,
    loader: Callable[[Path], Primitive],
) -> tuple[list[Primitive], list[OperationContract]]:
    """Walk one ``templates/<kind>/<name>/`` tree once.

    Factored out of :func:`discover_primitives` so the bundled walk and
    each sideloaded walk share one body. ``loader`` is the
    per-walk-flavour constructor (bundled vs. sideload-with-source);
    everything else — kind-directory skip rules, manifest-missing skip
    rule, outcome-verb shape check — is identical.

    Returns ``(primitives_loaded, operation_contracts_loaded)``;
    cross-walk collision and verb-uniqueness checks happen at the
    :func:`discover_primitives` merge step against the union.
    """

    primitives: list[Primitive] = []
    operation_contracts: list[OperationContract] = []
    if not templates_dir.exists():
        return primitives, operation_contracts
    for kind_dir in sorted(templates_dir.iterdir()):
        if not kind_dir.is_dir() or kind_dir.name not in _CATALOG_DIRS:
            continue
        for primitive_dir in sorted(kind_dir.iterdir()):
            if not primitive_dir.is_dir():
                continue
            if not (primitive_dir / "primitive.yaml").exists():
                continue
            primitive = loader(primitive_dir)
            primitives.append(primitive)
            if primitive.kind is PrimitiveKind.OPERATION:
                contract = load_operation_contract(primitive_dir)
                if contract is None:
                    continue
                for verb in contract.outcomes:
                    is_well_formed_outcome_verb(verb)
                operation_contracts.append(contract)
    return primitives, operation_contracts


def _check_name_collisions(primitives: list[Primitive]) -> None:
    """Raise :class:`WikiError` on any name collision across the merged catalog.

    Spec §"Collision policy" cases 1 and 2: a sideloaded primitive name
    that matches a bundled name, or that matches another sideloaded
    primitive's name. The check is source-aware so the error message
    can route the user to the right fix (uninstall vs. rename), but
    primitive ordering inside ``primitives`` does not matter — the
    function picks the bundled member as the canonical "owner" in
    bundled-vs-sideload pairs.

    Implementation note: this runs against the full merged primitive
    list. Bundled-vs-bundled collisions cannot happen (the kit's own
    catalog is hand-curated and would already have been caught by
    other constraints), but the check fires symmetrically — a future
    structural refactor that introduces a second bundled tree should
    not silently accept a duplicate name.
    """

    seen: dict[str, Primitive] = {}
    for primitive in primitives:
        existing = seen.get(primitive.name)
        if existing is None:
            seen[primitive.name] = primitive
            continue
        # Order the contributors so the bundled side, if any, appears
        # first in the message — the user typically reads
        # "X is bundled" and decides to rename the sideload.
        a, b = existing, primitive
        if a.source != "bundled" and b.source == "bundled":
            a, b = b, a
        if a.source == "bundled" and b.source != "bundled":
            sideload_pkg = b.source.split(":", 1)[1] if ":" in b.source else b.source
            raise WikiError(
                f"sideload package '{sideload_pkg}' provides primitive "
                f"'{a.name}', but '{a.name}' is already "
                f"bundled with the kit. Uninstall '{sideload_pkg}' or "
                "rename its primitive."
            )
        # Two sideload packages provide the same name.
        pkg_a = a.source.split(":", 1)[1] if ":" in a.source else a.source
        pkg_b = b.source.split(":", 1)[1] if ":" in b.source else b.source
        raise WikiError(
            f"sideload packages '{pkg_a}' and '{pkg_b}' both provide "
            f"primitive '{a.name}'. Uninstall one."
        )


def _check_skill_path_collisions(primitives: list[Primitive]) -> None:
    """Raise :class:`WikiError` on shared ``files/skills/<skill>/`` paths.

    Spec §"Collision policy" case 5. Two operation primitives across
    the merged catalog cannot ship the same ``files/skills/<skill>/``
    directory because the install pipeline would write conflicting
    SKILL.md content into one vault location. The bundled-only loader
    has no such case today (hand-curated), but the merged catalog
    must enforce it — sideload package authors aren't coordinated.

    The check inspects each primitive's ``_source_dir / "files" / "skills"``
    for present subdirectories (operation primitives ship these as part
    of the outcome-named-entry-points contract; non-operation
    primitives may ship them too for other purposes). A skill
    directory name is treated as colliding only when it appears under
    two distinct primitives.
    """

    skill_owner: dict[str, Primitive] = {}
    for primitive in primitives:
        if primitive._source_dir is None:
            continue
        skills_root = primitive._source_dir / "files" / "skills"
        if not skills_root.is_dir():
            continue
        for skill_dir in sorted(skills_root.iterdir()):
            if not skill_dir.is_dir():
                continue
            existing = skill_owner.get(skill_dir.name)
            if existing is None:
                skill_owner[skill_dir.name] = primitive
                continue
            # Order contributors so the bundled side, if any, appears
            # first in the message.
            a, b = existing, primitive
            if a.source != "bundled" and b.source == "bundled":
                a, b = b, a
            raise WikiError(
                f"SKILL directory 'files/skills/{skill_dir.name}/' is "
                f"contributed by both primitive '{a.name}' "
                f"(source={a.source}) and primitive '{b.name}' "
                f"(source={b.source}); two primitives cannot ship the "
                "same SKILL directory."
            )


def discover_primitives(templates_dir: Path) -> list[Primitive]:
    """Walk ``templates_dir/<kind>/<name>/`` and load every primitive.

    Returns an empty list when ``templates_dir`` does not exist (a fresh
    repo before any primitives have been authored is not an error). Skips
    directories at the top level whose name is not one of the four
    :class:`~llm_wiki_kit.models.PrimitiveKind` values; debris like a
    top-level ``README.md`` or a ``.DS_Store`` directory does not crash
    discovery. A directory inside a kind subdirectory without a
    ``primitive.yaml`` is also skipped — that pattern shows up during
    primitive authoring, where the skeleton may exist before the manifest.

    A *manifest* that fails to load is fatal: a typo in
    ``primitive.yaml`` would otherwise hide the primitive from every
    recipe that depends on it, which is exactly the failure mode Pydantic
    is meant to catch.

    **Outcome-verb catalog gate** (per
    ``docs/specs/outcome-named-entry-points/spec.md``): for every
    operation-kind primitive whose ``contract.yaml`` is present, each
    declared ``outcomes`` verb runs through
    :func:`is_well_formed_outcome_verb`. After the walk completes,
    :func:`check_outcome_verb_uniqueness` runs across every loaded
    operation contract so the spec's
    "the catalog is the namespace" invariant fires before any
    user vault sees a primitive. Both checks raise :class:`WikiError`
    directly, matching the spec's "primitive-load-time error" framing.

    **Sideload merge** (per ``docs/specs/primitive-sideload/spec.md``):
    after the bundled walk completes, the function calls
    :func:`_discover_sideloaded_template_dirs` to enumerate
    ``wiki-primitive`` entry-point packages and walks each one's
    ``templates/`` directory with the same per-kind / per-primitive
    body. Sideloaded primitives load through :func:`_load_sideload_primitive`
    (which uses the source-scoped ``extra='ignore'`` policy from
    :meth:`Primitive.from_sideload`) and carry source attribution as
    ``"sideload:<package>"`` on each instance. After every walk
    completes, cross-source name collisions, region collisions
    (delegated to the install pipeline), SKILL-path collisions, and
    outcome-verb uniqueness all fire across the merged catalog. An
    installation with no ``wiki-primitive`` entry-point packages
    behaves bit-for-bit identically to the pre-sideload kit — no log
    line, no synthetic event, no behavior change.
    """

    bundled, bundled_contracts = _walk_templates_tree(templates_dir, loader=load_primitive)

    sideload_triples = _discover_sideloaded_template_dirs()
    sideloaded: list[Primitive] = []
    sideloaded_contracts: list[OperationContract] = []
    for package_name, _version, sideload_templates_path in sideload_triples:
        source_label = f"sideload:{package_name}"
        if not sideload_templates_path.exists():
            raise WikiError(
                f"sideload package '{package_name}' is installed but no "
                f"templates/ directory was found at its package root "
                f"(expected: {sideload_templates_path})."
            )

        def _loader(primitive_dir: Path, *, _source: str = source_label) -> Primitive:
            return _load_sideload_primitive(primitive_dir, source=_source)

        pkg_primitives, pkg_contracts = _walk_templates_tree(
            sideload_templates_path, loader=_loader
        )
        sideloaded.extend(pkg_primitives)
        sideloaded_contracts.extend(pkg_contracts)

    merged = bundled + sideloaded

    # Collision checks run against the *fully* merged catalog — bundled
    # primitives, the kit's ``core`` primitive (which ships SKILLs like
    # ``wiki-bootstrap`` / ``wiki-conflict`` / ``ingest`` that a
    # sideload package could otherwise quietly shadow), and every
    # sideloaded primitive. ``core`` lives at the kit-root level and is
    # loaded separately by every install handler (``cli._cmd_init`` /
    # ``_cmd_add`` / ``_cmd_upgrade``); pulling it in here ensures the
    # collision contract from ``docs/specs/primitive-sideload/spec.md``
    # §"Collision policy" cases 1 + 5 fires uniformly across every
    # source the install pipeline will actually walk.
    collision_inputs = _augment_with_core(merged, templates_dir)
    _check_name_collisions(collision_inputs)
    _check_skill_path_collisions(collision_inputs)
    source_by_operation: dict[str, str] = {
        primitive.name: primitive.source
        for primitive in merged
        if primitive.kind is PrimitiveKind.OPERATION
    }
    check_outcome_verb_uniqueness(
        bundled_contracts + sideloaded_contracts,
        source_by_operation=source_by_operation,
    )

    merged.sort(key=lambda p: p.name)
    return merged


def _augment_with_core(primitives: list[Primitive], templates_dir: Path) -> list[Primitive]:
    """Return ``primitives`` plus the kit's ``core`` primitive when present.

    ``discover_primitives`` walks ``templates/`` only — by design, since
    ``core`` is a special primitive at the kit root. But the collision
    checks need to see ``core`` so a sideload package shipping
    ``files/skills/wiki-bootstrap/`` (a SKILL the core primitive
    contributes) raises at load time rather than at the next
    ``safe_write`` drift conflict. The helper is private because the
    rest of the kit deliberately keeps ``core`` out of the catalog's
    declarative shape; the collision walk is the only consumer that
    needs the union view.
    """

    if templates_dir.parent is None:
        return list(primitives)
    core_dir = templates_dir.parent / "core"
    if not (core_dir / "primitive.yaml").is_file():
        return list(primitives)
    core_primitive = load_primitive(core_dir)
    return [core_primitive, *primitives]


def is_installed_agent(name: str, state: VaultState, kit_root: Path) -> bool:
    """Return True iff ``name`` is an installed primitive of kind ``agent``.

    Two-condition check used by schedule-install validation (PR-4) and
    dispatch-time validation (PR-5) — the two sites that consume
    :class:`VaultState`. Returns ``True`` only when both halves hold:

    1. ``name in state.installed_primitives`` — the primitive has been
       installed into this vault (i.e. a ``PrimitiveInstallEvent``
       was journaled and no later ``PrimitiveRemoveEvent`` popped it).
    2. The kit-side catalog at ``kit_root / "templates"`` declares
       the primitive's ``kind`` as :attr:`PrimitiveKind.AGENT`.

    The second half walks the catalog via :func:`discover_primitives`
    because ``VaultState.installed_primitives`` is ``dict[str, str]``
    (name → version) and carries no kind information. The walk is
    O(catalog-size) per call; PR-4 / PR-5 callers each invoke this
    once per ``wiki schedule install`` or ``wiki run``, not in a hot
    loop.

    ``kit_root`` follows the existing convention used by
    :func:`recipes.installed_outcome_verbs`, :func:`cli._kit_paths`,
    and :func:`operations._load_contract` — it points at the repo-side
    catalog root (the directory containing ``templates/``).

    Recipe-load validation (PR-3) walks the recipe's ``primitives:``
    closure before any install has happened; no ``VaultState`` exists
    at that point, so this helper is not callable there. The closure
    walk is a separate validation path; see
    ``docs/specs/wiki-agents/spec.md`` §Invariants.

    **Catalog-level errors propagate.** The helper delegates the kind
    lookup to :func:`discover_primitives`, which runs the full
    catalog validation (outcome-verb uniqueness, malformed
    ``primitive.yaml``, etc.) as a side effect. A vault with a
    catalog-corruption duplicate-outcome will see this helper raise
    :class:`WikiError` from `check_outcome_verb_uniqueness` rather
    than returning ``False`` — that's the right shape (broken
    catalog should fail loudly anywhere it's touched), and PR-4 /
    PR-5 callers want catalog corruption surfaced at dispatch rather
    than silently treated as "agent missing." If a future
    contributor needs a pure name+kind probe without the catalog
    side effects, narrow the lookup to
    ``load_primitive(kit_root / "templates" / "agents" / name)``
    and document the change against this docstring.
    """

    if name not in state.installed_primitives:
        return False
    for primitive in discover_primitives(kit_root / "templates"):
        if primitive.name == name:
            return primitive.kind is PrimitiveKind.AGENT
    return False


@dataclass(frozen=True)
class AgentRow:
    """One row in the ``wiki agents`` table.

    Frozen — every consumer treats the row as a value. Per
    ``docs/specs/wiki-agents/spec.md`` §"Contracts with other modules":
    a small dataclass, not a registry/factory. The fields land verbatim
    in the TSV output rendered by ``cli._cmd_agents``.

    ``recipes`` and ``operations`` are sorted alphabetically (the
    rendering shape pinned by spec §Outputs ``wiki agents``); the
    empty-list shape renders as ``—`` at the CLI boundary.
    """

    name: str
    recipes: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)


def list_agents(vault_root: Path, kit_root: Path) -> list[AgentRow]:
    """Enumerate installed agent primitives with their recipe + operation bindings.

    Driven by ``cli._cmd_agents`` (``wiki agents``). The function:

    1. Reads the vault's journal to derive ``state.installed_primitives``.
       A vault with no journal returns ``[]`` (matches the
       ``recipes.installed_outcome_verbs`` precedent — the helper is
       pure and the dispatcher handles "not a vault" at its boundary).
    2. Walks the catalog at ``kit_root / "templates"`` **once** via
       :func:`discover_primitives` and builds a ``name → Primitive``
       map. The kind for each installed name is recovered from this
       map — :class:`VaultState.installed_primitives` is
       ``dict[str, str]`` (name → version) and carries no kind. The
       single-walk shape keeps the call O(catalog-size), not
       O(catalog-size * installed-agents).
    3. Walks the catalog's recipes at ``kit_root / "recipes"`` once
       via :func:`recipes.discover_recipes`, resolving each recipe's
       closure to support the spec's two-rule RECIPES contribution
       (§Outputs ``wiki agents``):

       - Rule (a): the recipe's ``agents:`` block contains an entry
         for this agent name.
       - Rule (b): the agent name appears in the recipe's
         ``primitives:`` closure (via
         :func:`recipes.resolve_recipe_primitives`).

       Rule (b) covers the installed-but-unbound case (e.g.
       ``decision-companion`` shipped in ``personal.yaml``'s closure
       with no ``agents:`` binding — see ``docs/specs/wiki-agents/spec.md``
       CT-19).
    4. Builds the OPERATIONS column as the union of:

       - Every ``runs:`` operation across every recipe binding this
         agent (rule (i)).
       - Every operation whose ``contract.preferred_agent`` matches
         this agent name (rule (ii)).

    Recipes / operations lists are sorted alphabetically and
    deduplicated. The empty case is the empty list (the CLI renders
    ``—`` at its boundary; the helper returns the raw shape).

    ``kit_root`` follows the same convention as
    :func:`is_installed_agent`, :func:`recipes.installed_outcome_verbs`,
    :func:`cli._kit_paths`, and :func:`operations._load_contract` —
    the repo-side catalog root (the directory containing ``templates/``,
    ``recipes/``, ``core/``).

    **Cost.** O(journal-events + catalog-primitives + recipes *
    closure-size + operations * contract-load). The per-agent inner
    loop below is set-membership only — no catalog re-walk per agent.
    A refactor that accidentally moves :func:`discover_primitives` or
    :func:`recipes.resolve_recipe_primitives` inside the per-agent
    loop is a documented regression.

    **Catalog-level errors mostly propagate; closure-mismatch errors do
    not.** Like :func:`is_installed_agent`, the helper delegates to
    :func:`discover_primitives` and :func:`recipes.discover_recipes` —
    both raise on a corrupt catalog (malformed ``primitive.yaml``,
    malformed recipe YAML, outcome-verb-uniqueness violations), and
    those errors propagate so ``wiki agents`` fails loudly the same
    way every other surface that touches the catalog does. The one
    asymmetry is :class:`~llm_wiki_kit.errors.RecipeError` from
    :func:`recipes.resolve_recipe_primitives` (e.g. an
    ``agents.X.runs`` entry pointing at an out-of-closure operation):
    the helper swallows that per-recipe and contributes only the
    recipe's ``agents:`` block half to the RECIPES column. Spec
    §Outputs ``wiki agents`` doesn't pin closure-walk failure
    behavior; this best-effort posture keeps a vault listable
    against a partially-broken recipe (PR-3's recipe-load CTs and
    ``wiki doctor``'s primitive checks already surface the failure
    elsewhere).
    """

    # Lazy import to avoid the ``recipes`` ↔ ``primitives`` import cycle
    # (``recipes`` imports :func:`resolve_dependencies` /
    # :func:`load_operation_contract` from this module at module-import
    # time; we can only consume ``recipes`` from inside a function).
    from llm_wiki_kit.errors import RecipeError
    from llm_wiki_kit.journal import read_events, replay_state
    from llm_wiki_kit.recipes import discover_recipes, resolve_recipe_primitives

    journal_path = vault_root / ".wiki.journal" / "journal.jsonl"
    if not journal_path.is_file():
        return []
    state = replay_state(read_events(journal_path))

    templates_dir = kit_root / "templates"
    catalog = discover_primitives(templates_dir)
    catalog_by_name: dict[str, Primitive] = {primitive.name: primitive for primitive in catalog}

    # Short-circuit when the vault has no installed agents — the
    # downstream recipe + contract walks are pure waste in that case
    # (every installed-primitive name in the inner loop would filter
    # out at the ``kind is AGENT`` gate). The pre-PR-7a state and any
    # opt-out vault hits this path.
    if not any(
        catalog_by_name.get(name) is not None and catalog_by_name[name].kind is PrimitiveKind.AGENT
        for name in state.installed_primitives
    ):
        return []

    # Recipes contribute to RECIPES + OPERATIONS by both binding rule
    # (a) (agents: block) and rule (b) (primitives: closure). Walk once,
    # collect both relations, then per-agent fold below.
    recipes_dir = kit_root / "recipes"
    recipes_catalog: list[Primitive] = list(catalog)
    core_dir = kit_root / "core"
    if (core_dir / "primitive.yaml").is_file():
        # ``resolve_recipe_primitives`` requires ``core`` in its catalog
        # input. Add it if the kit root exposes one; the fixture-kit
        # tests construct a minimal ``core/`` so this branch fires.
        recipes_catalog.append(load_primitive(core_dir))
    all_recipes = discover_recipes(recipes_dir)

    # Per-recipe view: (a) the agent names declared in ``agents:``;
    # (b) the set of agent-kind primitive names in the closure; the
    # union of ``runs:`` lists keyed by agent name.
    block_by_recipe: dict[str, set[str]] = {}
    closure_agents_by_recipe: dict[str, set[str]] = {}
    runs_by_recipe_agent: dict[tuple[str, str], list[str]] = {}
    for recipe in all_recipes:
        block_by_recipe[recipe.name] = set(recipe.agents.keys())
        for agent_name, binding in recipe.agents.items():
            runs_by_recipe_agent[(recipe.name, agent_name)] = list(binding.runs)
        try:
            closure = resolve_recipe_primitives(recipe, recipes_catalog)
        except RecipeError:
            # Narrow catch: only closure-mismatch errors surface here.
            # YAML / schema errors die earlier in ``discover_recipes`` /
            # ``load_recipe``. The ``agents:`` block view filed above
            # is still the recipe-author-visible contribution.
            # Closure-walk errors surface separately at ``wiki doctor``
            # / recipe-load time (PR-3's CTs); silently dropping the
            # closure half here keeps a partial-catalog vault listable.
            closure_agents_by_recipe[recipe.name] = set()
            continue
        closure_agents_by_recipe[recipe.name] = {
            p.name for p in closure if p.kind is PrimitiveKind.AGENT
        }

    # Operation contracts: which ones declare ``preferred_agent``?
    contract_preferred_by_agent: dict[str, set[str]] = {}
    for primitive in catalog:
        if primitive.kind is not PrimitiveKind.OPERATION:
            continue
        contract = load_operation_contract(templates_dir / "operations" / primitive.name)
        if contract is None or contract.preferred_agent is None:
            continue
        contract_preferred_by_agent.setdefault(contract.preferred_agent, set()).add(primitive.name)

    rows: list[AgentRow] = []
    for installed_name in sorted(state.installed_primitives):
        catalog_entry = catalog_by_name.get(installed_name)
        if catalog_entry is None or catalog_entry.kind is not PrimitiveKind.AGENT:
            continue

        recipe_names: set[str] = set()
        operation_names: set[str] = set()
        for recipe in all_recipes:
            via_block = installed_name in block_by_recipe.get(recipe.name, set())
            via_closure = installed_name in closure_agents_by_recipe.get(recipe.name, set())
            if via_block or via_closure:
                recipe_names.add(recipe.name)
            if via_block:
                operation_names.update(runs_by_recipe_agent.get((recipe.name, installed_name), []))
        operation_names.update(contract_preferred_by_agent.get(installed_name, set()))

        rows.append(
            AgentRow(
                name=installed_name,
                recipes=sorted(recipe_names),
                operations=sorted(operation_names),
            )
        )
    return rows


@dataclass(frozen=True)
class WorkspaceRow:
    """One row in the ``wiki workspaces`` table (workspace-primitive spec).

    A distinct value type from :class:`AgentRow` — the workspace lister's
    columns are NAME / SCOPE / AGENT / OPERATIONS, where ``scope`` is the
    lens's membership tags (empty ⇒ a cross-cutting lens that covers all
    notes), ``agent`` is the single referenced agent name (or ``None``),
    and ``operations`` are the operations surfaced in the lens. Frozen —
    every consumer treats the row as a value. ``scope`` and ``operations``
    are sorted at construction for reproducible output; the CLI renders the
    empty cases at its boundary.
    """

    name: str
    scope: list[str] = field(default_factory=list)
    agent: str | None = None
    operations: list[str] = field(default_factory=list)


def list_workspaces(vault_root: Path, kit_root: Path) -> list[WorkspaceRow]:
    """Enumerate installed workspace primitives with their scope/agent/operations.

    Driven by ``cli._cmd_workspaces`` (``wiki workspaces``). Mirrors the
    *structure* of :func:`list_agents` — read the vault journal to derive
    the installed set, walk the catalog once to recover each name's
    primitive — but the workspace's lens fields (``scope``, ``agent``,
    ``operations``) come straight off the ``primitive.yaml`` manifest, so
    no recipe or contract walk is needed.

    A vault with no journal returns ``[]`` (matches the
    :func:`list_agents` / :func:`installed_outcome_verbs` precedent — the
    helper is pure and the dispatcher handles "not a vault" at its
    boundary). Rows are sorted alphabetically by NAME.
    """

    from llm_wiki_kit.journal import read_events, replay_state

    journal_path = vault_root / ".wiki.journal" / "journal.jsonl"
    if not journal_path.is_file():
        return []
    state = replay_state(read_events(journal_path))

    catalog = discover_primitives(kit_root / "templates")
    catalog_by_name: dict[str, Primitive] = {primitive.name: primitive for primitive in catalog}

    rows: list[WorkspaceRow] = []
    for installed_name in sorted(state.installed_primitives):
        primitive = catalog_by_name.get(installed_name)
        if primitive is None or primitive.kind is not PrimitiveKind.WORKSPACE:
            continue
        scope_tags = list(primitive.scope.workspaces) if primitive.scope is not None else []
        rows.append(
            WorkspaceRow(
                name=installed_name,
                scope=sorted(scope_tags),
                agent=primitive.agent,
                operations=sorted(primitive.operations),
            )
        )
    return rows


def resolve_dependencies(primitives: list[Primitive]) -> list[Primitive]:
    """Return ``primitives`` topologically sorted by ``requires:``.

    The input is assumed to be the closed set of primitives the caller
    intends to install — every name appearing in any primitive's
    ``requires:`` must also appear in ``primitives``. A missing dependency
    is the caller's bug (a recipe references a primitive it didn't
    install, or the always-include-core policy was skipped) and is raised
    as a :class:`PrimitiveError` rather than papered over.

    Cycles raise :class:`PrimitiveError`. Two primitives with no
    dependency relationship are ordered alphabetically by name so the
    journal of a freshly-rendered vault is reproducible.
    """

    by_name: dict[str, Primitive] = {}
    for primitive in primitives:
        if primitive.name in by_name:
            raise PrimitiveError(
                f"duplicate primitive name '{primitive.name}' in resolve_dependencies input"
            )
        by_name[primitive.name] = primitive

    for primitive in primitives:
        for required in primitive.requires:
            if required not in by_name:
                raise PrimitiveError(
                    f"primitive '{primitive.name}' requires '{required}' "
                    "but it is not in the input set"
                )

    ordered: list[Primitive] = []
    placed: set[str] = set()
    in_progress: set[str] = set()

    def visit(name: str, chain: tuple[str, ...]) -> None:
        if name in placed:
            return
        if name in in_progress:
            cycle = " -> ".join((*chain, name))
            raise PrimitiveError(f"cycle in primitive requires: {cycle}")
        in_progress.add(name)
        primitive = by_name[name]
        for required in sorted(primitive.requires):
            visit(required, (*chain, name))
        in_progress.discard(name)
        placed.add(name)
        ordered.append(primitive)

    for name in sorted(by_name):
        visit(name, ())

    return ordered
