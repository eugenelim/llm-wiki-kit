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

from pathlib import Path

import yaml
from pydantic import ValidationError as PydanticValidationError

from llm_wiki_kit.errors import PrimitiveError, ValidationError
from llm_wiki_kit.models import Primitive

# Catalog directory names per ``docs/architecture/overview.md``. The kit ships
# the kind subdirectories pluralized (``ontologies/`` for the ``ontology``
# kind, etc.); ``infrastructure`` is uncountable and matches its kind value
# directly. The mapping is one-way (directory → expected kind) — discovery
# does not enforce that a primitive in ``ontologies/`` declares ``kind:
# ontology``; that's a primitive-author check we leave to ``wiki doctor``.
_CATALOG_DIRS: frozenset[str] = frozenset(
    [
        "ontologies",
        "content-types",
        "operations",
        "infrastructure",
    ]
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
        return Primitive.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(f"primitive.yaml at {path}", exc) from exc


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
    """

    if not templates_dir.exists():
        return []

    primitives: list[Primitive] = []
    for kind_dir in sorted(templates_dir.iterdir()):
        if not kind_dir.is_dir() or kind_dir.name not in _CATALOG_DIRS:
            continue
        for primitive_dir in sorted(kind_dir.iterdir()):
            if not primitive_dir.is_dir():
                continue
            if not (primitive_dir / "primitive.yaml").exists():
                continue
            primitives.append(load_primitive(primitive_dir))

    primitives.sort(key=lambda p: p.name)
    return primitives


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
