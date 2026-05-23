"""Tests for ``llm_wiki_kit.schedule.taskscheduler``.

Six groups matching plan step 7 in ``docs/specs/wiki-schedule/plan.md``:

1. Golden-XML assertions per cadence kind (daily / weekly / monthly /
   quarterly). The rendered XML is inspected via
   ``ET.fromstring(rendered.decode("utf-16"))`` because raw UTF-16 bytes
   are not human-readable as inline strings. This approach is documented in
   the module docstring as the canonical way to pin the XML shape in tests.

2. Round-trip: byte-for-byte serialise/parse stability. Verifies the XML
   is well-formed and that ``ET.tostring(ET.fromstring(bytes))`` is
   idempotent — i.e. a second parse-then-serialise produces the same bytes.

3. ``activate``/``deactivate`` are no-ops: produce no stdout, no exceptions,
   and never invoke ``subprocess.run``. Format helpers return the expected
   instruction strings without spawning any subprocess.

4. Critical XML structure verification: ``<LogonType>``, ``<RunLevel>``,
   ``<Actions Context>``, and ``<CalendarTrigger/Enabled>`` are pinned to
   their spec-mandated values.

5. Battery policy: both ``DisallowStartIfOnBatteries`` and
   ``StopIfGoingOnBatteries`` are ``true`` (laptop-friendly pair).

6. ``inspect(artifact_path)`` returns ``"missing-file"`` when the file is
   absent (or is a directory) and ``"not-inspectable"`` when it is a file.

**XML encoding choice.** ``render_artifact`` returns UTF-16 bytes with BOM
and an XML declaration. Golden assertions parse with
``ET.fromstring(rendered.decode("utf-16"))`` — this strips the declaration and
BOM automatically, leaving a tree we can traverse semantically. The raw-bytes
representation is pinned via the byte-for-byte round-trip test (group 2).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock
from xml.etree import ElementTree as ET

import pytest

from llm_wiki_kit.schedule.dsl import ResolvedCadence
from llm_wiki_kit.schedule.taskscheduler import (
    TaskSchedulerEmitter,
    format_activation_instruction,
    format_deactivation_instruction,
)

_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VAULT_ID = "abc123def456"
OPERATION = "weekly-digest"
VAULT_ROOT = Path("/home/user/my-vault")
EXEC_COMMAND = ["/usr/local/bin/wiki", "run", "--exec", OPERATION]

_DAILY = ResolvedCadence(period="daily", hour=7, minute=0)
_WEEKLY_SUN = ResolvedCadence(period="weekly", hour=9, minute=0, day_of_week=0)
_WEEKLY_TUE = ResolvedCadence(period="weekly", hour=18, minute=30, day_of_week=2)
_MONTHLY = ResolvedCadence(period="monthly", hour=9, minute=0, day_of_month=1)
_QUARTERLY = ResolvedCadence(period="quarterly", hour=9, minute=0, day_of_month=1)


def _render(cadence: ResolvedCadence, operation: str = OPERATION) -> bytes:
    emitter = TaskSchedulerEmitter()
    return emitter.render_artifact(
        operation=operation,
        vault_root=VAULT_ROOT,
        vault_id=VAULT_ID,
        cadence=cadence,
        exec_command=EXEC_COMMAND,
    )


def _parse(rendered: bytes) -> ET.Element:
    """Decode UTF-16, strip XML declaration, return the root element."""
    return ET.fromstring(rendered.decode("utf-16"))


def _find(root: ET.Element, tag: str) -> ET.Element:
    """Find a single namespaced element; fail the test if absent."""
    elem = root.find(f".//{{{_NS}}}{tag}")
    assert elem is not None, f"<{tag}> not found in rendered XML"
    return elem


# ---------------------------------------------------------------------------
# Group 1 — Golden-XML assertions per cadence kind.
#
# Each test inspects the semantic content of the rendered XML tree via
# ET.fromstring rather than pinning raw bytes. The assertions cover:
#   - Root element tag and version attribute
#   - <URI> carries the correct task name
#   - <CalendarTrigger> is present in <Triggers>
#   - <StartBoundary> encodes the correct HH:MM
#   - The <ScheduleBy*> element is the right type and carries the right children
#   - <Command> / <Arguments> match exec_command
#   - <WorkingDirectory> matches vault_root
# ---------------------------------------------------------------------------


class TestGoldenXmlDailySchemaAssertions:
    """Golden-XML assertions for a daily cadence."""

    def test_root_tag_and_version(self) -> None:
        root = _parse(_render(_DAILY))
        assert root.tag == f"{{{_NS}}}Task"
        assert root.get("version") == "1.2"

    def test_task_name_in_registration_info(self) -> None:
        root = _parse(_render(_DAILY))
        uri = _find(root, "URI")
        assert uri.text == f"llm-wiki-kit-{VAULT_ID}-{OPERATION}"

    def test_triggers_contains_calendar_trigger(self) -> None:
        root = _parse(_render(_DAILY))
        triggers = _find(root, "Triggers")
        ct = triggers.find(f"{{{_NS}}}CalendarTrigger")
        assert ct is not None

    def test_start_boundary_encodes_hhmm(self) -> None:
        root = _parse(_render(_DAILY))
        sb = _find(root, "StartBoundary")
        assert sb.text is not None
        assert sb.text.endswith("T07:00:00"), f"got: {sb.text!r}"

    def test_schedule_by_day_present_with_interval_1(self) -> None:
        root = _parse(_render(_DAILY))
        sbd = _find(root, "ScheduleByDay")
        days_interval = sbd.find(f"{{{_NS}}}DaysInterval")
        assert days_interval is not None
        assert days_interval.text == "1"

    def test_exec_command_and_arguments(self) -> None:
        root = _parse(_render(_DAILY))
        cmd = _find(root, "Command")
        args = _find(root, "Arguments")
        assert cmd.text == "/usr/local/bin/wiki"
        assert args.text == "run --exec weekly-digest"

    def test_working_directory_matches_vault_root(self) -> None:
        root = _parse(_render(_DAILY))
        wd = _find(root, "WorkingDirectory")
        assert wd.text == str(VAULT_ROOT)

    # C4: critical XML structure assertions.
    def test_logon_type_is_interactive_token(self) -> None:
        root = _parse(_render(_DAILY))
        assert _find(root, "LogonType").text == "InteractiveToken"

    def test_run_level_is_least_privilege(self) -> None:
        root = _parse(_render(_DAILY))
        assert _find(root, "RunLevel").text == "LeastPrivilege"

    def test_actions_context_attribute_is_author(self) -> None:
        root = _parse(_render(_DAILY))
        actions = _find(root, "Actions")
        assert actions.get("Context") == "Author"

    def test_calendar_trigger_enabled_is_true(self) -> None:
        root = _parse(_render(_DAILY))
        ct = _find(root, "CalendarTrigger")
        enabled = ct.find(f"{{{_NS}}}Enabled")
        assert enabled is not None
        assert enabled.text == "true"


class TestGoldenXmlWeeklySchemaAssertions:
    """Golden-XML assertions for a weekly (Sunday) cadence."""

    def test_start_boundary_encodes_hhmm(self) -> None:
        root = _parse(_render(_WEEKLY_SUN))
        sb = _find(root, "StartBoundary")
        assert sb.text is not None
        assert sb.text.endswith("T09:00:00"), f"got: {sb.text!r}"

    def test_schedule_by_week_present(self) -> None:
        root = _parse(_render(_WEEKLY_SUN))
        sbw = _find(root, "ScheduleByWeek")
        weeks_interval = sbw.find(f"{{{_NS}}}WeeksInterval")
        assert weeks_interval is not None
        assert weeks_interval.text == "1"

    def test_days_of_week_has_sunday_child(self) -> None:
        root = _parse(_render(_WEEKLY_SUN))
        sbw = _find(root, "ScheduleByWeek")
        days_of_week = sbw.find(f"{{{_NS}}}DaysOfWeek")
        assert days_of_week is not None
        sunday = days_of_week.find(f"{{{_NS}}}Sunday")
        assert sunday is not None

    def test_tuesday_cadence_days_of_week_has_tuesday_child(self) -> None:
        root = _parse(_render(_WEEKLY_TUE))
        sbw = _find(root, "ScheduleByWeek")
        days_of_week = sbw.find(f"{{{_NS}}}DaysOfWeek")
        assert days_of_week is not None
        tuesday = days_of_week.find(f"{{{_NS}}}Tuesday")
        assert tuesday is not None
        # Sunday must not appear for a Tuesday schedule.
        sunday = days_of_week.find(f"{{{_NS}}}Sunday")
        assert sunday is None

    def test_tuesday_start_boundary_encodes_hhmm(self) -> None:
        root = _parse(_render(_WEEKLY_TUE))
        sb = _find(root, "StartBoundary")
        assert sb.text is not None
        assert sb.text.endswith("T18:30:00"), f"got: {sb.text!r}"


class TestGoldenXmlMonthlySchemaAssertions:
    """Golden-XML assertions for a monthly cadence."""

    def test_start_boundary_encodes_hhmm(self) -> None:
        root = _parse(_render(_MONTHLY))
        sb = _find(root, "StartBoundary")
        assert sb.text is not None
        assert sb.text.endswith("T09:00:00"), f"got: {sb.text!r}"

    def test_schedule_by_month_present(self) -> None:
        root = _parse(_render(_MONTHLY))
        _find(root, "ScheduleByMonth")

    def test_days_of_month_has_day_1_child(self) -> None:
        root = _parse(_render(_MONTHLY))
        sbm = _find(root, "ScheduleByMonth")
        dom = sbm.find(f"{{{_NS}}}DaysOfMonth")
        assert dom is not None
        day = dom.find(f"{{{_NS}}}Day")
        assert day is not None
        assert day.text == "1"

    def test_monthly_months_has_all_12_months(self) -> None:
        root = _parse(_render(_MONTHLY))
        sbm = _find(root, "ScheduleByMonth")
        months = sbm.find(f"{{{_NS}}}Months")
        assert months is not None
        month_tags = [child.tag.split("}")[-1] for child in months]
        assert set(month_tags) == {
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        }


class TestGoldenXmlQuarterlySchemaAssertions:
    """Golden-XML assertions for a quarterly cadence."""

    def test_start_boundary_encodes_hhmm(self) -> None:
        root = _parse(_render(_QUARTERLY))
        sb = _find(root, "StartBoundary")
        assert sb.text is not None
        assert sb.text.endswith("T09:00:00"), f"got: {sb.text!r}"

    def test_schedule_by_month_present(self) -> None:
        root = _parse(_render(_QUARTERLY))
        _find(root, "ScheduleByMonth")

    def test_days_of_month_has_day_1_child(self) -> None:
        root = _parse(_render(_QUARTERLY))
        sbm = _find(root, "ScheduleByMonth")
        dom = sbm.find(f"{{{_NS}}}DaysOfMonth")
        assert dom is not None
        day = dom.find(f"{{{_NS}}}Day")
        assert day is not None
        assert day.text == "1"

    def test_quarterly_months_has_exactly_four_quarter_start_months(self) -> None:
        """Quarterly fires in Jan/Apr/Jul/Oct — the four quarter starts.

        Pins that the emitter passed the full quarterly month set (not just
        all 12 months, which would silently turn a quarterly into monthly).
        """
        root = _parse(_render(_QUARTERLY))
        sbm = _find(root, "ScheduleByMonth")
        months = sbm.find(f"{{{_NS}}}Months")
        assert months is not None
        month_tags = [child.tag.split("}")[-1] for child in months]
        assert set(month_tags) == {"January", "April", "July", "October"}
        assert len(month_tags) == 4


# ---------------------------------------------------------------------------
# Group 2 — Round-trip: byte-for-byte serialise/parse stability.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cadence,label",
    [
        (_DAILY, "daily"),
        (_WEEKLY_SUN, "weekly_sun"),
        (_MONTHLY, "monthly"),
        (_QUARTERLY, "quarterly"),
    ],
)
def test_render_artifact_round_trips_through_xml_parse(
    cadence: ResolvedCadence, label: str
) -> None:
    """Rendered XML is byte-for-byte stable under parse → serialise → parse → serialise.

    The contract: ``ET.tostring(ET.fromstring(bytes), encoding="utf-16",
    xml_declaration=True)`` applied twice must produce identical bytes. This
    pins that the output is well-formed, deterministically serialised UTF-16
    XML with no drift across repeated round-trips.
    """
    rendered = _render(cadence)

    # N5: pin UTF-16 LE BOM — Task Scheduler requires UTF-16 LE encoding.
    assert rendered[:2] == b"\xff\xfe", f"[{label}] expected UTF-16 LE BOM"

    s1 = ET.tostring(
        ET.fromstring(rendered.decode("utf-16")), encoding="utf-16", xml_declaration=True
    )
    # C2: pin that the first parse/serialise is byte-for-byte identical to
    # the original rendered output (not just that two round-trips agree).
    assert s1 == rendered, f"[{label}] first round-trip differs from rendered output"
    s2 = ET.tostring(ET.fromstring(s1.decode("utf-16")), encoding="utf-16", xml_declaration=True)
    assert s1 == s2, f"[{label}] XML is not byte-for-byte stable across round-trips"


# ---------------------------------------------------------------------------
# Group 3 — activate/deactivate are no-ops; format helpers return the right
# instruction strings; nothing spawns subprocess.run.
# ---------------------------------------------------------------------------


def test_activate_produces_no_stdout(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """``activate()`` is a true no-op: produces no stdout output."""
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    TaskSchedulerEmitter().activate(artifact)
    assert capsys.readouterr().out == ""


def test_deactivate_produces_no_stdout(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """``deactivate()`` is a true no-op: produces no stdout output."""
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    TaskSchedulerEmitter().deactivate(artifact)
    assert capsys.readouterr().out == ""


def test_activate_and_deactivate_never_invoke_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither ``activate`` nor ``deactivate`` may spawn a subprocess.

    Windows v1 special case: the kit cannot fail here — no subprocess is
    ever invoked against ``schtasks``. This invariant is load-bearing for
    the journal-ordering guarantee (spec §"Windows v1 special case").
    """
    mock = MagicMock()
    monkeypatch.setattr(subprocess, "run", mock)

    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    emitter = TaskSchedulerEmitter()
    emitter.activate(artifact)
    assert not mock.called, "activate() must not invoke subprocess.run"

    mock.reset_mock()
    emitter.deactivate(artifact)
    assert not mock.called, "deactivate() must not invoke subprocess.run"


def test_format_activation_instruction_returns_schtasks_create_line(
    tmp_path: Path,
) -> None:
    """``format_activation_instruction`` returns the correct ``schtasks /Create`` string."""
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    expected_task_name = "llm-wiki-kit-abc123def456-weekly-digest"
    result = format_activation_instruction(artifact)
    assert result == f'schtasks /Create /XML "{artifact}" /TN "{expected_task_name}"'


def test_format_deactivation_instruction_returns_schtasks_delete_line(
    tmp_path: Path,
) -> None:
    """``format_deactivation_instruction`` returns the correct ``schtasks /Delete`` string."""
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    expected_task_name = "llm-wiki-kit-abc123def456-weekly-digest"
    result = format_deactivation_instruction(artifact)
    assert result == f'schtasks /Delete /TN "{expected_task_name}" /F'


def test_format_helpers_never_invoke_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Format helpers must not spawn a subprocess — they are pure string builders."""
    mock = MagicMock()
    monkeypatch.setattr(subprocess, "run", mock)

    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    format_activation_instruction(artifact)
    assert not mock.called, "format_activation_instruction must not invoke subprocess.run"

    mock.reset_mock()
    format_deactivation_instruction(artifact)
    assert not mock.called, "format_deactivation_instruction must not invoke subprocess.run"


# ---------------------------------------------------------------------------
# Group 4 — Battery policy: both flags must be "true" (laptop-friendly pair).
# ---------------------------------------------------------------------------


def test_battery_policy_disallow_start_on_battery_is_true() -> None:
    """``DisallowStartIfOnBatteries`` must be ``true`` — don't start on battery."""
    root = _parse(_render(_DAILY))
    elem = _find(root, "DisallowStartIfOnBatteries")
    assert elem.text == "true"


def test_battery_policy_stop_if_going_on_batteries_is_true() -> None:
    """``StopIfGoingOnBatteries`` must be ``true`` — kill mid-run on battery transition."""
    root = _parse(_render(_DAILY))
    elem = _find(root, "StopIfGoingOnBatteries")
    assert elem.text == "true"


# ---------------------------------------------------------------------------
# Group 5 — inspect() is file-presence only (is_file(), not exists()).
# ---------------------------------------------------------------------------


def test_inspect_returns_missing_file_when_artifact_absent(tmp_path: Path) -> None:
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    assert not artifact.exists()
    result = TaskSchedulerEmitter().inspect(artifact)
    assert result == "missing-file"


def test_inspect_returns_not_inspectable_when_artifact_present(tmp_path: Path) -> None:
    """File-presence is the only signal at v1.

    When the file exists, the emitter returns ``"not-inspectable"`` — it cannot
    determine whether Task Scheduler has actually loaded the task (no
    ``schtasks /Query`` invocation at v1). This is the Windows v1 special case
    from ``spec.md`` §"Windows v1 special case" and the ``_Emitter`` docstring.
    """
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    artifact.write_bytes(b"<placeholder>")
    result = TaskSchedulerEmitter().inspect(artifact)
    assert result == "not-inspectable"


def test_inspect_treats_directory_as_missing(tmp_path: Path) -> None:
    """``inspect`` uses ``is_file()``, so a directory at the artifact path is ``"missing-file"``.

    ``Path.exists()`` returns True for directories; using ``is_file()`` avoids
    a false ``"not-inspectable"`` when a directory happens to share the name.
    """
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    artifact.mkdir()
    result = TaskSchedulerEmitter().inspect(artifact)
    assert result == "missing-file"


# ---------------------------------------------------------------------------
# artifact_path() — portability and naming contract.
# ---------------------------------------------------------------------------


def test_artifact_path_uses_localappdata_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``artifact_path`` prefers ``LOCALAPPDATA`` when set."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = TaskSchedulerEmitter().artifact_path("abc123", "weekly-digest")
    assert path == tmp_path / "llm-wiki-kit" / "schedules" / "abc123-weekly-digest.xml"


def test_artifact_path_falls_back_to_home_appdata_local_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On non-Windows CI runners, ``LOCALAPPDATA`` may be unset."""
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    path = TaskSchedulerEmitter().artifact_path("abc123", "my-op")
    # Stem must be <vault-id>-<operation>.xml regardless of base.
    assert path.name == "abc123-my-op.xml"
    # Parent directory structure.
    assert path.parent.name == "schedules"
    assert path.parent.parent.name == "llm-wiki-kit"


def test_artifact_path_stem_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stem is always ``<vault-id>-<operation>`` without any suffix."""
    monkeypatch.setenv("LOCALAPPDATA", "/tmp/fake_local")
    path = TaskSchedulerEmitter().artifact_path("deadbeef1234", "meal-planning")
    assert path.stem == "deadbeef1234-meal-planning"
    assert path.suffix == ".xml"


# ---------------------------------------------------------------------------
# C1 — exec_command guard raises ValueError (not stripped under python -O).
# ---------------------------------------------------------------------------


def test_render_artifact_raises_value_error_for_empty_exec_command() -> None:
    """Empty ``exec_command`` must raise ``ValueError``, not be silently skipped.

    The guard was previously an ``assert`` statement, which is stripped under
    ``python -O``. The ``ValueError`` fires in all interpreter modes.
    """
    emitter = TaskSchedulerEmitter()
    with pytest.raises(ValueError, match="exec_command must be non-empty"):
        emitter.render_artifact(
            operation=OPERATION,
            vault_root=VAULT_ROOT,
            vault_id=VAULT_ID,
            cadence=_DAILY,
            exec_command=[],
        )


# ---------------------------------------------------------------------------
# C4 — task-name cross-function invariant: <URI> matches /TN token.
# ---------------------------------------------------------------------------


def test_uri_task_name_matches_activation_instruction_tn_token() -> None:
    """``<URI>`` task name must equal the ``/TN`` argument in the activation instruction.

    If a future change renames one side but not the other, ``schtasks /Create``
    would register the task under a different name than what's in the XML,
    silently breaking scheduling. This test pins the cross-function invariant.
    """
    rendered = _render(_DAILY)
    root = _parse(rendered)
    uri = _find(root, "URI")
    assert uri.text is not None
    embedded_task_name = uri.text

    artifact_path = TaskSchedulerEmitter().artifact_path(VAULT_ID, OPERATION)
    activation_line = format_activation_instruction(artifact_path)

    # The /TN token is the last quoted argument: /TN "<task-name>"
    assert f'/TN "{embedded_task_name}"' in activation_line, (
        f"Task name mismatch: <URI> has {embedded_task_name!r} "
        f"but activation instruction is: {activation_line!r}"
    )


# ---------------------------------------------------------------------------
# disabled_hint — Windows never reaches the not-loaded branch (inspect()
# returns "not-inspectable" or "missing-file" only), but the Protocol
# contract requires a string for any future broadening of that path.
# ---------------------------------------------------------------------------


def test_disabled_hint_delegates_to_default_helper() -> None:
    """Windows ``disabled_hint`` returns exactly ``default_disabled_hint(path)``.

    The Windows ``inspect()`` only emits ``"missing-file"`` /
    ``"not-inspectable"`` at v1, so this branch is unreachable from
    doctor today. Equality against the shared
    :func:`default_disabled_hint` helper is the structural pin:
    any future drive-by that grafts a Windows-specific recovery
    command (``schtasks /Run``, ``Enable-ScheduledTask``, …) onto
    this method fails the comparison without the test having to
    enumerate the forbidden verbs.
    """
    from llm_wiki_kit.schedule._emitter import default_disabled_hint

    emitter = TaskSchedulerEmitter()
    xml_path = Path("C:/Users/u/AppData/Local/llm-wiki-kit/schedules/abc-op.xml")
    assert emitter.disabled_hint(xml_path) == default_disabled_hint(xml_path)
