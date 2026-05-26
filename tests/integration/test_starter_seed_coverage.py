"""Integration tests for ``starters/check_coverage.py`` against the live tree.

Spec: ``docs/specs/starter-seed-coverage/spec.md``.
Plan: ``docs/specs/starter-seed-coverage/plan.md``.

Covers AC1 (baseline-clean claim) and AC7 (read-only invariant against
the live repo). Fixture-driven ACs live in
``tests/unit/test_starter_seed_coverage.py``; the AC8 AST scan lives in
``tests/unit/test_starter_seed_coverage_boundary.py``.

The AC1 test is the load-bearing CI gate: a new content-type or
ontology primitive lands without a seed page and this test goes red.
The mechanism (pytest assertion vs. a goal-based workflow step running
``python starters/check_coverage.py``) is interchangeable — see plan
§Steps step 6.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _import_check_coverage() -> types.ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from starters import check_coverage

    return check_coverage


# ---------------------------------------------------------------------------
# AC1 — baseline-clean claim
# ---------------------------------------------------------------------------


def test_starter_seed_coverage_clean_against_live_tree() -> None:
    """The shipped starters cover every content-type and ontology in
    their recipes' closures.

    When a future PR adds a new content-type or ontology to ``family``
    or ``work-os`` without a matching seed page, this test goes red.
    The fix is to author the seed page in the same PR; see spec
    §"What the maintainer does when the check fires."
    """

    cc = _import_check_coverage()
    # Use `_walk_coverage` so the assertion message (which is built
    # lazily only when the assertion fires) gets the same counts
    # render_report needs. A previous version of this test called
    # render_report(findings, REPO_ROOT) which would TypeError the
    # moment AC1 turns red, masking the actual coverage regression.
    findings, scored, starters = cc._walk_coverage(REPO_ROOT)
    assert findings == [], (
        "Starter seed coverage is not clean against the live tree.\n"
        + cc.render_report(findings, scored, starters)
    )


# ---------------------------------------------------------------------------
# AC7 — read-only invariant against the live tree
# ---------------------------------------------------------------------------


def _fingerprint_paths() -> list[Path]:
    """The four directory roots the check reads from."""

    return [
        REPO_ROOT / "starters",
        REPO_ROOT / "recipes",
        REPO_ROOT / "templates",
        REPO_ROOT / "core",
    ]


def _fingerprint() -> set[tuple[str, int, int]]:
    """Return ``{(rel-posix-path, size, mtime_ns)}`` across the four roots.

    Spans size and mtime_ns so an edit that preserved size while
    changing content still surfaces (mtime would shift) and an edit
    that preserved mtime while changing size still surfaces (filesystem
    truncate-write under a frozen clock).

    ``__pycache__/`` directories and ``.pyc`` files are Python-
    interpreter artifacts, not files the kit writes — they appear and
    update whenever any test imports ``starters.regenerate`` (or any
    other module under one of the fingerprinted roots). The AC7
    invariant the spec protects is *the kit does not write to its own
    tree*, not *the interpreter never updates its caches*; filter
    them out so the test does not depend on which test ran first.
    """

    out: set[tuple[str, int, int]] = set()
    for root in _fingerprint_paths():
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts or p.suffix == ".pyc":
                continue
            stat = p.stat()
            out.add((str(p.relative_to(REPO_ROOT).as_posix()), stat.st_size, stat.st_mtime_ns))
    return out


def test_check_is_read_only_against_live_tree() -> None:
    cc = _import_check_coverage()
    before = _fingerprint()
    # Run both the callable and the CLI-shaped main; either should
    # have zero side effects on the kit tree.
    cc.check_coverage(REPO_ROOT)
    cc.main([], kit_root=REPO_ROOT)
    after = _fingerprint()
    assert before == after, "check_coverage / main wrote to the live kit tree"
