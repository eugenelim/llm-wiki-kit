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
from pathlib import Path

import pytest

# Gate: skip on non-Linux or when systemd-run is absent.
pytestmark = pytest.mark.slow

_LINUX_WITH_SYSTEMD = platform.system() == "Linux" and shutil.which("systemd-run") is not None


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
        for p in (timer_path, svc_path):
            p.unlink(missing_ok=True)
