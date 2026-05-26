"""Integration tests for the merged-catalog sideload surface.

Spec: ``docs/specs/primitive-sideload/spec.md``. Plan tasks T1, T4, T5,
T8, T15, T16, T18.

Fixture strategy per spec §Acceptance criteria: tests monkeypatch
``primitives._discover_sideloaded_template_dirs`` to inject ``tmp_path``-
built fake packages with ``templates/<kind>/<name>/primitive.yaml``
trees. No ``pip install`` in the test loop — the loader reads from a
directory on disk after entry-point resolution, and the
monkeypatch lets each test vary the sideloaded set freely.
"""

from __future__ import annotations

import importlib.metadata
import textwrap
from pathlib import Path

import pytest

from llm_wiki_kit import primitives as primitives_module
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.install import (
    check_region_owner_uniqueness,
    validate_outcome_skill_fragments,
)
from llm_wiki_kit.primitives import discover_primitives

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_fake_package(
    root: Path,
    *,
    package_name: str,
    primitive_kind: str,
    primitive_name: str,
    primitive_yaml: str,
    extra_files: dict[str, str] | None = None,
) -> Path:
    """Build a fake sideload package on disk and return its templates path.

    Layout mirrors a real sideload package:
        <root>/<package_name>/templates/<kind>/<name>/primitive.yaml
    plus any extra files keyed by relative path under ``<name>/``.
    """

    package_root = root / package_name
    primitive_root = package_root / "templates" / primitive_kind / primitive_name
    primitive_root.mkdir(parents=True)
    (primitive_root / "primitive.yaml").write_text(primitive_yaml, encoding="utf-8")
    for relative, content in (extra_files or {}).items():
        target = primitive_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return package_root / "templates"


def _patch_sideload(monkeypatch: pytest.MonkeyPatch, triples: list[tuple[str, str, Path]]) -> None:
    """Inject ``triples`` as the result of the sideload-discovery helper."""

    monkeypatch.setattr(
        primitives_module,
        "_discover_sideloaded_template_dirs",
        lambda: list(triples),
    )


# ---------------------------------------------------------------------------
# AC1 / AC2 — no-sideload byte-equivalence + one-package merge
# ---------------------------------------------------------------------------


def test_no_sideload_discover_returns_bundled_only() -> None:
    """AC1: no entry points → loader output is the bundled catalog only."""

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    primitives = discover_primitives(kit_templates)
    assert primitives, "kit should have at least one bundled primitive"
    assert all(p.source == "bundled" for p in primitives)


def test_discover_merges_one_sideload_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: one fixture package contributes one content-type to the merge."""

    yaml_text = textwrap.dedent("""
        name: sample-foo
        kind: content-type
        version: 0.1.0
        description: Sample content-type from a fixture sideload package.
    """).lstrip()
    templates_path = _make_fake_package(
        tmp_path,
        package_name="fake-pkg",
        primitive_kind="content-types",
        primitive_name="sample-foo",
        primitive_yaml=yaml_text,
    )
    _patch_sideload(monkeypatch, [("fake-pkg", "1.2.3", templates_path)])

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    primitives = discover_primitives(kit_templates)
    sideloaded = [p for p in primitives if p.source != "bundled"]
    assert len(sideloaded) == 1
    assert sideloaded[0].name == "sample-foo"
    assert sideloaded[0].source == "sideload:fake-pkg"


# ---------------------------------------------------------------------------
# AC3 / AC4 — name-collision policies
# ---------------------------------------------------------------------------


def test_name_collision_bundled_vs_sideload_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: sideload providing a bundled name (`recipe`) raises with both names."""

    yaml_text = textwrap.dedent("""
        name: recipe
        kind: content-type
        version: 0.1.0
        description: Conflicts with bundled primitive name.
    """).lstrip()
    templates_path = _make_fake_package(
        tmp_path,
        package_name="evil-pkg",
        primitive_kind="content-types",
        primitive_name="recipe",
        primitive_yaml=yaml_text,
    )
    _patch_sideload(monkeypatch, [("evil-pkg", "0.1.0", templates_path)])

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    # The bundled catalog includes `recipe`; verify the collision fires.
    # If the bundled catalog ever drops `recipe`, this test will need to
    # pick a different bundled name — leaving the assertion abstract so
    # the failure mode is clear.
    with pytest.raises(WikiError) as exc_info:
        discover_primitives(kit_templates)
    message = str(exc_info.value)
    assert "evil-pkg" in message
    assert "recipe" in message


def test_name_collision_two_sideloads_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: two sideload packages providing the same name raise naming both."""

    yaml_text = textwrap.dedent("""
        name: dnd-session-notes
        kind: content-type
        version: 0.1.0
        description: Sideload primitive.
    """).lstrip()
    pkg_a = _make_fake_package(
        tmp_path / "a",
        package_name="pkg-one",
        primitive_kind="content-types",
        primitive_name="dnd-session-notes",
        primitive_yaml=yaml_text,
    )
    pkg_b = _make_fake_package(
        tmp_path / "b",
        package_name="pkg-two",
        primitive_kind="content-types",
        primitive_name="dnd-session-notes",
        primitive_yaml=yaml_text,
    )
    _patch_sideload(
        monkeypatch,
        [("pkg-one", "0.1.0", pkg_a), ("pkg-two", "0.1.0", pkg_b)],
    )

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    with pytest.raises(WikiError) as exc_info:
        discover_primitives(kit_templates)
    message = str(exc_info.value)
    assert "pkg-one" in message and "pkg-two" in message


# ---------------------------------------------------------------------------
# AC5 — outcome-verb collision across merged catalog
# ---------------------------------------------------------------------------


def test_outcome_verb_collision_across_catalog_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: sideload op declaring a bundled verb (`digest`) raises."""

    primitive_yaml = textwrap.dedent("""
        name: rival-digest
        kind: operation
        version: 0.1.0
        description: Rival operation that claims a bundled verb.
    """).lstrip()
    contract_yaml = textwrap.dedent("""
        name: rival-digest
        description: Rival.
        skill: rival-digest
        outcomes:
          - digest
    """).lstrip()
    skill_md = textwrap.dedent("""\
        ---
        description: digest the week
        ---
        Body.
    """)
    templates_path = _make_fake_package(
        tmp_path,
        package_name="rival-pkg",
        primitive_kind="operations",
        primitive_name="rival-digest",
        primitive_yaml=primitive_yaml,
        extra_files={
            "contract.yaml": contract_yaml,
            "files/skills/rival-digest/SKILL.md": skill_md,
        },
    )
    _patch_sideload(monkeypatch, [("rival-pkg", "0.1.0", templates_path)])

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    with pytest.raises(WikiError) as exc_info:
        discover_primitives(kit_templates)
    assert "digest" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC10 — SKILL-directory path collision
# ---------------------------------------------------------------------------


def test_skill_path_collision_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC10: sideload shipping the same `files/skills/<name>/` raises."""

    # Pick a SKILL directory the bundled catalog ships. weekly-digest
    # operation ships files/skills/weekly-digest/. A sideload that
    # also ships files/skills/weekly-digest/ collides.
    primitive_yaml = textwrap.dedent("""
        name: shadow-skill
        kind: operation
        version: 0.1.0
        description: Ships a SKILL directory that collides with bundled.
    """).lstrip()
    contract_yaml = textwrap.dedent("""
        name: shadow-skill
        description: Shadow.
        skill: weekly-digest
        outcomes: []
    """).lstrip()
    templates_path = _make_fake_package(
        tmp_path,
        package_name="shadow-pkg",
        primitive_kind="operations",
        primitive_name="shadow-skill",
        primitive_yaml=primitive_yaml,
        extra_files={
            "contract.yaml": contract_yaml,
            "files/skills/weekly-digest/SKILL.md": "---\ndescription: x\n---\n",
        },
    )
    _patch_sideload(monkeypatch, [("shadow-pkg", "0.1.0", templates_path)])

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    with pytest.raises(WikiError) as exc_info:
        discover_primitives(kit_templates)
    assert "files/skills/weekly-digest" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC9 — region collision (install pipeline)
# ---------------------------------------------------------------------------


def test_region_collision_via_install_pipeline_raises(tmp_path: Path) -> None:
    """AC9: a bundled and sideload primitive sharing a region raises in install."""

    from llm_wiki_kit.models import Primitive, PrimitiveKind

    bundled = Primitive.model_validate(
        {
            "name": "bundled-contrib",
            "kind": PrimitiveKind.CONTENT_TYPE.value,
            "version": "0.1.0",
            "description": "Bundled contributor to a region.",
            "contributes_to": [{"file": "frontmatter.schema.yaml", "region": "types"}],
        }
    )
    bundled.source = "bundled"
    sideload = Primitive.from_sideload(
        {
            "name": "sideload-contrib",
            "kind": PrimitiveKind.CONTENT_TYPE.value,
            "version": "0.1.0",
            "description": "Sideload contributor to the same region.",
            "contributes_to": [{"file": "frontmatter.schema.yaml", "region": "types"}],
        },
        source="sideload:rival",
    )

    with pytest.raises(WikiError) as exc_info:
        check_region_owner_uniqueness([bundled, sideload])
    message = str(exc_info.value)
    assert "rival" in message
    assert "frontmatter.schema.yaml" in message


def test_region_collision_order_independent(tmp_path: Path) -> None:
    """Region collision fires regardless of caller iteration order.

    Regression test for the single-pass walk that silently accepted a
    bundled-vs-sideload collision when the sideload primitive's name
    sorted ahead of the bundled contributor's name (raised by adversarial
    review). The two-pass implementation must catch the collision both
    ways.
    """

    from llm_wiki_kit.models import Primitive, PrimitiveKind

    # ``aa-`` sorts before ``zz-`` alphabetically.
    sideload = Primitive.from_sideload(
        {
            "name": "aa-sideload",
            "kind": PrimitiveKind.CONTENT_TYPE.value,
            "version": "0.1.0",
            "description": "Sideload contributor whose name sorts first.",
            "contributes_to": [{"file": "frontmatter.schema.yaml", "region": "types"}],
        },
        source="sideload:order-pkg",
    )
    bundled = Primitive.model_validate(
        {
            "name": "zz-bundled",
            "kind": PrimitiveKind.CONTENT_TYPE.value,
            "version": "0.1.0",
            "description": "Bundled contributor whose name sorts last.",
            "contributes_to": [{"file": "frontmatter.schema.yaml", "region": "types"}],
        }
    )
    bundled.source = "bundled"

    # Sideload-first order: would silently pass under the single-pass walk.
    with pytest.raises(WikiError):
        check_region_owner_uniqueness([sideload, bundled])
    # Bundled-first order: also raises.
    with pytest.raises(WikiError):
        check_region_owner_uniqueness([bundled, sideload])


# ---------------------------------------------------------------------------
# AC15 — recipe binding across merged catalog
# ---------------------------------------------------------------------------


def test_recipe_resolves_against_merged_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC15: user recipe can reference one bundled + one sideloaded primitive."""

    from llm_wiki_kit.models import Recipe
    from llm_wiki_kit.recipes import resolve_recipe_primitives

    yaml_text = textwrap.dedent("""
        name: sideload-extra
        kind: content-type
        version: 0.1.0
        description: Sideload content-type.
    """).lstrip()
    templates_path = _make_fake_package(
        tmp_path,
        package_name="extra-pkg",
        primitive_kind="content-types",
        primitive_name="sideload-extra",
        primitive_yaml=yaml_text,
    )
    _patch_sideload(monkeypatch, [("extra-pkg", "0.1.0", templates_path)])

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    catalog = discover_primitives(kit_templates)

    # Add core so the recipe resolver's always-include-core rule works.
    from llm_wiki_kit.primitives import load_primitive

    kit_root = Path(__file__).resolve().parents[2]
    catalog.append(load_primitive(kit_root / "core"))

    recipe = Recipe(
        name="user-recipe",
        version="0.1.0",
        description="User recipe combining bundled + sideload primitives.",
        primitives=["meeting", "sideload-extra"],
    )
    closure = resolve_recipe_primitives(recipe, catalog)
    closure_names = {p.name for p in closure}
    assert "sideload-extra" in closure_names
    assert "meeting" in closure_names
    assert "core" in closure_names


# ---------------------------------------------------------------------------
# AC11 — SKILL-fragment gate fires on sideload paths
# ---------------------------------------------------------------------------


def test_skill_fragment_gate_fires_on_sideload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC11: a sideload op declaring `plan-podcasts` w/o it in SKILL desc raises."""

    primitive_yaml = textwrap.dedent("""
        name: pod-prep
        kind: operation
        version: 0.1.0
        description: Plan podcasts (fixture).
    """).lstrip()
    contract_yaml = textwrap.dedent("""
        name: pod-prep
        description: Plan podcasts.
        skill: pod-prep
        outcomes:
          - plan-podcasts
    """).lstrip()
    # Description deliberately omits "plan-podcasts" as whole word.
    skill_md = textwrap.dedent("""\
        ---
        description: A skill that does pod stuff
        ---
        Body.
    """)
    templates_path = _make_fake_package(
        tmp_path,
        package_name="podcaster-pkg",
        primitive_kind="operations",
        primitive_name="pod-prep",
        primitive_yaml=primitive_yaml,
        extra_files={
            "contract.yaml": contract_yaml,
            "files/skills/pod-prep/SKILL.md": skill_md,
        },
    )
    _patch_sideload(monkeypatch, [("podcaster-pkg", "0.1.0", templates_path)])

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    catalog = discover_primitives(kit_templates)
    sideloaded = [p for p in catalog if p.source != "bundled"]
    assert len(sideloaded) == 1
    sources = {p.name: p._source_dir for p in sideloaded if p._source_dir is not None}
    with pytest.raises(WikiError) as exc_info:
        validate_outcome_skill_fragments(primitives=sideloaded, sources=sources)
    assert "plan-podcasts" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC13b — `wiki outcomes` always-present Source column (no-sideload case)
# ---------------------------------------------------------------------------


def test_outcomes_renders_mixed_bundled_and_sideload_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC13a: mixed bundled + sideload operations render with distinct source labels.

    Patches a sideload package whose operation primitive ships an
    outcome verb, installs both the family recipe (which gives us a
    bundled operation surfacing ``digest``) and the sideload primitive
    via direct journal seeding, then asserts ``wiki outcomes`` shows
    one row tagged ``bundled`` and another tagged
    ``sideload:<package>``.
    """

    from datetime import UTC, datetime

    from llm_wiki_kit.cli import main
    from llm_wiki_kit.journal import append_event
    from llm_wiki_kit.models import PrimitiveInstallEvent
    from llm_wiki_kit.render import render_tree

    primitive_yaml = textwrap.dedent("""
        name: side-op
        kind: operation
        version: 0.1.0
        description: Sideload operation that ships a unique outcome verb.
    """).lstrip()
    contract_yaml = textwrap.dedent("""
        name: side-op
        description: Side op.
        skill: side-op
        outcomes:
          - log-sideload
    """).lstrip()
    skill_md = "---\ndescription: log-sideload is the verb\n---\nBody.\n"
    templates_path = _make_fake_package(
        tmp_path,
        package_name="mixed-pkg",
        primitive_kind="operations",
        primitive_name="side-op",
        primitive_yaml=primitive_yaml,
        extra_files={
            "contract.yaml": contract_yaml,
            "files/skills/side-op/SKILL.md": skill_md,
        },
    )
    _patch_sideload(monkeypatch, [("mixed-pkg", "0.1.0", templates_path)])

    vault = tmp_path / "vault"
    assert main(["init", str(vault), "--no-git", "--recipe", "family"]) == 0
    capsys.readouterr()

    # Manually install the sideload operation primitive into the
    # vault: render its ``files/`` tree and journal a
    # ``PrimitiveInstallEvent`` so ``state.installed_primitives``
    # carries the name when ``installed_outcome_verbs_with_sources``
    # walks the journal. Bypassing ``wiki add`` here because the
    # sideload primitive isn't in a recipe — the mixed case the AC
    # asserts is "bundled via recipe + sideload via direct install."
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    render_tree(
        templates_path.parent / "templates" / "operations" / "side-op" / "files",
        vault,
        {"vault_name": "vault", "recipe_name": "family"},
        journal_path,
        by="side-op",
    )
    append_event(
        journal_path,
        PrimitiveInstallEvent(
            timestamp=datetime.now(UTC),
            by="wiki-add",
            primitive="side-op",
            version="0.1.0",
            source="sideload:mixed-pkg",
        ),
    )

    monkeypatch.chdir(vault)
    assert main(["outcomes"]) == 0
    captured = capsys.readouterr()
    lines = [ln for ln in captured.out.splitlines() if ln.strip()]
    sideload_rows = [ln for ln in lines if "sideload:mixed-pkg" in ln]
    bundled_rows = [ln for ln in lines if "bundled" in ln.split()]
    assert sideload_rows, f"expected a sideload row; got: {lines}"
    assert bundled_rows, f"expected at least one bundled row; got: {lines}"


def test_outcomes_source_column_always_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC13b: with no sideload packages, every row shows ``bundled``."""

    from llm_wiki_kit.cli import main

    vault = tmp_path / "vault"
    assert main(["init", str(vault), "--no-git", "--recipe", "family"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(vault)
    assert main(["outcomes"]) == 0
    captured = capsys.readouterr()
    lines = [ln for ln in captured.out.splitlines() if ln.strip()]
    assert lines, "wiki outcomes produced no output for a family-recipe vault"
    for line in lines:
        # Every row's second column is the Source. ``bundled`` must
        # appear in every row when no sideload packages are installed.
        assert "bundled" in line.split()


# ---------------------------------------------------------------------------
# AC8 — schema version freeze symmetry
# ---------------------------------------------------------------------------


def test_schema_version_2_sideload_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC8: a sideload primitive declaring schema_version: 2 raises."""

    yaml_text = textwrap.dedent("""
        name: future-foo
        kind: content-type
        version: 0.1.0
        description: Declares a future schema version.
        schema_version: 2
    """).lstrip()
    templates_path = _make_fake_package(
        tmp_path,
        package_name="future-pkg",
        primitive_kind="content-types",
        primitive_name="future-foo",
        primitive_yaml=yaml_text,
    )
    _patch_sideload(monkeypatch, [("future-pkg", "0.1.0", templates_path)])

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    with pytest.raises(Exception) as exc_info:
        discover_primitives(kit_templates)
    # The wrapped error chains the original ValidationError; the
    # supported-versions string lives in the chained message.
    chained = str(exc_info.value.__cause__ or exc_info.value)
    assert "schema_version" in chained and "supported" in chained


# ---------------------------------------------------------------------------
# AC6 — sideload extra=ignore + dropped-field surfacing via doctor
# ---------------------------------------------------------------------------


def test_doctor_reports_dropped_fields_for_sideload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC6: a sideload primitive's unknown field surfaces in doctor info."""

    from llm_wiki_kit.doctor import gather_sideload_info

    yaml_text = textwrap.dedent("""
        name: forward-compat
        kind: content-type
        version: 0.1.0
        description: Sideload primitive with a forward-compat hint.
        hint_for_kit_2_2: anything
    """).lstrip()
    templates_path = _make_fake_package(
        tmp_path,
        package_name="forward-pkg",
        primitive_kind="content-types",
        primitive_name="forward-compat",
        primitive_yaml=yaml_text,
    )
    _patch_sideload(monkeypatch, [("forward-pkg", "0.1.0", templates_path)])

    kit_root = Path(__file__).resolve().parents[2]
    info = gather_sideload_info(kit_root)
    assert info.primitives
    assert any(row.name == "forward-compat" for row in info.primitives)
    assert info.dropped_fields, "dropped fields surface should be populated"
    package, primitive_name, fields = info.dropped_fields[0]
    assert package == "forward-pkg"
    assert primitive_name == "forward-compat"
    assert "hint_for_kit_2_2" in fields


# ---------------------------------------------------------------------------
# AC12 — `wiki doctor` sideload section header
# ---------------------------------------------------------------------------


def test_doctor_lists_installed_sideload_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC12: doctor's structural helper returns one row per sideloaded primitive."""

    from llm_wiki_kit.doctor import gather_sideload_info

    yaml_a = textwrap.dedent("""
        name: pkg-a-foo
        kind: content-type
        version: 0.1.0
        description: Sideload primitive A.
    """).lstrip()
    yaml_b = textwrap.dedent("""
        name: pkg-a-bar
        kind: ontology
        version: 0.1.0
        description: Sideload ontology.
    """).lstrip()
    pkg_root = tmp_path / "pkg-a"
    (pkg_root / "templates" / "content-types" / "pkg-a-foo").mkdir(parents=True)
    (pkg_root / "templates" / "content-types" / "pkg-a-foo" / "primitive.yaml").write_text(
        yaml_a, encoding="utf-8"
    )
    (pkg_root / "templates" / "ontologies" / "pkg-a-bar").mkdir(parents=True)
    (pkg_root / "templates" / "ontologies" / "pkg-a-bar" / "primitive.yaml").write_text(
        yaml_b, encoding="utf-8"
    )
    _patch_sideload(monkeypatch, [("pkg-a", "2.0.0", pkg_root / "templates")])

    kit_root = Path(__file__).resolve().parents[2]
    info = gather_sideload_info(kit_root)
    names = sorted(row.name for row in info.primitives)
    assert names == ["pkg-a-bar", "pkg-a-foo"]
    assert all(row.package == "pkg-a" for row in info.primitives)
    assert all(row.version == "2.0.0" for row in info.primitives)


# ---------------------------------------------------------------------------
# AC14 — slash-stub provenance region
# ---------------------------------------------------------------------------


def test_sideloaded_stub_has_populated_provenance_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC14: a sideloaded operation's slash stub carries a populated block."""

    from llm_wiki_kit.install import write_outcome_slash_stubs
    from llm_wiki_kit.models import Primitive, PrimitiveKind

    # Build a fake sideloaded operation primitive directly. The
    # ``write_outcome_slash_stubs`` writer reads ``primitive.source``
    # to render the provenance body; we set the field directly to
    # avoid the importlib.metadata.version() dance for an
    # unregistered package.
    primitive = Primitive.from_sideload(
        {
            "name": "test-op",
            "kind": PrimitiveKind.OPERATION.value,
            "version": "0.1.0",
            "description": "Test op.",
        },
        source="sideload:demo-pkg",
    )
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    contract = textwrap.dedent("""
        name: test-op
        description: Test op.
        skill: test-op
        outcomes:
          - log-demo
    """).lstrip()
    (source_dir / "contract.yaml").write_text(contract, encoding="utf-8")
    primitive._source_dir = source_dir

    vault = tmp_path / "vault"
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    journal_path.parent.mkdir(parents=True)
    journal_path.touch()

    write_outcome_slash_stubs(
        primitives=[primitive],
        sources={"test-op": source_dir},
        journal_path=journal_path,
        by="wiki-init",
    )
    stub = (vault / ".claude" / "commands" / "log-demo.md").read_text(encoding="utf-8")
    assert "<!-- BEGIN MANAGED: outcome-provenance -->" in stub
    assert "<!-- END MANAGED: outcome-provenance -->" in stub
    assert "From sideload package: `demo-pkg`" in stub


# ---------------------------------------------------------------------------
# AC18 — zipped-wheel sideload non-goal documented
# ---------------------------------------------------------------------------


def test_slash_stub_round_trips_through_safe_write_unchanged_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC14 round-trip: a re-render with unchanged version produces identical bytes.

    Spec §Outputs "Slash-stub managed-region provenance block": the
    block "round-trips through `safe_write` without drift on a no-op
    `wiki upgrade` **when the sideload package version is unchanged
    between runs**". Drives the stub writer twice with the same
    primitive (same source label) and asserts byte equality between
    runs — that's the contract that lets ``wiki upgrade`` stay quiet
    when nothing has actually changed.
    """

    from llm_wiki_kit.install import write_outcome_slash_stubs
    from llm_wiki_kit.models import Primitive, PrimitiveKind

    primitive = Primitive.from_sideload(
        {
            "name": "stable-op",
            "kind": PrimitiveKind.OPERATION.value,
            "version": "0.1.0",
            "description": "Stable op for round-trip test.",
        },
        source="sideload:stable-pkg",
    )
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    contract = textwrap.dedent("""
        name: stable-op
        description: Stable op.
        skill: stable-op
        outcomes:
          - log-stable
    """).lstrip()
    (source_dir / "contract.yaml").write_text(contract, encoding="utf-8")
    primitive._source_dir = source_dir

    vault = tmp_path / "vault"
    journal_path = vault / ".wiki.journal" / "journal.jsonl"
    journal_path.parent.mkdir(parents=True)
    journal_path.touch()

    write_outcome_slash_stubs(
        primitives=[primitive],
        sources={"stable-op": source_dir},
        journal_path=journal_path,
        by="wiki-init",
    )
    stub_path = vault / ".claude" / "commands" / "log-stable.md"
    first = stub_path.read_bytes()

    # Re-run the writer with the same primitive (same source label, no
    # version change). The bytes must match — that's the no-drift
    # contract the spec pins, and the precondition for ``wiki upgrade``
    # being a silent no-op when nothing has actually changed.
    write_outcome_slash_stubs(
        primitives=[primitive],
        sources={"stable-op": source_dir},
        journal_path=journal_path,
        by="wiki-upgrade",
    )
    second = stub_path.read_bytes()
    assert first == second, "stub bytes drifted across no-op re-render"


def test_zipped_wheel_sideload_raises_on_first_fs_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC18: a sideload whose templates path does not exist raises loudly.

    The kit's reliance on ``pathlib.Path`` operations is the
    documented mechanism for surfacing zipped-wheel layouts (which
    return a different Traversable subclass from
    ``importlib.resources.files``). A missing-templates-dir simulation
    is the closest fixture-only proxy — the error message names the
    package, matching the spec contract.
    """

    nonexistent_templates = tmp_path / "ghost-pkg" / "templates"
    # Don't create the directory — simulate the missing-traversal case.
    _patch_sideload(monkeypatch, [("ghost-pkg", "0.1.0", nonexistent_templates)])

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    with pytest.raises(WikiError) as exc_info:
        discover_primitives(kit_templates)
    assert "ghost-pkg" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC19 — recipes/-at-package-root soft warning
# ---------------------------------------------------------------------------


def test_doctor_warns_on_package_recipes_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC19: a sideload shipping `recipes/` at package root surfaces a warning."""

    from llm_wiki_kit.doctor import gather_sideload_info

    yaml_text = textwrap.dedent("""
        name: rcp-foo
        kind: content-type
        version: 0.1.0
        description: Sideload that also ships a recipes/ directory.
    """).lstrip()
    pkg_root = tmp_path / "rcp-pkg"
    (pkg_root / "templates" / "content-types" / "rcp-foo").mkdir(parents=True)
    (pkg_root / "templates" / "content-types" / "rcp-foo" / "primitive.yaml").write_text(
        yaml_text, encoding="utf-8"
    )
    # Ship a recipes/ directory at the package root — kit ignores it.
    (pkg_root / "recipes").mkdir()
    (pkg_root / "recipes" / "stub.yaml").write_text("name: stub\n", encoding="utf-8")
    _patch_sideload(monkeypatch, [("rcp-pkg", "0.1.0", pkg_root / "templates")])

    kit_root = Path(__file__).resolve().parents[2]
    info = gather_sideload_info(kit_root)
    assert len(info.package_recipes_warnings) == 1
    package, dropped_path = info.package_recipes_warnings[0]
    assert package == "rcp-pkg"
    assert dropped_path.name == "recipes"


# ---------------------------------------------------------------------------
# AC17 — uninstalled-sideload mismatch hint
# ---------------------------------------------------------------------------


def test_doctor_hints_at_uninstalled_sideload_package(tmp_path: Path) -> None:
    """AC17: a journal `PrimitiveInstallEvent` with sideload source surfaces a hint."""

    from datetime import UTC, datetime

    from llm_wiki_kit.doctor import check_primitive_missing
    from llm_wiki_kit.models import PrimitiveInstallEvent, VaultState

    kit_root = tmp_path / "kit"
    (kit_root / "core").mkdir(parents=True)
    (kit_root / "core" / "primitive.yaml").write_text(
        "name: core\nkind: infrastructure\nversion: 0.1.0\ndescription: core.\n",
        encoding="utf-8",
    )
    state = VaultState(installed_primitives={"core": "0.1.0", "ghost-from-sideload": "0.1.0"})
    install_event = PrimitiveInstallEvent(
        timestamp=datetime.now(UTC),
        by="wiki-add",
        primitive="ghost-from-sideload",
        version="0.1.0",
        source="sideload:vanished-pkg",
    )
    issues = check_primitive_missing(state, [install_event], kit_root)
    assert len(issues) == 1
    assert "vanished-pkg" in issues[0].detail


# ---------------------------------------------------------------------------
# Sideload-discovery helper itself (entry-point resolution)
# ---------------------------------------------------------------------------


def test_helper_raises_on_missing_templates_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sideload whose templates/ directory is absent raises a clear error."""

    nonexistent = tmp_path / "no-templates-here"
    _patch_sideload(monkeypatch, [("broken-pkg", "0.1.0", nonexistent)])

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    with pytest.raises(WikiError) as exc_info:
        discover_primitives(kit_templates)
    assert "broken-pkg" in str(exc_info.value)


def test_doctor_renders_sideload_section_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC12 end-to-end: ``wiki doctor`` stdout carries the sideload section.

    Drives the CLI command (not just ``gather_sideload_info``) and
    asserts against captured stdout. Catches regressions in the
    section header, per-package grouping, and dropped-fields
    subsection rendering — none of which the helper-shape tests
    elsewhere in this file would notice if the CLI rendering broke.
    """

    from llm_wiki_kit.cli import main

    yaml_text = textwrap.dedent("""
        name: doctor-test-foo
        kind: content-type
        version: 0.1.0
        description: Sideload primitive surfaced via doctor.
        hint_for_kit_2_2: anything
    """).lstrip()
    pkg_root = tmp_path / "pkg"
    (pkg_root / "templates" / "content-types" / "doctor-test-foo").mkdir(parents=True)
    (pkg_root / "templates" / "content-types" / "doctor-test-foo" / "primitive.yaml").write_text(
        yaml_text, encoding="utf-8"
    )
    # Also ship a recipes/ directory at the package root so the
    # third rendering branch (the package-recipes warning) fires too.
    (pkg_root / "recipes").mkdir()
    (pkg_root / "recipes" / "stub.yaml").write_text("name: stub\n", encoding="utf-8")
    _patch_sideload(monkeypatch, [("doctor-test-pkg", "3.4.5", pkg_root / "templates")])

    vault = tmp_path / "vault"
    assert main(["init", str(vault), "--no-git", "--recipe", "family"]) == 0
    capsys.readouterr()
    monkeypatch.chdir(vault)
    main(["doctor"])
    captured = capsys.readouterr()
    out = captured.out
    assert "Sideload primitives:" in out
    assert "From package doctor-test-pkg (version 3.4.5):" in out
    assert "- content-type: doctor-test-foo" in out
    assert "Sideload primitives with dropped unknown fields:" in out
    assert "doctor-test-pkg::doctor-test-foo" in out
    assert "hint_for_kit_2_2" in out
    assert "Sideload package warnings:" in out
    assert "doctor-test-pkg" in out
    assert "recipes/" in out or "recipes" in out


def test_outcome_verb_collision_message_includes_source_attribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §"Error cases": verb collision message names ``bundled`` + the package.

    Concern 3 from adversarial review. The earlier `test_outcome_verb_
    collision_across_catalog_raises` only asserted that the verb name
    appeared; this test pins the *attribution* — a user with two
    packages each shipping the same verb must see which package to
    uninstall.
    """

    primitive_yaml = textwrap.dedent("""
        name: rival-digest-2
        kind: operation
        version: 0.1.0
        description: Rival operation claiming a bundled verb.
    """).lstrip()
    contract_yaml = textwrap.dedent("""
        name: rival-digest-2
        description: Rival.
        skill: rival-digest-2
        outcomes:
          - digest
    """).lstrip()
    skill_md = "---\ndescription: digest the week\n---\nBody.\n"
    templates_path = _make_fake_package(
        tmp_path,
        package_name="attrib-test-pkg",
        primitive_kind="operations",
        primitive_name="rival-digest-2",
        primitive_yaml=primitive_yaml,
        extra_files={
            "contract.yaml": contract_yaml,
            "files/skills/rival-digest-2/SKILL.md": skill_md,
        },
    )
    _patch_sideload(monkeypatch, [("attrib-test-pkg", "0.1.0", templates_path)])

    kit_templates = Path(__file__).resolve().parents[2] / "templates"
    with pytest.raises(WikiError) as exc_info:
        discover_primitives(kit_templates)
    message = str(exc_info.value)
    assert "bundled" in message
    assert "sideload:attrib-test-pkg" in message


def test_entry_point_naming_kit_module_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sec-3: an entry-point value naming ``llm_wiki_kit`` itself is refused.

    Defends against a malicious or sloppy sideload package declaring
    ``wiki-primitive = "llm_wiki_kit"``, which would otherwise resolve
    the kit's own ``templates/`` and report attacker-controlled
    package name in every collision/error message.
    """

    from llm_wiki_kit.errors import PrimitiveError

    # We bypass the helper's monkeypatch (which already supplies
    # resolved triples) and instead patch ``importlib.metadata.entry_points``
    # so the helper itself executes its refusal path.
    class _FakeEntryPoint:
        value = "llm_wiki_kit"
        dist = None

    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda **_: [_FakeEntryPoint()],
    )
    with pytest.raises(PrimitiveError) as exc_info:
        primitives_module._discover_sideloaded_template_dirs()
    assert "llm_wiki_kit" in str(exc_info.value)


def test_provenance_block_sanitises_malicious_package_name(tmp_path: Path) -> None:
    """Sec-1: a package label containing markdown-active bytes renders as ``invalid``.

    Defence-in-depth against a hand-crafted wheel whose METADATA Name
    contains newlines or backticks: the slash-stub's
    ``outcome-provenance`` block is the only place the kit synthesises
    sideload-sourced bytes into a vault file Claude Code reads as a
    slash-command, so the rendering must not allow byte sequences that
    break out of the inline-code span / blockquote.
    """

    # The Pydantic Pattern on Primitive.source already rejects such
    # values at parse time (Q-2 hardening), so a malicious wheel
    # cannot actually land a sideload primitive with a bad source
    # label through the loader. Exercise the rendering path directly
    # with a synthetic source string to assert the secondary defence.
    from llm_wiki_kit.install import _outcome_provenance_block_body
    from llm_wiki_kit.models import Primitive, PrimitiveKind

    primitive = Primitive.from_sideload(
        {
            "name": "fixture-op",
            "kind": PrimitiveKind.OPERATION.value,
            "version": "0.1.0",
            "description": "Fixture op.",
        },
        source="sideload:legitimate-pkg",
    )
    # Force a malformed source post-construction (simulating a
    # downstream code path that bypassed the loader's pattern check).
    object.__setattr__(primitive, "source", "sideload:evil`\nattack")
    body = _outcome_provenance_block_body(primitive)
    # The rendering helper must replace the malformed token with the
    # ``invalid`` sentinel rather than emit the raw bytes.
    assert "evil`" not in body
    assert "attack" not in body
    assert "invalid" in body


def test_bundled_primitive_yaml_rejecting_source_field() -> None:
    """Q-2: a bundled primitive.yaml declaring a bogus ``source:`` line is rejected.

    The Pydantic Pattern on ``Primitive.source`` rejects out-of-
    vocabulary values at parse time, surfacing the typo even though
    the bundled loader would have overwritten the value to
    ``"bundled"`` post-construction.
    """

    from pydantic import ValidationError as PydanticValidationError

    from llm_wiki_kit.models import Primitive, PrimitiveKind

    with pytest.raises(PydanticValidationError):
        Primitive.model_validate(
            {
                "name": "fixture-foo",
                "kind": PrimitiveKind.CONTENT_TYPE.value,
                "version": "0.1.0",
                "description": "Fixture.",
                "source": "totally-not-bundled",
            }
        )


def test_empty_entry_point_group_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_discover_sideloaded_template_dirs`` returns [] with no entry points."""

    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda **_: [],
    )
    assert primitives_module._discover_sideloaded_template_dirs() == []
