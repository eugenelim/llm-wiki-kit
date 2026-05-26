"""Region-contribution aggregator used by ``wiki init`` and ``wiki add``.

ADR-0006 pins the contract: when N primitives declare a contribution to
the same managed region of a shared file, the installer concatenates
their snippet files in install order and calls
:func:`write_helper.safe_write_region` exactly once for that region.

This module exposes two surfaces:

* :func:`validate_contributions` — fail-before-writing check that every
  ``contributes_to`` entry on a primitive has a matching snippet file
  under ``<primitive_root>/regions/<file>.<region>``, and every snippet
  file in that directory has a matching ``contributes_to`` entry.
* :func:`aggregate_region_contributions` — the second pass of the
  install pipeline. Walks the installed primitives, groups their
  contributions by ``(file, region)``, concatenates snippets in
  install order, and writes each region once.

The two-pass split exists because ADR-0006 §Mechanics step 5 mandates
that primitives' ``files/`` trees land *before* their region
contributions are applied — so seed shared files (e.g.
``core/files/frontmatter.schema.yaml``) are on disk by the time
:func:`safe_write_region` looks for their region markers.

The aggregator's ``by`` attribution is the install vehicle
(``"wiki-init"``, ``"wiki-add"``), not any one contributing primitive.
A composed region body has multiple authors and naming any one of them
in the journal would be arbitrary; the contributing primitives are
already journaled by their own ``primitive.install`` events.
"""

from __future__ import annotations

import importlib.metadata
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from llm_wiki_kit import journal
from llm_wiki_kit.errors import PrimitiveError, WikiError
from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import (
    Contribution,
    OperationContract,
    Primitive,
    PrimitiveInstallEvent,
    PrimitiveKind,
)
from llm_wiki_kit.primitives import load_operation_contract
from llm_wiki_kit.render import _iter_files_relative, render_tree
from llm_wiki_kit.write_helper import safe_write, safe_write_region

_logger = logging.getLogger(__name__)

# Above this many journal events, an install pipeline that runs
# without an active ``use_journal_cache`` scope is operating on the
# wrong perf curve (O(events * writes)). The warning surfaces the
# discipline gap at the same severity as the journal-locking
# fallback warning in ``journal.py``.
_UNCACHED_INSTALL_PIPELINE_WARN_THRESHOLD = 50

# One warning per resolved journal path per process, so a multi-invocation
# session (or a test that drives install_primitives many times) doesn't
# carpet-bomb the log.
_UNCACHED_PIPELINE_WARNED: set[Path] = set()


def _warn_if_install_pipeline_uncached(journal_path: Path) -> None:
    """Emit one WARNING per resolved journal path if no cache scope is active.

    The cache is opt-in at the handler boundary; a new install-style
    handler that forgets the ``with journal.use_journal_cache(...):``
    wrapper falls back to O(events * writes) baseline lookups silently
    — no test fails, the install is just slow. This warning is the
    runtime signal that turns "the install feels slow" into a
    grep-able log line naming the spec.

    Below ``_UNCACHED_INSTALL_PIPELINE_WARN_THRESHOLD`` events, the
    perf cliff is negligible; we don't warn. The threshold is
    intentionally lenient — the warning is for an honest forgot-the-
    wrapper bug on a real-sized vault, not a one-off small write.
    """

    if journal._CURRENT_READER.get() is not None:
        return
    if not journal_path.exists():
        return  # fresh vault; nothing yet to count
    try:
        event_count = sum(1 for _ in journal_path.open("r", encoding="utf-8"))
    except OSError:
        return  # don't crash on a transient read failure
    if event_count < _UNCACHED_INSTALL_PIPELINE_WARN_THRESHOLD:
        return
    resolved = journal_path.resolve()
    if resolved in _UNCACHED_PIPELINE_WARNED:
        return
    _UNCACHED_PIPELINE_WARNED.add(resolved)
    _logger.warning(
        "install pipeline running without a journal.use_journal_cache() "
        "scope on a vault with %d events at %s — baseline lookups will "
        "be O(events * writes). See docs/specs/journal-reader-cache/spec.md.",
        event_count,
        resolved,
    )


_REGIONS_SUBDIR = "regions"


def enumerate_rendered_paths(
    primitives: Sequence[Primitive],
    sources: Mapping[str, Path],
) -> set[str]:
    """Return the vault-relative POSIX paths the renderer would produce.

    Walks each primitive's ``<source>/files/`` tree (via the shared
    private :func:`llm_wiki_kit.render._iter_files_relative` helper)
    and returns the union of relative paths as a set. Pure function:
    no writes, no journal events, no side effects.

    **Scope.** Source-of-truth for the *renderer's* path set — only
    what :func:`llm_wiki_kit.render.render_tree` will actually write
    to disk via :func:`safe_write`. Managed-region host files that
    no primitive ships in its ``files/`` tree but DO appear as a
    `contributes_to` target are NOT in this set; the adopt-set
    computation in :func:`llm_wiki_kit.adopt.compute_adoption_set`
    unions them in separately. The AC22 structural pin
    (spec ``docs/specs/wiki-init-adopt/spec.md`` §Contracts;
    ADR-0008 §Decision sub-choice 2) keeps this walker AND the
    renderer's walker pointed at the same code path
    (``_iter_files_relative``) so the two cannot drift. A primitive
    with no source root in ``sources`` or no ``files/`` directory
    contributes nothing.
    """

    paths: set[str] = set()
    for primitive in primitives:
        root = sources.get(primitive.name)
        if root is None:
            continue
        for relative_posix in _iter_files_relative(root / "files"):
            paths.add(relative_posix)
    return paths


@dataclass(frozen=True)
class _Bucket:
    """One ``(file, region)`` pair and its contributors in install order."""

    file: str
    region: str
    contributors: tuple[tuple[str, Path], ...]  # (primitive_name, snippet_path)


def _snippet_filename(contribution: Contribution) -> str:
    """Return the on-disk filename for ``contribution`` under ``regions/``.

    Per ADR-0006 §Mechanics step 1, the filename is the literal ``file``
    value joined to the literal ``region`` value with a single ``.``.
    Path traversal is forbidden in either component — both come from a
    Pydantic-validated manifest, but defence in depth catches a future
    refactor that loosens the schema.
    """

    if "/" in contribution.file or "/" in contribution.region:
        raise PrimitiveError(
            f"contribution file/region must not contain '/': "
            f"file={contribution.file!r} region={contribution.region!r}"
        )
    if contribution.file.startswith(".."):
        raise PrimitiveError(f"contribution file must not start with '..': {contribution.file!r}")
    return f"{contribution.file}.{contribution.region}"


def _declared_snippets(primitive: Primitive) -> dict[str, Contribution]:
    return {_snippet_filename(c): c for c in primitive.contributes_to}


def validate_contributions(primitive: Primitive, primitive_root: Path) -> None:
    """Raise :class:`PrimitiveError` if a primitive's contribution shape is wrong.

    ADR-0006 §Mechanics step 6 names two fatal mismatches:

    * **Missing snippet:** a ``contributes_to`` entry with no
      corresponding file under ``regions/``.
    * **Orphan snippet:** a file under ``regions/`` whose name is not
      declared in ``contributes_to``.

    A primitive with no ``contributes_to`` entries and no ``regions/``
    directory is valid and a no-op here.
    """

    declared = _declared_snippets(primitive)
    regions_dir = primitive_root / _REGIONS_SUBDIR

    for snippet_name, contribution in declared.items():
        snippet_path = regions_dir / snippet_name
        if not snippet_path.is_file():
            raise PrimitiveError(
                f"primitive '{primitive.name}' declares contribution to "
                f"{contribution.file}:{contribution.region} but snippet file "
                f"{snippet_path} is missing"
            )

    if not regions_dir.is_dir():
        # No regions/ directory at all: declared must also be empty
        # (the loop above would have raised). Nothing more to check.
        return

    for entry in sorted(regions_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.name not in declared:
            raise PrimitiveError(
                f"primitive '{primitive.name}' has orphan snippet "
                f"{entry} with no matching contributes_to entry"
            )


def _normalise_snippet(text: str) -> str:
    """Return ``text`` with exactly one trailing newline (ADR-0006 step 4)."""

    return text.rstrip("\n") + "\n"


def _plan(
    primitives: Sequence[Primitive],
    primitive_sources: Mapping[str, Path],
) -> list[_Bucket]:
    """Group contributions across ``primitives`` into install-ordered buckets.

    ``primitives`` is assumed to already be in install order
    (topologically sorted by ``requires:``, alphabetical tiebreaker —
    see :func:`primitives.resolve_dependencies`). The aggregator
    preserves that order within each bucket. Buckets themselves are
    emitted in alphabetical order by ``(file, region)`` so the install
    pipeline is reproducible.
    """

    grouped: dict[tuple[str, str], list[tuple[str, Path]]] = {}
    for primitive in primitives:
        root = primitive_sources.get(primitive.name)
        if root is None:
            raise PrimitiveError(
                f"install: no source directory recorded for primitive '{primitive.name}'"
            )
        for contribution in primitive.contributes_to:
            snippet_path = root / _REGIONS_SUBDIR / _snippet_filename(contribution)
            key = (contribution.file, contribution.region)
            grouped.setdefault(key, []).append((primitive.name, snippet_path))

    buckets: list[_Bucket] = []
    for file, region in sorted(grouped):
        buckets.append(
            _Bucket(file=file, region=region, contributors=tuple(grouped[(file, region)]))
        )
    return buckets


def check_region_owner_uniqueness(primitives: Sequence[Primitive]) -> None:
    """Reject sideload contributions to managed regions a bundled primitive already owns.

    Per ``docs/specs/primitive-sideload/spec.md`` §"Collision policy"
    case 4 and §Invariants ("cannot override a bundled region"): a
    sideload package may not contribute to a ``(file, region)`` pair
    that any bundled primitive also contributes to. Multiple bundled
    primitives contributing to the same region remain supported
    (ADR-0006 is unchanged); the asymmetry is the load-bearing
    "additive-only at the sideload boundary" invariant — a sideload
    package cannot piggyback on a region the bundled catalog
    structurally owns.

    Two sideload packages contributing to the same region are also
    rejected here (cross-sideload region-content collisions can't be
    coordinated and would silently glue together in install order).

    The check runs at the install boundary so the error fires
    against the same primitive set the aggregator is about to walk;
    discovery-time was the wrong layer because the bundled catalog
    contains the legitimate multi-bundled-contributor case.
    """

    # Two-pass walk so the collision contract is invariant to the
    # caller's primitive ordering. ``aggregate_region_contributions``
    # passes the topologically/alphabetically sorted ``all_installed``
    # list; a one-pass walk would silently accept a bundled-vs-sideload
    # collision when the sideload primitive's name happens to sort
    # ahead of the bundled contributor. Pass 1 registers every bundled
    # owner; pass 2 checks every sideload contribution against the
    # fully-built map, plus cross-sideload uniqueness.
    bundled_owners: dict[tuple[str, str], str] = {}
    for primitive in primitives:
        if primitive.source != "bundled":
            continue
        for contribution in primitive.contributes_to:
            key = (contribution.file, contribution.region)
            bundled_owners.setdefault(key, primitive.name)

    sideload_owners: dict[tuple[str, str], str] = {}
    for primitive in primitives:
        if primitive.source == "bundled":
            continue
        sideload_pkg = (
            primitive.source.split(":", 1)[1] if ":" in primitive.source else primitive.source
        )
        for contribution in primitive.contributes_to:
            key = (contribution.file, contribution.region)
            if key in bundled_owners:
                raise WikiError(
                    f"sideload primitive '{primitive.name}' from package "
                    f"'{sideload_pkg}' contributes to region "
                    f"'{contribution.file}:{contribution.region}', which is "
                    f"already owned by bundled primitive "
                    f"'{bundled_owners[key]}'. Sideload packages cannot "
                    "override bundled regions; uninstall the package or "
                    "ask the upstream maintainer to add the contribution "
                    "to the kit."
                )
            if key in sideload_owners:
                raise WikiError(
                    f"sideload primitive '{primitive.name}' (from package "
                    f"'{sideload_pkg}') and another sideload primitive "
                    f"'{sideload_owners[key]}' both contribute to region "
                    f"'{contribution.file}:{contribution.region}'. Two "
                    "sideload packages cannot share a managed-region "
                    "contribution; uninstall one."
                )
            sideload_owners[key] = primitive.name


def aggregate_region_contributions(
    primitives: Sequence[Primitive],
    primitive_sources: Mapping[str, Path],
    journal_path: Path,
    by: str,
) -> None:
    """Apply every region contribution across ``primitives`` to the vault.

    Reads each contributor's snippet from disk, normalises trailing
    newlines, concatenates in install order, and calls
    :func:`safe_write_region` exactly once per ``(file, region)``
    bucket. Idempotent on re-run: a body whose hash matches the most
    recent ``managed_region.write`` event is a no-op write (the kit
    still emits the event, by design — the audit trail records every
    composed body, not just the ones that changed bytes).

    Pre-condition: every primitive's ``files/`` tree has already been
    rendered into the vault, so the shared file the region lives in is
    on disk. ``safe_write_region`` raises :class:`FileNotFoundError`
    otherwise.
    """

    check_region_owner_uniqueness(primitives)
    buckets = _plan(primitives, primitive_sources)
    vault_root = journal_path.parent.parent

    for bucket in buckets:
        body_parts: list[str] = []
        for _primitive_name, snippet_path in bucket.contributors:
            text = snippet_path.read_text(encoding="utf-8")
            body_parts.append(_normalise_snippet(text))
        composed = "".join(body_parts)
        safe_write_region(
            file_path=vault_root / bucket.file,
            region_id=bucket.region,
            new_content=composed,
            by=by,
            journal_path=journal_path,
        )


def install_primitives(
    *,
    to_install: Sequence[Primitive],
    all_installed: Sequence[Primitive],
    sources: Mapping[str, Path],
    journal_path: Path,
    context: Mapping[str, str],
    install_vehicle: str,
    now: datetime,
) -> None:
    """Render ``to_install`` and run the region aggregator over ``all_installed``.

    Shared between ``wiki init`` and ``wiki add``. The split between the
    two sequences is what lets ``wiki add`` re-aggregate every region
    over the full installed set (so existing bodies survive) without
    re-rendering primitives that have already landed (which would emit
    duplicate ``page.write`` events).

    Pre-condition: every primitive in ``to_install`` has already passed
    :func:`validate_contributions`. The caller (``_cmd_init``,
    ``_cmd_add``) owns that pre-flight so a malformed primitive cannot
    leak into the half-installed state this function would produce.
    ``sources`` must cover every primitive in ``all_installed``.

    ``install_vehicle`` is the ``by`` attribution recorded on the
    aggregator's ``managed_region.write`` events — ``"wiki-init"`` for
    initial vault creation, ``"wiki-add"`` for subsequent ``wiki add``
    installs. Per-primitive ``files/`` renders attribute to the
    primitive name itself, matching the existing render contract.
    """

    _warn_if_install_pipeline_uncached(journal_path)
    vault_root = journal_path.parent.parent
    for primitive in to_install:
        # Sideloaded primitives record their ``"sideload:<package>"``
        # source on the install event so ``wiki doctor`` can hint at
        # the previously-installed package after the package is
        # uninstalled (``docs/specs/primitive-sideload/spec.md`` AC17).
        # Bundled primitives omit the field (write ``None``) so the
        # journal-line shape is unchanged for installations that never
        # touch a sideload package — older journal lines replay
        # identically.
        primitive_source = primitive.source if primitive.source != "bundled" else None
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=now,
                by=install_vehicle,
                primitive=primitive.name,
                version=primitive.version,
                source=primitive_source,
            ),
        )
        render_tree(
            sources[primitive.name] / "files",
            vault_root,
            context,
            journal_path,
            by=primitive.name,
        )

    aggregate_region_contributions(
        all_installed,
        sources,
        journal_path,
        by=install_vehicle,
    )

    # Outcome-named entry points: write one slash stub per declared
    # verb across every installed operation primitive (spec
    # ``docs/specs/outcome-named-entry-points/spec.md`` §Outputs §2).
    # Walks ``all_installed`` rather than ``to_install`` so a
    # ``wiki add`` of a non-outcome-declaring primitive does not
    # drop stubs for the already-installed outcome-declaring ones.
    write_outcome_slash_stubs(
        primitives=all_installed,
        sources=sources,
        journal_path=journal_path,
        by=install_vehicle,
    )


# ---------------------------------------------------------------------------
# Outcome-named entry points — slash-stub writer and SKILL-fragment validator
#
# Spec: ``docs/specs/outcome-named-entry-points/spec.md`` §Outputs §2 +
# §Inputs §3. Both functions are shared between the init/add path
# (``install_primitives``) and the upgrade path
# (``upgrade.upgrade_primitives``); the SKILL validator is called by
# the CLI handlers BEFORE their ``journal.use_journal_cache`` scope
# opens so a missing-verb failure leaves zero side effects.
# ---------------------------------------------------------------------------


_SLASH_STUB_TEMPLATE = (
    "---\n"
    "description: Invoke the {operation} operation (alias: /{verb}).\n"
    "---\n"
    "Run the `{skill}` skill from this vault. See the SKILL's own\n"
    "`when to load` section for inputs.\n"
    "\n"
    "<!-- BEGIN MANAGED: outcome-provenance -->\n"
    "{provenance_block_body}"
    "<!-- END MANAGED: outcome-provenance -->\n"
)

# Region body for the ``outcome-provenance`` managed-region inside a
# slash stub. Bundled stubs ship the block with an empty body (an empty
# string), so the region delimiters round-trip stably through
# ``safe_write`` on every ``wiki upgrade``. Sideloaded stubs ship the
# block populated with a blockquote-rendered note naming the package and
# version, per ``docs/specs/primitive-sideload/spec.md`` §"Outputs
# ``Slash-stub managed-region provenance block``".
_SIDELOAD_PROVENANCE_TEMPLATE = (
    "> From sideload package: `{package}` (version `{version}`).\n"
    "> The kit does not validate third-party trigger rates.\n"
)

# PEP 503 normalised distribution name + PEP 440 version (loose) — used
# to validate package + version strings sourced from third-party wheels
# before interpolating them into a vault file Claude Code reads. A
# hand-crafted wheel whose METADATA carries a backtick or newline in
# Name: or Version: could otherwise break out of the slash-stub's
# inline-code span and blockquote, injecting instructions into the
# agent's context. The validator rejects any byte outside the
# documented character classes; out-of-spec values render as the
# literal placeholder ``invalid`` (see :func:`_outcome_provenance_block_body`).
_PEP503_NORMALISED_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PEP440_LOOSE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+!-]*$")


def _safe_provenance_token(value: str, pattern: re.Pattern[str]) -> str:
    """Return ``value`` if it matches ``pattern``, else the literal ``invalid``.

    Defence-in-depth at the only place the kit synthesises sideload-
    sourced bytes into vault content (the slash-stub provenance block):
    a malicious or malformed wheel METADATA file could ship a Name or
    Version containing newlines, backticks, or other markdown-active
    bytes. Replacing such values with the literal string ``invalid``
    keeps the block well-formed; the operator notices the placeholder
    and can ``pip show`` the offending package to diagnose.
    """

    return value if pattern.fullmatch(value) else "invalid"


def _outcome_provenance_block_body(primitive: Primitive) -> str:
    """Return the body of the ``outcome-provenance`` managed region.

    Empty string for bundled primitives (the region delimiters still
    surround empty space — present-and-empty rather than absent — so
    the managed-region machinery treats the block as kit-owned and
    the diff is stable across ``wiki upgrade`` runs). For sideloaded
    primitives, the body is a blockquote naming the package and the
    version resolved at render time via
    :func:`importlib.metadata.version`. A sideload package version
    bump between runs legitimately changes the body and surfaces
    through the existing ``.proposed`` drift path (ADR-0004) — that
    is the spec's named contract, not a bug.
    """

    if primitive.source == "bundled":
        return ""
    if not primitive.source.startswith("sideload:"):
        # Defensive: a future source label we don't recognise renders
        # as a sanitised single-line provenance note rather than a
        # crash. The label itself is sanitised because the source
        # field's Pydantic validator (see ``Primitive.source``) is the
        # primary defence — this branch is belt-and-braces.
        token = _safe_provenance_token(primitive.source, _PEP503_NORMALISED_NAME)
        return f"> From source: `{token}`.\n"
    raw_package = primitive.source.split(":", 1)[1]
    try:
        raw_version = importlib.metadata.version(raw_package)
    except importlib.metadata.PackageNotFoundError:
        # The discovery walk saw the package's metadata; if the
        # subsequent ``version()`` lookup fails the wheel was likely
        # uninstalled between discovery and stub render. ``unknown`` is
        # the kit's sentinel for "metadata didn't resolve"; the user
        # notices it and can ``pip show`` to diagnose.
        _logger.warning(
            "sideload package '%s' metadata vanished between discovery "
            "and slash-stub render; provenance version will render as "
            "'unknown'",
            raw_package,
        )
        raw_version = "unknown"
    package = _safe_provenance_token(raw_package, _PEP503_NORMALISED_NAME)
    version = _safe_provenance_token(raw_version, _PEP440_LOOSE_VERSION)
    return _SIDELOAD_PROVENANCE_TEMPLATE.format(package=package, version=version)


def _resolved_skill_name(contract: OperationContract) -> str:
    """Return the skill name with ``contract.skill or contract.name`` fallback.

    Matches ``_cmd_run``'s resolution (``run.py:508``) and PR-4's
    ``installed_outcome_verbs`` so the on-disk stub and the
    discovery surface stay consistent for an operation that omits
    ``skill:``.
    """

    return contract.skill or contract.name


def write_outcome_slash_stubs(
    *,
    primitives: Sequence[Primitive],
    sources: Mapping[str, Path],
    journal_path: Path,
    by: str,
) -> None:
    """Write one slash stub per declared outcome verb in ``primitives``.

    For each operation-kind primitive whose ``contract.yaml``
    declares one or more outcomes, write
    ``<vault>/.claude/commands/<verb>.md`` via :func:`safe_write`.
    The stub body is the fixed-body template from spec §Outputs §2
    with ``{operation}``, ``{verb}``, and ``{skill}`` substituted.

    Walks ``primitives`` in the order given — callers pass
    ``all_installed`` (topologically sorted) so the on-disk write
    order is reproducible.

    ``by`` is the calling vehicle (``INSTALL_VEHICLE_INIT``,
    ``INSTALL_VEHICLE_ADD``, ``UPGRADE_VEHICLE``) — stubs attribute
    to their caller, not a stub-specific vehicle constant (plan
    §PR-3 step 3 "no new vehicle constant"). The same primitive's
    region-aggregator writes share this convention.
    """

    vault_root = journal_path.parent.parent
    for primitive in primitives:
        if primitive.kind is not PrimitiveKind.OPERATION:
            continue
        source = sources.get(primitive.name)
        if source is None:
            continue
        contract = load_operation_contract(source)
        if contract is None or not contract.outcomes:
            continue
        skill = _resolved_skill_name(contract)
        provenance_block_body = _outcome_provenance_block_body(primitive)
        for verb in contract.outcomes:
            body = _SLASH_STUB_TEMPLATE.format(
                operation=primitive.name,
                verb=verb,
                skill=skill,
                provenance_block_body=provenance_block_body,
            )
            safe_write(
                path=vault_root / ".claude" / "commands" / f"{verb}.md",
                content=body,
                by=by,
                journal_path=journal_path,
            )


def _read_skill_description(
    *,
    primitive_name: str,
    contract_path: Path,
    skill_md_path: Path,
) -> str:
    """Read the SKILL.md frontmatter ``description:`` field, or raise.

    Three distinct failure modes get distinct ``WikiError`` messages
    so a primitive author hits the actual root cause rather than the
    misleading "verb missing" surface:

    1. SKILL.md not on disk — likely a wrong ``skill:`` value in the
       contract.
    2. SKILL.md has no YAML frontmatter — file is structurally wrong.
    3. Frontmatter parses but ``description:`` is missing or non-string.

    Malformed YAML inside the frontmatter still raises with the
    SKILL.md path, since the parser's own message is the
    user-actionable detail. The validator below catches the
    "frontmatter parses but verb absent" case separately.
    """

    if not skill_md_path.is_file():
        raise WikiError(
            f"operation '{primitive_name}' declares outcomes but its "
            f"SKILL.md is missing.\n"
            f"  contract.yaml: {contract_path}\n"
            f"  expected SKILL.md: {skill_md_path}\n"
            "Check the contract's `skill:` value matches the on-disk "
            "skill directory name."
        )
    text = skill_md_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise WikiError(
            f"operation '{primitive_name}' declares outcomes but its "
            f"SKILL.md has no YAML frontmatter.\n"
            f"  SKILL.md: {skill_md_path}\n"
            "Add a `--- ... ---` frontmatter block with a "
            "`description:` field naming the verb."
        )
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise WikiError(
            f"operation '{primitive_name}' SKILL.md frontmatter is "
            f"malformed YAML.\n"
            f"  SKILL.md: {skill_md_path}\n"
            f"  parser:   {exc}"
        ) from exc
    description = meta.get("description")
    if not isinstance(description, str):
        raise WikiError(
            f"operation '{primitive_name}' SKILL.md frontmatter has no "
            f"string `description:` field.\n"
            f"  SKILL.md: {skill_md_path}\n"
            "Add `description: <natural-language sentence naming the "
            "verb>` to the frontmatter."
        )
    if not description.strip():
        raise WikiError(
            f"operation '{primitive_name}' SKILL.md frontmatter "
            f"`description:` field is empty.\n"
            f"  SKILL.md: {skill_md_path}\n"
            "Add natural-language text naming the outcome verb so the "
            "SKILL describes when to load itself."
        )
    return description


def validate_outcome_skill_fragments(
    *,
    primitives: Sequence[Primitive],
    sources: Mapping[str, Path],
) -> None:
    """Refuse the install if any declared verb is missing from its SKILL.md.

    Pre-flight validator called by ``_cmd_init`` / ``_cmd_add`` /
    ``_cmd_upgrade`` BEFORE their ``journal.use_journal_cache``
    scope opens — same call site as :func:`validate_contributions`.
    Reads each operation primitive's ``contract.yaml`` and the
    matching ``files/skills/<skill>/SKILL.md`` from the source tree
    (not the vault); raises :class:`WikiError` naming both files on
    the first verb that is not present as a whole word (``\\b<verb>\\b``)
    in the SKILL's frontmatter ``description``.

    Verbs are ASCII-only by spec §Inputs §2 rule 2, so the regex is
    safe in Python's default Unicode-aware mode. Note that ``\\b``
    fires at hyphen-to-letter transitions, so a verb like
    ``prep-digest`` *would* technically match inside ``re-prep-digest``;
    this is a known loose-boundary behaviour. No realistic SKILL.md
    description triggers it, but a future spec amendment can tighten
    to ``(?<![\\w-])<verb>(?![\\w-])`` if needed.
    """

    for primitive in primitives:
        if primitive.kind is not PrimitiveKind.OPERATION:
            continue
        source = sources.get(primitive.name)
        if source is None:
            continue
        contract = load_operation_contract(source)
        if contract is None or not contract.outcomes:
            continue
        skill = _resolved_skill_name(contract)
        skill_md_path = source / "files" / "skills" / skill / "SKILL.md"
        description = _read_skill_description(
            primitive_name=primitive.name,
            contract_path=source / "contract.yaml",
            skill_md_path=skill_md_path,
        )
        for verb in contract.outcomes:
            if not re.search(rf"\b{re.escape(verb)}\b", description):
                raise WikiError(
                    f"operation '{primitive.name}' declares outcome verb "
                    f"'{verb}' but the SKILL.md description does not "
                    f"contain it as a whole word.\n"
                    f"  contract.yaml: {source / 'contract.yaml'}\n"
                    f"  SKILL.md:      {skill_md_path}\n"
                    "Add the verb to the SKILL's frontmatter "
                    "`description:` field (spec §Inputs §3)."
                )
