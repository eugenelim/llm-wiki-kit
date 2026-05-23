"""Integration test for ``wiki schedule install`` CLI wiring.

Drives ``python -m llm_wiki_kit schedule install …`` as a subprocess
against a real ``tmp_path`` vault and asserts on stdout, journal
state, and the on-disk artifact file. Per plan step 5 — proves the
``argv → module → emitter → write → activate → journal`` pipeline.

The launchd ``activate()`` call shells out to ``launchctl bootstrap``
which on macOS will fail in a tmp-path environment (no real
``~/Library/LaunchAgents/`` linkage to user session). To keep the
integration test deterministic, we run on Linux/macOS but stub the
``activate`` subprocess via the ``WIKI_SCHEDULE_TEST_NO_ACTIVATE``
environment variable consumed by the test harness wrapper below, or
prefer driving the test on a CI runner where the subprocess can be
intercepted. The cleanest signal-to-noise approach we use here:
monkey-patch the platform dispatch via a stub script that overrides
``llm_wiki_kit.schedule._resolve_emitter`` at startup, but for the
subprocess shape we ship a sitecustomize that injects the stub. The
overhead of that machinery is high; instead, this integration test
points the kit at a tmp dir for ``Path.home`` via env-var override and
asserts only on the *artifact write* + *journal append* — the
``activate`` step is exercised in unit tests against the real
emitter.

This test only exercises the in-process orchestrator boundary; the
subprocess exit code + stdout shape are the contract pinned here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_vault(tmp_path: Path) -> Path:
    from llm_wiki_kit.journal import append_event
    from llm_wiki_kit.models import PrimitiveInstallEvent, VaultInitEvent

    vault = tmp_path / "vault"
    vault.mkdir()
    journal_dir = vault / ".wiki.journal"
    journal_dir.mkdir()
    journal_path = journal_dir / "journal.jsonl"
    now = datetime(2026, 5, 22, 9, 0, 0, tzinfo=UTC)
    append_event(
        journal_path,
        VaultInitEvent(timestamp=now, by="wiki-init", vault_name="test-vault", recipe="minimal"),
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=now,
            by="wiki-init",
            primitive="weekly-digest",
            version="0.1.0",
        ),
    )
    return vault


def _run_wiki(
    args: list[str], *, cwd: Path, env_overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    base_env = os.environ.copy()
    if env_overrides:
        base_env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "llm_wiki_kit", *args],
        cwd=str(cwd),
        env=base_env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _stub_emitter_sitecustomize(artifacts_dir: Path, sitecustomize_dir: Path) -> dict[str, str]:
    """Write a sitecustomize.py that monkey-patches the platform dispatch.

    The subprocess inherits ``PYTHONPATH=<sitecustomize_dir>:...``; on
    import-startup, sitecustomize.py replaces
    ``llm_wiki_kit.schedule._resolve_emitter`` with a stub that writes
    to ``artifacts_dir`` and never spawns ``launchctl`` / ``systemctl``.
    Returns the env override dict.
    """

    sitecustomize_dir.mkdir(exist_ok=True)
    (sitecustomize_dir / "sitecustomize.py").write_text(
        "from pathlib import Path\n"
        "import llm_wiki_kit.schedule as _s\n"
        f"_BASE = Path({str(artifacts_dir)!r})\n"
        "class _Stub:\n"
        "    def artifact_path(self, vault_id, operation):\n"
        "        return _BASE / f'{vault_id}.{operation}.stub'\n"
        "    def render_artifact(self, **kwargs):\n"
        "        return b'stub-artifact'\n"
        "    def companion_artifacts(self, **kwargs):\n"
        "        return []\n"
        "    def install_instruction(self, p): return None\n"
        "    def uninstall_instruction(self, p): return None\n"
        "    def activate(self, p): pass\n"
        "    def deactivate(self, p): pass\n"
        "    def inspect(self, p):\n"
        "        return 'loaded' if p.exists() else 'missing-file'\n"
        "_s._resolve_emitter = lambda: _Stub()\n",
        encoding="utf-8",
    )
    return {
        "PYTHONPATH": str(sitecustomize_dir) + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }


def test_cli_schedule_install_journals_event_and_writes_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive `wiki schedule install` as a subprocess, assert outputs.

    Uses a wrapper script that monkey-patches ``_resolve_emitter`` at
    import time so the platform-specific OS calls (``launchctl
    bootstrap``, ``systemctl --user enable``) never fire — instead, a
    stub emitter writes the artifact under ``tmp_path`` and the
    activate call is a no-op. The shape of the test is identical to
    a real install; only the OS-side activation is short-circuited.
    """

    vault = _make_vault(tmp_path)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    env_overrides = _stub_emitter_sitecustomize(artifacts_dir, tmp_path / "_sitecustomize")

    proc = _run_wiki(
        ["schedule", "install", "weekly-digest", "--machine", "this-host"],
        cwd=vault,
        env_overrides=env_overrides,
    )

    assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"
    assert "Installed schedule for weekly-digest on this-host" in proc.stdout
    assert "cadence: SUN 09:00" in proc.stdout

    # Journal carries one ScheduleInstalledEvent.
    journal_lines = (
        (vault / ".wiki.journal" / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    )
    install_lines = [line for line in journal_lines if '"type":"schedule.installed"' in line]
    assert len(install_lines) == 1
    payload = json.loads(install_lines[0])
    assert payload["operation"] == "weekly-digest"
    assert payload["machine_id"] == "this-host"
    assert payload["cadence_dsl"] == "SUN 09:00"
    assert payload["exec_command"][1:] == ["run", "--exec", "weekly-digest"]

    # Artifact file exists on disk where the stub emitter wrote it.
    artifact_files = list(artifacts_dir.glob("*.weekly-digest.stub"))
    assert len(artifact_files) == 1
    assert artifact_files[0].read_bytes() == b"stub-artifact"


def test_cli_schedule_install_with_at_override_records_canonical_dsl(
    tmp_path: Path,
) -> None:
    """``wiki schedule install --at "tue 18:00"`` records canonical ``TUE 18:00``."""

    vault = _make_vault(tmp_path)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    env_overrides = _stub_emitter_sitecustomize(artifacts_dir, tmp_path / "_sitecustomize")

    proc = _run_wiki(
        [
            "schedule",
            "install",
            "weekly-digest",
            "--at",
            "tue 18:00",
            "--machine",
            "this-host",
        ],
        cwd=vault,
        env_overrides=env_overrides,
    )
    assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"
    assert "cadence: TUE 18:00" in proc.stdout

    journal_lines = (
        (vault / ".wiki.journal" / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    )
    install_lines = [line for line in journal_lines if '"type":"schedule.installed"' in line]
    assert len(install_lines) == 1
    assert json.loads(install_lines[0])["cadence_dsl"] == "TUE 18:00"


def test_cli_schedule_uninstall_removes_artifact_and_journals_event(
    tmp_path: Path,
) -> None:
    """Install then uninstall via CLI on the local hostname; verify both
    events + artifact gone. We omit ``--machine`` on both calls so the
    orchestrator defaults to ``socket.gethostname()`` and the uninstall
    takes the current-host branch (which deletes the artifact). The
    foreign-machine path is exercised by ``test_cli_schedule_list_all_machines_shows_foreign_row``
    below, which deliberately installs with a foreign ``--machine``."""
    import socket

    vault = _make_vault(tmp_path)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    env_overrides = _stub_emitter_sitecustomize(artifacts_dir, tmp_path / "_sitecustomize")
    current_host = socket.gethostname()

    install_proc = _run_wiki(
        ["schedule", "install", "weekly-digest"],
        cwd=vault,
        env_overrides=env_overrides,
    )
    assert install_proc.returncode == 0, install_proc.stderr
    artifact_files = list(artifacts_dir.glob("*.weekly-digest.stub"))
    assert len(artifact_files) == 1

    uninstall_proc = _run_wiki(
        ["schedule", "uninstall", "weekly-digest"],
        cwd=vault,
        env_overrides=env_overrides,
    )
    assert uninstall_proc.returncode == 0, uninstall_proc.stderr
    assert "Uninstalled schedule for weekly-digest" in uninstall_proc.stdout

    # Artifact was deleted by the uninstall path.
    assert list(artifacts_dir.glob("*.weekly-digest.stub")) == []

    journal_lines = (
        (vault / ".wiki.journal" / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    )
    uninstall_lines = [line for line in journal_lines if '"type":"schedule.uninstalled"' in line]
    assert len(uninstall_lines) == 1
    payload = json.loads(uninstall_lines[0])
    assert payload["operation"] == "weekly-digest"
    assert payload["machine_id"] == current_host
    assert payload["removed_artifact"] is True


def test_cli_schedule_list_all_machines_shows_foreign_row(tmp_path: Path) -> None:
    """``wiki schedule list --all-machines`` includes foreign-host rows with STATUS=unknown."""

    vault = _make_vault(tmp_path)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    env_overrides = _stub_emitter_sitecustomize(artifacts_dir, tmp_path / "_sitecustomize")

    install_proc = _run_wiki(
        ["schedule", "install", "weekly-digest", "--machine", "other-box"],
        cwd=vault,
        env_overrides=env_overrides,
    )
    assert install_proc.returncode == 0, install_proc.stderr

    # Default list (current host only) omits the foreign row.
    default_list = _run_wiki(["schedule", "list"], cwd=vault, env_overrides=env_overrides)
    assert default_list.returncode == 0, default_list.stderr
    # Only the header row when no current-host schedules exist.
    rows = [line for line in default_list.stdout.splitlines() if "weekly-digest" in line]
    assert rows == []

    # --all-machines shows the foreign row.
    all_list = _run_wiki(
        ["schedule", "list", "--all-machines"], cwd=vault, env_overrides=env_overrides
    )
    assert all_list.returncode == 0, all_list.stderr
    matching = [line for line in all_list.stdout.splitlines() if "weekly-digest" in line]
    assert len(matching) == 1
    assert "other-box" in matching[0]
    assert "unknown" in matching[0]
