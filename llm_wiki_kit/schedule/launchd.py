"""macOS launchd emitter for ``wiki schedule``.

Implements the ``_Emitter`` Protocol from ``schedule/_emitter.py``
for the macOS platform. Renders a launchd plist via stdlib ``plistlib``,
writes it via ``write_helper.write_os_artifact()``, and wraps
``launchctl bootstrap`` / ``bootout`` / ``print`` for activation,
deactivation, and inspection.

Artifact path: ``~/Library/LaunchAgents/com.llm-wiki-kit.<vault-id>.<operation>.plist``

Activation command: ``launchctl bootstrap gui/<uid> <plist>``
  (replaces the deprecated ``launchctl load``; spec §"OS-side activation")

Error phrasing (per ``_emitter.py`` style conventions): ``activate()``
raises ``WikiError`` whose message names both the OS verb
(``launchctl bootstrap``) and the artifact path. ``deactivate()`` logs
non-zero to stderr but does not raise.

Contract pinned in ``docs/specs/wiki-schedule/spec.md`` §"Contracts
with other modules" and §"Artifact templates / launchd plist".
Construction tests live in ``tests/unit/test_schedule_launchd.py``
(plan step 4 in ``docs/specs/wiki-schedule/plan.md``).
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.schedule._emitter import InspectResult
from llm_wiki_kit.schedule.dsl import ResolvedCadence, to_launchd_calendar_interval


class LaunchdEmitter:
    """macOS launchd implementation of the ``_Emitter`` Protocol.

    Instantiated once per platform dispatch; all methods are stateless
    and safe to call from any thread.
    """

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    def artifact_path(self, vault_id: str, operation: str) -> Path:
        """Return the absolute path to the plist under ``~/Library/LaunchAgents/``."""
        return (
            Path.home()
            / "Library"
            / "LaunchAgents"
            / f"com.llm-wiki-kit.{vault_id}.{operation}.plist"
        )

    def render_artifact(
        self,
        *,
        operation: str,
        vault_root: Path,
        vault_id: str,
        cadence: ResolvedCadence,
        exec_command: list[str],
    ) -> bytes:
        """Render the launchd plist as UTF-8 XML bytes.

        Uses stdlib ``plistlib.dumps`` (``FMT_XML``, ``sort_keys=True``
        default). The ``StartCalendarInterval`` key receives the full
        list returned by ``to_launchd_calendar_interval`` so that a
        quarterly cadence's four-entry fan-out is handled by the DSL
        layer, not here.

        The ``exec_command`` list is embedded verbatim in
        ``ProgramArguments``; the first element must be the absolute
        path to the ``wiki`` binary. ``wiki run --exec <operation>``
        is the shape the spec pins in §Invariants and CT-2.
        """
        label = f"com.llm-wiki-kit.{vault_id}.{operation}"
        log_dir = vault_root / ".wiki.journal" / "exec-logs"

        payload: dict[str, object] = {
            "Label": label,
            "ProgramArguments": exec_command,
            "WorkingDirectory": str(vault_root),
            "StartCalendarInterval": to_launchd_calendar_interval(cadence),
            "StandardOutPath": str(log_dir / "launchd-stdout.log"),
            "StandardErrorPath": str(log_dir / "launchd-stderr.log"),
            "RunAtLoad": False,
        }
        return plistlib.dumps(payload, fmt=plistlib.FMT_XML)

    def activate(self, artifact_path: Path) -> None:
        """Bootstrap the plist into the per-user launchd domain.

        Runs ``launchctl bootstrap gui/<uid> <plist>``. Raises
        ``WikiError`` on non-zero exit; the message names both the OS
        verb and the artifact path per the ``_emitter.py`` style
        convention.
        """
        uid = os.getuid()
        result = subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(artifact_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise WikiError(
                f"launchctl bootstrap gui/{uid} {artifact_path} failed"
                + (f": {stderr}" if stderr else "")
            )

    def deactivate(self, artifact_path: Path) -> None:
        """Bootout the plist from the per-user launchd domain.

        Runs ``launchctl bootout gui/<uid> <plist>``. Non-zero exit is
        logged to stderr but does not raise — the journal still records
        the user's uninstall intent (``_emitter.py`` style convention).
        """
        uid = os.getuid()
        result = subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(artifact_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            print(
                f"warning: launchctl bootout gui/{uid} {artifact_path} returned"
                f" {result.returncode}" + (f": {stderr}" if stderr else ""),
                file=sys.stderr,
            )

    def inspect(self, artifact_path: Path) -> InspectResult:
        """Report the artifact's current launchd liveness.

        ``artifact_path`` must end in ``.plist``; the service label is
        derived from the filename stem (e.g.
        ``com.llm-wiki-kit.<vault-id>.<op>.plist`` → label
        ``com.llm-wiki-kit.<vault-id>.<op>``).  Passing a path without
        a ``.plist`` suffix raises ``WikiError`` immediately, before any
        filesystem or subprocess calls.

        Outcome mapping:

        - ``"missing-file"`` — the plist file is absent on disk.
        - ``"loaded"``       — ``launchctl print gui/<uid>/<label>``
                               returns exit-0 (service is known to launchd).
        - ``"not-loaded"``   — ``launchctl print`` returns non-zero
                               (service is not registered, e.g. after a
                               ``bootout`` or a system restart without a
                               re-bootstrap).

        ``"not-inspectable"`` is the Windows v1 fallback and is never
        returned by this implementation.
        """
        if artifact_path.suffix != ".plist":
            raise WikiError(f"inspect() requires a .plist path; got {artifact_path!r}")

        if not artifact_path.exists():
            return "missing-file"

        # Derive the service label from the plist filename (sans ``.plist``).
        label = artifact_path.stem
        uid = os.getuid()
        result = subprocess.run(
            ["launchctl", "print", f"gui/{uid}/{label}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return "loaded"
        return "not-loaded"
