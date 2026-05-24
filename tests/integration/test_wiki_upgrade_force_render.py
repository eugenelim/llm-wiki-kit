"""End-to-end ``wiki upgrade --force-render`` integration tests.

Pinned by ``docs/specs/wiki-upgrade-force-render/spec.md`` AC1-AC20.
The fixture builder lives at ``tests/fixtures/partial_install.py``
(shared with sibling specs); helper-local ``_install_kit`` /
``_init_vault`` mirror ``tests/integration/test_wiki_upgrade.py``'s
shape.
"""

from __future__ import annotations

import inspect
import shutil
from pathlib import Path

import pytest
import yaml

from llm_wiki_kit import cli
from llm_wiki_kit import doctor as doctor_module
from llm_wiki_kit.journal import read_events, replay_state
from llm_wiki_kit.models import (
    ManagedRegionWriteEvent,
    PageProposalEvent,
    PageWriteEvent,
    Primitive,
    PrimitiveForceRenderEvent,
    PrimitiveInstallEvent,
    PrimitiveUpgradeEvent,
    VaultState,
)
from tests.fixtures.partial_install import (
    PartialInstallVault,
    make_init_only_vault,
    make_partial_install_vault,
    make_two_primitive_partial_install_vault,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _install_kit(tmp_path: Path) -> Path:
    """Mirror ``test_wiki_upgrade._install_kit`` — copy a minimal kit."""

    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")

    templates_src = REPO_ROOT / "templates"
    (kit / "templates").mkdir()
    for relative in (
        "ontologies/people",
        "content-types/meeting",
        "operations/weekly-digest",
    ):
        kind = relative.split("/", 1)[0]
        (kit / "templates" / kind).mkdir(exist_ok=True)
        shutil.copytree(templates_src / relative, kit / "templates" / relative)

    recipes_dir = kit / "recipes"
    recipes_dir.mkdir()
    (recipes_dir / "minimal.yaml").write_text(
        "name: minimal\n"
        "version: 0.1.0\n"
        "description: Core-only recipe for wiki upgrade tests.\n"
        "primitives:\n"
        "  - core\n"
        "variables:\n"
        "  recipe_name: minimal\n",
        encoding="utf-8",
    )
    return kit


@pytest.fixture
def kit_root(tmp_path: Path) -> Path:
    return _install_kit(tmp_path)


def _journal_path(vault: Path) -> Path:
    return vault / ".wiki.journal" / "journal.jsonl"


# ---------------------------------------------------------------------------
# Smoke (plan step 5) — flag is recognised by argparse
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_flag_recognised(
    kit_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``wiki upgrade --force-render --help`` returns 0 and mentions the flag.

    Plan step 5 smoke: pins that argparse accepts the new flag and the
    help text surfaces it. The behavior contract (planner narrowing,
    event-swap) is pinned at the unit level (steps 3 + 4).
    """

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["upgrade", "--help"], kit_root=kit_root)
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "--force-render" in out


# ---------------------------------------------------------------------------
# AC1, AC16, AC18 — scope-guard short-circuit on a clean closure
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_clean_closure_short_circuits(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC1: a clean-closure vault short-circuits with zero side effects.

    Counting monkeypatch on ``install.validate_contributions`` pins
    the carve-out in Invariant 7 (pre-flight does NOT run on the
    clean-closure path).
    """

    vault = tmp_path / "v"
    assert cli.main(["init", str(vault), "--recipe", "minimal", "--no-git"], kit_root=kit_root) == 0
    journal_path = _journal_path(vault)
    monkeypatch.chdir(vault)

    pre_journal_bytes = journal_path.read_bytes()

    import llm_wiki_kit.cli as _cli_mod
    from llm_wiki_kit.install import validate_contributions as _validate

    calls = {"n": 0}

    def counting_validate(primitive: Primitive, primitive_root: Path) -> None:
        calls["n"] += 1
        _validate(primitive, primitive_root)

    monkeypatch.setattr(_cli_mod, "validate_contributions", counting_validate)
    capsys.readouterr()

    assert cli.main(["upgrade", "--force-render"], kit_root=kit_root) == 0

    captured = capsys.readouterr()
    assert "wiki upgrade --force-render: no recovery needed (closure is complete)." in captured.out
    # Recovery-UX diagnostic: when state.installed_primitives is non-empty
    # the scope-guard short-circuit prints a one-line stderr note naming
    # the primitive count + the doctor follow-up. Pins the recovery-path
    # signal so a future refactor doesn't silently drop it.
    assert (
        "note: checked 1 installed primitive against the catalog; "
        "run 'wiki doctor' if you suspect drift."
    ) in captured.err
    assert journal_path.read_bytes() == pre_journal_bytes
    # No ``.proposed`` sidecars anywhere under the vault.
    assert list(vault.rglob("*.proposed")) == []
    assert calls["n"] == 0, (
        "AC1: validate_contributions must NOT run on the clean-closure path; "
        f"got {calls['n']} calls"
    )


def test_wiki_upgrade_force_render_pending_proposal_alone_does_not_trigger(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC16: a vault with one ``.proposed`` and zero missing paths short-circuits.

    Spec §Edge cases bullet 4: pending proposals are the user's to
    merge via ``wiki-conflict``; the scope guard does not include
    them.
    """

    # Pre-place a kit-owned file with user bytes so --adopt picks it
    # up and the renderer ships a .proposed sidecar.
    vault = tmp_path / "v"
    vault.mkdir()
    # ``AGENTS.md`` is shipped by core and depends on recipe context;
    # write a distinct bytes blob so adopt records user bytes and the
    # subsequent install pipeline emits a PageProposalEvent.
    (vault / "AGENTS.md").write_text("user-edited agents content\n", encoding="utf-8")
    assert (
        cli.main(
            ["init", str(vault), "--recipe", "minimal", "--no-git", "--adopt"],
            kit_root=kit_root,
        )
        == 0
    )
    monkeypatch.chdir(vault)

    # Verify precondition: exactly one pending-proposal, zero missing,
    # zero region drift.
    journal_path = _journal_path(vault)
    events = read_events(journal_path)
    state = replay_state(events)
    from llm_wiki_kit.cli import _unrendered_closure_paths

    catalog = _load_catalog(kit_root)
    sources = _sources_for_catalog(catalog, kit_root, state)
    assert _unrendered_closure_paths(state, vault, catalog, sources) == []
    assert doctor_module.check_managed_region_drift(events, vault, state) == []
    # Sanity: at least one .proposed exists.
    sidecars = list(vault.rglob("*.proposed"))
    assert sidecars, "fixture precondition: at least one .proposed sidecar"
    pre_sidecar_bytes = {s: s.read_bytes() for s in sidecars}
    pre_journal_bytes = journal_path.read_bytes()
    capsys.readouterr()

    assert cli.main(["upgrade", "--force-render"], kit_root=kit_root) == 0

    out = capsys.readouterr().out
    assert "no recovery needed (closure is complete)." in out
    assert journal_path.read_bytes() == pre_journal_bytes
    for sidecar, bytes_pre in pre_sidecar_bytes.items():
        assert sidecar.read_bytes() == bytes_pre


def test_wiki_upgrade_force_render_idempotent_across_invocations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC4: two consecutive ``--force-render`` runs yield value-equal journals."""

    vault = make_partial_install_vault(
        tmp_path,
        with_adopt=False,
        primitives=["core", "people"],
        cut_after_primitive="core",
    )
    monkeypatch.chdir(vault.vault_root)
    capsys.readouterr()

    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0
    events_first = read_events(vault.journal_path)
    capsys.readouterr()

    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0
    events_second = read_events(vault.journal_path)

    out = capsys.readouterr().out
    assert "no recovery needed (closure is complete)." in out
    assert events_second == events_first
    from llm_wiki_kit.cli import _unrendered_closure_paths

    post_state = replay_state(events_second)
    catalog = _load_catalog(vault.kit_root)
    sources = _sources_for_catalog(catalog, vault.kit_root, post_state)
    assert _unrendered_closure_paths(post_state, vault.vault_root, catalog, sources) == []


def test_wiki_upgrade_force_render_empty_installed_primitives_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC18: an init-only vault prints the recovery hint on stderr."""

    vault = make_init_only_vault(tmp_path)
    monkeypatch.chdir(vault.vault_root)
    capsys.readouterr()

    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0
    captured = capsys.readouterr()
    assert "no recovery needed (closure is complete)." in captured.out
    assert (
        "note: this vault has no installed primitives; if init was interrupted, "
        "run 'wiki init --adopt' to resume."
    ) in captured.err
    # The recovery-UX diagnostic (non-empty installed_primitives case)
    # must NOT also fire here — the init-in-progress hint is the right
    # signal for an empty vault, and a "checked 0 primitives" message
    # would muddle the recovery story.
    assert "checked 0 installed" not in captured.err
    assert "run 'wiki doctor' if you suspect drift" not in captured.err
    assert read_events(vault.journal_path) == [
        e for e in read_events(vault.journal_path) if e.type == "vault.init"
    ]


# ---------------------------------------------------------------------------
# AC2, AC11, AC15 — partial-install recovery
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_recovers_missing_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC2: a partial-install vault heals; adopt-baseline branches fire correctly.

    Construct a vault where the cut leaves only ``core`` in
    ``state.installed_primitives``. Pre-place two adopted paths under
    ``core``'s closure: one with kit-render bytes (no-rewrite branch),
    one with user bytes (proposal branch).
    """

    # Probe the kit's would-render bytes for AGENTS.md so the
    # byte-identical adopted path can actually fire the no-rewrite
    # branch. Two subtleties: (1) the render is context-dependent on
    # ``target.name`` (interpolated into rendered files via
    # ``vault_name``), so the probe MUST init at a directory whose
    # basename matches the real fixture's vault_root.name (the helper
    # always uses ``vault_root = tmp_path / "vault"``); (2) the probe
    # must use a fresh kit_root to avoid polluting the real fixture's
    # kit (the synthetic kit dirs are copies, not symlinks, but
    # sharing them across init calls would still introduce sequencing
    # surprises). Cheap and explicit.
    probe = make_partial_install_vault(
        tmp_path / "probe",
        with_adopt=False,
        primitives=["core", "people"],
        cut_after_primitive="core",
    )
    plain_parent = tmp_path / "plain"
    plain_parent.mkdir()
    plain = plain_parent / "vault"
    assert (
        cli.main(
            ["init", str(plain), "--recipe", "partial", "--no-git"],
            kit_root=probe.kit_root,
        )
        == 0
    )
    kit_render_agents = (plain / "AGENTS.md").read_bytes()

    # Build the real fixture with --adopt + adopted paths.
    vault = make_partial_install_vault(
        tmp_path / "real",
        with_adopt=True,
        primitives=["core", "people"],
        cut_after_primitive="core",
        adopted_paths={
            "AGENTS.md": kit_render_agents,  # byte-identical
            ".gitignore": b"user-edited gitignore content\n",  # byte-differing
        },
    )

    # Pre-call snapshots.
    pre_unrendered = list(vault.pre_call_unrendered)
    assert pre_unrendered, "fixture invariant: closure must have missing paths"
    pre_identical_bytes = (vault.vault_root / "AGENTS.md").read_bytes()
    pre_identical_inode = (vault.vault_root / "AGENTS.md").stat().st_ino
    pre_differing_bytes = (vault.vault_root / ".gitignore").read_bytes()
    pre_differing_inode = (vault.vault_root / ".gitignore").stat().st_ino
    events_before = read_events(vault.journal_path)

    monkeypatch.chdir(vault.vault_root)
    capsys.readouterr()

    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0

    # (a) every missing path is now on disk.
    for relative in pre_unrendered:
        assert (vault.vault_root / relative).is_file(), (
            f"AC2(a): expected {relative} to be re-rendered"
        )

    # (b) exactly one PrimitiveForceRenderEvent per installed primitive.
    # state.installed_primitives post-truncation contains only `core`
    # (people's install event was cut).
    new_events = read_events(vault.journal_path)[len(events_before) :]
    force_events = [e for e in new_events if isinstance(e, PrimitiveForceRenderEvent)]
    assert [(e.primitive, e.by) for e in force_events] == [("core", "wiki-upgrade")]

    # (c) byte-identical adopted path: no rewrite (bytes AND inode unchanged).
    # The proposal-branch firing here would also preserve bytes+inode (it
    # touches only the .proposed sidecar), so the bytes/inode pin alone is
    # weak. Add a negative-existence pin on the sidecar and a zero-count
    # pin on PageProposalEvent.by==<primitive> for this path: the no-rewrite
    # branch must NOT produce a sidecar.
    post_identical_bytes = (vault.vault_root / "AGENTS.md").read_bytes()
    post_identical_inode = (vault.vault_root / "AGENTS.md").stat().st_ino
    assert post_identical_bytes == pre_identical_bytes, "AC2(c): byte-identical bytes changed"
    assert post_identical_inode == pre_identical_inode, "AC2(c): byte-identical inode changed"
    assert not (vault.vault_root / "AGENTS.md.proposed").exists(), (
        "AC2(c): the no-rewrite branch must NOT emit a proposal sidecar; "
        "if this fires, the probe's would-render bytes diverged from the real "
        "vault's render (verify target.name parity)"
    )
    assert not any(
        isinstance(e, PageProposalEvent) and e.path == "AGENTS.md" for e in new_events
    ), "AC2(c): the no-rewrite branch must NOT emit a PageProposalEvent"

    # (d) byte-differing adopted path: original untouched + sidecar exists.
    post_differing_bytes = (vault.vault_root / ".gitignore").read_bytes()
    post_differing_inode = (vault.vault_root / ".gitignore").stat().st_ino
    assert post_differing_bytes == pre_differing_bytes, "AC2(d): user bytes changed"
    assert post_differing_inode == pre_differing_inode, "AC2(d): user file inode changed"
    sidecar = vault.vault_root / ".gitignore.proposed"
    assert sidecar.is_file(), "AC2(d): expected .proposed sidecar"
    # PageProposalEvent for .gitignore in new-events slice.
    proposal_events = [
        e for e in new_events if isinstance(e, PageProposalEvent) and e.path == ".gitignore"
    ]
    assert proposal_events, "AC2(d): expected PageProposalEvent for .gitignore"

    # (e) post-run closure clean.
    from llm_wiki_kit.cli import _unrendered_closure_paths

    post_events = read_events(vault.journal_path)
    post_state = replay_state(post_events)
    catalog = _load_catalog(vault.kit_root)
    sources = _sources_for_catalog(catalog, vault.kit_root, post_state)
    assert _unrendered_closure_paths(post_state, vault.vault_root, catalog, sources) == []
    assert doctor_module.check_managed_region_drift(post_events, vault.vault_root, post_state) == []

    # (f) totals row: singular for one primitive.
    out = capsys.readouterr().out
    assert "wiki upgrade --force-render: re-rendered 1 primitive." in out
    # Per-primitive marker line shape (spec §Outputs.Stdout). Pinning
    # the ``@ <version>`` separator catches a future refactor that
    # drops or changes it (the per-primitive line is otherwise
    # un-tested across AC1-AC20).
    core_install = next(
        e for e in events_before if isinstance(e, PrimitiveInstallEvent) and e.primitive == "core"
    )
    assert f"force-rendered core @ {core_install.version}" in out

    # AC11 + AC15 inherited: every PrimitiveForceRenderEvent attributes
    # to "wiki-upgrade"; every ManagedRegionWriteEvent attributes to
    # "wiki-upgrade"; every per-primitive PageWriteEvent attributes
    # to the primitive name.
    for event in new_events:
        if isinstance(event, PrimitiveForceRenderEvent):
            assert event.by == "wiki-upgrade"
        elif isinstance(event, ManagedRegionWriteEvent):
            assert event.by == "wiki-upgrade"
        elif isinstance(event, PageWriteEvent):
            # Per-primitive renderer attribution.
            assert event.by == "core"


# ---------------------------------------------------------------------------
# AC5 — --primitive narrows the re-render scope
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_primitive_restricts_event_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: ``--primitive people`` re-renders only ``people`` but aggregator still walks all.

    Uses the two-cut helper so BOTH primitives have missing closure
    paths; the narrowing test must show exactly one
    ``PrimitiveForceRenderEvent(primitive="people")`` and zero
    ``PageWriteEvent``s attributed to a non-``people`` primitive.
    """

    vault = make_two_primitive_partial_install_vault(
        tmp_path,
        primitives=["core", "people"],
    )
    monkeypatch.chdir(vault.vault_root)
    events_before = read_events(vault.journal_path)

    assert (
        cli.main(["upgrade", "--force-render", "--primitive", "people"], kit_root=vault.kit_root)
        == 0
    )

    new_events = read_events(vault.journal_path)[len(events_before) :]
    force_events = [e for e in new_events if isinstance(e, PrimitiveForceRenderEvent)]
    # (a) Exactly one PrimitiveForceRenderEvent for "people".
    assert [e.primitive for e in force_events] == ["people"]
    # (b) Zero PageWriteEvents attributed to any non-"people" primitive.
    page_writes_by_other = [
        e for e in new_events if isinstance(e, PageWriteEvent) and e.by != "people"
    ]
    assert page_writes_by_other == [], (
        f"AC5(b): non-people PageWriteEvents in new-events slice: "
        f"{[(e.path, e.by) for e in page_writes_by_other]}"
    )


# ---------------------------------------------------------------------------
# AC6 — --primitive with version mismatch refuses
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_primitive_with_version_mismatch_refuses(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC6: refuse when catalog ships a newer version than installed.

    The conflict check must run BEFORE the scope guard so the AC6
    test's "stdout does NOT contain `no recovery needed`" pin
    catches a misordering.
    """

    vault = tmp_path / "v"
    assert cli.main(["init", str(vault), "--recipe", "minimal", "--no-git"], kit_root=kit_root) == 0
    monkeypatch.chdir(vault)
    events_before = read_events(_journal_path(vault))

    # Bump core's catalog version. Replicates the helper from
    # test_wiki_upgrade._bump_primitive_version.
    manifest = kit_root / "core" / "primitive.yaml"
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    data["version"] = "0.2.0"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    capsys.readouterr()
    assert (
        cli.main(["upgrade", "--force-render", "--primitive", "core"], kit_root=kit_root)
        == cli.WIKI_ERROR_EXIT
    )
    captured = capsys.readouterr()
    assert "--force-render conflicts with a pending upgrade for 'core'" in captured.err
    assert "no recovery needed" not in captured.out
    assert read_events(_journal_path(vault)) == events_before


# ---------------------------------------------------------------------------
# AC7 — non-adopt-initialized partial install
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_recovers_non_adopt_init(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC7: ``--force-render`` heals a non-adopt-init partial vault.

    Zero ``PageProposalEvent`` rows (no adopt baselines to disagree
    with); every missing path lands.
    """

    vault = make_partial_install_vault(
        tmp_path,
        with_adopt=False,
        primitives=["core"],
        cut_after_primitive="core",
    )
    monkeypatch.chdir(vault.vault_root)
    pre_unrendered = list(vault.pre_call_unrendered)
    assert pre_unrendered

    events_before = read_events(vault.journal_path)
    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0

    for relative in pre_unrendered:
        assert (vault.vault_root / relative).is_file()
    new_events = read_events(vault.journal_path)[len(events_before) :]
    assert not any(isinstance(e, PageProposalEvent) for e in new_events)

    from llm_wiki_kit.cli import _unrendered_closure_paths

    post_events = read_events(vault.journal_path)
    post_state = replay_state(post_events)
    catalog = _load_catalog(vault.kit_root)
    sources = _sources_for_catalog(catalog, vault.kit_root, post_state)
    assert _unrendered_closure_paths(post_state, vault.vault_root, catalog, sources) == []


# ---------------------------------------------------------------------------
# AC10, AC12 — event ordering invariants
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_event_ordering_within_primitive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC12: each primitive's ``PrimitiveForceRenderEvent`` index < its page-event indices."""

    vault = make_partial_install_vault(
        tmp_path,
        with_adopt=False,
        primitives=["core", "people"],
        cut_after_primitive="core",
    )
    monkeypatch.chdir(vault.vault_root)
    events_before = read_events(vault.journal_path)

    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0

    new_events = read_events(vault.journal_path)[len(events_before) :]
    per_primitive: dict[str, dict[str, list[int]]] = {}
    for index, event in enumerate(new_events):
        if isinstance(event, PrimitiveForceRenderEvent):
            per_primitive.setdefault(event.primitive, {"force": [], "page": []})["force"].append(
                index
            )
        elif (
            isinstance(event, PageWriteEvent | PageProposalEvent)
            and event.by in per_primitive
            and event.by != "wiki-upgrade"
        ):
            per_primitive[event.by]["page"].append(index)
        elif isinstance(event, PageWriteEvent | PageProposalEvent) and event.by != "wiki-upgrade":
            per_primitive.setdefault(event.by, {"force": [], "page": []})["page"].append(index)

    for primitive_name, indices in per_primitive.items():
        if indices["force"] and indices["page"]:
            assert max(indices["force"]) < min(indices["page"]), (
                f"AC12: force-render event for {primitive_name} must precede every page event"
            )


def test_wiki_upgrade_force_render_aggregator_pass_after_per_primitive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC10: aggregator-phase events come strictly after per-primitive-phase events."""

    vault = make_two_primitive_partial_install_vault(
        tmp_path,
        primitives=["core", "meeting"],
    )
    monkeypatch.chdir(vault.vault_root)
    events_before = read_events(vault.journal_path)

    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0

    new_events = read_events(vault.journal_path)[len(events_before) :]
    aggregator_indices = [
        i
        for i, e in enumerate(new_events)
        if isinstance(e, ManagedRegionWriteEvent)
        or (isinstance(e, PageProposalEvent) and e.by == "wiki-upgrade")
    ]
    per_primitive_indices = [
        i
        for i, e in enumerate(new_events)
        if (isinstance(e, PageWriteEvent) and e.by != "wiki-upgrade")
        or (isinstance(e, PageProposalEvent) and e.by != "wiki-upgrade")
    ]
    # Pin both lists are non-empty so the strict-after check below
    # cannot pass vacuously on a fixture where one phase produced no
    # events. The two-cut fixture with [core, meeting] guarantees
    # both — make the precondition explicit.
    assert aggregator_indices, "AC10 precondition: aggregator must emit at least one event"
    assert per_primitive_indices, "AC10 precondition: at least one per-primitive event must land"
    assert max(per_primitive_indices) < min(aggregator_indices)


# ---------------------------------------------------------------------------
# AC13 — cache-discipline structural pin
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_uses_journal_cache_scope() -> None:
    """AC13: the force-render runner sits inside ``journal.use_journal_cache``.

    Structural pin (grep over ``_cmd_upgrade`` source). The runtime
    cache-load count is already pinned by the existing
    ``test_upgrade_cache_loads_baseline_once_via_journal_reader`` test
    in ``test_wiki_upgrade.py`` — both paths share the same runner.
    """

    source = inspect.getsource(cli._cmd_upgrade)
    assert "use_journal_cache" in source
    # The upgrade_primitives call must sit inside a ``with`` block that
    # uses ``use_journal_cache``. A regex-grep over indentation is brittle;
    # the structural shape is enforced by a substring check below — the
    # ``with journal.use_journal_cache(journal_path):`` line must precede
    # the only ``upgrade_primitives(`` call.
    cache_open = source.index("use_journal_cache")
    runner_call = source.index("upgrade_primitives(\n")
    assert cache_open < runner_call, (
        "AC13: the upgrade runner must be invoked inside use_journal_cache(...)"
    )


# ---------------------------------------------------------------------------
# AC14 — outside-vault refusal
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_outside_vault_exits_2(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC14: ``--force-render`` outside a vault exits 2 with "not a wiki vault"."""

    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)
    capsys.readouterr()

    assert cli.main(["upgrade", "--force-render"], kit_root=kit_root) == cli.WIKI_ERROR_EXIT
    err = capsys.readouterr().err
    assert "not a wiki vault" in err


# ---------------------------------------------------------------------------
# AC17 — validate_contributions runs on non-clean closure, NOT on clean
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_validates_contributions_when_closure_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC17: non-clean closure + broken kit → exit 2 BEFORE any force-render event."""

    vault = make_partial_install_vault(
        tmp_path,
        with_adopt=False,
        primitives=["core", "people"],
        cut_after_primitive="core",
    )
    monkeypatch.chdir(vault.vault_root)

    # Break a contribution snippet on disk. ``core`` has no
    # contributes_to, so we need a primitive that does. ``people``
    # could but it's cut from state. Instead, make ``core`` look like
    # it ships a stray regions/ file (orphan-snippet failure mode).
    regions_dir = vault.kit_root / "core" / "regions"
    regions_dir.mkdir(parents=True, exist_ok=True)
    (regions_dir / "frontmatter.schema.yaml.types").write_text("- orphan\n", encoding="utf-8")

    events_before = read_events(vault.journal_path)
    capsys.readouterr()

    rc = cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root)
    assert rc == cli.WIKI_ERROR_EXIT
    new_events = read_events(vault.journal_path)[len(events_before) :]
    assert not any(isinstance(e, PrimitiveForceRenderEvent) for e in new_events)


def test_wiki_upgrade_force_render_does_not_validate_when_closure_clean(
    tmp_path: Path,
    kit_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC17 complement: clean closure short-circuits BEFORE pre-flight discovers broken kit.

    Counting monkeypatch on ``cli.validate_contributions`` confirms
    zero calls. The user-recommended diagnostic surface for the
    broken kit is ``wiki doctor``, not ``--force-render``.
    """

    vault = tmp_path / "v"
    assert cli.main(["init", str(vault), "--recipe", "minimal", "--no-git"], kit_root=kit_root) == 0
    monkeypatch.chdir(vault)

    # Break the kit (same as the prior test).
    regions_dir = kit_root / "core" / "regions"
    regions_dir.mkdir(parents=True, exist_ok=True)
    (regions_dir / "frontmatter.schema.yaml.types").write_text("- orphan\n", encoding="utf-8")

    import llm_wiki_kit.cli as _cli_mod
    from llm_wiki_kit.install import validate_contributions as _validate

    calls = {"n": 0}

    def counting_validate(primitive: Primitive, primitive_root: Path) -> None:
        calls["n"] += 1
        _validate(primitive, primitive_root)

    monkeypatch.setattr(_cli_mod, "validate_contributions", counting_validate)
    capsys.readouterr()

    assert cli.main(["upgrade", "--force-render"], kit_root=kit_root) == 0
    assert "no recovery needed (closure is complete)." in capsys.readouterr().out
    assert calls["n"] == 0


# ---------------------------------------------------------------------------
# AC19 — per-file audit attribution via journal-index brackets
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_page_events_attributable_via_per_primitive_bracket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC19: every page-scope event resolves to a prior PrimitiveForceRenderEvent.

    Bracket query: for each page-scope event at index ``i`` with
    ``by`` equal to a primitive name, the most recent
    ``PrimitiveForceRenderEvent`` at index ``j < i`` must have
    ``primitive == event.by``, with no other ``Primitive*Event`` for
    that primitive between ``j`` and ``i``.
    """

    vault = make_partial_install_vault(
        tmp_path,
        with_adopt=False,
        primitives=["core", "people"],
        cut_after_primitive="core",
    )
    monkeypatch.chdir(vault.vault_root)
    events_before = read_events(vault.journal_path)

    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0

    new_events = read_events(vault.journal_path)[len(events_before) :]
    for i, event in enumerate(new_events):
        is_page_scope = isinstance(event, PageWriteEvent) or (
            isinstance(event, PageProposalEvent) and event.by != "wiki-upgrade"
        )
        if not is_page_scope:
            continue
        # Look up the most recent PrimitiveForceRenderEvent before i.
        match_index: int | None = None
        for j in range(i - 1, -1, -1):
            candidate = new_events[j]
            if isinstance(candidate, PrimitiveForceRenderEvent) and candidate.primitive == event.by:
                match_index = j
                break
            # If any other Primitive*Event for this primitive sits
            # between, it interrupts the bracket. Cover the whole
            # ``Primitive*Event`` family per spec AC19 (Install,
            # Upgrade, ForceRender for a *different* primitive — the
            # match for the same primitive is caught above — and
            # Remove).
            from llm_wiki_kit.models import PrimitiveRemoveEvent as _RM

            if (
                isinstance(
                    candidate,
                    PrimitiveInstallEvent | PrimitiveUpgradeEvent | _RM,
                )
                and getattr(candidate, "primitive", None) == event.by
            ):
                break
        assert match_index is not None, (
            f"AC19 page-scope: event at index {i} ({type(event).__name__}, by={event.by}) "
            f"has no preceding PrimitiveForceRenderEvent for primitive={event.by!r}"
        )


def test_wiki_upgrade_force_render_region_events_attributable_via_run_slice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC19 region-scope: every region-scope event lies after the last force-render event."""

    vault = make_two_primitive_partial_install_vault(
        tmp_path,
        primitives=["core", "meeting"],
    )
    monkeypatch.chdir(vault.vault_root)
    events_before = read_events(vault.journal_path)

    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0

    new_events = read_events(vault.journal_path)[len(events_before) :]
    last_force_index = max(
        i for i, e in enumerate(new_events) if isinstance(e, PrimitiveForceRenderEvent)
    )
    region_indices = [
        i
        for i, e in enumerate(new_events)
        if isinstance(e, ManagedRegionWriteEvent)
        or (isinstance(e, PageProposalEvent) and e.by == "wiki-upgrade")
    ]
    for index in region_indices:
        # Strict-after: spec says the slice is ``[k, ...)`` where k is
        # the LAST PrimitiveForceRenderEvent index, but a region event
        # cannot be AT index k (that's the force-render event itself)
        # — so the first region event lives at index ``> k``.
        assert index > last_force_index, (
            f"AC19 region-scope: event at index {index} precedes the last "
            f"PrimitiveForceRenderEvent (index {last_force_index})"
        )


# ---------------------------------------------------------------------------
# AC20 — shared-host-file partial recovery
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_recovers_shared_host_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC20: a shared host file healed by core's render + meeting's region contribution.

    Two-cut fixture so BOTH primitives are in state and BOTH have
    missing closure paths. The host file ``frontmatter.schema.yaml``
    (shipped by core, contributed-to by meeting) lands with both
    contributors.
    """

    vault = make_two_primitive_partial_install_vault(
        tmp_path,
        primitives=["core", "meeting"],
    )
    monkeypatch.chdir(vault.vault_root)

    # Pre-call: assert frontmatter.schema.yaml is in the missing closure.
    assert "frontmatter.schema.yaml" in vault.pre_call_unrendered

    events_before = read_events(vault.journal_path)
    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0

    # (a) Host file on disk with composed body containing meeting's snippet.
    host = vault.vault_root / "frontmatter.schema.yaml"
    assert host.is_file()
    body = host.read_text(encoding="utf-8")
    types_section = body.split("# BEGIN MANAGED: types\n", 1)[1].split("  # END MANAGED: types", 1)[
        0
    ]
    assert "- meeting" in types_section

    # (b) Journal contains one PrimitiveForceRenderEvent per primitive
    # in state.installed_primitives, plus a PageWriteEvent for the host
    # by core, plus at least one ManagedRegionWriteEvent.
    new_events = read_events(vault.journal_path)[len(events_before) :]
    force_primitives = {e.primitive for e in new_events if isinstance(e, PrimitiveForceRenderEvent)}
    post_state = replay_state(read_events(vault.journal_path))
    assert force_primitives == set(post_state.installed_primitives.keys())
    page_writes = [
        e
        for e in new_events
        if isinstance(e, PageWriteEvent) and e.path == "frontmatter.schema.yaml"
    ]
    assert page_writes, "AC20(b): expected a PageWriteEvent for frontmatter.schema.yaml"
    assert page_writes[0].by == "core"
    region_writes = [
        e for e in new_events if isinstance(e, ManagedRegionWriteEvent) and e.by == "wiki-upgrade"
    ]
    assert region_writes

    # (c) Post-run closure clean.
    from llm_wiki_kit.cli import _unrendered_closure_paths

    catalog = _load_catalog(vault.kit_root)
    sources = _sources_for_catalog(catalog, vault.kit_root, post_state)
    assert _unrendered_closure_paths(post_state, vault.vault_root, catalog, sources) == []


# ---------------------------------------------------------------------------
# AC3 — drift on a force-rendered file produces a proposal
# ---------------------------------------------------------------------------


def test_wiki_upgrade_force_render_drift_produces_proposal_not_silent_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC3: a force-rendered file with user-drifted bytes produces a .proposed sidecar."""

    vault = make_partial_install_vault(
        tmp_path,
        with_adopt=True,
        primitives=["core"],
        cut_after_primitive="core",
        adopted_paths={".gitignore": b"user-edited content\n"},
    )
    monkeypatch.chdir(vault.vault_root)
    pre_bytes = (vault.vault_root / ".gitignore").read_bytes()
    pre_inode = (vault.vault_root / ".gitignore").stat().st_ino
    events_before = read_events(vault.journal_path)
    capsys.readouterr()

    assert cli.main(["upgrade", "--force-render"], kit_root=vault.kit_root) == 0

    # (a) Original bytes and inode unchanged.
    assert (vault.vault_root / ".gitignore").read_bytes() == pre_bytes
    assert (vault.vault_root / ".gitignore").stat().st_ino == pre_inode
    # (b) .proposed sidecar exists.
    sidecar = vault.vault_root / ".gitignore.proposed"
    assert sidecar.is_file()
    # (c) PageProposalEvent journaled.
    new_events = read_events(vault.journal_path)[len(events_before) :]
    proposals = [
        e for e in new_events if isinstance(e, PageProposalEvent) and e.path == ".gitignore"
    ]
    assert proposals
    # (d) Stdout drift line.
    out = capsys.readouterr().out
    assert "Wrote .gitignore.proposed (drift detected on .gitignore)" in out
    # (e) Test passes via runner entry (not short-circuit).
    assert any(isinstance(e, PrimitiveForceRenderEvent) for e in new_events)


# ---------------------------------------------------------------------------
# Shared helpers (catalog + sources resolution against a synthetic kit)
# ---------------------------------------------------------------------------


def _load_catalog(kit_root: Path) -> list[Primitive]:
    from llm_wiki_kit.primitives import discover_primitives, load_primitive

    catalog = [load_primitive(kit_root / "core")]
    catalog.extend(discover_primitives(kit_root / "templates"))
    return catalog


def _sources_for_catalog(
    catalog: list[Primitive], kit_root: Path, state: VaultState
) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    by_name = {p.name: p for p in catalog}
    for name in state.installed_primitives:
        if name not in by_name:
            continue
        primitive = by_name[name]
        sources[name] = cli._primitive_source_dir(
            primitive, kit_root / "core", kit_root / "templates"
        )
    return sources


# Silence unused-import guards for cross-test reuse.
_ = (
    inspect,
    yaml,
    PartialInstallVault,
    make_two_primitive_partial_install_vault,
    PageProposalEvent,
    PageWriteEvent,
    PrimitiveForceRenderEvent,
    PrimitiveInstallEvent,
    PrimitiveUpgradeEvent,
    ManagedRegionWriteEvent,
)
