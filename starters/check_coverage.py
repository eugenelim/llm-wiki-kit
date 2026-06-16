#!/usr/bin/env python3
"""Detect when a starter's seed pages don't demo every content-type / ontology.

Spec: ``docs/specs/starter-seed-coverage/spec.md``.
Plan: ``docs/specs/starter-seed-coverage/plan.md``.

Read-only mechanical check. For each starter recipe (``family``,
``work-os`` at v1), the script:

* loads the recipe and walks its primitive closure;
* for every ``content-type`` primitive, asserts at least one seed page
  under ``starters/_seed/<recipe>/wiki/**/*.md`` carries that primitive
  name in YAML frontmatter ``type:``;
* for every ``ontology`` primitive, asserts the wiki folder(s) it
  actually seeds (resolved from its ``files/wiki/`` tree — usually
  ``wiki/<name>/``, but the RFC-0009 container registries nest under
  ``efforts/<type>/``) contain at least one ``.md`` file;
* skips ``operation`` / ``agent`` / ``infrastructure`` primitives —
  they carry no structural seed-page signal (see spec §Non-goal 1).

The check is the input-side complement to
``starters/regenerate.py --check`` (which catches output-side byte
divergence). Lives outside ``llm_wiki_kit/`` deliberately so the
``pyproject.toml`` ``packages`` setting keeps it off the wheel surface.

Exit codes:

* ``0`` — clean (no findings)
* ``1`` — one or more primitives uncovered (per-recipe report on stdout)
* ``2`` — internal error (catalog won't parse, recipe loader raises)
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llm_wiki_kit.errors import WikiError  # noqa: E402
from llm_wiki_kit.models import Primitive, PrimitiveKind  # noqa: E402
from llm_wiki_kit.primitives import discover_primitives, load_primitive  # noqa: E402
from llm_wiki_kit.recipes import load_recipe, resolve_recipe_primitives  # noqa: E402

# ---------------------------------------------------------------------------
# Finding shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class Finding:
    """One uncovered primitive in one starter recipe.

    ``order=True`` makes ``sorted(findings)`` deterministic without a
    key function. **Field order is load-bearing as the sort key** —
    recipe first, primitive second, kind third, hint last — and
    matches spec §Outputs' per-recipe report shape. Reordering fields
    silently changes the report ordering without breaking any test
    that compares against the determinism contract (since the new
    order is also deterministic, just different). Do not reorder.
    """

    recipe: str
    primitive: str
    kind: str  # "content-type" or "ontology"
    hint: str


# ---------------------------------------------------------------------------
# Lazy access to RECIPE_TARGETS (plan §Approach — concern #5 / #7)
# ---------------------------------------------------------------------------


def _load_recipe_targets() -> dict[str, tuple[str, Path]]:
    """Lazy-import ``starters.regenerate`` to pull its ``RECIPE_TARGETS``.

    The import is *inside* this function so the script's top-of-file
    import list does not transitively touch ``regenerate.py``'s
    ``llm_wiki_kit.cli`` import. Per the AC8 boundary, this script
    must not surface ``regenerate.safe_write`` as a module-level
    alias — keeping the import local guarantees that property.
    """

    from starters import regenerate

    return regenerate.RECIPE_TARGETS


def _seed_dir(kit_root: Path, recipe: str) -> Path:
    return kit_root / "starters" / "_seed" / recipe


def _ontology_seeded_wiki_dirs(kit_root: Path, name: str) -> list[str]:
    """Return the wiki-relative folder(s) an ontology seeds, from its source tree.

    Most ontologies seed ``wiki/<name>/``, but the RFC-0009 container
    registries nest under ``efforts/<type>/`` (the ``trips`` ontology seeds
    ``files/wiki/efforts/trips/``). We read the primitive's own
    ``files/wiki/`` tree and return the relative path of every directory that
    directly contains a file — so coverage is checked against where the
    ontology *actually* seeds, not an assumed ``wiki/<name>/``. Falls back to
    ``[name]`` when the source tree is absent (e.g. a sideloaded primitive
    outside ``templates/ontologies``).
    """

    src = kit_root / "templates" / "ontologies" / name / "files" / "wiki"
    if not src.is_dir():
        return [name]
    rels = {
        str(f.parent.relative_to(src)).replace("\\", "/") for f in src.rglob("*") if f.is_file()
    }
    return sorted(rels) or [name]


# ---------------------------------------------------------------------------
# Catalog and frontmatter
# ---------------------------------------------------------------------------


def _load_catalog(kit_root: Path) -> list[Primitive]:
    """Union of ``templates/<kind>/<name>/primitive.yaml`` + ``core/primitive.yaml``."""

    primitives: list[Primitive] = []
    core_dir = kit_root / "core"
    if (core_dir / "primitive.yaml").is_file():
        primitives.append(load_primitive(core_dir))
    primitives.extend(discover_primitives(kit_root / "templates"))
    return primitives


def _read_frontmatter_type(path: Path) -> str | None:
    """Return the YAML frontmatter ``type:`` value, or ``None`` on any failure.

    Failure modes that return ``None`` (never raise):
    file unreadable, missing leading ``---\\n`` delimiter, unterminated
    frontmatter (no closing ``---``), invalid YAML inside the
    frontmatter, non-mapping top level, missing ``type:`` key, and
    non-string ``type:`` value.

    The contract that every failure path returns ``None`` is what makes
    a future ``pyyaml`` upgrade "only ever reduce coverage, never crash"
    — see plan §Risks R5.
    """

    try:
        # ``utf-8-sig`` transparently strips a UTF-8 BOM if present (some
        # editors inject one). Normalize CRLF → LF so Windows-authored
        # seed pages do not silently miss coverage; the spec's failure
        # mode for malformed frontmatter is None-return, not a silent
        # editor-induced regression that no diagnostic can surface.
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    # Look for the closing `\n---` (followed by EOL or EOF).
    end = text.find("\n---", 4)
    if end == -1:
        return None
    after = text[end + 4 : end + 5]
    if after not in {"", "\n", "\r"}:
        return None
    fm_text = text[4:end]
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    type_val = fm.get("type")
    if not isinstance(type_val, str):
        return None
    return type_val


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------


def _walk_coverage(kit_root: Path) -> tuple[list[Finding], int, int]:
    """Single-pass walk returning ``(findings, scored_count, starter_count)``.

    This is the **one** place coverage logic lives. ``check_coverage``
    delegates here for back-compat; ``main`` calls it directly so the
    summary line ("N primitive(s) across M starter(s) covered") and
    the findings list always agree by construction. A previous
    implementation kept a sibling ``_count_scored_primitives`` that
    re-walked the catalog and recipes — that drift bait, and the gap
    where ``_count_scored_primitives`` could raise outside ``main``'s
    ``try/except WikiError`` block, are both gone.
    """

    targets = _load_recipe_targets()
    starter_recipes = sorted(
        name for name, (_basename, parent) in targets.items() if parent.name == "starters"
    )
    catalog = _load_catalog(kit_root)
    findings: list[Finding] = []
    scored = 0
    starter_count = 0

    for recipe_name in starter_recipes:
        basename = targets[recipe_name][0]
        committed = kit_root / "starters" / basename
        if not committed.is_dir():
            sys.stderr.write(
                f"recipe {recipe_name} in RECIPE_TARGETS but {committed} absent — skipping\n"
            )
            continue

        recipe_path = kit_root / "recipes" / f"{recipe_name}.yaml"
        recipe_obj = load_recipe(recipe_path)
        closure = resolve_recipe_primitives(recipe_obj, catalog)
        starter_count += 1

        seed_dir = _seed_dir(kit_root, recipe_name)
        if seed_dir.is_dir():
            type_index: set[str] = {
                t
                for p in sorted(seed_dir.rglob("*.md"))
                if (t := _read_frontmatter_type(p)) is not None
            }
        else:
            type_index = set()

        for primitive in closure:
            if primitive.kind is PrimitiveKind.CONTENT_TYPE:
                scored += 1
                if primitive.name not in type_index:
                    findings.append(
                        Finding(
                            recipe=recipe_name,
                            primitive=primitive.name,
                            kind="content-type",
                            hint=(
                                f"author a seed page under "
                                f"starters/_seed/{recipe_name}/wiki/<ontology>/ "
                                f"with `type: {primitive.name}` in frontmatter"
                            ),
                        )
                    )
            elif primitive.kind is PrimitiveKind.ONTOLOGY:
                scored += 1
                # An ontology's seeded folder is *not* always ``wiki/<name>/``:
                # the RFC-0009 container registries nest under
                # ``efforts/<type>/`` (e.g. the ``trips`` ontology seeds
                # ``wiki/efforts/trips/``). Resolve the real seeded folder(s)
                # from the primitive's own ``files/wiki/`` tree rather than
                # assuming name == folder.
                seeded_rels = _ontology_seeded_wiki_dirs(kit_root, primitive.name)
                covered = any(
                    (d := seed_dir / "wiki" / rel).is_dir() and any(d.rglob("*.md"))
                    for rel in seeded_rels
                )
                if not covered:
                    where = " or ".join(f"wiki/{rel}/" for rel in seeded_rels) or (
                        f"wiki/{primitive.name}/"
                    )
                    findings.append(
                        Finding(
                            recipe=recipe_name,
                            primitive=primitive.name,
                            kind="ontology",
                            hint=(
                                f"author at least one .md file under "
                                f"starters/_seed/{recipe_name}/{where}"
                            ),
                        )
                    )
            # else: OPERATION, AGENT, INFRASTRUCTURE — skipped by design.

    return sorted(findings), scored, starter_count


def check_coverage(kit_root: Path) -> list[Finding]:
    """Return findings — empty list = clean.

    Thin wrapper over :func:`_walk_coverage` for callers that only need
    the findings list (e.g. tests that compare against ``[]``).
    """

    findings, _scored, _starters = _walk_coverage(kit_root)
    return findings


# ---------------------------------------------------------------------------
# Report rendering (pure — no I/O, takes counts from `_walk_coverage`)
# ---------------------------------------------------------------------------


def render_report(findings: list[Finding], scored: int, starters: int) -> str:
    """Render the stdout report.

    Pure function — does no I/O. Counts come from the same single
    walk that produced ``findings``, so the clean-summary line and
    the findings list cannot disagree.

    Clean: single-line summary.
    Findings: per-recipe blocks in alphabetical recipe order,
    primitives sorted alphabetically within each block.
    """

    if not findings:
        return f"coverage clean — {scored} primitive(s) across {starters} starter(s) covered\n"

    by_recipe: dict[str, list[Finding]] = {}
    for finding in findings:
        by_recipe.setdefault(finding.recipe, []).append(finding)

    blocks: list[str] = []
    for recipe in sorted(by_recipe):
        lines = [f"=== {recipe} ==="]
        for finding in by_recipe[recipe]:  # already sorted from _walk_coverage
            lines.append(f"  {finding.kind}: {finding.primitive} uncovered — {finding.hint}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None, *, kit_root: Path | None = None) -> int:
    """Run the coverage check.

    ``kit_root`` is the test seam (plan §Approach AC9 interpretation).
    Production CLI passes ``None``, falling back to module-level
    ``REPO_ROOT`` computed from ``__file__``.
    """

    parser = argparse.ArgumentParser(
        description="Check that starter seed pages demo every recipe content-type / ontology."
    )
    parser.parse_args(argv)

    effective_root = REPO_ROOT if kit_root is None else kit_root
    try:
        findings, scored, starters = _walk_coverage(effective_root)
    except WikiError as exc:
        sys.stderr.write(f"check_coverage: {exc}\n")
        return 2
    sys.stdout.write(render_report(findings, scored, starters))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
