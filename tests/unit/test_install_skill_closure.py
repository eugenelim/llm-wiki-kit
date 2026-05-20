"""Regression tests for ``tools/install-skill.py`` dependency closures.

Pins the contract from issue #60 lane 2 task 1: installing the
``bug-fix`` skill must not drag in the Ralph harness. Ralph is the AFK
variant of ``work-loop`` — adopters who only want the bug-fix flow
should not have to take ``tools/ralph.sh`` and ``tools/RALPH.md``
along for the ride.

The originating PR (#24) shipped the closure that did drag Ralph in,
flagged as a known follow-up. This test exists so the trimmed closure
stays trimmed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "tools" / "install-skill.py"


def _install(skill: str, dest: Path) -> set[Path]:
    """Run install-skill.py for ``skill`` into ``dest`` and return the
    set of dest-relative paths it produced."""
    subprocess.run(
        [sys.executable, str(INSTALLER), skill, str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    return {p.relative_to(dest) for p in dest.rglob("*") if p.is_file()}


def test_bugfix_closure_excludes_ralph(tmp_path: Path) -> None:
    """The ``bug-fix`` install closure must not contain Ralph artefacts.

    Adopters who only want the bug-fix flow should not see the AFK
    harness land in their repo. Ralph is reachable from the ``work-loop``
    skill's prose; pulling it in is an opt-in act, not a transitive
    side effect.
    """
    produced = _install("bug-fix", tmp_path)
    ralph_paths = {Path("tools/ralph.sh"), Path("tools/RALPH.md")}
    leaked = ralph_paths & produced
    assert not leaked, (
        f"bug-fix install closure should not contain Ralph artefacts; "
        f"found {sorted(str(p) for p in leaked)}"
    )


def test_bugfix_closure_still_pulls_workloop(tmp_path: Path) -> None:
    """Sanity check: trimming Ralph from ``work-loop``'s deps must not
    accidentally trim ``work-loop`` itself out of the ``bug-fix``
    closure. ``bug-fix`` declares a direct dependency on ``work-loop``,
    so the SKILL file must still land at the destination."""
    produced = _install("bug-fix", tmp_path)
    assert Path(".claude/skills/work-loop/SKILL.md") in produced
    assert Path(".claude/skills/bug-fix/SKILL.md") in produced
