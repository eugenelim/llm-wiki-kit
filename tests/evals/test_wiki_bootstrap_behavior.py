"""Behavior eval: the ``wiki-bootstrap`` SKILL runs end-to-end.

Spec: ``docs/specs/wiki-bootstrap/spec.md``
Plan: ``docs/specs/wiki-bootstrap/plan.md`` § T5

Covers ACs 8-16 across six eval cases. Each drives Claude Code via
subprocess against a per-test fixture vault and asserts the wizard's
file/journal/tool-call postconditions. The transcript line-count
bound (≤ 6 non-blank lines) is the structural short-circuit signal.

These cases are slow and cost real money; ``pytestmark =
pytest.mark.eval`` keeps them out of the default lane. CI runs them
in the dedicated Evals workflow.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import pytest

from tests import evalkit

pytestmark = pytest.mark.eval


# Tool grants. The wizard needs Read (marker probe + journal +
# verb-skill SKILL.md), Glob (general discovery), Bash(wiki outcomes)
# for the verb table, Bash(rm -f) for the marker-replacement path,
# and Write for the marker. `wiki <verb>` is never granted — the
# wizard's read-only demo is enforced by absence at the tool grant.
ALLOWED_FULL_FLOW: list[str] = [
    "Read",
    "Glob",
    "Bash(wiki outcomes)",
    "Bash(rm -f *)",
    "Write",
]
ALLOWED_NO_OP: list[str] = ["Read", "Glob"]

CANONICAL_TRIGGER_PROMPT = "I just made a new vault, help me get started."

# Verbs the wizard might be tempted to shell out to. Catches the
# sugared verb names AND the un-sugared operation names — spec
# Invariant 7 forbids any path that triggers the operation.
_VERB_RE = re.compile(
    r"\bwiki\s+(?:run\s+)?"
    r"(digest|plan-meals|refresh-stakeholders|"
    r"weekly-digest|meal-planning|stakeholder-map-refresh)\b"
)

# Path pattern matching only the three shipped *operation* SKILL.md
# files (never the wizard's own SKILL.md). Used by the AC 13 / 14
# evidence assertions where "demo happened / didn't" is the
# question, not "any skill was loaded".
_OP_SKILL_RE = re.compile(
    r"/skills/(weekly-digest|meal-planning|stakeholder-map-refresh)/SKILL\.md"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_vault(vault: Path, *, exclude: Iterable[str] = ()) -> dict[str, str]:
    """SHA-256 of every regular file under ``vault``, keyed by relative path.

    ``exclude`` names paths relative to the vault root that should be
    skipped (e.g. ``".wiki.bootstrap"`` after a happy-path run).
    """

    exclude_set = {Path(p) for p in exclude}
    manifest: dict[str, str] = {}
    for path in vault.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(vault)
        if rel in exclude_set:
            continue
        manifest[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def _skip_guard() -> None:
    """Two-layer guard: deselected at marker, skipped at credentials."""

    evalkit.skip_if_env_unset("ANTHROPIC_API_KEY")
    evalkit.skip_if_no_claude()


def _run_or_fail(
    prompt: str, vault: Path, allowed_tools: list[str], *, timeout_s: float = 180.0
) -> evalkit.ClaudeRunResult:
    result = evalkit.run_claude(
        prompt=prompt,
        vault=vault,
        allowed_tools=allowed_tools,
        timeout_s=timeout_s,
    )
    if result.timed_out:
        pytest.fail(f"claude timed out: {evalkit.redact(result.stderr[:400])}")
    if result.decode_failures:
        pytest.fail(
            f"transcript had {result.decode_failures} undecodable lines; "
            f"order-sensitive assertions cannot be trusted"
        )
    return result


def _assert_iso8601_utc(line: str) -> None:
    """The marker contents must parse as a single ISO-8601 UTC line."""

    stripped = line.strip()
    # Accept ``Z`` suffix (the SKILL writes this form) and
    # ``+00:00`` (Python's ``isoformat`` default with tz). Reject any
    # other timezone — the marker is UTC by spec.
    if stripped.endswith("Z"):
        candidate = stripped[:-1] + "+00:00"
    else:
        candidate = stripped
    parsed = datetime.fromisoformat(candidate)
    offset = parsed.utcoffset()
    assert offset is not None, f"marker timestamp lacks timezone info: {line!r}"
    assert offset.total_seconds() == 0, f"marker timestamp is not UTC: {line!r}"


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def test_happy_path_postconditions(personal_vault: Path) -> None:
    """ACs 8, 9, 10, 12 — fresh vault writes marker only.

    AC 12 (re-run after partial completion) is covered transitively:
    a fresh-init vault IS the post-partial-abort equivalence class
    because every pre-marker step is read-only (Invariants 2, 3, 7).
    """

    _skip_guard()

    pre_manifest = _hash_vault(personal_vault)
    journal = personal_vault / ".wiki.journal" / "journal.jsonl"
    pre_journal_bytes = journal.read_bytes()

    result = _run_or_fail(CANONICAL_TRIGGER_PROMPT, personal_vault, ALLOWED_FULL_FLOW)

    marker = personal_vault / ".wiki.bootstrap"
    assert marker.is_file(), (
        f"AC 8: marker not written; stdout[:400]={evalkit.redact(result.stdout[:400])!r}"
    )
    contents = marker.read_text(encoding="utf-8")
    lines = [line for line in contents.splitlines() if line.strip()]
    assert len(lines) == 1, (
        f"AC 8: marker should contain one non-blank line, got {len(lines)}: {contents!r}"
    )
    _assert_iso8601_utc(lines[0])

    assert journal.read_bytes() == pre_journal_bytes, (
        "AC 9: journal byte-changed during wizard run; spec Invariant 2 forbids appends"
    )

    post_manifest = _hash_vault(personal_vault, exclude={".wiki.bootstrap"})
    assert post_manifest == pre_manifest, (
        f"AC 10: vault files outside the marker changed; "
        f"differing keys: {sorted(set(post_manifest) ^ set(pre_manifest))!r}"
    )


def test_idempotent_rerun_writes_nothing(bootstrapped_personal_vault: Path) -> None:
    """AC 11 — a re-trigger on a bootstrapped vault writes nothing."""

    _skip_guard()

    pre_manifest = _hash_vault(bootstrapped_personal_vault)
    journal = bootstrapped_personal_vault / ".wiki.journal" / "journal.jsonl"
    pre_journal_bytes = journal.read_bytes()

    _run_or_fail(CANONICAL_TRIGGER_PROMPT, bootstrapped_personal_vault, ALLOWED_NO_OP)

    assert journal.read_bytes() == pre_journal_bytes, (
        "AC 11: journal grew during a re-run; the marker must short-circuit the wizard"
    )
    post_manifest = _hash_vault(bootstrapped_personal_vault)
    assert post_manifest == pre_manifest, (
        f"AC 11: vault files changed on re-run; differing keys: "
        f"{sorted(set(post_manifest) ^ set(pre_manifest))!r}"
    )


def test_no_verbs_degradation(no_verbs_vault: Path) -> None:
    """AC 13 — a vault with zero outcome verbs skips the demo and still marks."""

    _skip_guard()

    result = _run_or_fail(CANONICAL_TRIGGER_PROMPT, no_verbs_vault, ALLOWED_FULL_FLOW)

    tool_calls = evalkit.ordered_tool_calls(result)

    # (a) No verb-backing operation should have been invoked.
    offenders = [
        tu.input.get("command")
        for tu in tool_calls
        if tu.name == "Bash" and _VERB_RE.search(tu.input.get("command", ""))
    ]
    assert not offenders, (
        f"AC 13: wizard invoked a verb operation against a no-verbs vault: {offenders!r}"
    )

    # (b) Positive evidence the demo step was skipped — no Read of
    # any operation skill's SKILL.md. Distinguishes the no-verbs
    # branch from a wizard that walked into the demo and bailed
    # before the verb invocation.
    demo_reads = [
        tu.input.get("file_path")
        for tu in tool_calls
        if tu.name == "Read" and _OP_SKILL_RE.search(tu.input.get("file_path", ""))
    ]
    assert not demo_reads, (
        f"AC 13: wizard Read an operation SKILL.md against a no-verbs vault: {demo_reads!r}"
    )

    marker = no_verbs_vault / ".wiki.bootstrap"
    assert marker.is_file(), (
        f"AC 13: marker not written even on the no-verbs degraded path; "
        f"stdout[:400]={evalkit.redact(result.stdout[:400])!r}"
    )


def test_demo_is_side_effect_free(personal_vault: Path) -> None:
    """AC 14 — the demo reads SKILL.md but never invokes a verb operation.

    Four assertions collected via an accumulator so first-failure-wins
    doesn't mask co-occurring regressions. A regression to live
    `wiki <verb>` invocation fails (b); a regression to journaling
    fails (c); a regression to writing under `outputs/` fails (d); a
    regression that skips SKILL.md entirely fails (a).
    """

    _skip_guard()

    prompt = (
        "I just made a new vault, help me get started. "
        "When you ask which verb to gloss, pick `digest` for me."
    )
    result = _run_or_fail(prompt, personal_vault, ALLOWED_FULL_FLOW)

    failures: list[str] = []
    tool_calls = evalkit.ordered_tool_calls(result)

    # (a) Positive evidence — at least one Read of an *operation*
    # SKILL.md. A bare ``/skills/`` substring would also match a
    # Read of the wizard's own SKILL.md (guaranteed on every run),
    # which would let a demo-skipped wizard pass the positive
    # check. Match only the three shipped operation skills.
    if not any(
        tu.name == "Read" and _OP_SKILL_RE.search(tu.input.get("file_path", ""))
        for tu in tool_calls
    ):
        failures.append("no Read of skills/<operation-skill>/SKILL.md")

    # (b) Negative evidence — no wiki <verb> in any sugared/un-sugared form.
    for tu in tool_calls:
        if tu.name == "Bash" and _VERB_RE.search(tu.input.get("command", "")):
            failures.append(f"wiki <verb> invoked: {tu.input['command']!r}")

    # (c) No OperationRunEvent appended to the journal.
    journal_path = personal_vault / ".wiki.journal" / "journal.jsonl"
    for raw in journal_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if row.get("type") == "operation.run":
            failures.append("OperationRunEvent appeared in journal")
            break

    # (d) outputs/ absent or empty.
    outputs = personal_vault / "outputs"
    if outputs.is_dir() and any(outputs.iterdir()):
        failures.append("outputs/ has contents")

    assert not failures, "demo regressions: " + "; ".join(failures)


def test_malformed_marker_is_treated_as_present(personal_vault: Path) -> None:
    """AC 15 — a readable but non-ISO marker still short-circuits the wizard."""

    _skip_guard()

    marker = personal_vault / ".wiki.bootstrap"
    marker.write_text("garbage not iso\n", encoding="utf-8")
    pre_bytes = marker.read_bytes()

    result = _run_or_fail(CANONICAL_TRIGGER_PROMPT, personal_vault, ALLOWED_NO_OP)

    # (a) Short-circuit: the response stays under the bound.
    response_lines = evalkit.count_non_blank_lines(evalkit.final_assistant_text(result))
    assert response_lines <= 6, (
        f"AC 15: malformed marker should short-circuit; got {response_lines} non-blank lines"
    )

    # (b) Wizard never called `wiki outcomes` — the demo branch is gated off.
    tool_calls = evalkit.ordered_tool_calls(result)
    for tu in tool_calls:
        if tu.name == "Bash":
            command = tu.input.get("command", "")
            assert "wiki outcomes" not in command, (
                f"AC 15: wizard called `wiki outcomes` on the short-circuit path: {command!r}"
            )

    # (c) Marker byte-stable.
    assert marker.read_bytes() == pre_bytes, (
        "AC 15: malformed marker was rewritten; spec §Edge cases forbids re-bootstrap"
    )


@pytest.mark.skipif(sys.platform == "win32", reason="chmod 000 not meaningful on Windows")
def test_unreadable_marker_triggers_full_wizard_and_replacement(
    personal_vault: Path,
) -> None:
    """AC 16 — a mode-0o000 marker is treated as absent and replaced."""

    _skip_guard()

    marker = personal_vault / ".wiki.bootstrap"
    marker.write_text("stale\n", encoding="utf-8")
    os.chmod(marker, 0o000)
    try:
        result = _run_or_fail(CANONICAL_TRIGGER_PROMPT, personal_vault, ALLOWED_FULL_FLOW)
    finally:
        # Restore permissions so the tmp_path cleanup can unlink the
        # file even if the assertions below fail.
        if marker.exists():
            try:
                os.chmod(marker, 0o600)
            except PermissionError:
                pass

    # (a) The full wizard ran — response well above the short-circuit bound.
    response_lines = evalkit.count_non_blank_lines(evalkit.final_assistant_text(result))
    assert response_lines > 6, (
        f"AC 16: unreadable marker should trigger full wizard; got only {response_lines} lines"
    )

    # (b) New marker is owned by the running user.
    st = marker.stat()
    assert st.st_uid == os.getuid(), (
        f"AC 16: replacement marker owned by uid={st.st_uid}, expected {os.getuid()}"
    )

    # (c) New marker is at-least user-readable. umask-independent.
    assert st.st_mode & stat.S_IRUSR, (
        f"AC 16: replacement marker not user-readable; mode={oct(st.st_mode)!r}"
    )

    # (d) New marker contains a parseable ISO-8601 timestamp.
    contents = marker.read_text(encoding="utf-8")
    lines = [line for line in contents.splitlines() if line.strip()]
    assert len(lines) == 1, (
        f"AC 16: replacement marker should be one line, got {len(lines)}: {contents!r}"
    )
    _assert_iso8601_utc(lines[0])
