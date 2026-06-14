"""T7: the enter-workspace contract doc pins the real ``_build_argv`` shape.

Spec AC-8: ``docs/`` documents the enter-workspace ``claude -p``
prompt-scoping contract; the documented argv must be byte-equal to the argv
``wiki run --exec`` actually builds today (via ``run.py::_build_argv``), so
the doc fails if the real argv drifts — not "the doc agrees with itself" —
and it adds no new flag.

The test rebuilds the argv from ``_build_argv`` with the exact placeholder
values the doc uses, renders it with ``shlex.join`` (the canonical shell
form), and asserts that line appears verbatim in the doc. A new flag,
reorder, or removal in ``_build_argv`` breaks this test.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from llm_wiki_kit.run import _build_argv

_DOC = (
    Path(__file__).resolve().parents[2] / "docs" / "guides" / "explanation" / "workspace-scoping.md"
)


def test_documented_argv_matches_build_argv() -> None:
    argv = _build_argv(
        claude_binary=Path("claude"),
        vault_root=Path("/vaults/my-wiki"),
        prompt="WORKSPACE_PROMPT",
        max_budget_usd=None,
        agent="personal-coordinator",
    )
    documented = shlex.join(argv)

    doc_text = _DOC.read_text(encoding="utf-8")
    assert documented in doc_text, (
        f"doc argv drifted from _build_argv; expected line:\n{documented}"
    )


def test_doc_adds_no_new_flag_beyond_run_exec() -> None:
    """The documented argv introduces no flag absent from the no-agent baseline.

    The enter-workspace contract reuses ADR-0009's flags plus ADR-0010's
    optional ``--agent``; it must not add a workspace-specific flag. Compare
    the with-agent argv against the no-agent baseline and assert the only
    difference is the ``--agent <name>`` pair.
    """

    baseline = _build_argv(
        claude_binary=Path("claude"),
        vault_root=Path("/vaults/my-wiki"),
        prompt="WORKSPACE_PROMPT",
        max_budget_usd=None,
        agent=None,
    )
    with_agent = _build_argv(
        claude_binary=Path("claude"),
        vault_root=Path("/vaults/my-wiki"),
        prompt="WORKSPACE_PROMPT",
        max_budget_usd=None,
        agent="personal-coordinator",
    )
    extra = [tok for tok in with_agent if tok not in baseline]
    assert extra == ["--agent", "personal-coordinator"]
