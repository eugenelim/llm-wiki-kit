"""Tests for ``llm_wiki_kit.schedule.systemd``.

Covers the two test case categories from plan step 6:

1. **Golden-string assertions** for the rendered ``.service`` AND ``.timer``
   per cadence kind (daily / weekly / monthly / quarterly).  Each pins the
   ``OnCalendar=`` string verbatim.

2. **``inspect()`` state mapping** — each ``InspectResult`` state given
   fixture ``systemctl --user is-enabled <timer>`` outputs (mocked via
   ``monkeypatch`` of ``subprocess.run`` inside the emitter module, not
   globally).  States mapped:

   * ``"missing-file"`` — the timer file is absent.
   * ``"loaded"`` — ``is-enabled`` stdout is ``"enabled"``.
   * ``"not-loaded"`` — ``is-enabled`` returns ``"disabled"``.
   * ``"not-loaded"`` — ``is-enabled`` returns ``"static"`` (non-``enabled``
     stdout).
   * ``"not-loaded"`` — ``is-enabled`` exits non-zero.

Subprocess mocking follows the project convention (see ``test_search.py``,
``test_evalkit_runner.py``): ``monkeypatch.setattr(subprocess, "run", ...)``
patches the ``subprocess`` module object, which the emitter imports as
``import subprocess``; the mock is therefore scoped to the test and does not
leak globally.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.schedule.dsl import ResolvedCadence
from llm_wiki_kit.schedule.systemd import (
    SystemdEmitter,
    activate,
    artifact_path,
    deactivate,
    inspect,
    render_artifact,
    render_service,
    service_path,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VAULT_ROOT = Path("/home/user/my-vault")
_VAULT_ID = "abc123def456"
_OPERATION = "weekly-digest"
_EXEC_CMD = ["/usr/local/bin/wiki", "run", "--exec", _OPERATION]

# One ResolvedCadence per cadence kind — these are the canonical golden
# inputs; changing them here breaks all golden assertions below (intentional).
_DAILY = ResolvedCadence(period="daily", hour=7, minute=0)
_WEEKLY_SUN = ResolvedCadence(period="weekly", hour=9, minute=0, day_of_week=0)
_MONTHLY = ResolvedCadence(period="monthly", hour=9, minute=0, day_of_month=1)
_QUARTERLY = ResolvedCadence(period="quarterly", hour=9, minute=0, day_of_month=1)


def _cp(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# 1a. artifact_path + service_path helpers
# ---------------------------------------------------------------------------


def test_artifact_path_returns_timer_under_systemd_user_dir() -> None:
    path = artifact_path("abc123", "my-op")
    assert path == Path.home() / ".config" / "systemd" / "user" / "llm-wiki-kit-abc123-my-op.timer"


def test_service_path_same_stem_different_suffix() -> None:
    timer = artifact_path("abc123", "my-op")
    svc = service_path(timer)
    assert svc.stem == timer.stem
    assert svc.suffix == ".service"
    assert svc.parent == timer.parent


# ---------------------------------------------------------------------------
# 1b. Golden-string assertions — .timer per cadence kind
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cadence,expected_timer",
    [
        (
            _DAILY,
            (
                "[Unit]\n"
                "Description=Timer for llm-wiki-kit weekly-digest in /home/user/my-vault\n"
                "\n"
                "[Timer]\n"
                "OnCalendar=*-*-* 07:00:00\n"
                "Persistent=true\n"
                "\n"
                "[Install]\n"
                "WantedBy=timers.target\n"
            ),
        ),
        (
            _WEEKLY_SUN,
            (
                "[Unit]\n"
                "Description=Timer for llm-wiki-kit weekly-digest in /home/user/my-vault\n"
                "\n"
                "[Timer]\n"
                "OnCalendar=Sun *-*-* 09:00:00\n"
                "Persistent=true\n"
                "\n"
                "[Install]\n"
                "WantedBy=timers.target\n"
            ),
        ),
        (
            _MONTHLY,
            (
                "[Unit]\n"
                "Description=Timer for llm-wiki-kit weekly-digest in /home/user/my-vault\n"
                "\n"
                "[Timer]\n"
                "OnCalendar=*-*-01 09:00:00\n"
                "Persistent=true\n"
                "\n"
                "[Install]\n"
                "WantedBy=timers.target\n"
            ),
        ),
        (
            _QUARTERLY,
            (
                "[Unit]\n"
                "Description=Timer for llm-wiki-kit weekly-digest in /home/user/my-vault\n"
                "\n"
                "[Timer]\n"
                "OnCalendar=*-01,04,07,10-01 09:00:00\n"
                "Persistent=true\n"
                "\n"
                "[Install]\n"
                "WantedBy=timers.target\n"
            ),
        ),
    ],
    ids=["daily", "weekly-sun", "monthly", "quarterly"],
)
def test_render_artifact_timer_golden_string(cadence: ResolvedCadence, expected_timer: str) -> None:
    """Pin the exact timer body byte-for-byte per cadence kind."""
    result = render_artifact(
        operation=_OPERATION,
        vault_root=_VAULT_ROOT,
        vault_id=_VAULT_ID,
        cadence=cadence,
        exec_command=_EXEC_CMD,
    )
    assert result == expected_timer


# ---------------------------------------------------------------------------
# 1c. Golden-string assertion — .service (cadence-independent)
# ---------------------------------------------------------------------------


def test_render_service_golden_string() -> None:
    """The service body does not depend on cadence; pin it once."""
    result = render_service(
        operation=_OPERATION,
        vault_root=_VAULT_ROOT,
        vault_id=_VAULT_ID,
        exec_command=_EXEC_CMD,
    )
    expected = (
        "[Unit]\n"
        "Description=llm-wiki-kit scheduled run: weekly-digest in /home/user/my-vault\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "WorkingDirectory=/home/user/my-vault\n"
        "ExecStart=/usr/local/bin/wiki run --exec weekly-digest\n"
    )
    assert result == expected


def test_render_service_exec_start_contains_op() -> None:
    """ExecStart= embeds the operation name (argv shape pinned by spec)."""
    result = render_service(
        operation="meal-planning",
        vault_root=_VAULT_ROOT,
        vault_id=_VAULT_ID,
        exec_command=["/usr/bin/wiki", "run", "--exec", "meal-planning"],
    )
    assert "ExecStart=/usr/bin/wiki run --exec meal-planning" in result


def test_render_service_working_directory_set() -> None:
    result = render_service(
        operation=_OPERATION,
        vault_root=Path("/some/other/vault"),
        vault_id=_VAULT_ID,
        exec_command=_EXEC_CMD,
    )
    assert "WorkingDirectory=/some/other/vault" in result


# ---------------------------------------------------------------------------
# 1d. OnCalendar strings pinned verbatim per cadence kind
# ---------------------------------------------------------------------------
#
# These are distinct from the full golden-string assertions above; they pin
# only the OnCalendar value so a reader can immediately see the mapping
# between cadence and systemd calendar syntax without wading through the
# whole timer body.
#


@pytest.mark.parametrize(
    "cadence,expected_oncalendar",
    [
        (_DAILY, "OnCalendar=*-*-* 07:00:00"),
        (_WEEKLY_SUN, "OnCalendar=Sun *-*-* 09:00:00"),
        (_MONTHLY, "OnCalendar=*-*-01 09:00:00"),
        (_QUARTERLY, "OnCalendar=*-01,04,07,10-01 09:00:00"),
    ],
    ids=["daily", "weekly", "monthly", "quarterly"],
)
def test_render_artifact_oncalendar_line_verbatim(
    cadence: ResolvedCadence, expected_oncalendar: str
) -> None:
    """Each cadence kind produces the expected OnCalendar= line verbatim."""
    timer = render_artifact(
        operation=_OPERATION,
        vault_root=_VAULT_ROOT,
        vault_id=_VAULT_ID,
        cadence=cadence,
        exec_command=_EXEC_CMD,
    )
    assert expected_oncalendar in timer


# ---------------------------------------------------------------------------
# 2. inspect() state mapping
# ---------------------------------------------------------------------------


def test_inspect_returns_missing_file_when_timer_absent(tmp_path: Path) -> None:
    """File absent → ``"missing-file"`` without calling subprocess."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"
    assert not timer.exists()
    assert inspect(timer) == "missing-file"


def test_inspect_returns_loaded_when_is_enabled_stdout_is_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``is-enabled`` stdout ``"enabled"`` → ``"loaded"``."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"
    timer.write_text("")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: _cp(stdout="enabled\n", returncode=0),
    )
    assert inspect(timer) == "loaded"


def test_inspect_returns_not_loaded_when_is_enabled_stdout_is_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``is-enabled`` stdout ``"disabled"`` → ``"not-loaded"``."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"
    timer.write_text("")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: _cp(stdout="disabled\n", returncode=1),
    )
    assert inspect(timer) == "not-loaded"


def test_inspect_returns_not_loaded_when_is_enabled_stdout_is_static(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``is-enabled`` stdout ``"static"`` → ``"not-loaded"``."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"
    timer.write_text("")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: _cp(stdout="static\n", returncode=0),
    )
    assert inspect(timer) == "not-loaded"


def test_inspect_returns_not_loaded_when_is_enabled_exits_nonzero_empty_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-zero exit + no stdout → ``"not-loaded"``."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"
    timer.write_text("")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: _cp(stdout="", returncode=4),
    )
    assert inspect(timer) == "not-loaded"


# ---------------------------------------------------------------------------
# 3. activate() — subprocess mocked inside the emitter module
# ---------------------------------------------------------------------------


def test_activate_calls_daemon_reload_then_enable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``activate`` issues daemon-reload then enable --now."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return _cp(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    activate(timer)

    assert len(calls) == 2
    assert calls[0] == ["systemctl", "--user", "daemon-reload"]
    assert calls[1] == ["systemctl", "--user", "enable", "--now", timer.name]


def test_activate_raises_wiki_error_if_daemon_reload_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-zero exit from daemon-reload → WikiError naming the artifact path."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        return _cp(returncode=1, stderr="Failed to connect to bus", stdout="some output")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(WikiError) as exc:
        activate(timer)
    msg = str(exc.value)
    assert "daemon-reload" in msg
    assert str(timer) in msg
    # C3: both streams present in error message
    assert "stderr=" in msg
    assert "stdout=" in msg


def test_activate_raises_wiki_error_if_enable_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-zero exit from enable --now → WikiError naming the artifact path."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"
    call_count = 0

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        # daemon-reload succeeds; enable --now fails
        if call_count == 1:
            return _cp(returncode=0)
        return _cp(returncode=1, stderr="Unit not found", stdout="hint on stdout")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(WikiError) as exc:
        activate(timer)
    msg = str(exc.value)
    assert "enable --now" in msg
    assert str(timer) in msg
    # C3: both streams present in error message
    assert "stderr=" in msg
    assert "stdout=" in msg


# ---------------------------------------------------------------------------
# C1. timeout=10.0 on all subprocess calls; TimeoutExpired mapped correctly
# ---------------------------------------------------------------------------


def test_inspect_returns_not_loaded_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TimeoutExpired from is-enabled → ``"not-loaded"``."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"
    timer.write_text("")

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10.0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert inspect(timer) == "not-loaded"


def test_activate_raises_wiki_error_on_daemon_reload_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TimeoutExpired from daemon-reload → WikiError with timeout message."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10.0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(WikiError) as exc:
        activate(timer)
    assert "daemon-reload" in str(exc.value)
    assert "timed out" in str(exc.value)


def test_activate_raises_wiki_error_on_enable_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TimeoutExpired from enable --now → WikiError with timeout message."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"
    call_count = 0

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _cp(returncode=0)  # daemon-reload succeeds
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10.0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(WikiError) as exc:
        activate(timer)
    assert "enable --now" in str(exc.value)
    assert "timed out" in str(exc.value)


def test_deactivate_does_not_raise_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TimeoutExpired from disable --now must not raise (best-effort)."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=10.0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    deactivate(timer)  # must not raise


# ---------------------------------------------------------------------------
# 4. deactivate() — best-effort, no raise on non-zero
# ---------------------------------------------------------------------------


def test_deactivate_does_not_raise_on_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-zero exit from disable --now must not raise."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _cp(returncode=1, stderr="Unit not loaded")
    )

    # Must not raise — deactivate is best-effort per spec.
    deactivate(timer)


def test_deactivate_calls_disable_now(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``deactivate`` issues ``systemctl --user disable --now <timer>``."""
    timer = tmp_path / "llm-wiki-kit-xyz-op.timer"
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return _cp(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    deactivate(timer)
    assert calls == [["systemctl", "--user", "disable", "--now", timer.name]]


# ---------------------------------------------------------------------------
# 5. SystemdEmitter class delegates to module-level functions
# ---------------------------------------------------------------------------


def test_systemd_emitter_delegates_artifact_path_and_render_artifact() -> None:
    """SystemdEmitter delegates to module-level functions; pin output against the daily golden."""
    e = SystemdEmitter()

    # artifact_path delegation
    expected_ap = Path.home() / ".config" / "systemd" / "user" / "llm-wiki-kit-vid-myop.timer"
    assert e.artifact_path("vid", "myop") == expected_ap

    # render_artifact delegation — assert against the canonical golden for daily cadence
    expected = (
        "[Unit]\n"
        "Description=Timer for llm-wiki-kit weekly-digest in /home/user/my-vault\n"
        "\n"
        "[Timer]\n"
        "OnCalendar=*-*-* 07:00:00\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )
    assert (
        e.render_artifact(
            operation=_OPERATION,
            vault_root=_VAULT_ROOT,
            vault_id=_VAULT_ID,
            cadence=_DAILY,
            exec_command=_EXEC_CMD,
        )
        == expected
    )


# ---------------------------------------------------------------------------
# 6. C2 — render_service raises WikiError on whitespace in exec_command
# ---------------------------------------------------------------------------


def test_render_service_raises_on_whitespace_in_exec_command() -> None:
    """exec_command elements with whitespace must raise WikiError at the boundary."""
    with pytest.raises(WikiError) as exc:
        render_service(
            operation=_OPERATION,
            vault_root=_VAULT_ROOT,
            vault_id=_VAULT_ID,
            exec_command=["/usr/local/bin/wiki run", "--exec", _OPERATION],
        )
    assert "whitespace" in str(exc.value)


# ---------------------------------------------------------------------------
# 7. C4 — inspect returns "not-loaded" when returncode != 0, even if stdout is
#    "enabled" (inconsistent state guard)
# ---------------------------------------------------------------------------


def test_inspect_returns_not_loaded_when_returncode_nonzero_stdout_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """stdout='enabled' but returncode!=0 must still return ``"not-loaded"``."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"
    timer.write_text("")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: _cp(stdout="enabled\n", returncode=1),
    )
    assert inspect(timer) == "not-loaded"


# ---------------------------------------------------------------------------
# 8. N8 — deactivate stderr warning contains expected strings
# ---------------------------------------------------------------------------


def test_deactivate_stderr_warning_contains_disable_now_and_timer_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Non-zero exit warning must mention ``disable --now`` and the timer basename."""
    timer = tmp_path / "llm-wiki-kit-abc-op.timer"

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _cp(returncode=2, stderr="some error"))

    deactivate(timer)

    err = capsys.readouterr().err
    assert "disable --now" in err
    assert timer.name in err


# ---------------------------------------------------------------------------
# companion_artifacts — added by PR-5's _Emitter Protocol lift
# ---------------------------------------------------------------------------


def test_systemd_emitter_companion_artifacts_returns_service_pair_for_timer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Unit-test the new ``SystemdEmitter.companion_artifacts`` method.

    Returned list has exactly one entry; path equals
    ``service_path(timer_path)`` and body equals ``render_service(...)``
    for the same inputs (byte-for-byte). Pins the documented systemd
    "Orchestrator contract" — call ``render_artifact`` for the
    ``.timer`` body, ``render_service`` for the ``.service`` body, in
    that order.
    """

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    emitter = SystemdEmitter()
    operation = "weekly-digest"
    vault_id = "deadbeef0123"
    vault_root = Path("/srv/vault")
    cadence = ResolvedCadence(period="daily", hour=7, minute=0)
    exec_command = ["/usr/local/bin/wiki", "run", "--exec", operation]

    pairs = emitter.companion_artifacts(
        operation=operation,
        vault_root=vault_root,
        vault_id=vault_id,
        cadence=cadence,
        exec_command=exec_command,
    )
    assert len(pairs) == 1
    sp, body = pairs[0]
    timer = emitter.artifact_path(vault_id, operation)
    assert sp == service_path(timer)
    assert body == render_service(
        operation=operation,
        vault_root=vault_root,
        vault_id=vault_id,
        exec_command=exec_command,
    )


# ---------------------------------------------------------------------------
# disabled_hint — surfaced by ``wiki doctor`` when inspect() == "not-loaded"
# ---------------------------------------------------------------------------


def test_disabled_hint_names_systemctl_user_enable_with_timer_basename() -> None:
    """``disabled_hint`` returns ``systemctl --user enable --now <timer-basename>``.

    The hint uses ``artifact_path.name`` rather than the full path —
    ``systemctl --user`` resolves units by name within the user unit
    search path.
    """
    emitter = SystemdEmitter()
    timer_path = Path("/home/u/.config/systemd/user/llm-wiki-kit-abc-op.timer")
    assert emitter.disabled_hint(timer_path) == (
        "systemctl --user enable --now llm-wiki-kit-abc-op.timer"
    )
