"""Tests for ``llm_wiki_kit.write_helper.write_os_artifact``.

The schedule module's ``_Emitter`` implementations materialise files
outside the user's vault — launchd plists under
``~/Library/LaunchAgents/``, systemd units under
``~/.config/systemd/user/``, Task Scheduler XML under
``%LOCALAPPDATA%/llm-wiki-kit/schedules/``. ``safe_write`` is the
in-vault writer (``_relative_to_vault`` raises on out-of-vault paths
by design), so the kit needs one blessed out-of-vault writer for these
artifacts. ``write_os_artifact`` is that helper. See
``docs/specs/wiki-schedule/spec.md`` §"Contracts with other modules"
and ``docs/specs/wiki-schedule/plan.md`` step 1; precedent for the
exemption pattern is ``_ensure_obsidianignore``
(``docs/specs/safe-write-ordering/spec.md`` §"Documented exceptions").
"""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

import pytest

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.write_helper import write_os_artifact


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A vault root with the canonical journal directory beneath it."""
    (tmp_path / "vault" / ".wiki.journal").mkdir(parents=True)
    return tmp_path / "vault"


@pytest.fixture
def os_artifact_dir(tmp_path: Path) -> Path:
    """A throwaway directory simulating ``~/Library/LaunchAgents/`` etc.

    Kept on a sibling path under ``tmp_path`` so it is *not* a child of
    the ``vault`` fixture's directory — the in-vault refusal test needs
    that disjoint layout to be meaningful.
    """
    target = tmp_path / "launchagents"
    target.mkdir()
    return target


# ---------------------------------------------------------------------------
# Happy path: bytes round-trip
# ---------------------------------------------------------------------------


def test_writes_str_content_and_round_trips(os_artifact_dir: Path, vault: Path) -> None:
    target = os_artifact_dir / "com.llm-wiki-kit.abcdef123456.weekly-digest.plist"
    payload = '<?xml version="1.0"?>\n<plist><dict/></plist>\n'
    write_os_artifact(target, payload, vault_root=vault)
    assert target.read_text(encoding="utf-8") == payload


def test_writes_bytes_content_and_round_trips(os_artifact_dir: Path, vault: Path) -> None:
    target = os_artifact_dir / "schedule.xml"
    payload = b'<?xml version="1.0" encoding="UTF-16"?>\n<Task/>\n'
    write_os_artifact(target, payload, vault_root=vault)
    assert target.read_bytes() == payload


def test_creates_missing_parent_directories(os_artifact_dir: Path, vault: Path) -> None:
    # The schedule orchestrator computes artifact paths under
    # ``~/.config/systemd/user/`` and similar, which may not exist on a
    # fresh machine. The helper creates the parent directory rather than
    # forcing every caller to mkdir first.
    target = os_artifact_dir / "nested" / "deeper" / "unit.timer"
    write_os_artifact(target, "[Timer]\n", vault_root=vault)
    assert target.read_text(encoding="utf-8") == "[Timer]\n"


# ---------------------------------------------------------------------------
# Atomic replace: final bytes match new content, no .tmp* siblings
# ---------------------------------------------------------------------------


def test_replaces_existing_file_with_new_content(os_artifact_dir: Path, vault: Path) -> None:
    target = os_artifact_dir / "unit.service"
    write_os_artifact(target, "[Service]\nExecStart=/old\n", vault_root=vault)
    write_os_artifact(target, "[Service]\nExecStart=/new\n", vault_root=vault)
    assert target.read_text(encoding="utf-8") == "[Service]\nExecStart=/new\n"


def test_replace_leaves_no_tmp_siblings(os_artifact_dir: Path, vault: Path) -> None:
    target = os_artifact_dir / "unit.service"
    write_os_artifact(target, "v1\n", vault_root=vault)
    write_os_artifact(target, "v2\n", vault_root=vault)
    # The directory should contain exactly the target file — the
    # ``NamedTemporaryFile`` + ``os.replace`` swap leaves no debris.
    siblings = list(os_artifact_dir.iterdir())
    assert siblings == [target], (
        f"expected only {target.name} in {os_artifact_dir}, found {[p.name for p in siblings]}"
    )


# ---------------------------------------------------------------------------
# In-vault refusal: routes back through safe_write
# ---------------------------------------------------------------------------


def test_refuses_path_inside_vault(vault: Path) -> None:
    target = vault / "notes" / "weekly.plist"
    target.parent.mkdir()
    with pytest.raises(WikiError) as excinfo:
        write_os_artifact(target, "<plist/>", vault_root=vault)
    msg = str(excinfo.value)
    assert "safe_write" in msg, f"error must redirect caller to safe_write, got: {msg!r}"
    assert not target.exists(), "in-vault refusal must not write the file"


def test_refuses_file_directly_under_vault_root(vault: Path) -> None:
    # A file directly under the vault root is in-vault. Pins the
    # ``resolved_vault in resolved_path.parents`` clause when the path
    # has exactly one component below the vault.
    target = vault / "schedule.plist"
    with pytest.raises(WikiError):
        write_os_artifact(target, "<plist/>", vault_root=vault)


def test_refuses_vault_root_directory_itself(vault: Path) -> None:
    # Pathological caller hands the vault root itself as the artifact
    # path. Pins the ``resolved_path == resolved_vault`` equality clause —
    # otherwise dead code, per the helper's documented file-not-directory
    # contract.
    with pytest.raises(WikiError):
        write_os_artifact(vault, "<plist/>", vault_root=vault)


def test_refuses_path_inside_vault_via_dotdot(vault: Path, tmp_path: Path) -> None:
    # Lexical escape that resolves back inside the vault: ``vault/../vault/x``.
    # The helper resolves both sides before comparing.
    lexical_path = vault / ".." / vault.name / "schedule.plist"
    with pytest.raises(WikiError):
        write_os_artifact(lexical_path, "<plist/>", vault_root=vault)


# ---------------------------------------------------------------------------
# OSError bubbles: helper does not swallow filesystem failures
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory-permission semantics required")
def test_permission_denied_bubbles_as_oserror(
    os_artifact_dir: Path, vault: Path, request: pytest.FixtureRequest
) -> None:
    # Strip write permission on the artifact directory so the
    # tempfile open inside it fails. The helper must not swallow the
    # OSError — schedule.install relies on it to abort the install.
    os_artifact_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    # ``addfinalizer`` runs even on ``KeyboardInterrupt`` / xdist worker
    # SIGKILL between the chmod and the test body, so a killed process
    # leaves no read-only directory blocking the next ``tmp_path``
    # cleanup. try/finally would skip on those signals.
    request.addfinalizer(lambda: os_artifact_dir.chmod(stat.S_IRWXU))
    target = os_artifact_dir / "schedule.plist"
    with pytest.raises(OSError):
        write_os_artifact(target, "<plist/>", vault_root=vault)


def test_fsync_failure_propagates_and_cleans_up(
    os_artifact_dir: Path, vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pin the durability claim: a mid-write fsync failure must (a)
    # propagate as OSError, (b) leave no .tmp debris in the artifact
    # directory, (c) not clobber a pre-existing artifact at the target.
    target = os_artifact_dir / "unit.service"
    target.write_text("preexisting\n", encoding="utf-8")

    def boom(_fd: int) -> None:
        raise OSError(errno.EIO, "simulated fsync failure")

    monkeypatch.setattr("llm_wiki_kit.write_helper.os.fsync", boom)

    with pytest.raises(OSError):
        write_os_artifact(target, "new\n", vault_root=vault)

    # No tempfile debris.
    siblings = sorted(p.name for p in os_artifact_dir.iterdir())
    assert siblings == ["unit.service"], f"fsync failure must unlink tempfile; found {siblings}"
    # Pre-existing file untouched — partial-write under a failed fsync
    # must not have replaced the old content.
    assert target.read_text(encoding="utf-8") == "preexisting\n"
