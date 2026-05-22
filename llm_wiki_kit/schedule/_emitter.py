"""Internal Protocol shared by the three per-OS schedule emitters.

Hoisted into its own module so the three emitter implementations
(``schedule/launchd.py``, ``schedule/systemd.py``,
``schedule/taskscheduler.py``) can import it without round-tripping
through ``schedule/__init__.py`` — which means the three emitter PRs
(plan steps 4, 6, 7) can ship in parallel without touching shared
init-module state.

Style conventions every emitter PR inherits:
- **Golden-string assertions.** Render-function tests pin the exact bytes
  the emitter produces (no `re.search`), so a templating drift fails the
  diff loudly rather than passing by accident.
- **Subprocess mocking via monkeypatch.** Tests stub the
  ``subprocess.run`` call inside the emitter module, not
  ``subprocess.run`` globally; the mock returns a
  ``subprocess.CompletedProcess`` with the expected stdout/stderr the
  emitter parses.
- **Error phrasing.** ``activate()`` failures raise ``WikiError`` whose
  message names both the OS verb (``launchctl bootstrap``, etc.) and
  the artifact path. ``deactivate()`` failures log to stderr but do not
  raise — the journal still gets the uninstall event so user intent is
  captured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from llm_wiki_kit.schedule.dsl import ResolvedCadence

# A four-way liveness result for ``_Emitter.inspect``. ``"not-inspectable"``
# covers Windows v1: file-presence is the only signal the kit reads.
InspectResult = Literal["loaded", "not-loaded", "missing-file", "not-inspectable"]


class _Emitter(Protocol):
    """The per-OS interface ``schedule.install``/``uninstall``/``list_schedules`` dispatch over.

    Implemented by ``schedule/launchd.py`` (macOS), ``schedule/systemd.py``
    (Linux), ``schedule/taskscheduler.py`` (Windows). Defined in this
    module (not in ``schedule/__init__.py``) so the three implementations
    can import the Protocol without colliding on a shared namespace.
    """

    def artifact_path(self, vault_id: str, operation: str) -> Path:
        """Absolute path to the OS-side artifact for this (vault, operation)."""
        ...

    def render_artifact(
        self,
        *,
        operation: str,
        vault_root: Path,
        vault_id: str,
        cadence: ResolvedCadence,
        exec_command: list[str],
    ) -> str | bytes:
        """Render the artifact body to write to ``artifact_path``."""
        ...

    def activate(self, artifact_path: Path) -> None:
        """Load the artifact into the OS scheduler.

        Raises ``WikiError`` on non-zero exit (or any failure). On Windows
        v1 this is a no-op — see ``docs/specs/wiki-schedule/spec.md``
        §"Windows v1 special case".
        """
        ...

    def deactivate(self, artifact_path: Path) -> None:
        """Unload the artifact from the OS scheduler.

        Best-effort: log non-zero exit to stderr but do not raise — the
        journal still records the user's uninstall intent.
        """
        ...

    def inspect(self, artifact_path: Path) -> InspectResult:
        """Report the artifact's current OS-side liveness."""
        ...
