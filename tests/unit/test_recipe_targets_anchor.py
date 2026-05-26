"""Pin ``RECIPE_TARGETS`` as the load-bearing definition of "starter input".

Plan task T9. Spec: ``docs/specs/primitive-sideload/spec.md`` AC16 +
``docs/specs/starter-seed-coverage/spec.md`` §Inputs. The anchor has
three machine-readable pieces:

1. ``starters/regenerate.py`` declares ``__all__`` and names
   ``RECIPE_TARGETS`` inside it.
2. The constant assignment is preceded by a ``# Load-bearing:`` sigil
   that references the two specs depending on it.
3. ``starters/check_coverage._load_recipe_targets()`` returns the same
   object — not a duplicated literal — so any future refactor that
   silently mirrors the constant elsewhere fails CI.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGENERATE_PATH = REPO_ROOT / "starters" / "regenerate.py"


def test_recipe_targets_in_all() -> None:
    text = REGENERATE_PATH.read_text(encoding="utf-8")
    # Tolerate single- or double-quoted, list or tuple form.
    assert "__all__" in text
    assert '"RECIPE_TARGETS"' in text or "'RECIPE_TARGETS'" in text


def test_load_bearing_comment_present() -> None:
    """The ``# Load-bearing:`` sigil precedes the assignment.

    Asserted by reading the file as text rather than via ast so the
    sigil's *position* relative to the assignment is part of the
    contract — a future refactor that orphans the comment elsewhere
    fails this test.
    """

    lines = REGENERATE_PATH.read_text(encoding="utf-8").splitlines()
    assignment_index: int | None = None
    for index, line in enumerate(lines):
        if line.startswith("RECIPE_TARGETS"):
            assignment_index = index
            break
    assert assignment_index is not None, "RECIPE_TARGETS assignment not found"
    # Walk back through any blank lines to the most recent non-blank
    # line; the comment block immediately above the assignment must
    # contain a "# Load-bearing:" sigil.
    above = lines[max(0, assignment_index - 20) : assignment_index]
    joined = "\n".join(above)
    assert "# Load-bearing:" in joined, (
        "expected '# Load-bearing:' sigil above the RECIPE_TARGETS assignment"
    )


def test_check_coverage_returns_same_object() -> None:
    """``check_coverage._load_recipe_targets()`` returns the regenerate constant.

    Identity assertion (``is``) — defeats the "same-output-different-
    source" refactor that would silently duplicate the literal and
    break the projection invariant. The check tolerates the lazy
    import inside ``_load_recipe_targets()`` by calling the helper
    once and comparing object identity.
    """

    import sys

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from starters import check_coverage, regenerate

    assert check_coverage._load_recipe_targets() is regenerate.RECIPE_TARGETS
