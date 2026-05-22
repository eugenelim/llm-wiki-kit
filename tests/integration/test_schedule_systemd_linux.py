"""Opt-in Linux integration test for the systemd emitter.

This test requires a live Linux host with systemd user-session support:
- ``platform.system() == "Linux"``
- ``shutil.which("systemd-run") is not None``

It is marked ``@pytest.mark.slow`` and is **not** part of the standard CI
gate (``pytest -m 'not slow'``).  A maintainer runs it locally on Linux before
shipping the systemd emitter.

The test exercises the full write → activate → inspect → deactivate → cleanup
cycle against the real systemd user instance:

1. Render the ``.service`` and ``.timer`` files via the module-level helpers.
2. Write both files via :func:`~llm_wiki_kit.write_helper.write_os_artifact`.
3. Call :func:`~llm_wiki_kit.schedule.systemd.activate` (daemon-reload +
   enable --now).
4. Assert :func:`~llm_wiki_kit.schedule.systemd.inspect` returns ``"loaded"``.
5. Call :func:`~llm_wiki_kit.schedule.systemd.deactivate` (disable --now).
6. Delete the written files.

Failures in this test indicate a real systemd compatibility issue on the
Linux host, not a code bug visible on other platforms.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Gate: skip on non-Linux or when systemd-run is absent.
pytestmark = pytest.mark.slow

_LINUX_WITH_SYSTEMD = platform.system() == "Linux" and shutil.which("systemd-run") is not None
_SYSTEMD_ANALYZE = shutil.which("systemd-analyze")

# ---------------------------------------------------------------------------
# C3. systemd-analyze calendar round-trip — one per cadence kind
# ---------------------------------------------------------------------------

_ONCALENDAR_STRINGS = [
    ("daily", "*-*-* 07:00:00"),
    ("weekly-sun", "Sun *-*-* 09:00:00"),
    ("monthly", "*-*-01 09:00:00"),
    ("quarterly", "*-01,04,07,10-01 09:00:00"),
]


@pytest.mark.skipif(
    not _LINUX_WITH_SYSTEMD,
    reason="requires Linux with systemd-run available",
)
@pytest.mark.skipif(
    _SYSTEMD_ANALYZE is None,
    reason="systemd-analyze not available",
)
@pytest.mark.parametrize(
    "cadence_id,on_calendar", _ONCALENDAR_STRINGS, ids=[c for c, _ in _ONCALENDAR_STRINGS]
)
def test_oncalendar_accepted_by_systemd_analyze(cadence_id: str, on_calendar: str) -> None:
    """Each OnCalendar string must be accepted by ``systemd-analyze calendar``."""
    result = subprocess.run(
        ["systemd-analyze", "calendar", on_calendar],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"systemd-analyze calendar {on_calendar!r} exited {result.returncode}; "
        f"stderr: {result.stderr.strip()}"
    )


@pytest.mark.skipif(
    not _LINUX_WITH_SYSTEMD,
    reason="requires Linux with systemd-run available",
)
def test_systemd_write_activate_inspect_deactivate(tmp_path: Path) -> None:
    """Full write → activate → inspect → deactivate cycle on a live systemd."""

    from llm_wiki_kit.schedule.dsl import ResolvedCadence
    from llm_wiki_kit.schedule.systemd import (
        activate,
        artifact_path,
        deactivate,
        inspect,
        render_artifact,
        render_service,
        service_path,
    )
    from llm_wiki_kit.write_helper import write_os_artifact

    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    vault_id = "testdeadbeef"
    operation = "llm-wiki-kit-integration-test-op"

    # Use a simple daily cadence for the timer.
    cadence = ResolvedCadence(period="daily", hour=23, minute=59)

    # Use /bin/true as the exec command so systemd can actually resolve it.
    true_bin = shutil.which("true") or "/usr/bin/true"
    exec_command = [true_bin]

    timer_path = artifact_path(vault_id, operation)
    svc_path = service_path(timer_path)

    try:
        # Step 1 — render.
        service_body = render_service(
            operation=operation,
            vault_root=vault_root,
            vault_id=vault_id,
            exec_command=exec_command,
        )
        timer_body = render_artifact(
            operation=operation,
            vault_root=vault_root,
            vault_id=vault_id,
            cadence=cadence,
            exec_command=exec_command,
        )

        # Step 2 — write both files.
        write_os_artifact(svc_path, service_body, vault_root=vault_root)
        write_os_artifact(timer_path, timer_body, vault_root=vault_root)

        assert svc_path.exists(), f"service file missing after write: {svc_path}"
        assert timer_path.exists(), f"timer file missing after write: {timer_path}"

        # Step 3 — activate.
        activate(timer_path)

        # Step 4 — inspect returns "loaded".
        result = inspect(timer_path)
        assert result == "loaded", (
            f"expected 'loaded' after activate, got {result!r}; "
            f"run 'systemctl --user is-enabled {timer_path.name}' to diagnose"
        )

        # Step 5 — deactivate (best-effort; should succeed on a clean session).
        deactivate(timer_path)

    finally:
        # Step 6 — clean up regardless of test outcome.
        # Deactivate the timer best-effort so the user session is not left with
        # residual systemd state if the test body raises mid-way.
        try:
            deactivate(timer_path)
        except Exception as exc:
            print(f"warning: deactivate during cleanup failed: {exc}", file=sys.stderr)
        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            print(
                f"warning: daemon-reload during cleanup failed: {exc}",
                file=sys.stderr,
            )
        for p in (timer_path, svc_path):
            p.unlink(missing_ok=True)
