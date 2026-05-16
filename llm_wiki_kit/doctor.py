"""Vault-state validator behind ``wiki doctor``.

Replays the journal, compares to disk, and reports six kinds of issue:

* ``page-drift`` — a journaled ``page.write`` whose on-disk hash no
  longer matches, with no outstanding ``page.proposal`` to explain it.
* ``managed-region-drift`` — a journaled ``managed_region.write``
  whose on-disk region body no longer matches.
* ``pending-proposal`` — a ``.proposed`` sidecar awaiting resolution.
* ``orphan`` — a file under a kit-owned path with no journal event.
* ``missing`` — a journaled ``page.write`` whose file is gone.
* ``primitive-missing`` — a journal-recorded primitive that the kit's
  catalog no longer carries (e.g. after a kit downgrade).

Doctor only reports. Auto-fix lives in a future ``wiki doctor --fix``
task. The CLI surface maps a non-empty report to exit code 1; ``2`` is
reserved for internal errors raised through :class:`WikiError`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from llm_wiki_kit import managed_regions
from llm_wiki_kit.errors import ManagedRegionError
from llm_wiki_kit.journal import read_events, replay_state
from llm_wiki_kit.models import Event, ManagedRegionWriteEvent, VaultState
from llm_wiki_kit.primitives import discover_primitives, load_primitive

# Issue kinds (also serve as the line prefix in the CLI output).
PAGE_DRIFT = "page-drift"
MANAGED_REGION_DRIFT = "managed-region-drift"
PENDING_PROPOSAL = "pending-proposal"
ORPHAN = "orphan"
MISSING = "missing"
PRIMITIVE_MISSING = "primitive-missing"

# Kit-owned vault paths. Files outside these are user-owned and invisible
# to the orphan check by design (ADR-0004: the kit never touches user
# territory). Keep in sync with the install pipeline's render targets.
KIT_OWNED_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "CORE.md",
    "frontmatter.schema.yaml",
    ".gitignore",
)
KIT_OWNED_DIRS: tuple[str, ...] = ("skills", "_templates", "wiki")


@dataclass(frozen=True)
class Issue:
    """One finding from ``run_doctor``.

    Not a Pydantic model because :class:`Issue` never crosses disk —
    ADR-0005 reserves Pydantic for the disk-bound schemas. ``detail``
    is optional context (e.g. "region missing"); empty string by default
    so the rendered line stays compact.
    """

    kind: str
    path: str
    detail: str = ""


def format_issue(issue: Issue) -> str:
    """Render an :class:`Issue` as one CLI line, prefixed with its kind."""

    if issue.detail:
        return f"{issue.kind}: {issue.path} ({issue.detail})"
    return f"{issue.kind}: {issue.path}"


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_page_drift(state: VaultState, vault_root: Path) -> list[Issue]:
    """Pages whose on-disk hash diverges from the latest ``page.write``.

    A path with an outstanding ``page.proposal`` is reported as
    ``pending-proposal``, not ``page-drift`` — the user already knows
    the kit wanted to write something there.
    """

    issues: list[Issue] = []
    for relative, event in state.page_writes.items():
        if relative in state.pending_proposals:
            continue
        abs_path = vault_root / relative
        if not abs_path.exists():
            continue  # surfaces via check_missing
        if _hash(abs_path.read_bytes()) != event.hash:
            issues.append(Issue(PAGE_DRIFT, relative))
    return issues


def check_managed_region_drift(
    events: list[Event], vault_root: Path, state: VaultState
) -> list[Issue]:
    """Managed regions whose on-disk body diverges from the latest write.

    Walks ``events`` (not the replayed state) because
    ``managed_region.write`` events aren't projected into
    :class:`VaultState`. Per-region "latest" is the last event for
    ``(file, region)`` in journal order.

    A file with an outstanding ``page.proposal`` is skipped — the
    proposal already explains every region inside it, and reporting
    both ``pending-proposal`` and ``managed-region-drift`` for the
    same file is double-counting (retro-review #B6, pairs with
    ``write_helper.resolve_proposal``'s region re-baseline fix #F-B1).
    """

    latest: dict[tuple[str, str], ManagedRegionWriteEvent] = {}
    for event in events:
        if isinstance(event, ManagedRegionWriteEvent):
            latest[(event.file, event.region)] = event

    file_cache: dict[str, dict[str, str] | None] = {}
    issues: list[Issue] = []
    for (file_path, region), event in latest.items():
        if file_path in state.pending_proposals:
            continue
        abs_file = vault_root / file_path
        if not abs_file.exists():
            continue  # surfaces via check_missing
        if file_path not in file_cache:
            try:
                file_cache[file_path] = managed_regions.parse(abs_file.read_text(encoding="utf-8"))
            except ManagedRegionError:
                file_cache[file_path] = None
        parsed = file_cache[file_path]
        target = f"{file_path}:{region}"
        if parsed is None:
            issues.append(Issue(MANAGED_REGION_DRIFT, target, "markers malformed"))
            continue
        body = parsed.get(region)
        if body is None:
            issues.append(Issue(MANAGED_REGION_DRIFT, target, "region missing"))
            continue
        if _hash(body.encode("utf-8")) != event.content_hash:
            issues.append(Issue(MANAGED_REGION_DRIFT, target))
    return issues


def check_pending_proposals(state: VaultState) -> list[Issue]:
    """One issue per unresolved ``.proposed`` sidecar.

    Surfaces the sidecar's vault-relative path so the user can hand it
    to the vault-side ``wiki-conflict`` skill.
    """

    return [
        Issue(PENDING_PROPOSAL, event.proposed_path) for event in state.pending_proposals.values()
    ]


def check_missing(state: VaultState, vault_root: Path) -> list[Issue]:
    """Journal-recorded pages whose file is no longer on disk."""

    return [
        Issue(MISSING, relative)
        for relative in state.page_writes
        if not (vault_root / relative).exists()
    ]


def check_orphans(state: VaultState, vault_root: Path) -> list[Issue]:
    """Files under kit-owned paths with no corresponding journal event.

    Skips ``.proposed`` sidecars (those surface as pending-proposal)
    and files outside :data:`KIT_OWNED_FILES` / :data:`KIT_OWNED_DIRS`
    (user-owned territory).
    """

    journaled = set(state.page_writes)
    proposal_sidecars = {e.proposed_path for e in state.pending_proposals.values()}

    candidates: list[str] = []
    for name in KIT_OWNED_FILES:
        if (vault_root / name).is_file():
            candidates.append(name)
    for dir_name in KIT_OWNED_DIRS:
        directory = vault_root / dir_name
        if not directory.is_dir():
            continue
        for entry in directory.rglob("*"):
            if entry.is_file():
                candidates.append(entry.relative_to(vault_root).as_posix())

    issues: list[Issue] = []
    for relative in candidates:
        if relative.endswith(".proposed"):
            continue
        if relative in proposal_sidecars:
            continue
        if relative not in journaled:
            issues.append(Issue(ORPHAN, relative))
    return issues


def check_primitive_missing(state: VaultState, kit_root: Path) -> list[Issue]:
    """Installed primitives the current kit catalog no longer ships.

    Useful when a user downgrades the kit underneath a vault — the
    journal still references primitives the new install can't render or
    upgrade. Names are surfaced verbatim; the user (or the kit's future
    ``wiki upgrade`` step) decides what to do.
    """

    catalog_names: set[str] = set()
    core_dir = kit_root / "core"
    if (core_dir / "primitive.yaml").is_file():
        catalog_names.add(load_primitive(core_dir).name)
    for primitive in discover_primitives(kit_root / "templates"):
        catalog_names.add(primitive.name)

    return [
        Issue(PRIMITIVE_MISSING, name)
        for name in state.installed_primitives
        if name not in catalog_names
    ]


def run_doctor(vault_root: Path, kit_root: Path) -> list[Issue]:
    """Replay the journal and return every issue, sorted by ``(kind, path)``."""

    journal_path = vault_root / ".wiki.journal" / "journal.jsonl"
    events = read_events(journal_path)
    state = replay_state(events)

    issues: list[Issue] = []
    issues.extend(check_page_drift(state, vault_root))
    issues.extend(check_managed_region_drift(events, vault_root, state))
    issues.extend(check_pending_proposals(state))
    issues.extend(check_orphans(state, vault_root))
    issues.extend(check_missing(state, vault_root))
    issues.extend(check_primitive_missing(state, kit_root))
    issues.sort(key=lambda issue: (issue.kind, issue.path, issue.detail))
    return issues
