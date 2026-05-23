"""Windows Task Scheduler emitter — file emission only.

Implements the ``_Emitter`` Protocol from ``schedule/_emitter.py`` for
Windows. At v1 this is **file-emission only**: ``activate()`` and
``deactivate()`` are no-ops (no subprocess, no print). The caller (PR-5
orchestrator) obtains the user-facing ``schtasks`` instruction lines via
the module-level helpers ``format_activation_instruction`` and
``format_deactivation_instruction`` and includes them in the stdout summary
block (spec §"Windows v1 special case"). No subprocess is invoked against
``schtasks`` anywhere in this module.

**XML encoding choice.** ``render_artifact`` returns ``bytes`` (UTF-16 LE
with BOM). Task Scheduler expects UTF-16 XML; the stdlib
``xml.etree.ElementTree.tostring(..., encoding="utf-16", xml_declaration=True)``
call produces that. UTF-16 bytes are not human-readable as raw byte
strings, so golden assertions in the companion test file use
``ET.fromstring(rendered.decode("utf-16"))`` to traverse the tree
semantically — see ``tests/unit/test_schedule_taskscheduler.py`` for the
documented choice and the round-trip proof.

**Task Scheduler XML schema.** The namespace is
``http://schemas.microsoft.com/windows/2004/02/mit/task`` (Task Scheduler 2.0).
The structure is: ``<Task>`` root containing ``<RegistrationInfo>``,
``<Triggers>`` (one ``<CalendarTrigger>`` from ``dsl.to_task_scheduler_trigger``),
``<Principals>`` (current user), ``<Settings>`` (minimal defaults), and
``<Actions>`` (one ``<Exec>`` wrapping ``wiki run --exec <op>``). The template
is kept minimal — no registration metadata that the user would need to scrub.

**Artifact path.** ``%LOCALAPPDATA%/llm-wiki-kit/schedules/<vault-id>-<op>.xml``,
with a fallback to ``~/AppData/Local`` when ``LOCALAPPDATA`` is unset so tests
on non-Windows CI runners work without mocking environment variables.

Ref: ``docs/specs/wiki-schedule/spec.md`` §"Outputs / install / OS-side artifact",
§"Windows v1 special case", §"Contracts with other modules".
"""

from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree as ET

from llm_wiki_kit.schedule._emitter import InspectResult, default_disabled_hint
from llm_wiki_kit.schedule.dsl import ResolvedCadence, to_task_scheduler_trigger

# Task Scheduler 2.0 XML namespace.
_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def _el(tag: str, parent: ET.Element | None = None) -> ET.Element:
    """Create an element with the Task Scheduler namespace, optionally appended to a parent."""
    full_tag = f"{{{_NS}}}{tag}"
    if parent is None:
        return ET.Element(full_tag)
    return ET.SubElement(parent, full_tag)


class TaskSchedulerEmitter:
    """Windows Task Scheduler emitter.

    Implements ``_Emitter`` for the Task Scheduler XML artifact. File-emission
    only at v1; ``activate``/``deactivate`` are no-ops — the orchestrator
    calls ``format_activation_instruction``/``format_deactivation_instruction``
    to obtain the ``schtasks`` lines and includes them in its stdout summary.
    ``inspect`` is file-presence only (no ``schtasks /Query`` invocation at v1).
    """

    def artifact_path(self, vault_id: str, operation: str) -> Path:
        """Return ``%LOCALAPPDATA%/llm-wiki-kit/schedules/<vault-id>-<operation>.xml``.

        Falls back to ``~/AppData/Local`` when ``LOCALAPPDATA`` is unset so
        the code paths exercise correctly on non-Windows CI runners.
        """
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return base / "llm-wiki-kit" / "schedules" / f"{vault_id}-{operation}.xml"

    def render_artifact(
        self,
        *,
        operation: str,
        vault_root: Path,
        vault_id: str,
        cadence: ResolvedCadence,
        exec_command: list[str],
    ) -> bytes:
        """Render the Task Scheduler XML artifact to UTF-16 bytes.

        Returns ``bytes`` (UTF-16 with BOM + XML declaration) ready for
        ``write_os_artifact`` to write atomically. The task name embedded in
        ``<URI>`` is ``llm-wiki-kit-<vault-id>-<operation>``; the same name
        is used by ``format_activation_instruction`` and
        ``format_deactivation_instruction`` when building the ``schtasks``
        instruction lines for the orchestrator's stdout summary.

        The trigger block delegates to ``dsl.to_task_scheduler_trigger``,
        which is covered by ``test_schedule_dsl.py``; this function only
        wraps the trigger in the full ``<Task>`` envelope.
        """
        task_name = f"llm-wiki-kit-{vault_id}-{operation}"

        root = _el("Task")
        root.set("version", "1.2")

        # <RegistrationInfo>
        reg = _el("RegistrationInfo", root)
        uri = _el("URI", reg)
        uri.text = task_name

        # <Triggers> — one CalendarTrigger from the DSL converter.
        triggers = _el("Triggers", root)
        trigger_elem = to_task_scheduler_trigger(cadence)
        # The trigger element produced by dsl.to_task_scheduler_trigger has no
        # namespace; wrap it by re-serialising into the namespaced tree.
        _copy_trigger_into_ns(trigger_elem, triggers)

        # <Principals>
        principals = _el("Principals", root)
        principal = _el("Principal", principals)
        principal.set("id", "Author")
        log_on = _el("LogonType", principal)
        log_on.text = "InteractiveToken"
        run_level = _el("RunLevel", principal)
        run_level.text = "LeastPrivilege"

        # <Settings> — minimal defaults; Task Scheduler fills the rest.
        settings = _el("Settings", root)
        _el_with_text("MultipleInstancesPolicy", "IgnoreNew", settings)
        # Battery policy: both true = laptop-friendly. Don't start on battery;
        # don't run if power transitions mid-task. The next scheduled trigger
        # picks it up when back on AC. Both-false would drain the battery;
        # the mixed (false/true) pair is a partial-run failure mode worse than
        # either consistent choice — start succeeds but the task is killed
        # mid-run on battery transition.
        _el_with_text("DisallowStartIfOnBatteries", "true", settings)
        _el_with_text("StopIfGoingOnBatteries", "true", settings)
        _el_with_text("ExecutionTimeLimit", "PT1H", settings)
        _el_with_text("Enabled", "true", settings)

        # <Actions>
        # exec_command is preconditioned non-empty per orchestrator contract
        # (the caller must pass at least the wiki executable path).
        if not exec_command:
            raise ValueError("exec_command must be non-empty per _Emitter contract")
        actions = _el("Actions", root)
        actions.set("Context", "Author")
        exec_el = _el("Exec", actions)
        command_el = _el("Command", exec_el)
        command_el.text = exec_command[0]
        args_el = _el("Arguments", exec_el)
        args_el.text = " ".join(exec_command[1:])
        working_dir = _el("WorkingDirectory", exec_el)
        working_dir.text = str(vault_root)

        result = ET.tostring(root, encoding="utf-16", xml_declaration=True)
        # ET.tostring with encoding="utf-16" returns bytes; mypy infers Any
        # from the overloaded stub so we assert the type explicitly.
        assert isinstance(result, bytes)
        return result

    def companion_artifacts(
        self,
        *,
        operation: str,
        vault_root: Path,
        vault_id: str,
        cadence: ResolvedCadence,
        exec_command: list[str],
    ) -> list[tuple[Path, str | bytes]]:
        """Task Scheduler emits a single ``.xml`` artifact — no companions."""
        return []

    def install_instruction(self, artifact_path: Path) -> str | None:
        """Return the user-facing ``schtasks /Create /XML`` line for the stdout summary.

        Windows v1 doesn't auto-activate (``activate()`` is a no-op);
        the orchestrator prints this string so the user can run the
        command by hand to enable the task. Delegates to the existing
        module-level helper so PR-7's golden-string assertions stay
        green.
        """
        return format_activation_instruction(artifact_path)

    def uninstall_instruction(self, artifact_path: Path) -> str | None:
        """Return the user-facing ``schtasks /Delete`` line for the uninstall summary."""
        return format_deactivation_instruction(artifact_path)

    def activate(self, artifact_path: Path) -> None:
        """No-op. Windows v1 special case: no subprocess is spawned.

        The orchestrator (PR-5) calls ``format_activation_instruction``
        separately and includes the ``schtasks /Create`` line in the stdout
        summary block. This method is a true no-op so that the
        ``write → activate → journal`` ordering stays uniform across OSes
        without any risk of failure or output here.
        """

    def deactivate(self, artifact_path: Path) -> None:
        """No-op. Windows v1 special case: no subprocess is spawned.

        Symmetric to ``activate()``. The orchestrator includes the
        ``schtasks /Delete`` instruction in its own stdout summary.
        """

    def inspect(self, artifact_path: Path) -> InspectResult:
        """Return ``"missing-file"`` or ``"not-inspectable"``.

        File-presence (``is_file()``) is the only signal at v1 (no
        ``schtasks /Query`` invocation). ``"not-inspectable"`` when the file
        exists — the kit cannot determine whether Task Scheduler has actually
        loaded it. ``"missing-file"`` when the file is absent or is a
        directory.
        """
        if not artifact_path.is_file():
            return "missing-file"
        return "not-inspectable"

    def disabled_hint(self, artifact_path: Path) -> str:
        """Windows never returns ``not-loaded`` from ``inspect`` at v1.

        Delegates to :func:`default_disabled_hint` so the string is
        defined in one place — ``_Emitter`` is a structural
        :class:`typing.Protocol` (the concrete emitter classes do not
        inherit from it), so the Protocol's default body never executes
        at runtime; sharing the helper keeps this concrete impl and
        the Protocol-default docstring contract from drifting. A
        future ``schtasks /Query`` integration that grows a
        ``"not-loaded"`` result should replace this body with a
        Windows-specific recovery hint rather than fall back to it
        silently.
        """
        return default_disabled_hint(artifact_path)


# ---------------------------------------------------------------------------
# Public format helpers — called by the PR-5 orchestrator to compose the
# stdout summary block. These return strings; they never spawn a subprocess.
#
# C3 DEFERRED (PR-5's call): these are module-level for v1. If PR-5's
# orchestrator finds the Windows-specific branch awkward, consider lifting
# ``post_install_instruction`` / ``post_uninstall_instruction`` to the
# ``_Emitter`` Protocol with ``None``-default impls on launchd/systemd.
# ---------------------------------------------------------------------------


def format_activation_instruction(artifact_path: Path) -> str:
    """Return the ``schtasks /Create`` line for inclusion in the install summary.

    The orchestrator prints this as part of the ``wiki schedule install``
    stdout summary (spec §"Windows v1 special case"). Keeping it out of
    ``activate()`` means ``activate()`` is a pure no-op and cannot fail or
    produce unexpected output on its own.
    """
    task_name = _task_name_from_path(artifact_path)
    return f'schtasks /Create /XML "{artifact_path}" /TN "{task_name}"'


def format_deactivation_instruction(artifact_path: Path) -> str:
    """Return the ``schtasks /Delete`` line for inclusion in the uninstall summary.

    Symmetric to ``format_activation_instruction``.
    """
    task_name = _task_name_from_path(artifact_path)
    return f'schtasks /Delete /TN "{task_name}" /F'


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _el_with_text(tag: str, text: str, parent: ET.Element) -> ET.Element:
    """Create a namespaced child element with text content and append it."""
    child = _el(tag, parent)
    child.text = text
    return child


def _copy_trigger_into_ns(src: ET.Element, parent: ET.Element) -> None:
    """Recursively copy a namespace-less ElementTree element into the Task Scheduler namespace.

    ``dsl.to_task_scheduler_trigger`` builds the trigger tree without a
    namespace (plain tag names like ``"CalendarTrigger"``, ``"StartBoundary"``,
    etc.). This helper re-creates each element under ``_NS`` so the full
    ``<Task>`` document uses a uniform namespace, which is what Task Scheduler
    expects.
    """
    dest = ET.SubElement(parent, f"{{{_NS}}}{src.tag}")
    if src.text:
        dest.text = src.text
    for attr_name, attr_val in src.attrib.items():
        dest.set(attr_name, attr_val)
    for child in src:
        _copy_trigger_into_ns(child, dest)


def _task_name_from_path(artifact_path: Path) -> str:
    """Derive the Task Scheduler task name from the artifact file path.

    The artifact is named ``<vault-id>-<operation>.xml``; the task name is
    ``llm-wiki-kit-<vault-id>-<operation>``.  Stripping ``.xml`` from the
    stem and prepending the fixed prefix recovers the name without requiring
    the caller to pass vault_id + operation separately.
    """
    return f"llm-wiki-kit-{artifact_path.stem}"
