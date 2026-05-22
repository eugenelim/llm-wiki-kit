"""macOS-only integration test for the launchd emitter.

Marked ``@pytest.mark.slow`` — CI does not run ``-m slow``; this is
for the maintainer's macOS box only (plan step 4 in
``docs/specs/wiki-schedule/plan.md``).

The test installs a no-op plist that ``echo``'s on fire, calls real
``launchctl bootstrap``, verifies ``inspect()`` returns ``"loaded"``,
then ``bootout``'s.

Gate conditions:
- Platform must be Darwin (macOS).
- ``launchctl`` must be on PATH (present on all macOS systems since 10.10).

If ``launchctl bootstrap`` fails because the label is already loaded
(exit code 17 — "File exists", or exit code 37 — "Operation already in
progress" on older macOS, or stderr contains "already loaded" /
"already bootstrapped"), the test is marked ``xfail`` — that
environment state is outside the test's control.  Any other bootstrap
failure is a real test failure.
"""

from __future__ import annotations

import platform
import time
from pathlib import Path

import pytest

from llm_wiki_kit.schedule.dsl import ResolvedCadence
from llm_wiki_kit.schedule.launchd import LaunchdEmitter

pytestmark = pytest.mark.slow

# Skip the entire module on non-Darwin platforms.
if platform.system() != "Darwin":
    pytest.skip("launchd integration tests require macOS", allow_module_level=True)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Minimal vault directory."""
    (tmp_path / ".wiki.journal" / "exec-logs").mkdir(parents=True)
    return tmp_path


def test_bootstrap_inspect_bootout(vault: Path, tmp_path: Path) -> None:
    """Full round-trip: write plist → bootstrap → inspect → bootout.

    Side-effect: this test materialises a real plist under the maintainer's
    ``~/Library/LaunchAgents/`` directory and bootstraps it into the
    per-user launchd domain.  The ``finally`` block always runs
    ``launchctl bootout`` and ``unlink``'s the plist, so the service is
    removed whether the assertions pass or fail.

    Uses a harmless ``echo`` command so the service fires safely if launchd
    decides to run it during the short window the test holds it loaded.
    """
    emitter = LaunchdEmitter()

    # Use a unique label derived from tmp_path to avoid collisions.
    vault_id = "test" + str(abs(hash(str(tmp_path))))[:8]
    operation = "noop-echo"
    plist_path = (
        Path.home() / "Library" / "LaunchAgents" / f"com.llm-wiki-kit.{vault_id}.{operation}.plist"
    )

    # Compose a cadence that fires at a fixed future time (unlikely to
    # overlap with the test window).
    cadence = ResolvedCadence(period="daily", hour=3, minute=0)
    exec_command = ["/bin/echo", "llm-wiki-kit-test-noop"]

    rendered = emitter.render_artifact(
        operation=operation,
        vault_root=vault,
        vault_id=vault_id,
        cadence=cadence,
        exec_command=exec_command,
    )

    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(rendered)

    try:
        # Bootstrap — only xfail when the failure is the "label already
        # loaded" class (exit code 17 = File exists, exit code 37 = Operation
        # already in progress on older macOS, or stderr variant "already
        # loaded" / "already bootstrapped").  Any other failure is a real
        # regression.
        try:
            emitter.activate(plist_path)
        except Exception as exc:
            msg = str(exc)
            already_loaded = (
                "exit code 17" in msg
                or "exit code 37" in msg
                or "already loaded" in msg.lower()
                or "already bootstrapped" in msg.lower()
            )
            if already_loaded:
                pytest.xfail(f"launchctl bootstrap failed (label already loaded): {exc}")
            raise

        # Give launchd a moment to register the service.
        time.sleep(0.5)

        status = emitter.inspect(plist_path)
        assert status == "loaded", f"expected 'loaded' after bootstrap, got {status!r}"

    finally:
        # Always attempt bootout and cleanup, even if the assertions fail.
        try:
            emitter.deactivate(plist_path)
        except Exception:
            # deactivate is best-effort; swallow here to let cleanup proceed.
            pass
        try:
            plist_path.unlink(missing_ok=True)
        except OSError:
            pass

    # After bootout the file is gone; inspect must return missing-file.
    assert not plist_path.exists()
    status_after = emitter.inspect(plist_path)
    assert status_after == "missing-file"
