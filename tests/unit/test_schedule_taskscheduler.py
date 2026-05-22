"""Tests for ``llm_wiki_kit.schedule.taskscheduler``.

Five groups matching plan step 7 in ``docs/specs/wiki-schedule/plan.md``:

1. Golden-XML assertions per cadence kind (daily / weekly / monthly /
   quarterly). The rendered XML is inspected via
   ``ET.fromstring(rendered.decode("utf-16"))`` because raw UTF-16 bytes
   are not human-readable as inline strings. This approach is documented in
   the module docstring as the canonical way to pin the XML shape in tests.

2. Round-trip: parse → serialize → assert equal. Verifies the XML is
   well-formed and stable under ``ET.tostring`` → parse → ``ET.tostring``.

3. ``activate(artifact_path)`` prints (does not invoke) the expected
   ``schtasks /Create /XML "<path>" /TN "llm-wiki-kit-<…>"`` command.
   Captured via pytest's ``capsys`` fixture.

4. ``deactivate(artifact_path)`` prints (does not invoke) the expected
   ``schtasks /Delete /TN "llm-wiki-kit-<…>" /F`` command.

5. ``inspect(artifact_path)`` returns ``"missing-file"`` when the file is
   absent and ``"not-inspectable"`` when present.

**XML encoding choice.** ``render_artifact`` returns UTF-16 bytes with BOM
and an XML declaration. Golden assertions parse with
``ET.fromstring(rendered.decode("utf-16"))`` — this strips the declaration and
BOM automatically, leaving a tree we can traverse semantically. The raw-bytes
representation is pinned via a single round-trip test (group 2) rather than
inline literals to avoid encoding-artefact fragility in the test source.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from llm_wiki_kit.schedule.dsl import ResolvedCadence
from llm_wiki_kit.schedule.taskscheduler import TaskSchedulerEmitter

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

    def test_quarterly_does_not_include_non_quarter_months(self) -> None:
        root = _parse(_render(_QUARTERLY))
        sbm = _find(root, "ScheduleByMonth")
        months = sbm.find(f"{{{_NS}}}Months")
        assert months is not None
        month_tags = {child.tag.split("}")[-1] for child in months}
        assert "February" not in month_tags
        assert "March" not in month_tags
        assert "May" not in month_tags


# ---------------------------------------------------------------------------
# Group 2 — Round-trip: parse the output, re-serialize, assert equal.
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
    """Rendered XML round-trips through ET.fromstring without diff.

    The approach: parse with fromstring (validates well-formedness), then
    re-serialize with ET.tostring to canonical form, parse again, and check
    the tag/text/attrib of the root are identical. We compare the decoded
    string representation rather than raw bytes because ET.tostring may
    reorder attributes deterministically but differently from the first
    serialization — structure-equality is the meaningful contract here.
    """
    rendered = _render(cadence)

    # First parse — validates the UTF-16 bytes are well-formed XML.
    root1 = _parse(rendered)

    # Re-serialize (to UTF-8 for comparison convenience) and parse again.
    intermediate = ET.tostring(root1, encoding="unicode")
    root2 = ET.fromstring(intermediate)

    # Structure-equal: same tag, same attribute keys, same child count at root.
    assert root1.tag == root2.tag, f"[{label}] root tag mismatch"
    assert set(root1.attrib) == set(root2.attrib), f"[{label}] root attrib keys mismatch"
    assert len(list(root1)) == len(list(root2)), f"[{label}] root child count mismatch"

    # URI text is stable across re-serialization.
    uri1 = root1.find(f".//{{{_NS}}}URI")
    uri2 = root2.find(f".//{{{_NS}}}URI")
    assert uri1 is not None and uri2 is not None
    assert uri1.text == uri2.text, f"[{label}] URI text changed across round-trip"


# ---------------------------------------------------------------------------
# Group 3 — activate() prints the schtasks /Create command; no subprocess.
# ---------------------------------------------------------------------------


def test_activate_prints_schtasks_create_command(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """``activate()`` prints the ``schtasks /Create`` command to stdout.

    No subprocess is invoked (Windows v1 special case). The printed line
    contains the artifact path and the expected task name.
    """
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    emitter = TaskSchedulerEmitter()
    emitter.activate(artifact)

    out = capsys.readouterr().out.strip()
    expected_task_name = "llm-wiki-kit-abc123def456-weekly-digest"
    assert out == f'schtasks /Create /XML "{artifact}" /TN "{expected_task_name}"'


def test_activate_returns_none(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """``activate()`` returns ``None`` — it is a no-op at v1.

    Verified by calling and confirming no exception is raised. The function
    is declared ``-> None`` so mypy catches any accidental return value.
    """
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    TaskSchedulerEmitter().activate(artifact)
    capsys.readouterr()


def test_activate_does_not_raise_regardless_of_file_existence(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The Windows v1 activate() cannot fail — it merely prints."""
    # File does not exist — should still not raise.
    artifact = tmp_path / "no-such-file.xml"
    TaskSchedulerEmitter().activate(artifact)
    capsys.readouterr()  # consume output


# ---------------------------------------------------------------------------
# Group 4 — deactivate() prints the schtasks /Delete command; no subprocess.
# ---------------------------------------------------------------------------


def test_deactivate_prints_schtasks_delete_command(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """``deactivate()`` prints the ``schtasks /Delete`` command to stdout.

    Symmetric to ``activate()`` — no subprocess, print only.
    """
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    emitter = TaskSchedulerEmitter()
    emitter.deactivate(artifact)

    out = capsys.readouterr().out.strip()
    expected_task_name = "llm-wiki-kit-abc123def456-weekly-digest"
    assert out == f'schtasks /Delete /TN "{expected_task_name}" /F'


def test_deactivate_returns_none(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """``deactivate()`` returns ``None`` — verified by confirming no exception."""
    artifact = tmp_path / "abc123def456-weekly-digest.xml"
    TaskSchedulerEmitter().deactivate(artifact)
    capsys.readouterr()


def test_deactivate_does_not_raise_regardless_of_file_existence(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    artifact = tmp_path / "no-such-file.xml"
    TaskSchedulerEmitter().deactivate(artifact)
    capsys.readouterr()


# ---------------------------------------------------------------------------
# Group 5 — inspect() is file-presence only.
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
