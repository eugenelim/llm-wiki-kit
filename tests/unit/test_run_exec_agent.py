"""Tests for ``wiki run --exec``'s agent resolution + passthrough (RFC-0004 PR-5).

Spec coverage from ``docs/specs/wiki-agents/spec.md``:

- CT-14: ``_build_argv`` inserts ``--agent <name>`` immediately before
  the trailing prompt positional (ADR-0010); with no agent the argv
  shape is byte-identical to ADR-0009.
- CT-15: agent-missing at exec time journals one
  ``OperationExecFailedEvent(reason="agent-missing")`` and no
  ``OperationRunByAgentEvent``.
- CT-16: the success path pairs ``OperationRunEvent`` +
  ``OperationRunByAgentEvent`` inside one ``journal.transaction(...)``
  (one lock-pair bracketing both, same ``event_id``, OperationRunEvent
  precedes OperationRunByAgentEvent on disk).

Pure-function CTs (CT-14) hit ``_build_argv`` directly; orchestrator
CTs (CT-15, CT-16) drive ``dispatch_and_exec`` against a fixture
``kit_root`` + ``exec_vault`` modeled on ``test_run_exec.py``'s slice-3
shape, with an inline stub ``claude`` binary that echoes ``$0
{argv[*]}`` to a file so the argv passthrough is observable.
"""

from __future__ import annotations

import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.journal import append_event, read_events
from llm_wiki_kit.models import (
    LockAcquiredEvent,
    LockReleasedEvent,
    OperationExecFailedEvent,
    OperationRunByAgentEvent,
    OperationRunEvent,
    PrimitiveInstallEvent,
    PrimitiveRemoveEvent,
    VaultInitEvent,
)
from llm_wiki_kit.run import _build_argv, dispatch_and_exec

NOW = datetime(2026, 5, 24, 9, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# CT-14: _build_argv inserts --agent before the prompt positional
# ---------------------------------------------------------------------------


def _make_executable(tmp_path: Path, name: str = "claude") -> Path:
    binary = tmp_path / name
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC | stat.S_IXUSR | stat.S_IXGRP)
    return binary


def test_build_argv_inserts_agent_flag_before_prompt_positional(
    tmp_path: Path,
) -> None:
    """CT-14: ``--agent <name>`` lands between the existing flags and the prompt.

    ADR-0010 §Decision pins "two tokens immediately before the
    trailing prompt positional." This pins both halves of CT-14:
    the with-agent shape (assert ``argv[-3:] == ["--agent", "<name>",
    <prompt>]``) and the without-agent shape (``"--agent" not in
    argv`` — also covered at v1 by
    ``test_run_exec.py::test_build_argv_omits_agent_when_none``).
    """

    binary = _make_executable(tmp_path)
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    prompt = "run weekly-digest"

    argv_with = _build_argv(
        claude_binary=binary,
        vault_root=vault_root,
        prompt=prompt,
        max_budget_usd=None,
        agent="household-manager",
    )
    # Tail-three: --agent <name> <prompt>; nothing after the prompt.
    assert argv_with[-3:] == ["--agent", "household-manager", prompt]
    # ADR-0009 prefix unchanged.
    assert argv_with[:8] == [
        str(binary),
        "-p",
        "--add-dir",
        str(vault_root),
        "--permission-mode",
        "dontAsk",
        "--output-format",
        "json",
    ]

    argv_without = _build_argv(
        claude_binary=binary,
        vault_root=vault_root,
        prompt=prompt,
        max_budget_usd=None,
        agent=None,
    )
    assert "--agent" not in argv_without
    # The negative-half no-agent shape is byte-identical to the
    # ADR-0009 form (matches ``test_run_exec::test_build_argv_matches_adr_0009_shape``).
    assert argv_without == [
        str(binary),
        "-p",
        "--add-dir",
        str(vault_root),
        "--permission-mode",
        "dontAsk",
        "--output-format",
        "json",
        prompt,
    ]


def test_build_argv_agent_lands_after_max_budget(tmp_path: Path) -> None:
    """Agent and budget compose: both pairs precede the prompt; budget first."""

    binary = _make_executable(tmp_path)
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    argv = _build_argv(
        claude_binary=binary,
        vault_root=vault_root,
        prompt="x",
        max_budget_usd="5.00",
        agent="trip-planner",
    )
    # tail-five = --max-budget-usd 5.00 --agent trip-planner x
    assert argv[-5:] == ["--max-budget-usd", "5.00", "--agent", "trip-planner", "x"]


# ---------------------------------------------------------------------------
# Fixtures: kit_root + exec_vault tailored for the orchestrator tests
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parents[2]

_WEEKLY_DIGEST_CONTRACT = """\
name: weekly-digest
description: Weekly digest test contract.
period: weekly
skill: weekly-digest
inputs:
  window:
    type: iso_week
outputs:
  digest:
    type: page
    path_pattern: outputs/digests/{window}.md
"""


def _write_file(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


@pytest.fixture
def kit_root(tmp_path: Path) -> Path:
    """A kit_root with weekly-digest + a household-manager agent primitive."""

    kit = tmp_path / "kit"
    kit.mkdir()
    shutil.copytree(REPO_ROOT / "core", kit / "core")
    templates = kit / "templates"
    templates.mkdir()
    # weekly-digest operation primitive.
    op_dir = templates / "operations" / "weekly-digest"
    op_dir.mkdir(parents=True)
    (op_dir / "contract.yaml").write_text(_WEEKLY_DIGEST_CONTRACT, encoding="utf-8")
    (op_dir / "primitive.yaml").write_text(
        "name: weekly-digest\n"
        "kind: operation\n"
        "version: 0.1.0\n"
        "description: weekly-digest test primitive.\n",
        encoding="utf-8",
    )
    (op_dir / "files").mkdir()
    # household-manager agent primitive (catalog only — install events
    # are written into the vault journal per-test).
    agent_dir = templates / "agents" / "household-manager"
    agent_dir.mkdir(parents=True)
    (agent_dir / "primitive.yaml").write_text(
        "name: household-manager\n"
        "kind: agent\n"
        "version: 0.1.0\n"
        "description: household-manager test agent.\n",
        encoding="utf-8",
    )
    return kit


def _build_exec_vault(
    tmp_path: Path,
    *,
    agent_installed: bool,
    agent_removed: bool = False,
) -> Path:
    """A vault with weekly-digest installed, SKILL in place, and optional agent."""

    v = tmp_path / "exec-vault"
    (v / ".wiki.journal").mkdir(parents=True)
    journal_path = v / ".wiki.journal" / "journal.jsonl"
    append_event(
        journal_path,
        VaultInitEvent(
            timestamp=NOW,
            by="wiki-init",
            vault_name="test-vault",
            recipe="minimal",
        ),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=NOW,
            by="wiki-init",
            primitive="weekly-digest",
            version="0.1.0",
        ),
    )
    if agent_installed:
        append_event(
            journal_path,
            PrimitiveInstallEvent(
                timestamp=NOW,
                by="wiki-init",
                primitive="household-manager",
                version="0.1.0",
            ),
        )
    if agent_removed:
        # Stale-binding setup: install then remove. Per spec §"Edge
        # cases / Agent removed", the journaled binding stays frozen
        # but ``is_installed_agent`` returns False once the remove
        # event lands.
        append_event(
            journal_path,
            PrimitiveRemoveEvent(
                timestamp=NOW,
                by="wiki-remove",
                primitive="household-manager",
            ),
        )
    skill_dir = v / ".claude" / "skills" / "weekly-digest"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# weekly-digest\n", encoding="utf-8")
    return v


# ---------------------------------------------------------------------------
# CT-15: agent-missing at exec time journals one OperationExecFailedEvent
# ---------------------------------------------------------------------------


def test_run_exec_agent_missing_journals_exec_failed_event(tmp_path: Path, kit_root: Path) -> None:
    """CT-15: ``wiki remove agent:<name>`` after install → ``--exec`` refuses.

    The vault journaled both ``PrimitiveInstallEvent`` and
    ``PrimitiveRemoveEvent`` for ``household-manager``, so the
    OS-side artifact's frozen ``--agent household-manager`` arrives
    at a kit whose ``is_installed_agent`` returns False. The kit
    must (a) raise WikiError beginning with the canonical
    "scheduled run resolved agent ..." prefix, (b) journal one
    ``OperationExecFailedEvent(reason="agent-missing")``, (c)
    journal **no** ``OperationRunByAgentEvent``.

    The dispatch-only ``OperationRunEvent`` MUST NOT be journaled
    either — spec §Invariants "Mid-flock agent re-validation"'s
    "not a partial write" rule applies whether the agent was missing
    at pre-transaction resolution (this test) or vanished mid-flock
    (sibling
    ``test_run_exec_agent_missing_mid_flock_journals_exec_failed_under_lock``).
    """

    vault = _build_exec_vault(tmp_path, agent_installed=True, agent_removed=True)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    binary = _make_executable(tmp_path)

    with pytest.raises(WikiError) as excinfo:
        dispatch_and_exec(
            "weekly-digest",
            ["--window=2026-W20"],
            vault_root=vault,
            kit_root=kit_root,
            journal_path=journal_path,
            now=NOW,
            claude_binary=binary,
            agent="household-manager",
        )
    assert str(excinfo.value).startswith(
        "scheduled run resolved agent 'household-manager' but it is not installed"
    )

    events = list(read_events(journal_path))

    # (b) exactly one OperationExecFailedEvent with reason="agent-missing"
    failures = [e for e in events if isinstance(e, OperationExecFailedEvent)]
    assert len(failures) == 1
    assert failures[0].reason == "agent-missing"
    # exit_code is the kit-side refusal sentinel (-3), not a subprocess code.
    assert failures[0].exit_code == -3
    # No subprocess invoked → no stderr_tail, no log_path.
    assert failures[0].stderr_tail == ""
    assert failures[0].log_path is None

    # (c) no OperationRunByAgentEvent
    by_agent = [e for e in events if isinstance(e, OperationRunByAgentEvent)]
    assert by_agent == []

    # Spec §Invariants "Mid-flock agent re-validation" — "not a partial
    # write" rule: no OperationRunEvent should land for this invocation
    # either. The agent-missing failure is the ONLY operation event of
    # any kind.
    runs = [e for e in events if isinstance(e, OperationRunEvent)]
    assert runs == []


# ---------------------------------------------------------------------------
# CT-16: OperationRunEvent + OperationRunByAgentEvent under one transaction
# ---------------------------------------------------------------------------


def _ensure_python_claude(tmp_path: Path, script: str) -> Path:
    """Create an executable stub ``claude`` running ``script`` via ``python3``."""

    stub = tmp_path / "claude"
    stub.write_text(f"#!/usr/bin/env python3\n{script}\n", encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXUSR | stat.S_IXGRP)
    return stub


def test_run_exec_agent_missing_mid_flock_journals_exec_failed_under_lock(
    tmp_path: Path, kit_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CT-15 (mid-flock half): re-validation under the transaction catches
    a ``wiki remove`` that lands between pre-transaction resolution and
    the in-transaction re-check.

    Spec §Invariants "Mid-flock agent re-validation" pins this
    branch: the kit must re-read ``VaultState`` inside the dispatch
    transaction and emit exactly one
    ``OperationExecFailedEvent(reason="agent-missing")`` under the
    same lock-pair (no ``OperationRunEvent``) when the resolved
    agent vanishes between pre-transaction resolution and lock
    acquire — the "not a partial write" rule.
    Asserts:
    (a) the in-transaction re-check fires (lock-pair bracket present),
    (b) exactly one ``OperationExecFailedEvent(reason="agent-missing")``
        inside the bracket,
    (c) no ``OperationRunEvent`` and no ``OperationRunByAgentEvent``.

    The race is simulated by monkeypatching
    ``llm_wiki_kit.run.is_installed_agent`` to return True on its first
    invocation (pre-transaction, ``_resolve_agent_for_run`` step 1) and
    False on its second (mid-flock, inside the dispatch transaction).
    The function is bound at module import time on ``llm_wiki_kit.run``,
    so the monkeypatch targets that name, not ``primitives``.
    """

    vault = _build_exec_vault(tmp_path, agent_installed=True)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    binary = _make_executable(tmp_path)

    call_count = {"n": 0}

    def fake_is_installed_agent(name: str, state: object, kit_root: Path) -> bool:
        call_count["n"] += 1
        # First call is the pre-transaction resolution step 1 inside
        # ``_resolve_agent_for_run``; it must return True so the chain
        # accepts the name and the dispatch reaches the transaction.
        # Subsequent calls are the in-transaction re-check; return
        # False to simulate ``wiki remove agent:household-manager``
        # landing under the lock.
        return call_count["n"] == 1

    monkeypatch.setattr("llm_wiki_kit.run.is_installed_agent", fake_is_installed_agent)

    events_before = list(read_events(journal_path))
    baseline = len(events_before)

    with pytest.raises(WikiError) as excinfo:
        dispatch_and_exec(
            "weekly-digest",
            ["--window=2026-W20"],
            vault_root=vault,
            kit_root=kit_root,
            journal_path=journal_path,
            now=NOW,
            claude_binary=binary,
            agent="household-manager",
        )
    assert str(excinfo.value).startswith(
        "scheduled run resolved agent 'household-manager' but it is not installed"
    )
    # The race-injection fired at least twice (step 1 + in-transaction
    # re-check). Sanity check that both branches ran.
    assert call_count["n"] >= 2

    after = list(read_events(journal_path))
    new_events = after[baseline:]

    # (a) Lock-pair brackets the failure event. The transaction's
    # context manager emits LockAcquiredEvent on enter and
    # LockReleasedEvent on exit (even on raise), so the slice must
    # contain exactly one of each, in order.
    acquires = [e for e in new_events if isinstance(e, LockAcquiredEvent)]
    releases = [e for e in new_events if isinstance(e, LockReleasedEvent)]
    assert len(acquires) == 1
    assert len(releases) == 1

    # (b) Exactly one agent-missing failure event landed inside the
    # bracket (the dispatch transaction's lock holds while the failure
    # is appended via ``_append_failure_event``'s held-fd path).
    failures = [e for e in new_events if isinstance(e, OperationExecFailedEvent)]
    assert len(failures) == 1
    assert failures[0].reason == "agent-missing"
    assert failures[0].exit_code == -3

    # Order check: acquire → exec_failed → release.
    acquire_idx = new_events.index(acquires[0])
    failure_idx = new_events.index(failures[0])
    release_idx = new_events.index(releases[0])
    assert acquire_idx < failure_idx < release_idx

    # (c) "Not a partial write": no OperationRunEvent, no
    # OperationRunByAgentEvent journaled by this invocation.
    runs = [e for e in new_events if isinstance(e, OperationRunEvent)]
    by_agents = [e for e in new_events if isinstance(e, OperationRunByAgentEvent)]
    assert runs == []
    assert by_agents == []


def test_run_exec_pairs_run_event_with_run_by_agent_event_under_one_lock(
    tmp_path: Path, kit_root: Path
) -> None:
    """CT-16: successful ``--exec`` pairs the two events under one journal lock.

    Asserts:
    (a) both events appended inside one ``LockAcquiredEvent`` /
        ``LockReleasedEvent`` pair bracketing them
        (one transaction round-trip — not two);
    (b) the paired ``OperationRunEvent.event_id is not None`` and
        the two events share the same ``event_id`` value;
    (c) the on-disk order is ``OperationRunEvent`` then
        ``OperationRunByAgentEvent`` (the dispatch event must precede
        the audit tag).
    """

    vault = _build_exec_vault(tmp_path, agent_installed=True)
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    claude = _ensure_python_claude(tmp_path, "import sys; sys.exit(0)")

    result = dispatch_and_exec(
        "weekly-digest",
        ["--window=2026-W20"],
        vault_root=vault,
        kit_root=kit_root,
        journal_path=journal_path,
        now=NOW,
        claude_binary=claude,
        agent="household-manager",
    )
    assert result.exec_status == "succeeded"
    assert result.dispatch.status == "dispatched"

    events = list(read_events(journal_path))

    # Find the two events and the lock-pair surrounding the dispatch slice.
    indices: dict[type, int] = {}
    for idx, event in enumerate(events):
        if isinstance(event, OperationRunEvent) and event.operation == "weekly-digest":
            indices[OperationRunEvent] = idx
        elif isinstance(event, OperationRunByAgentEvent):
            indices[OperationRunByAgentEvent] = idx

    assert OperationRunEvent in indices, "expected one OperationRunEvent for weekly-digest"
    assert OperationRunByAgentEvent in indices, (
        "expected one OperationRunByAgentEvent paired with the dispatch event"
    )

    run_idx = indices[OperationRunEvent]
    by_agent_idx = indices[OperationRunByAgentEvent]

    # (c) On-disk order: dispatch event precedes audit tag.
    assert run_idx < by_agent_idx, "OperationRunEvent must precede OperationRunByAgentEvent on disk"

    # (a) Exactly one LockAcquiredEvent immediately precedes the run,
    # and exactly one LockReleasedEvent immediately follows the
    # by-agent event — i.e. one pair brackets both appends.
    # Walk backwards from run_idx to find the nearest LockAcquiredEvent
    # and forwards from by_agent_idx to find the nearest LockReleasedEvent.
    acquire_idx = next(
        i for i in range(run_idx - 1, -1, -1) if isinstance(events[i], LockAcquiredEvent)
    )
    release_idx = next(
        i for i in range(by_agent_idx + 1, len(events)) if isinstance(events[i], LockReleasedEvent)
    )
    bracket_slice = events[acquire_idx : release_idx + 1]
    # The bracket must contain exactly: LockAcquired, OperationRunEvent,
    # OperationRunByAgentEvent, LockReleased — nothing else. No second
    # pair, no foreign events in between.
    assert isinstance(bracket_slice[0], LockAcquiredEvent)
    assert isinstance(bracket_slice[-1], LockReleasedEvent)
    assert len(bracket_slice) == 4
    assert isinstance(bracket_slice[1], OperationRunEvent)
    assert isinstance(bracket_slice[2], OperationRunByAgentEvent)
    # No extra lock events inside or around this transaction's bracket
    # (a second lock-pair would mean two transactions, violating "one
    # round-trip"). Filter the run-vs-failure slice for ranges that
    # could legitimately involve other locks (the subprocess invocation
    # itself doesn't touch the journal).
    locks_between = [
        e
        for e in events[acquire_idx + 1 : release_idx]
        if isinstance(e, (LockAcquiredEvent, LockReleasedEvent))
    ]
    assert locks_between == []

    # (b) Shared event_id.
    run_event = bracket_slice[1]
    by_agent_event = bracket_slice[2]
    assert isinstance(run_event, OperationRunEvent)
    assert isinstance(by_agent_event, OperationRunByAgentEvent)
    assert run_event.event_id is not None
    assert run_event.event_id == by_agent_event.event_id
    # And matches the DispatchResult's dispatch_event_id.
    assert run_event.event_id == result.dispatch.dispatch_event_id
    # The audit tag pins the agent name.
    assert by_agent_event.agent == "household-manager"
    assert by_agent_event.operation == "weekly-digest"

    # Sanity: no exec_failed events were journaled on the happy path.
    failures = [e for e in events if isinstance(e, OperationExecFailedEvent)]
    assert failures == []
