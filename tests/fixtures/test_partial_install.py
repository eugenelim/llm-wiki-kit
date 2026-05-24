"""Self-tests for the shared partial-install fixture helpers.

Every downstream integration AC that drives ``wiki upgrade
--force-render`` relies on these helpers producing a vault whose
scope-guard predicate is NON-empty post-fixture. Without this
self-test layer, downstream ACs could pass vacuously via the scope
guard's short-circuit (the runner never entered, so the assertions
about per-primitive events would pass on an empty new-events slice).

The self-tests are co-located under ``tests/fixtures/`` so they run
on every pytest invocation and never depend on a separately-imported
test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_wiki_kit.journal import read_events, replay_state
from llm_wiki_kit.models import (
    PageAdoptedEvent,
    PrimitiveInstallEvent,
    VaultInitEvent,
)
from tests.fixtures.partial_install import (
    make_init_only_vault,
    make_partial_install_vault,
    make_two_primitive_partial_install_vault,
)


def _state_for(vault: object) -> object:
    events = read_events(vault.journal_path)  # type: ignore[attr-defined]
    return replay_state(events)


def test_make_partial_install_vault_cuts_after_named_primitive(tmp_path: Path) -> None:
    """The journal's last event is the named primitive's ``PrimitiveInstallEvent``.

    Pins the single-cut contract: every event after the named
    primitive's install row is dropped. By construction, the cut
    primitive's renders and any subsequent primitive's install /
    renders are absent.
    """

    vault = make_partial_install_vault(
        tmp_path,
        with_adopt=False,
        primitives=["core", "people"],
        cut_after_primitive="core",
    )
    events = read_events(vault.journal_path)
    last = events[-1]
    assert isinstance(last, PrimitiveInstallEvent)
    assert last.primitive == "core"


def test_make_partial_install_vault_with_adopt_preserves_adopt_events(
    tmp_path: Path,
) -> None:
    """``with_adopt=True`` preserves ``PageAdoptedEvent`` rows before installs.

    The adopt phase emits its events BEFORE the install pipeline, so
    truncating to a primitive's install event keeps every adopt row.
    """

    # Pick a path that the kit ships under ``core``'s files/ tree.
    # ``AGENTS.md`` is one of the simplest kit-owned files; the
    # would-render bytes depend on the recipe context, so we pre-place
    # a placeholder and let --adopt capture user bytes.
    adopted_paths = {"AGENTS.md": b"placeholder bytes for adopt test\n"}
    vault = make_partial_install_vault(
        tmp_path,
        with_adopt=True,
        primitives=["core", "people"],
        cut_after_primitive="core",
        adopted_paths=adopted_paths,
    )
    events = read_events(vault.journal_path)
    adopt_events = [e for e in events if isinstance(e, PageAdoptedEvent)]
    assert len(adopt_events) >= 1
    adopted_paths_in_journal = {e.path for e in adopt_events}
    assert "AGENTS.md" in adopted_paths_in_journal
    # Adopt events come BEFORE PrimitiveInstallEvents.
    install_indices = [i for i, e in enumerate(events) if isinstance(e, PrimitiveInstallEvent)]
    adopt_indices = [i for i, e in enumerate(events) if isinstance(e, PageAdoptedEvent)]
    assert max(adopt_indices) < min(install_indices)


def test_make_partial_install_vault_no_adopt_emits_no_adopted_events(
    tmp_path: Path,
) -> None:
    """``with_adopt=False`` emits zero ``PageAdoptedEvent`` rows."""

    vault = make_partial_install_vault(
        tmp_path,
        with_adopt=False,
        primitives=["core", "people"],
        cut_after_primitive="core",
    )
    events = read_events(vault.journal_path)
    assert not any(isinstance(e, PageAdoptedEvent) for e in events)


def test_make_partial_install_vault_unrendered_closure_non_empty(
    tmp_path: Path,
) -> None:
    """The scope-guard predicate is non-empty post-fixture.

    Load-bearing self-test: without this assertion, downstream
    integration ACs could pass vacuously via the scope-guard
    short-circuit (the runner never entered, so the assertions about
    per-primitive force-render events would pass on an empty
    new-events slice).
    """

    vault = make_partial_install_vault(
        tmp_path,
        with_adopt=False,
        primitives=["core", "people"],
        cut_after_primitive="core",
    )
    assert vault.pre_call_unrendered, (
        "fixture invariant: a partial-install vault must have at least one "
        "missing closure path so wiki upgrade --force-render's scope guard "
        "does NOT short-circuit"
    )


def test_make_partial_install_vault_rejects_adopted_paths_outside_surviving_primitives(
    tmp_path: Path,
) -> None:
    """Adopted paths under a cut primitive raise ``ValueError`` before init.

    Contract: every adopted path must lie under a primitive that
    survives the cut so the runner's re-walk reaches it. A path
    under a cut primitive would silently break downstream ACs because
    the runner won't re-visit it.
    """

    # ``people`` is cut (cut_after_primitive="core" keeps only core).
    # An adopted path that only ``people`` ships would not be reached
    # by the force-render's re-walk.
    with pytest.raises(ValueError, match="does not lie under any surviving"):
        make_partial_install_vault(
            tmp_path,
            with_adopt=True,
            primitives=["core", "people"],
            cut_after_primitive="core",
            adopted_paths={"wiki/people/README.md": b"this path lives only under people\n"},
        )


def test_make_two_primitive_partial_install_vault_both_primitives_partial(
    tmp_path: Path,
) -> None:
    """Both primitives are in ``state.installed_primitives`` AND partial.

    Pins the two-cut helper's contract: BOTH install rows survive
    (state contains both names), BOTH have non-empty closures
    (so the runner enters for each).
    """

    vault = make_two_primitive_partial_install_vault(
        tmp_path,
        primitives=["core", "people"],
    )
    events = read_events(vault.journal_path)
    state = replay_state(events)

    # Both install rows survived.
    assert {"core", "people"} <= set(state.installed_primitives.keys())

    # At least one PrimitiveInstallEvent per primitive in the journal.
    install_names = [e.primitive for e in events if isinstance(e, PrimitiveInstallEvent)]
    assert "core" in install_names
    assert "people" in install_names

    # Pre-call closure non-empty (load-bearing for downstream ACs).
    assert vault.pre_call_unrendered, (
        "fixture invariant: a two-primitive partial-install vault must have "
        "missing closure paths so force-render's scope guard does NOT short-circuit"
    )


def test_make_init_only_vault_emits_only_vault_init(tmp_path: Path) -> None:
    """The journal contains exactly one ``VaultInitEvent``.

    Used by AC18 (empty-installed init-in-progress hint). The shared
    helper keeps the fixture in one module rather than hand-seeded in
    the test body.
    """

    vault = make_init_only_vault(tmp_path)
    events = read_events(vault.journal_path)
    assert len(events) == 1
    assert isinstance(events[0], VaultInitEvent)
    # No PrimitiveInstallEvents anywhere.
    assert not any(isinstance(e, PrimitiveInstallEvent) for e in events)
