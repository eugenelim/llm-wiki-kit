"""Adopt-aware-predicate contract tests for ``llm_wiki_kit.write_helper``.

Carved out of ``test_write_helper.py`` per ``docs/specs/wiki-init-adopt/plan.md``
PR-B's "Test-file note": a grep for ``adopted`` lands the contract pins in
one file (mirrors ``test_install_skill_closure.py``'s carve-out shape).

Pins ADR-0008 §Decision sub-choice 3 and the spec's AC13, AC14, AC15,
AC16, AC16b — the adopt-match no-rewrite + adopt-differ proposal
disjuncts in ``safe_write`` and ``safe_write_region``, the
``_latest_baseline_event_kind`` helper, and ``_known_regions_for_file``'s
adopt-event walk that ``resolve_proposal`` depends on for the
region-resolve clearing contract.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from llm_wiki_kit.journal import append_event, read_events
from llm_wiki_kit.models import (
    ManagedRegionAdoptedEvent,
    ManagedRegionWriteEvent,
    PageAdoptedEvent,
    PageConflictResolvedEvent,
    PageProposalEvent,
    PageWriteEvent,
)
from llm_wiki_kit.write_helper import (
    WriteResult,
    _known_regions_for_file,
    _latest_baseline_event_kind,
    _latest_managed_region_event_kind,
    resolve_proposal,
    safe_write,
    safe_write_region,
)


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    (tmp_path / ".wiki.journal").mkdir()
    return tmp_path


@pytest.fixture
def journal(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


def _seed_page_adopted(journal_path: Path, *, path: str, page_hash: str) -> None:
    append_event(
        journal_path,
        PageAdoptedEvent(timestamp=_now(), by="wiki-init-adopt", path=path, hash=page_hash),
    )


def _seed_page_write(journal_path: Path, *, path: str, page_hash: str, by: str = "core") -> None:
    append_event(
        journal_path,
        PageWriteEvent(timestamp=_now(), by=by, path=path, hash=page_hash),
    )


def _seed_region_adopted(journal_path: Path, *, file: str, region: str, content_hash: str) -> None:
    append_event(
        journal_path,
        ManagedRegionAdoptedEvent(
            timestamp=_now(),
            by="wiki-init-adopt",
            file=file,
            region=region,
            content_hash=content_hash,
        ),
    )


def _seed_region_write(
    journal_path: Path, *, file: str, region: str, content_hash: str, by: str = "core"
) -> None:
    append_event(
        journal_path,
        ManagedRegionWriteEvent(
            timestamp=_now(),
            by=by,
            file=file,
            region=region,
            content_hash=content_hash,
        ),
    )


# ---------------------------------------------------------------------------
# _latest_baseline_event_kind table tests
# ---------------------------------------------------------------------------


def test_latest_baseline_kind_returns_write_when_only_write(journal: Path) -> None:
    _seed_page_write(journal, path="page.md", page_hash=_sha256("v1"))
    assert _latest_baseline_event_kind(journal, "page.md") == "write"


def test_latest_baseline_kind_returns_adopted_when_only_adopted(journal: Path) -> None:
    _seed_page_adopted(journal, path="page.md", page_hash=_sha256("v1"))
    assert _latest_baseline_event_kind(journal, "page.md") == "adopted"


def test_latest_baseline_kind_returns_none_for_unknown_path(journal: Path) -> None:
    _seed_page_write(journal, path="other.md", page_hash=_sha256("x"))
    assert _latest_baseline_event_kind(journal, "page.md") == "none"


def test_latest_baseline_kind_empty_journal_returns_none(journal: Path) -> None:
    assert _latest_baseline_event_kind(journal, "page.md") == "none"


def test_latest_baseline_kind_write_supersedes_adopted(journal: Path) -> None:
    _seed_page_adopted(journal, path="page.md", page_hash=_sha256("user"))
    _seed_page_write(journal, path="page.md", page_hash=_sha256("kit"))
    assert _latest_baseline_event_kind(journal, "page.md") == "write"


def test_latest_baseline_kind_latest_adopted_wins(journal: Path) -> None:
    """Resolve-then-re-adopt is unusual but legal; latest wins."""
    _seed_page_write(journal, path="page.md", page_hash=_sha256("kit"))
    _seed_page_adopted(journal, path="page.md", page_hash=_sha256("user"))
    assert _latest_baseline_event_kind(journal, "page.md") == "adopted"


def test_latest_baseline_kind_ignores_other_paths(journal: Path) -> None:
    _seed_page_adopted(journal, path="other.md", page_hash=_sha256("x"))
    _seed_page_write(journal, path="page.md", page_hash=_sha256("v1"))
    assert _latest_baseline_event_kind(journal, "page.md") == "write"


# ---------------------------------------------------------------------------
# _latest_managed_region_event_kind table tests
# ---------------------------------------------------------------------------


def test_latest_region_kind_returns_adopted_when_only_adopted(journal: Path) -> None:
    _seed_region_adopted(
        journal, file="AGENTS.md", region="content-types", content_hash=_sha256("body\n")
    )
    assert _latest_managed_region_event_kind(journal, "AGENTS.md", "content-types") == "adopted"


def test_latest_region_kind_write_supersedes_adopted(journal: Path) -> None:
    _seed_region_adopted(
        journal, file="AGENTS.md", region="content-types", content_hash=_sha256("u\n")
    )
    _seed_region_write(
        journal, file="AGENTS.md", region="content-types", content_hash=_sha256("k\n")
    )
    assert _latest_managed_region_event_kind(journal, "AGENTS.md", "content-types") == "write"


def test_latest_region_kind_unknown_region_returns_none(journal: Path) -> None:
    _seed_region_adopted(
        journal, file="AGENTS.md", region="other-region", content_hash=_sha256("x\n")
    )
    assert _latest_managed_region_event_kind(journal, "AGENTS.md", "content-types") == "none"


# ---------------------------------------------------------------------------
# safe_write — adopt-differ proposal (AC13)
# ---------------------------------------------------------------------------


def test_safe_write_after_page_adopted_with_differing_content_proposes(
    vault: Path, journal: Path
) -> None:
    """AC13: differing kit content against a PageAdoptedEvent baseline
    must route to proposal — even though ``on_disk_hash == baseline_hash``
    (the spec-named silent-overwrite the predicate exists to prevent).
    """
    target = vault / "page.md"
    user_bytes = b"user version\n"
    target.write_bytes(user_bytes)
    _seed_page_adopted(journal, path="page.md", page_hash=hashlib.sha256(user_bytes).hexdigest())

    result = safe_write(target, "kit version\n", by="core", journal_path=journal)

    assert result is WriteResult.PROPOSAL
    assert target.read_bytes() == user_bytes  # original untouched
    sidecar = vault / "page.md.proposed"
    assert sidecar.read_bytes() == b"kit version\n"

    events = read_events(journal)
    proposal_events = [e for e in events if isinstance(e, PageProposalEvent)]
    assert len(proposal_events) == 1
    assert proposal_events[0].path == "page.md"
    assert proposal_events[0].proposed_path == "page.md.proposed"
    assert proposal_events[0].hash == _sha256("kit version\n")
    # Proposal is the latest event for the path.
    assert isinstance(events[-1], PageProposalEvent)


def test_safe_write_after_page_adopted_file_absent_routes_to_proposal(
    vault: Path, journal: Path
) -> None:
    """An adopt baseline whose file vanished before ``safe_write`` runs
    routes to proposal — NOT to the crash-recovery direct-write branch
    that fires when a ``PageWriteEvent`` baseline's file is absent.

    Once the kit has claimed user bytes as a baseline, a subsequent
    disappearance is treated as drift, not as fresh-write recovery.
    The sidecar lands; the user reconciles via ``wiki-conflict``.
    Pins the contract the implementation comment cites.
    """
    target = vault / "page.md"
    # No file on disk; only the adopt event in the journal.
    _seed_page_adopted(journal, path="page.md", page_hash=_sha256("kit content\n"))

    result = safe_write(target, "kit content\n", by="core", journal_path=journal)

    assert result is WriteResult.PROPOSAL
    assert not target.exists()
    sidecar = vault / "page.md.proposed"
    assert sidecar.read_bytes() == b"kit content\n"
    proposals = [e for e in read_events(journal) if isinstance(e, PageProposalEvent)]
    assert len(proposals) == 1


def test_safe_write_after_page_adopted_file_absent_differing_routes_to_proposal(
    vault: Path, journal: Path
) -> None:
    """File-absent + differing content under an adopt baseline routes
    to proposal — same as the matching-content variant above. Closes
    the truth-table cell ADR-0008 sub-choice 3 disjunct 2 ("any
    on_disk_hash") leaves implicit.
    """
    target = vault / "page.md"
    _seed_page_adopted(journal, path="page.md", page_hash=_sha256("user version\n"))

    result = safe_write(target, "kit version\n", by="core", journal_path=journal)

    assert result is WriteResult.PROPOSAL
    assert not target.exists()
    assert (vault / "page.md.proposed").read_bytes() == b"kit version\n"
    proposals = [e for e in read_events(journal) if isinstance(e, PageProposalEvent)]
    assert len(proposals) == 1
    assert proposals[0].hash == _sha256("kit version\n")


def test_safe_write_after_page_adopted_proposes_even_when_on_disk_diverges(
    vault: Path, journal: Path
) -> None:
    """TOCTOU residual: on_disk has drifted from adopt baseline after the walk.

    Pins the spec §Edge cases "TOCTOU between adoption walk and render
    -phase writes" sub-case 1 — kit content equals adopted_hash but the
    on-disk bytes have moved on. Predicate routes to proposal so the
    user's edit survives.
    """
    target = vault / "page.md"
    adopt_hash = _sha256("kit version\n")
    _seed_page_adopted(journal, path="page.md", page_hash=adopt_hash)
    # User edited the file after compute_adoption_set's hash snapshot.
    target.write_bytes(b"user edited after adopt\n")

    result = safe_write(target, "kit version\n", by="core", journal_path=journal)

    assert result is WriteResult.PROPOSAL
    assert target.read_bytes() == b"user edited after adopt\n"
    assert (vault / "page.md.proposed").read_bytes() == b"kit version\n"


# ---------------------------------------------------------------------------
# safe_write — adopt-match no-rewrite (AC14) — inode pin
# ---------------------------------------------------------------------------


def test_safe_write_after_page_adopted_with_matching_content_no_rewrite(
    vault: Path, journal: Path
) -> None:
    """AC14: new_hash == adopted_hash == on_disk_hash → write event,
    no file rewrite. Inode is the load-bearing pin AC2 depends on in
    PR-C: the per-file adopt fast-path's inode preservation is what
    keeps Obsidian / inotify consumers from seeing a spurious file
    change.
    """
    target = vault / "page.md"
    content = "shared\n"
    payload = content.encode("utf-8")
    target.write_bytes(payload)
    page_hash = hashlib.sha256(payload).hexdigest()
    _seed_page_adopted(journal, path="page.md", page_hash=page_hash)

    pre_stat = target.stat()
    pre_ino = pre_stat.st_ino
    pre_mtime_ns = pre_stat.st_mtime_ns

    result = safe_write(target, content, by="core", journal_path=journal)

    assert result is WriteResult.WRITTEN
    # File was NOT rewritten — inode AND mtime preserved. Inode alone
    # would survive a same-bytes ``write_bytes`` (POSIX truncates in
    # place); mtime catches that regression.
    post_stat = target.stat()
    assert post_stat.st_ino == pre_ino
    assert post_stat.st_mtime_ns == pre_mtime_ns
    assert target.read_bytes() == payload
    # No sidecar.
    assert not (vault / "page.md.proposed").exists()
    # Exactly one new PageWriteEvent — supersedes the adopt baseline.
    events = read_events(journal)
    page_writes = [e for e in events if isinstance(e, PageWriteEvent)]
    assert len(page_writes) == 1
    assert page_writes[0].path == "page.md"
    assert page_writes[0].hash == page_hash
    # Adopt event remains in history (latest-wins via class supersession).
    page_adopts = [e for e in events if isinstance(e, PageAdoptedEvent)]
    assert len(page_adopts) == 1


# ---------------------------------------------------------------------------
# Event-before-disk durability (AC13 branch)
# ---------------------------------------------------------------------------


def test_safe_write_after_page_adopted_event_durable_when_disk_write_raises(
    vault: Path, journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure-injected sidecar write in the adopt-differ branch leaves
    the PageProposalEvent durable, sidecar absent, and original file
    byte-identical to its pre-call content. Pairs with the spec's
    Invariant 1 "event-before-disk holds end-to-end" for the new branch.
    """
    target = vault / "page.md"
    user_bytes = b"user version\n"
    target.write_bytes(user_bytes)
    _seed_page_adopted(journal, path="page.md", page_hash=hashlib.sha256(user_bytes).hexdigest())

    proposed = vault / "page.md.proposed"
    original_write_bytes = Path.write_bytes
    proposed_abs = str(proposed.absolute())

    def fragile_write_bytes(self: Path, data: bytes) -> int:
        if str(self.absolute()) == proposed_abs:
            raise OSError("simulated sidecar failure")
        return original_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", fragile_write_bytes)

    with pytest.raises(OSError, match="simulated sidecar failure"):
        safe_write(target, "kit version\n", by="core", journal_path=journal)

    proposals = [e for e in read_events(journal) if isinstance(e, PageProposalEvent)]
    assert [e.path for e in proposals] == ["page.md"]
    assert proposals[0].hash == _sha256("kit version\n")
    assert not proposed.exists()
    assert target.read_bytes() == user_bytes


# ---------------------------------------------------------------------------
# resolve_proposal clears adopt sticky (AC16)
# ---------------------------------------------------------------------------


def test_safe_write_resolve_then_safe_write_clears_adopt_sticky(vault: Path, journal: Path) -> None:
    """AC16 at the unit level: an adopt-then-proposed page, once resolved,
    is back on the standard direct-write path. The PageWriteEvent
    ``resolve_proposal`` emits supersedes the PageAdoptedEvent via
    latest-wins; a subsequent ``safe_write`` of the same content takes
    the direct-write branch.
    """
    target = vault / "page.md"
    user_bytes = b"user version\n"
    target.write_bytes(user_bytes)
    _seed_page_adopted(journal, path="page.md", page_hash=hashlib.sha256(user_bytes).hexdigest())

    # Adopt-differ proposal lands.
    safe_write(target, "kit version\n", by="core", journal_path=journal)
    assert (vault / "page.md.proposed").exists()

    # User merges via wiki-conflict.
    resolve_proposal(target, "merged\n", by="wiki-conflict", journal_path=journal)
    assert target.read_text() == "merged\n"
    assert not (vault / "page.md.proposed").exists()

    # Subsequent safe_write with same content: direct-write branch, no proposal.
    pre_events = len(read_events(journal))
    result = safe_write(target, "merged\n", by="core", journal_path=journal)
    assert result is WriteResult.WRITTEN
    assert not (vault / "page.md.proposed").exists()
    events_after = read_events(journal)
    new_events = events_after[pre_events:]
    assert len(new_events) == 1
    assert isinstance(new_events[0], PageWriteEvent)
    assert new_events[0].hash == _sha256("merged\n")


# ---------------------------------------------------------------------------
# safe_write_region — adopt-differ proposal (AC15)
# ---------------------------------------------------------------------------


def _seed_agents_md(vault: Path, body: str = "user body") -> Path:
    target = vault / "AGENTS.md"
    target.write_text(
        "# AGENTS.md\n"
        "\n"
        "user prose outside any region.\n"
        "\n"
        "<!-- BEGIN MANAGED: content-types -->\n"
        f"{body}\n"
        "<!-- END MANAGED: content-types -->\n"
        "\n"
        "trailing user notes\n"
    )
    return target


def test_safe_write_region_after_adopted_with_differing_body_proposes(
    vault: Path, journal: Path
) -> None:
    """AC15: adopt-baseline region body that differs from the kit's
    aggregated body routes to proposal. Host file's bytes survive
    untouched; ``<host>.proposed`` carries the rewritten file.
    """
    target = _seed_agents_md(vault, body="user body")
    pre_text = target.read_text()
    pre_mtime_ns = target.stat().st_mtime_ns
    user_body_hash = _sha256("user body\n")  # canonical_region_body adds trailing newline
    _seed_region_adopted(
        journal, file="AGENTS.md", region="content-types", content_hash=user_body_hash
    )

    result = safe_write_region(target, "content-types", "kit body", by="core", journal_path=journal)

    assert result is WriteResult.PROPOSAL
    # Original host file untouched: bytes AND mtime preserved (mtime
    # catches a same-text rewrite that bytes-equality alone would miss).
    assert target.read_text() == pre_text
    assert target.stat().st_mtime_ns == pre_mtime_ns
    sidecar = vault / "AGENTS.md.proposed"
    assert sidecar.exists()
    # Sidecar carries the rewritten file.
    sidecar_text = sidecar.read_text()
    assert "kit body" in sidecar_text
    assert "user prose outside any region." in sidecar_text  # unmanaged content flows through
    # Journal: a PageProposalEvent for the host and zero stray
    # ManagedRegionWriteEvents — a regression that accidentally
    # emitted BOTH a region write AND a proposal in the proposal
    # branch would silently break the region baseline.
    events = read_events(journal)
    proposals = [e for e in events if isinstance(e, PageProposalEvent)]
    assert len(proposals) == 1
    assert proposals[0].path == "AGENTS.md"
    region_writes = [e for e in events if isinstance(e, ManagedRegionWriteEvent)]
    assert region_writes == []


# ---------------------------------------------------------------------------
# safe_write_region — adopt-match no-rewrite (AC15 inode)
# ---------------------------------------------------------------------------


def test_safe_write_region_after_adopted_with_matching_body_no_rewrite(
    vault: Path, journal: Path
) -> None:
    """AC15 inode pin: matching adopt baseline + matching on-disk region
    body → fresh ManagedRegionWriteEvent, host file inode preserved.
    """
    target = _seed_agents_md(vault, body="shared body")
    pre_text = target.read_text()
    region_hash = _sha256("shared body\n")
    _seed_region_adopted(
        journal, file="AGENTS.md", region="content-types", content_hash=region_hash
    )

    pre_stat = target.stat()
    pre_ino = pre_stat.st_ino
    pre_mtime_ns = pre_stat.st_mtime_ns

    result = safe_write_region(
        target, "content-types", "shared body", by="core", journal_path=journal
    )

    assert result is WriteResult.WRITTEN
    # Host file untouched: bytes, inode, AND mtime preserved. Inode +
    # bytes alone would survive a same-text ``write_text`` (POSIX
    # truncates in place); mtime catches that regression.
    post_stat = target.stat()
    assert post_stat.st_ino == pre_ino
    assert post_stat.st_mtime_ns == pre_mtime_ns
    assert target.read_text() == pre_text
    # Exactly one new ManagedRegionWriteEvent supersedes the adopt baseline.
    region_writes = [e for e in read_events(journal) if isinstance(e, ManagedRegionWriteEvent)]
    assert len(region_writes) == 1
    assert region_writes[0].file == "AGENTS.md"
    assert region_writes[0].region == "content-types"
    assert region_writes[0].content_hash == region_hash
    # No sidecar.
    assert not (vault / "AGENTS.md.proposed").exists()


def test_safe_write_region_after_adopted_routes_to_proposal_when_on_disk_diverges(
    vault: Path, journal: Path
) -> None:
    """Adopt-baseline region whose kit body matches the baseline but
    the on-disk region body has drifted (TOCTOU residual) still routes
    to proposal — adopt-differ-shape applies symmetrically when on-disk
    is the divergent side.
    """
    target = _seed_agents_md(vault, body="user body")
    baseline_hash = _sha256("kit body\n")  # adopted matches kit, but disk has user body
    _seed_region_adopted(
        journal, file="AGENTS.md", region="content-types", content_hash=baseline_hash
    )

    pre_text = target.read_text()
    result = safe_write_region(target, "content-types", "kit body", by="core", journal_path=journal)

    assert result is WriteResult.PROPOSAL
    assert target.read_text() == pre_text  # host untouched


# ---------------------------------------------------------------------------
# _known_regions_for_file walks adopt events
# ---------------------------------------------------------------------------


def test_known_regions_for_file_walks_adopted_events(journal: Path) -> None:
    """Pre-AC16b prerequisite: when a host's only history is adopt
    events, ``_known_regions_for_file`` returns those regions in
    first-seen order so ``resolve_proposal``'s re-baseline loop has
    something to clear.
    """
    _seed_region_adopted(journal, file="AGENTS.md", region="types", content_hash=_sha256("a\n"))
    _seed_region_adopted(journal, file="AGENTS.md", region="fields", content_hash=_sha256("b\n"))
    # Region on a different file shouldn't appear.
    _seed_region_adopted(journal, file="other.md", region="types", content_hash=_sha256("c\n"))

    assert _known_regions_for_file(journal, "AGENTS.md") == ["types", "fields"]


def test_known_regions_for_file_dedupes_across_classes(journal: Path) -> None:
    """An adopt+write pair for the same region returns the region once,
    in first-seen order (the adopt event came first in journal order).
    """
    _seed_region_adopted(journal, file="AGENTS.md", region="types", content_hash=_sha256("a\n"))
    _seed_region_write(journal, file="AGENTS.md", region="types", content_hash=_sha256("b\n"))
    assert _known_regions_for_file(journal, "AGENTS.md") == ["types"]


def test_known_regions_for_file_mixed_class_ordering(journal: Path) -> None:
    """Mixed adopt/write events across different regions preserve
    first-seen ordering regardless of which class introduced each
    region. Catches a future refactor that walked write and adopt
    events in separate passes (which would put all writes before all
    adopts, or vice versa).
    """
    _seed_region_adopted(journal, file="AGENTS.md", region="types", content_hash=_sha256("a\n"))
    _seed_region_write(journal, file="AGENTS.md", region="fields", content_hash=_sha256("b\n"))
    _seed_region_write(journal, file="AGENTS.md", region="types", content_hash=_sha256("c\n"))
    _seed_region_adopted(journal, file="AGENTS.md", region="kinds", content_hash=_sha256("d\n"))
    # First-seen across both classes: types (adopt), fields (write),
    # kinds (adopt). The second event for ``types`` doesn't reorder.
    assert _known_regions_for_file(journal, "AGENTS.md") == ["types", "fields", "kinds"]


# ---------------------------------------------------------------------------
# resolve_proposal re-baselines regions from adopt-only host (AC16b)
# ---------------------------------------------------------------------------


def _seed_host_with_two_regions(vault: Path, *, types_body: str, fields_body: str) -> Path:
    target = vault / "frontmatter.schema.yaml"
    target.write_text(
        "# Frontmatter schema\n"
        "\n"
        "# BEGIN MANAGED: types\n"
        f"{types_body}\n"
        "# END MANAGED: types\n"
        "\n"
        "# BEGIN MANAGED: fields\n"
        f"{fields_body}\n"
        "# END MANAGED: fields\n"
    )
    return target


def test_resolve_proposal_re_baselines_region_only_adopted_host(vault: Path, journal: Path) -> None:
    """AC16b: ``resolve_proposal`` against an adopted-then-proposed
    managed-region host emits one ``ManagedRegionWriteEvent`` per region
    present in BOTH the adopt events for the file AND the resolved
    content. Without the ``_known_regions_for_file`` adopt-event walk,
    zero region events emit and the region-level sticky-adopt baselines
    never clear, causing every subsequent aggregator pass to re-propose
    the host.
    """
    target = _seed_host_with_two_regions(vault, types_body="user types", fields_body="user fields")

    # Seed adopt baselines for both the page and its two regions.
    user_page_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    _seed_page_adopted(journal, path="frontmatter.schema.yaml", page_hash=user_page_hash)
    _seed_region_adopted(
        journal,
        file="frontmatter.schema.yaml",
        region="types",
        content_hash=_sha256("user types\n"),
    )
    _seed_region_adopted(
        journal,
        file="frontmatter.schema.yaml",
        region="fields",
        content_hash=_sha256("user fields\n"),
    )

    # Drive an adopt-differ page proposal (different content from
    # what's on disk; PageAdoptedEvent baseline forces proposal branch).
    merged = (
        "# Frontmatter schema (merged)\n"
        "\n"
        "# BEGIN MANAGED: types\n"
        "merged types\n"
        "# END MANAGED: types\n"
        "\n"
        "# BEGIN MANAGED: fields\n"
        "merged fields\n"
        "# END MANAGED: fields\n"
    )
    safe_write(target, merged, by="core", journal_path=journal)
    assert (vault / "frontmatter.schema.yaml.proposed").exists()

    pre_events_len = len(read_events(journal))
    resolve_proposal(target, merged, by="wiki-conflict", journal_path=journal)
    new_events = read_events(journal)[pre_events_len:]

    # Sequence per spec: one PageWriteEvent (the page-level baseline),
    # one PageConflictResolvedEvent (audit), then one
    # ManagedRegionWriteEvent per region whose adopt baseline must
    # clear.
    page_writes = [e for e in new_events if isinstance(e, PageWriteEvent)]
    assert len(page_writes) == 1
    assert page_writes[0].path == "frontmatter.schema.yaml"

    audits = [e for e in new_events if isinstance(e, PageConflictResolvedEvent)]
    assert len(audits) == 1

    region_writes = [e for e in new_events if isinstance(e, ManagedRegionWriteEvent)]
    assert len(region_writes) == 2
    assert {e.region for e in region_writes} == {"types", "fields"}
    # Hashes match canonical_region_body of the resolved bodies.
    by_region = {e.region: e for e in region_writes}
    assert by_region["types"].content_hash == _sha256("merged types\n")
    assert by_region["fields"].content_hash == _sha256("merged fields\n")
    # by attribution propagates from resolve_proposal's caller.
    assert all(e.by == "wiki-conflict" for e in region_writes)
