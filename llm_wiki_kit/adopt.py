"""Recipe-filtered adoption-set computation for ``wiki init --adopt``.

This module owns the adoption operation's identity (the
``"wiki-init-adopt"`` install-vehicle constant) and the pure-function
walker that turns a recipe closure plus an on-disk target into the
ordered list of pre-existing kit-owned files the adopt phase will
seed as journal baselines.

ADR-0008 §Decision sub-choice 2 pins what counts as kit-owned-by-
recipe: a path in
:func:`llm_wiki_kit.install.enumerate_rendered_paths` OR a managed-
region host file (a path named by any
:attr:`Primitive.contributes_to` entry's ``file`` value). The
adoption set is a strict subset of the recipe's rendered closure;
files outside it are left untouched by the adopt phase
(spec ``docs/specs/wiki-init-adopt/spec.md`` §Invariant 3).

Two refusal cases land here, BEFORE any journal event is appended
(spec §Error cases):

1. **Malformed managed-region markers** — a pre-existing host file
   the recipe needs whose markers do not parse via
   :func:`managed_regions.parse`.
2. **Missing required region** — a parseable host file lacking
   marker block(s) for a region a primitive's ``contributes_to``
   names.

Both raise :class:`WikiError`. The caller (``cli._cmd_init``) runs
the walker OUTSIDE the journal-cache scope so a refusal leaves zero
side effects on disk (no half-init journal, no kit-owned
directories created by ``target.mkdir``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from llm_wiki_kit import managed_regions
from llm_wiki_kit.errors import ManagedRegionError, WikiError
from llm_wiki_kit.install import enumerate_rendered_paths
from llm_wiki_kit.models import Primitive
from llm_wiki_kit.write_helper import _relative_to_vault

INSTALL_VEHICLE_ADOPT = "wiki-init-adopt"
"""The ``by`` attribution recorded on adoption-phase journal events.

Single source of truth for the string ``cli._cmd_init`` writes onto
every :class:`PageAdoptedEvent` and :class:`ManagedRegionAdoptedEvent`
during the adopt phase. ``VaultInitEvent``,
``PrimitiveInstallEvent``, and the aggregator-emitted
``ManagedRegionWriteEvent`` continue to attribute to ``"wiki-init"``
— see spec ``docs/specs/wiki-init-adopt/spec.md`` §Invariant 6.

Co-located here (rather than in ``cli.py`` next to
``INSTALL_VEHICLE_INIT``) so the value lives with the module that
defines the adopt operation's identity, mirroring
``upgrade.UPGRADE_VEHICLE``'s placement.
"""


@dataclass(frozen=True)
class AdoptedRegion:
    """One ``(region, content_hash)`` seed for a managed-region host file.

    ``content_hash`` is sha256 of
    :func:`managed_regions.canonical_region_body` applied to the
    region body on disk — the same canonicalisation
    :func:`safe_write_region`'s baseline lookup uses, so the
    region-baseline comparison matches without spurious drift on the
    aggregator's first call (spec §Outputs Journal events bullet 2).
    """

    region: str
    content_hash: str


@dataclass(frozen=True)
class HostAdoption:
    """One pre-existing kit-owned file the adopt phase will seed.

    ``hash`` is sha256 of the file's full byte content (NOT the
    kit's would-render content — spec §Outputs Journal events
    bullet 2). ``regions`` is non-empty only for managed-region host
    files; populated in ``sorted(region)`` order so the journal slice
    is deterministic across runs.
    """

    path: str
    hash: str
    regions: tuple[AdoptedRegion, ...]


@dataclass(frozen=True)
class AdoptionSet:
    """The result of :func:`compute_adoption_set`.

    ``host_adoptions`` lists each pre-existing kit-owned file in
    ``sorted(path)`` order (spec AC6).
    ``pre_existing_sidecars`` lists vault-relative POSIX paths of
    ``.proposed`` files whose non-``.proposed`` form is in the
    recipe's rendered closure — surfaced to the user via a
    stderr-only warning but NOT journaled (spec AC10; §Edge cases
    "Target contains `.proposed` sidecars from a prior run").
    """

    host_adoptions: tuple[HostAdoption, ...]
    pre_existing_sidecars: tuple[str, ...]


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _required_regions(primitives: Sequence[Primitive]) -> dict[str, set[str]]:
    """Return ``{host_file: {region_id, ...}}`` for every contribution.

    Built from every primitive's ``contributes_to`` declarations. Used
    by :func:`compute_adoption_set` to (a) decide which pre-existing
    host files need region-level seeding and (b) pre-flight that each
    needed region exists on disk before the install pipeline runs.
    """

    required: dict[str, set[str]] = {}
    for primitive in primitives:
        for contribution in primitive.contributes_to:
            required.setdefault(contribution.file, set()).add(contribution.region)
    return required


def compute_adoption_set(
    vault_root: Path,
    primitives: Sequence[Primitive],
    sources: Mapping[str, Path],
) -> AdoptionSet:
    """Build the ordered adoption set from the recipe closure and on-disk state.

    Pure modulo filesystem reads: walks every primitive's ``files/``
    tree (via :func:`enumerate_rendered_paths`), intersects with
    on-disk paths, hashes each adopted file, parses managed-region
    host files, and pre-flights region-marker presence. Does NOT
    append journal events; the caller (``cli._cmd_init``) writes them
    inside its ``journal.use_journal_cache`` scope.

    Refuses with :class:`WikiError` on:

    - A symlink under a kit-owned path whose target resolves outside
      ``vault_root`` (spec AC19).
    - A pre-existing host file the recipe needs whose markers do not
      parse (spec AC9).
    - A parseable host file lacking markers for a region the recipe
      contributes to (spec AC9b).

    All three are pre-flighted in this function so a refusal leaves
    no journal events behind.
    """

    rendered = enumerate_rendered_paths(primitives, sources)
    required_regions = _required_regions(primitives)
    # Managed-region host files belong to kit territory regardless of
    # whether any primitive's ``files/`` tree ships them — a host
    # file's region adopt is the only way to seed the region baseline.
    # Include the host paths in the adoption-candidate set so a
    # primitive whose only claim on the file is a ``contributes_to``
    # entry still gets the host's region rows journaled. The set
    # union deduplicates: a host file that's both rendered AND a
    # contribution target gets one walk, one ``PageAdoptedEvent``,
    # and the regions populated from ``required_regions``.
    adoption_candidates = rendered | set(required_regions)

    host_adoptions: list[HostAdoption] = []
    for relative_path in sorted(adoption_candidates):
        abs_path = vault_root / relative_path
        if not abs_path.exists() or not abs_path.is_file():
            continue

        # Symlink-escape pre-flight: a path that lives inside
        # vault_root lexically but resolves outside it raises.
        _relative_to_vault(abs_path, vault_root)

        file_bytes = abs_path.read_bytes()
        page_hash = _hash(file_bytes)

        regions: tuple[AdoptedRegion, ...] = ()
        needed_regions = required_regions.get(relative_path)
        if needed_regions:
            try:
                file_text = file_bytes.decode("utf-8")
                parsed = managed_regions.parse(file_text)
            except (ManagedRegionError, UnicodeDecodeError) as exc:
                raise WikiError(
                    f"cannot adopt managed-region host '{relative_path}': "
                    f"markers do not parse ({exc})"
                ) from exc
            for region_id in sorted(needed_regions):
                if region_id not in parsed:
                    raise WikiError(
                        f"cannot adopt managed-region host '{relative_path}': "
                        f"missing markers for region '{region_id}' the recipe needs"
                    )
            regions = tuple(
                AdoptedRegion(
                    region=region_id,
                    content_hash=_hash(managed_regions.canonical_region_body(parsed[region_id])),
                )
                for region_id in sorted(needed_regions)
            )

        host_adoptions.append(HostAdoption(path=relative_path, hash=page_hash, regions=regions))

    # Sidecar scan is scoped to ``rendered`` (the renderer's path
    # set), NOT to ``adoption_candidates``. Managed-region hosts
    # added to ``adoption_candidates`` via ``contributes_to`` are
    # always also in ``rendered`` for the kit's current catalog
    # (every host file is shipped by some primitive's ``files/``
    # tree — ``core/files/frontmatter.schema.yaml`` etc.), so
    # scoping to ``rendered`` is degenerate today. A future primitive
    # that introduces a region-host file via ``contributes_to`` alone
    # would lose BOTH consequences if the scoping isn't widened:
    # (a) the adopt-set wouldn't seed a region baseline for a
    # ``.proposed`` sidecar at the host path, AND (b) the stderr
    # warning wouldn't surface the sidecar — the operator loses the
    # audit trail entirely. Widen this walk to
    # ``sorted(adoption_candidates)`` at the same time the new
    # primitive lands.
    pre_existing_sidecars: list[str] = []
    for relative_path in sorted(rendered):
        sidecar_path = vault_root / (relative_path + ".proposed")
        if sidecar_path.exists() and sidecar_path.is_file():
            pre_existing_sidecars.append(relative_path + ".proposed")

    return AdoptionSet(
        host_adoptions=tuple(host_adoptions),
        pre_existing_sidecars=tuple(pre_existing_sidecars),
    )
