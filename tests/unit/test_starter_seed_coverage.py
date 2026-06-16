"""Unit tests for ``starters/check_coverage.py`` (plan steps 2-5).

Spec: ``docs/specs/starter-seed-coverage/spec.md``.
Plan: ``docs/specs/starter-seed-coverage/plan.md``.

Covers AC2-AC6, AC9, AC10 against fixture catalogs built under
``tmp_path``. AC1 / AC7 (live tree) live in the integration test;
AC8 (AST scan) lives in
``tests/unit/test_starter_seed_coverage_boundary.py``.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _import_check_coverage() -> types.ModuleType:
    """Lazy import — the script lives under ``starters/``, not on the wheel.

    The module has no mutable module-level state (``REPO_ROOT`` is a
    ``Path`` computed once from ``__file__`` and never reassigned), so
    the standard ``sys.modules``-cached import is correct.
    """

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from starters import check_coverage

    return check_coverage


# ---------------------------------------------------------------------------
# Fixture builder (plan §Steps step 3)
# ---------------------------------------------------------------------------


def _build_fixture_kit(
    tmp_path: Path,
    *,
    recipe_primitives: list[dict[str, Any]],
    seed_pages: list[tuple[str, str]],
    recipe_yaml_override: str | None = None,
    omit_starter_dir: bool = False,
    recipe_name: str = "family",
) -> Path:
    """Assemble a minimal kit tree under ``tmp_path``.

    ``recipe_primitives`` is a list of ``{"name", "kind", "requires"}``
    dicts. The builder writes a ``primitive.yaml`` for each plus a
    ``primitive.yaml`` for ``core`` (kind: ``infrastructure``).

    ``seed_pages`` is a list of ``(relative-path-under-wiki, content)``
    tuples. Each entry produces ``starters/_seed/<recipe>/wiki/<rel>``.

    ``recipe_yaml_override`` — when set, written as
    ``recipes/<recipe>.yaml`` instead of synthesizing one from
    ``recipe_primitives``. Used by the loader-raise fixture.

    ``omit_starter_dir`` — when ``True``, skips creating
    ``<tmp>/starters/<recipe>/``. Used by the missing-committed-starter
    fixture.

    ``recipe_name`` — must equal one of RECIPE_TARGETS' starter keys
    (``family`` or ``work-os``) so ``_starter_recipe_names`` accepts it.
    """

    if recipe_name not in {"family", "work-os"}:
        raise ValueError(
            f"recipe_name must be 'family' or 'work-os' (in RECIPE_TARGETS); got {recipe_name!r}"
        )

    # Catalog under templates/ + core/. ``exist_ok=True`` on every mkdir
    # so the builder can be called twice (e.g. once per recipe to populate
    # both family and work-os under the same ``tmp_path``).
    core_dir = tmp_path / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    (core_dir / "primitive.yaml").write_text(
        "name: core\nkind: infrastructure\nversion: 0.1.0\ndescription: core.\n",
        encoding="utf-8",
    )

    for entry in recipe_primitives:
        kind = entry["kind"]
        name = entry["name"]
        requires = entry.get("requires", [])
        kind_dir_map = {
            "ontology": "ontologies",
            "content-type": "content-types",
            "operation": "operations",
            "infrastructure": "infrastructure",
            "agent": "agents",
        }
        prim_dir = tmp_path / "templates" / kind_dir_map[kind] / name
        prim_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "name": name,
            "kind": kind,
            "version": "0.1.0",
            "description": f"fixture primitive {name}.",
        }
        if requires:
            manifest["requires"] = requires
        (prim_dir / "primitive.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")

    # Recipe
    recipes_dir = tmp_path / "recipes"
    recipes_dir.mkdir(parents=True, exist_ok=True)
    if recipe_yaml_override is not None:
        (recipes_dir / f"{recipe_name}.yaml").write_text(recipe_yaml_override, encoding="utf-8")
    else:
        recipe_yaml = {
            "name": recipe_name,
            "version": "0.1.0",
            "description": "fixture recipe.",
            "primitives": sorted(p["name"] for p in recipe_primitives),
            "variables": {"recipe_name": recipe_name},
        }
        (recipes_dir / f"{recipe_name}.yaml").write_text(
            yaml.safe_dump(recipe_yaml), encoding="utf-8"
        )

    # Committed starter dir (empty — we don't render, we just need the dir
    # for the "does committed starter exist?" gate).
    if not omit_starter_dir:
        (tmp_path / "starters" / recipe_name).mkdir(parents=True)

    # Seed pages
    seed_root = tmp_path / "starters" / "_seed" / recipe_name / "wiki"
    seed_root.mkdir(parents=True, exist_ok=True)
    for rel, content in seed_pages:
        seed_path = seed_root / rel
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        seed_path.write_text(content, encoding="utf-8")

    return tmp_path


def _frontmatter_page(type_value: str, body: str = "Fixture body.\n") -> str:
    """Build a minimal valid markdown page with ``type: <value>`` frontmatter."""

    return f"---\ntype: {type_value}\n---\n\n# Fixture\n\n{body}"


# ---------------------------------------------------------------------------
# AC5 — frontmatter reader handles every malformed shape gracefully
# ---------------------------------------------------------------------------


@pytest.fixture
def cc() -> types.ModuleType:
    return _import_check_coverage()


def test_frontmatter_reader_happy_path_returns_type(tmp_path: Path, cc: types.ModuleType) -> None:
    page = tmp_path / "p.md"
    page.write_text(_frontmatter_page("meeting"), encoding="utf-8")
    assert cc._read_frontmatter_type(page) == "meeting"


def test_frontmatter_reader_unterminated_returns_none(tmp_path: Path, cc: types.ModuleType) -> None:
    page = tmp_path / "p.md"
    page.write_text("---\ntype: meeting\n# never closes\n", encoding="utf-8")
    assert cc._read_frontmatter_type(page) is None


def test_frontmatter_reader_invalid_yaml_returns_none(tmp_path: Path, cc: types.ModuleType) -> None:
    page = tmp_path / "p.md"
    # `: : :` is a YAML mapping with no valid key/value.
    page.write_text("---\ntype: : :\n: : :\n---\nbody\n", encoding="utf-8")
    assert cc._read_frontmatter_type(page) is None


def test_frontmatter_reader_no_type_key_returns_none(tmp_path: Path, cc: types.ModuleType) -> None:
    page = tmp_path / "p.md"
    page.write_text("---\nstatus: active\ntags: [household]\n---\nbody\n", encoding="utf-8")
    assert cc._read_frontmatter_type(page) is None


def test_frontmatter_reader_non_string_type_returns_none(
    tmp_path: Path, cc: types.ModuleType
) -> None:
    page = tmp_path / "p.md"
    page.write_text("---\ntype: [a, b]\n---\nbody\n", encoding="utf-8")
    assert cc._read_frontmatter_type(page) is None


def test_frontmatter_reader_no_frontmatter_block_returns_none(
    tmp_path: Path, cc: types.ModuleType
) -> None:
    page = tmp_path / "p.md"
    page.write_text("# Just a markdown page\n\nNo frontmatter here.\n", encoding="utf-8")
    assert cc._read_frontmatter_type(page) is None


def test_frontmatter_reader_unreadable_file_returns_none(
    tmp_path: Path, cc: types.ModuleType
) -> None:
    missing = tmp_path / "does-not-exist.md"
    assert cc._read_frontmatter_type(missing) is None


def test_frontmatter_reader_strips_bom(tmp_path: Path, cc: types.ModuleType) -> None:
    """Seed pages saved with a UTF-8 BOM still parse — silent BOM-induced
    coverage misses would be invisible from the report."""

    page = tmp_path / "p.md"
    page.write_bytes(b"\xef\xbb\xbf---\ntype: meeting\n---\n\nbody\n")
    assert cc._read_frontmatter_type(page) == "meeting"


def test_frontmatter_reader_normalizes_crlf(tmp_path: Path, cc: types.ModuleType) -> None:
    """CRLF line endings (Windows-authored seed pages) parse the same as LF."""

    page = tmp_path / "p.md"
    page.write_bytes(b"---\r\ntype: meeting\r\n---\r\n\r\nbody\r\n")
    assert cc._read_frontmatter_type(page) == "meeting"


def test_malformed_seed_page_does_not_crash_check_coverage(
    tmp_path: Path, cc: types.ModuleType
) -> None:
    """AC5 end-to-end: a malformed seed page does not crash
    ``check_coverage`` and contributes nothing toward any primitive.

    Two scenarios:

    * the malformed page sits alongside a valid covering page → the
      finding *does not* fire (the valid page still covers);
    * the malformed page is the only candidate for a content-type →
      the finding *does* fire (because the malformed page contributes
      nothing, the primitive is uncovered).
    """

    # Scenario 1: malformed + valid → covered.
    kit_root_a = _build_fixture_kit(
        tmp_path / "with-valid",
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "meeting", "kind": "content-type", "requires": ["people"]},
        ],
        seed_pages=[
            ("people/alice.md", _frontmatter_page("person")),
            ("meetings/good.md", _frontmatter_page("meeting")),
            # Unterminated frontmatter — must be ignored, not crash.
            ("meetings/broken.md", "---\ntype: meeting\nno-close-here\n"),
        ],
    )
    assert cc.check_coverage(kit_root_a) == []

    # Scenario 2: malformed is the only `type: meeting` candidate → finding.
    kit_root_b = _build_fixture_kit(
        tmp_path / "only-broken",
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "meeting", "kind": "content-type", "requires": ["people"]},
        ],
        seed_pages=[
            ("people/alice.md", _frontmatter_page("person")),
            ("meetings/broken.md", "---\ntype: meeting\nno-close-here\n"),
        ],
    )
    findings_b = cc.check_coverage(kit_root_b)
    assert len(findings_b) == 1
    assert findings_b[0].primitive == "meeting"


# ---------------------------------------------------------------------------
# AC2 / AC4 — content-type coverage round-trip
# ---------------------------------------------------------------------------


def test_content_type_uncovered_emits_finding(tmp_path: Path, cc: types.ModuleType) -> None:
    """AC2 / AC4 shape: content-type installed but no seed page carries
    ``type: <name>``."""

    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "meeting", "kind": "content-type", "requires": ["people"]},
        ],
        seed_pages=[
            # People ontology folder has a person page (covers people),
            # but no `type: meeting` page anywhere.
            ("people/alice.md", _frontmatter_page("person")),
        ],
    )
    findings = cc.check_coverage(kit_root)
    assert len(findings) == 1
    assert findings[0].recipe == "family"
    assert findings[0].primitive == "meeting"
    assert findings[0].kind == "content-type"


def test_content_type_covered_emits_no_finding(tmp_path: Path, cc: types.ModuleType) -> None:
    """Inverse of AC2: adding a matching seed page makes the finding go away."""

    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "meeting", "kind": "content-type", "requires": ["people"]},
        ],
        seed_pages=[
            ("people/alice.md", _frontmatter_page("person")),
            ("meetings/2026-04-02.md", _frontmatter_page("meeting")),
        ],
    )
    findings = cc.check_coverage(kit_root)
    assert findings == []


# ---------------------------------------------------------------------------
# AC3 — ontology folder coverage
# ---------------------------------------------------------------------------


def test_ontology_folder_missing_emits_finding(tmp_path: Path, cc: types.ModuleType) -> None:
    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "trips", "kind": "ontology", "requires": []},
        ],
        seed_pages=[
            ("people/alice.md", _frontmatter_page("person")),
            # No trips/ folder.
        ],
    )
    findings = cc.check_coverage(kit_root)
    assert len(findings) == 1
    assert findings[0].primitive == "trips"
    assert findings[0].kind == "ontology"


def test_ontology_folder_empty_emits_finding(tmp_path: Path, cc: types.ModuleType) -> None:
    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "trips", "kind": "ontology", "requires": []},
        ],
        seed_pages=[],
    )
    # Create the folder but leave it empty.
    (kit_root / "starters" / "_seed" / "family" / "wiki" / "trips").mkdir(parents=True)
    findings = cc.check_coverage(kit_root)
    assert len(findings) == 1
    assert findings[0].primitive == "trips"


def test_ontology_folder_with_md_emits_no_finding(tmp_path: Path, cc: types.ModuleType) -> None:
    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "trips", "kind": "ontology", "requires": []},
        ],
        seed_pages=[
            # No frontmatter — ontology coverage only checks folder presence.
            ("trips/2026-06-portland.md", "# A trip\n"),
        ],
    )
    findings = cc.check_coverage(kit_root)
    assert findings == []


# ---------------------------------------------------------------------------
# AC6 — operation/agent/infrastructure primitives never in findings
# ---------------------------------------------------------------------------


def test_skipped_kinds_never_in_findings(tmp_path: Path, cc: types.ModuleType) -> None:
    """An installed operation, agent, and infrastructure primitive — all
    unseeded — must never appear in the findings list."""

    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "meeting", "kind": "content-type", "requires": ["people"]},
            {"name": "weekly-digest", "kind": "operation", "requires": ["meeting"]},
            {"name": "household-manager", "kind": "agent", "requires": []},
            # The default ``core`` primitive is already infrastructure-kind;
            # _build_fixture_kit writes it.
        ],
        seed_pages=[
            ("people/alice.md", _frontmatter_page("person")),
            ("meetings/m.md", _frontmatter_page("meeting")),
        ],
    )
    findings = cc.check_coverage(kit_root)
    assert findings == []
    # And specifically, none of the skipped-kind names show up even after
    # we delete the covering seed pages — they're skipped categorically,
    # not because they happen to be covered.
    for name in ["weekly-digest", "household-manager", "core"]:
        assert all(f.primitive != name for f in findings), (
            f"primitive {name} (skipped kind) should never appear in findings"
        )


# ---------------------------------------------------------------------------
# Step 4 edge cases — missing seed dir / missing committed starter
# ---------------------------------------------------------------------------


def test_missing_seed_dir_reports_every_scored_primitive(
    tmp_path: Path, cc: types.ModuleType
) -> None:
    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "trips", "kind": "ontology", "requires": []},
            {"name": "meeting", "kind": "content-type", "requires": ["people"]},
        ],
        seed_pages=[],
    )
    # Drop the seed directory entirely.
    import shutil

    shutil.rmtree(kit_root / "starters" / "_seed" / "family")
    findings = cc.check_coverage(kit_root)
    names = sorted(f.primitive for f in findings)
    assert names == ["meeting", "people", "trips"]


def test_missing_committed_starter_dir_skips_with_note(
    tmp_path: Path, cc: types.ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """The committed-starter-absent edge case (spec §"Error cases" 3):
    skipped with a stderr note, ``findings == []``, exit 0.

    Pins the *family* recipe's skip-note specifically (not "family
    appears somewhere on stderr"). Every fixture run also emits a
    work-os skip-note because the fixture only builds family — the
    assertion has to be tight enough that a regression dropping the
    recipe name from the message surfaces."""

    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
        ],
        seed_pages=[],
        omit_starter_dir=True,
    )
    findings = cc.check_coverage(kit_root)
    assert findings == []
    captured = capsys.readouterr()
    # The family-specific skip-note: name appears, anchored to the
    # `recipe ... in RECIPE_TARGETS but` shape so a future refactor
    # that drops the recipe name from the message trips this test.
    assert "recipe family in RECIPE_TARGETS but" in captured.err


# ---------------------------------------------------------------------------
# AC10 — determinism
# ---------------------------------------------------------------------------


def test_determinism_same_input_byte_equal_output(tmp_path: Path, cc: types.ModuleType) -> None:
    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "trips", "kind": "ontology", "requires": []},
            {"name": "meeting", "kind": "content-type", "requires": ["people"]},
        ],
        seed_pages=[
            # Intentionally leave both ontologies and meeting uncovered
            # so we exercise the report-rendering path, not just clean.
        ],
    )
    findings_a, scored_a, starters_a = cc._walk_coverage(kit_root)
    findings_b, scored_b, starters_b = cc._walk_coverage(kit_root)
    assert findings_a == findings_b
    assert (scored_a, starters_a) == (scored_b, starters_b)
    report_a = cc.render_report(findings_a, scored_a, starters_a)
    report_b = cc.render_report(findings_b, scored_b, starters_b)
    assert report_a == report_b


# ---------------------------------------------------------------------------
# Report rendering shape (clean and findings cases)
# ---------------------------------------------------------------------------


def test_clean_run_prints_single_line_summary(
    tmp_path: Path, cc: types.ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "meeting", "kind": "content-type", "requires": ["people"]},
        ],
        seed_pages=[
            ("people/alice.md", _frontmatter_page("person")),
            ("meetings/m.md", _frontmatter_page("meeting")),
        ],
    )
    rc = cc.main([], kit_root=kit_root)
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("coverage clean —")
    assert "2 primitive(s)" in out
    assert "1 starter(s)" in out


def test_findings_render_grouped_by_recipe_alphabetically(
    tmp_path: Path, cc: types.ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """Within-recipe primitives sort alphabetically (meeting < trips)."""

    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "trips", "kind": "ontology", "requires": []},
            {"name": "meeting", "kind": "content-type", "requires": ["people"]},
        ],
        seed_pages=[
            ("people/alice.md", _frontmatter_page("person")),
            # meeting and trips both uncovered.
        ],
    )
    rc = cc.main([], kit_root=kit_root)
    assert rc == 1
    out = capsys.readouterr().out
    # Family block exists, both uncovered primitives are listed, and they
    # appear in alphabetical order (meeting < trips).
    assert "=== family ===" in out
    meeting_pos = out.find("meeting")
    trips_pos = out.find("trips")
    assert meeting_pos != -1 and trips_pos != -1
    assert meeting_pos < trips_pos, "primitives within a recipe should sort alphabetically"


def test_findings_render_recipes_sorted_alphabetically_across(
    tmp_path: Path, cc: types.ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """Across-recipe sort: ``=== family ===`` block appears before
    ``=== work-os ===`` because ``family`` < ``work-os`` alphabetically.

    Spec AC3 names "recipes outer-sorted alphabetically" — this test
    pins the cross-recipe ordering that the within-recipe test above
    cannot exercise."""

    # Build a kit with both family and work-os, each with an uncovered
    # ontology so both recipes produce a finding block.
    _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
        ],
        seed_pages=[],
        recipe_name="family",
    )
    _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "customers", "kind": "ontology", "requires": []},
        ],
        seed_pages=[],
        recipe_name="work-os",
    )
    rc = cc.main([], kit_root=tmp_path)
    assert rc == 1
    out = capsys.readouterr().out
    family_pos = out.find("=== family ===")
    work_os_pos = out.find("=== work-os ===")
    assert family_pos != -1, "family block missing"
    assert work_os_pos != -1, "work-os block missing"
    assert family_pos < work_os_pos, "family must sort before work-os in the report"


# ---------------------------------------------------------------------------
# AC9 — exit codes via in-process main()
# ---------------------------------------------------------------------------


def test_main_exit_code_zero_on_clean_fixture(tmp_path: Path, cc: types.ModuleType) -> None:
    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
        ],
        seed_pages=[
            ("people/alice.md", _frontmatter_page("person")),
        ],
    )
    assert cc.main([], kit_root=kit_root) == 0


def test_main_exit_code_one_on_finding(tmp_path: Path, cc: types.ModuleType) -> None:
    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
        ],
        seed_pages=[],  # people ontology has no seed folder → finding.
    )
    assert cc.main([], kit_root=kit_root) == 1


def test_main_exit_code_two_on_loader_raise(
    tmp_path: Path, cc: types.ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC9 loader-raise case: bind on integer return value only, not on
    a specific error class. Structurally malformed YAML (the recipe's
    ``primitives:`` field is a string, not a list) makes the kit's
    recipe loader raise ``ValidationError`` — a ``WikiError`` subclass.

    Also asserts the fixture's path appears in stderr — this catches
    the R2 risk the plan names (a regression that ignores ``kit_root``
    and walks the real repo would emit the *real* path, not the
    fixture's tmp_path)."""

    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
        ],
        seed_pages=[],
        recipe_yaml_override=(
            # Recipe.primitives must be list[str]; a bare string violates
            # the Pydantic schema. The loader raises; the exact class is
            # not pinned by this test.
            "name: family\nversion: 0.1.0\ndescription: bad.\nprimitives: not-a-list\n"
        ),
    )
    assert cc.main([], kit_root=kit_root) == 2
    err = capsys.readouterr().err
    # Pin: the error message must reference the fixture's path (not the
    # real repo). A kwarg-ignored regression where `kit_root` is silently
    # discarded would emit a path under the real REPO_ROOT instead.
    assert str(kit_root) in err, (
        f"stderr should reference fixture path {kit_root}; "
        f"a `main(kit_root=…)` kwarg-ignored regression would print the "
        f"real repo path instead. Got: {err!r}"
    )


# ---------------------------------------------------------------------------
# Read-only invariant spot-check (also part of AC7; integration test
# repeats this against the live tree)
# ---------------------------------------------------------------------------


def _fingerprint(root: Path) -> set[tuple[str, int]]:
    """Return ``{(rel-posix-path, mtime_ns)}`` for every file under ``root``."""

    out: set[tuple[str, int]] = set()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            stat = p.stat()
            out.add((str(p.relative_to(root).as_posix()), stat.st_mtime_ns))
    return out


def test_check_is_read_only_against_fixture(tmp_path: Path, cc: types.ModuleType) -> None:
    kit_root = _build_fixture_kit(
        tmp_path,
        recipe_primitives=[
            {"name": "people", "kind": "ontology", "requires": []},
            {"name": "meeting", "kind": "content-type", "requires": ["people"]},
        ],
        seed_pages=[
            ("people/alice.md", _frontmatter_page("person")),
        ],
    )
    before = _fingerprint(kit_root)
    cc.check_coverage(kit_root)
    cc.check_coverage(kit_root)  # second call too
    cc.main([], kit_root=kit_root)
    after = _fingerprint(kit_root)
    assert before == after, "check_coverage / main wrote to the kit tree"


# ---------------------------------------------------------------------------
# Ontology seeded-folder resolution (RFC-0009 efforts/<type> nesting)
# ---------------------------------------------------------------------------


def test_ontology_seeded_wiki_dirs_resolves_container_nesting(cc: types.ModuleType) -> None:
    """A container registry seeds ``efforts/<type>/``, not ``wiki/<name>/``.

    Directed coverage for the RFC-0009 reshape: ``check_coverage`` must look
    where the ontology *actually* seeds (read from its ``files/wiki/`` tree),
    not assume name == folder. Exercised against the live catalog so a future
    re-home is caught here, not as an opaque live-tree coverage failure.
    """
    assert cc._ontology_seeded_wiki_dirs(REPO_ROOT, "trips") == ["efforts/trips"]
    assert cc._ontology_seeded_wiki_dirs(REPO_ROOT, "cases") == ["efforts/cases"]
    assert cc._ontology_seeded_wiki_dirs(REPO_ROOT, "projects") == ["efforts/projects"]
    # A plain role ontology still resolves to its own folder.
    assert cc._ontology_seeded_wiki_dirs(REPO_ROOT, "people") == ["people"]
    assert cc._ontology_seeded_wiki_dirs(REPO_ROOT, "efforts") == ["efforts"]


def test_ontology_seeded_wiki_dirs_falls_back_for_unknown_name(cc: types.ModuleType) -> None:
    """No source tree → fall back to ``[name]`` (no crash)."""
    assert cc._ontology_seeded_wiki_dirs(REPO_ROOT, "does-not-exist") == ["does-not-exist"]
