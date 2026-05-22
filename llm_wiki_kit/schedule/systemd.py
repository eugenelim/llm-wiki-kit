"""Linux systemd schedule emitter.

Implements the ``_Emitter`` Protocol defined in
:mod:`llm_wiki_kit.schedule._emitter` for Linux systems using
systemd user units.  The emitter produces two files per ``(vault,
operation)`` pair:

* a ``.service`` unit — one-shot type, sets ``WorkingDirectory`` and
  ``ExecStart`` to ``<wiki-binary> run --exec <op>``;
* a ``.timer`` unit — declares the ``OnCalendar=`` string (derived
  from the DSL via :func:`~llm_wiki_kit.schedule.dsl.to_systemd_oncalendar`)
  and ``Persistent=true`` so a missed fire catches up on next boot.

The `_Emitter` Protocol's ``artifact_path`` returns the ``.timer`` path
(that is what ``systemctl --user enable`` operates on).  The emitter
additionally exposes two public helpers so the orchestrator (PR-5) can
write both units via two :func:`~llm_wiki_kit.write_helper.write_os_artifact`
calls:

* :func:`service_path(timer_path) <service_path>` — derives the companion
  ``.service`` path from the ``.timer`` path (same stem, different
  extension).
* :func:`render_service` — renders the ``.service`` body as a string.

Orchestrator contract (PR-5 review note):
  1. Call ``render_artifact(...)`` → timer body.
  2. Call ``render_service(...)`` → service body.
  3. Write the service first via
     ``write_os_artifact(service_path(tp), service_body, vault_root=...)``.
  4. Write the timer via
     ``write_os_artifact(timer_path, timer_body, vault_root=...)``.
  5. Call ``activate(timer_path)`` to reload and enable the timer.

Spec reference: ``docs/specs/wiki-schedule/spec.md`` §"Artifact templates /
systemd ``.service`` and ``.timer``" and §"Contracts with other modules".

systemd's INI dialect does not round-trip cleanly through stdlib
``configparser`` (bare-value handling, leading-equals matching, blank-line
semantics differ), so both units are rendered as plain f-strings and pinned
byte-for-byte in ``tests/unit/test_schedule_systemd.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.schedule._emitter import InspectResult
from llm_wiki_kit.schedule.dsl import ResolvedCadence, to_systemd_oncalendar


def artifact_path(vault_id: str, operation: str) -> Path:
    """Return the ``.timer`` path for the given ``(vault_id, operation)`` pair.

    ``~/.config/systemd/user/llm-wiki-kit-<vault_id>-<operation>.timer``

    This is the path ``systemctl --user enable`` operates on.  The companion
    ``.service`` lives at :func:`service_path(artifact_path(...))
    <service_path>`.
    """

    name = f"llm-wiki-kit-{vault_id}-{operation}.timer"
    return Path.home() / ".config" / "systemd" / "user" / name


def service_path(timer_path: Path) -> Path:
    """Derive the ``.service`` path from the ``.timer`` path.

    Same parent directory and stem; only the suffix changes.  The service
    unit name must match the timer's basename stem — systemd's default-pair
    convention; the timer template omits an explicit ``Unit=`` field.

    Example::

        timer  = Path("~/.config/systemd/user/llm-wiki-kit-abc-op.timer")
        service = service_path(timer)
        # → Path("~/.config/systemd/user/llm-wiki-kit-abc-op.service")
    """

    return timer_path.with_suffix(".service")


def render_artifact(
    *,
    operation: str,
    vault_root: Path,
    vault_id: str,
    cadence: ResolvedCadence,
    exec_command: list[str],
) -> str:
    """Render the ``.timer`` unit body.

    The returned string is written to :func:`artifact_path` by the
    orchestrator.  The companion ``.service`` body is produced by
    :func:`render_service`; write it first (see module docstring for the
    two-call contract).

    Template (verbatim from spec §"Artifact templates")::

        [Unit]
        Description=Timer for llm-wiki-kit <op> in <vault-root>

        [Timer]
        OnCalendar=<systemd OnCalendar from DSL>
        Persistent=true

        [Install]
        WantedBy=timers.target
    """

    on_calendar = to_systemd_oncalendar(cadence)
    return (
        f"[Unit]\n"
        f"Description=Timer for llm-wiki-kit {operation} in {vault_root}\n"
        f"\n"
        f"[Timer]\n"
        f"OnCalendar={on_calendar}\n"
        f"Persistent=true\n"
        f"\n"
        f"[Install]\n"
        f"WantedBy=timers.target\n"
    )


def render_service(
    *,
    operation: str,
    vault_root: Path,
    vault_id: str,
    exec_command: list[str],
) -> str:
    """Render the ``.service`` unit body.

    Template (verbatim from spec §"Artifact templates")::

        [Unit]
        Description=llm-wiki-kit scheduled run: <op> in <vault-root>

        [Service]
        Type=oneshot
        WorkingDirectory=<vault-root>
        ExecStart=<wiki-binary> run --exec <op>

    ``exec_command`` is ``list[str]`` of the full argv the unit runs.
    Elements are joined with spaces — systemd's ``ExecStart=`` line takes
    a command string, not a JSON array.

    Precondition: no element of ``exec_command`` may contain whitespace or
    shell metacharacters.  systemd splits ``ExecStart=`` on whitespace; a
    path with a space would silently corrupt argv.  A :class:`WikiError` is
    raised at this boundary if any element violates this constraint.
    """

    bad = [el for el in exec_command if any(c in el for c in " \t\n\r")]
    if bad:
        raise WikiError(
            f"exec_command elements must not contain whitespace; offending element(s): {bad!r}"
        )

    exec_start = " ".join(exec_command)
    return (
        f"[Unit]\n"
        f"Description=llm-wiki-kit scheduled run: {operation} in {vault_root}\n"
        f"\n"
        f"[Service]\n"
        f"Type=oneshot\n"
        f"WorkingDirectory={vault_root}\n"
        f"ExecStart={exec_start}\n"
    )


def activate(timer_path: Path) -> None:
    """Load the timer into systemd with ``daemon-reload`` then ``enable --now``.

    Runs::

        systemctl --user daemon-reload
        systemctl --user enable --now <timer-basename>

    Raises :class:`~llm_wiki_kit.errors.WikiError` on non-zero exit, naming
    both the systemd verb and the artifact path in the message (per the
    error-phrasing convention in ``schedule/_emitter.py``).
    """

    timer_name = timer_path.name

    reload_result = subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        capture_output=True,
        text=True,
    )
    if reload_result.returncode != 0:
        raise WikiError(
            f"systemctl --user daemon-reload failed for {timer_path}: "
            f"{reload_result.stderr.strip()}"
        )

    enable_result = subprocess.run(
        ["systemctl", "--user", "enable", "--now", timer_name],
        capture_output=True,
        text=True,
    )
    if enable_result.returncode != 0:
        raise WikiError(
            f"systemctl --user enable --now {timer_name} failed for {timer_path}: "
            f"{enable_result.stderr.strip()}"
        )


def deactivate(timer_path: Path) -> None:
    """Unload the timer with ``systemctl --user disable --now``.

    Best-effort: non-zero exit is logged to stderr but does not raise.
    The journal still records the user's uninstall intent regardless of
    whether systemd successfully deactivated the timer.
    """

    timer_name = timer_path.name
    result = subprocess.run(
        ["systemctl", "--user", "disable", "--now", timer_name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"warning: systemctl --user disable --now {timer_name} "
            f"returned {result.returncode}: {result.stderr.strip()}",
            file=sys.stderr,
        )


def inspect(timer_path: Path) -> InspectResult:
    """Report the timer's current OS-side liveness.

    Returns:

    * ``"missing-file"`` — the ``.timer`` file does not exist on disk.
    * ``"loaded"`` — ``systemctl --user is-enabled`` returns ``enabled``.
    * ``"not-loaded"`` — file present but ``is-enabled`` returns anything
      other than ``enabled`` (``disabled``, ``static``, non-zero exit,
      etc.).
    * ``"not-inspectable"`` — not reachable on Linux; reserved for Windows.
    """

    if not timer_path.exists():
        return "missing-file"

    timer_name = timer_path.name
    result = subprocess.run(
        ["systemctl", "--user", "is-enabled", timer_name],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip() == "enabled":
        return "loaded"
    return "not-loaded"


# ---------------------------------------------------------------------------
# _Emitter Protocol adapter
#
# The _Emitter Protocol is defined with instance-method signatures.  The
# functions above are module-level for testability (no state needed).  This
# class wraps them so ``schedule/__init__.py`` can drop a ``SystemdEmitter()``
# into the platform-dispatch table and satisfy the Protocol structurally.
# ---------------------------------------------------------------------------


class SystemdEmitter:
    """Stateless ``_Emitter`` implementation for Linux systemd user units.

    Delegates every method to the module-level functions above so tests
    can call those functions directly without constructing an instance.
    """

    def artifact_path(self, vault_id: str, operation: str) -> Path:
        return artifact_path(vault_id, operation)

    def render_artifact(
        self,
        *,
        operation: str,
        vault_root: Path,
        vault_id: str,
        cadence: ResolvedCadence,
        exec_command: list[str],
    ) -> str:
        return render_artifact(
            operation=operation,
            vault_root=vault_root,
            vault_id=vault_id,
            cadence=cadence,
            exec_command=exec_command,
        )

    def activate(self, timer_path: Path) -> None:
        activate(timer_path)

    def deactivate(self, timer_path: Path) -> None:
        deactivate(timer_path)

    def inspect(self, timer_path: Path) -> InspectResult:
        return inspect(timer_path)


# Singleton for use by the orchestrator's platform-dispatch table.
emitter = SystemdEmitter()
