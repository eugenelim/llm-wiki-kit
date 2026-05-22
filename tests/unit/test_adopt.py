"""Unit tests for ``llm_wiki_kit.adopt.compute_adoption_set``.

Pins the recipe-filtered adoption-set computation (ADR-0008;
spec ``docs/specs/wiki-init-adopt/spec.md`` §Contracts
"`llm_wiki_kit.adopt`"; plan PR-C step 2). Each test ties to one
acceptance criterion or pre-flight refusal named in the spec.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from llm_wiki_kit import managed_regions
from llm_wiki_kit.adopt import (
    INSTALL_VEHICLE_ADOPT,
    AdoptedRegion,
    AdoptionSet,
    HostAdoption,
    compute_adoption_set,
)
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.models import Contribution, Primitive, PrimitiveKind


def _primitive(
    name: str,
    *,
    kind: PrimitiveKind = PrimitiveKind.CONTENT_TYPE,
    contributes_to: list[Contribution] | None = None,
) -> Primitive:
    return Primitive(
        name=name,
        kind=kind,
        version="0.1.0",
        description=f"Test primitive {name}.",
        contributes_to=contributes_to or [],
    )


def _seed_files(root: Path, paths: dict[str, str]) -> None:
    """Drop synthetic files under ``root/files`` (the renderer's source tree).

    Used to build a fake primitive whose ``files/`` tree contains the
    given vault-relative paths and their bodies, so
    ``enumerate_rendered_paths`` and ``compute_adoption_set`` see the
    primitive as kit-owning those paths.
    """

    files = root / "files"
    for relative, body in paths.items():
        target = files / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_compute_adoption_set_empty_target_returns_empty(tmp_path: Path) -> None:
    """A fresh, empty target produces an empty AdoptionSet."""

    vault = tmp_path / "vault"
    vault.mkdir()
    primitive_root = tmp_path / "p"
    _seed_files(primitive_root, {"wiki/people/README.md": "kit body\n"})

    result = compute_adoption_set(vault, [_primitive("p")], {"p": primitive_root})

    assert result == AdoptionSet(host_adoptions=(), pre_existing_sidecars=())


def test_compute_adoption_set_kit_owned_file_present_is_adopted(tmp_path: Path) -> None:
    """A pre-existing kit-owned file (no managed regions) is adopted with empty regions."""

    vault = tmp_path / "vault"
    vault.mkdir()
    primitive_root = tmp_path / "people"
    _seed_files(primitive_root, {"wiki/people/README.md": "kit body\n"})

    user_body = "user wrote this\n"
    (vault / "wiki" / "people").mkdir(parents=True)
    (vault / "wiki" / "people" / "README.md").write_text(user_body, encoding="utf-8")

    result = compute_adoption_set(vault, [_primitive("people")], {"people": primitive_root})

    assert result.host_adoptions == (
        HostAdoption(
            path="wiki/people/README.md",
            hash=_hash(user_body),
            regions=(),
        ),
    )
    assert result.pre_existing_sidecars == ()


def test_compute_adoption_set_user_territory_file_is_skipped(tmp_path: Path) -> None:
    """A file at a path no primitive claims is neither adopted nor surfaced."""

    vault = tmp_path / "vault"
    vault.mkdir()
    primitive_root = tmp_path / "p"
    _seed_files(primitive_root, {"wiki/people/README.md": "kit body\n"})

    (vault / "notes").mkdir()
    (vault / "notes" / "personal.md").write_text("user notes\n", encoding="utf-8")

    result = compute_adoption_set(vault, [_primitive("p")], {"p": primitive_root})

    assert result == AdoptionSet(host_adoptions=(), pre_existing_sidecars=())


def test_compute_adoption_set_user_file_in_kit_dir_is_skipped(tmp_path: Path) -> None:
    """A user-territory file under a kit-owned directory is NOT adopted.

    The recipe filter keys on per-path ownership, not on owned-dir
    membership; kit-owned-dir orphan signalling lives in
    ``doctor.check_orphans``.
    """

    vault = tmp_path / "vault"
    vault.mkdir()
    primitive_root = tmp_path / "people"
    _seed_files(primitive_root, {"wiki/people/README.md": "kit body\n"})

    (vault / "wiki" / "people").mkdir(parents=True)
    (vault / "wiki" / "people" / "uncle-bob.md").write_text("user wrote this\n", encoding="utf-8")

    result = compute_adoption_set(vault, [_primitive("people")], {"people": primitive_root})

    assert result == AdoptionSet(host_adoptions=(), pre_existing_sidecars=())


def test_compute_adoption_set_managed_region_host_emits_region_adopts(tmp_path: Path) -> None:
    """A pre-existing managed-region host file emits region adopt rows.

    Pinned to AC8: hashes match ``managed_regions.canonical_region_body``.
    """

    vault = tmp_path / "vault"
    vault.mkdir()

    # Two primitives both contribute to frontmatter.schema.yaml: one to
    # `types`, one to `fields`.
    p_types_root = tmp_path / "p-types"
    _seed_files(p_types_root, {"frontmatter.schema.yaml": "host kit body\n"})
    (p_types_root / "regions").mkdir()
    (p_types_root / "regions" / "frontmatter.schema.yaml.types").write_text(
        "  - kit-type\n", encoding="utf-8"
    )

    p_fields_root = tmp_path / "p-fields"
    (p_fields_root / "regions").mkdir(parents=True)
    (p_fields_root / "regions" / "frontmatter.schema.yaml.fields").write_text(
        "  kit_field:\n    type: string\n", encoding="utf-8"
    )

    p_types = _primitive(
        "p-types",
        contributes_to=[Contribution(file="frontmatter.schema.yaml", region="types")],
    )
    p_fields = _primitive(
        "p-fields",
        contributes_to=[Contribution(file="frontmatter.schema.yaml", region="fields")],
    )

    on_disk_host = (
        "types:\n"
        "  # BEGIN MANAGED: types\n"
        "  - user-type-a\n"
        "  - user-type-b\n"
        "  # END MANAGED: types\n"
        "fields:\n"
        "  # BEGIN MANAGED: fields\n"
        "  user_field:\n"
        "    type: string\n"
        "  # END MANAGED: fields\n"
    )
    (vault / "frontmatter.schema.yaml").write_text(on_disk_host, encoding="utf-8")

    sources = {"p-types": p_types_root, "p-fields": p_fields_root}
    result = compute_adoption_set(vault, [p_types, p_fields], sources)

    parsed = managed_regions.parse(on_disk_host)
    expected_types_hash = _hash(
        managed_regions.canonical_region_body(parsed["types"]).decode("utf-8")
    )
    expected_fields_hash = _hash(
        managed_regions.canonical_region_body(parsed["fields"]).decode("utf-8")
    )

    assert result.host_adoptions == (
        HostAdoption(
            path="frontmatter.schema.yaml",
            hash=_hash(on_disk_host),
            regions=(
                AdoptedRegion(region="fields", content_hash=expected_fields_hash),
                AdoptedRegion(region="types", content_hash=expected_types_hash),
            ),
        ),
    )


def test_compute_adoption_set_malformed_region_markers_raises(tmp_path: Path) -> None:
    """AC9 — unbalanced markers refuse with WikiError naming the file."""

    vault = tmp_path / "vault"
    vault.mkdir()
    primitive_root = tmp_path / "p"
    _seed_files(primitive_root, {"frontmatter.schema.yaml": "host kit body\n"})
    (primitive_root / "regions").mkdir()
    (primitive_root / "regions" / "frontmatter.schema.yaml.types").write_text(
        "  - kit-type\n", encoding="utf-8"
    )

    # Markers don't balance.
    (vault / "frontmatter.schema.yaml").write_text(
        "  # BEGIN MANAGED: types\n  - user-type\n",
        encoding="utf-8",
    )

    primitive = _primitive(
        "p", contributes_to=[Contribution(file="frontmatter.schema.yaml", region="types")]
    )

    with pytest.raises(WikiError) as exc_info:
        compute_adoption_set(vault, [primitive], {"p": primitive_root})

    msg = str(exc_info.value)
    assert "cannot adopt managed-region host" in msg
    assert "frontmatter.schema.yaml" in msg
    assert "markers do not parse" in msg


def test_compute_adoption_set_missing_required_region_raises(tmp_path: Path) -> None:
    """AC9b — parseable host missing a region the recipe needs is refused."""

    vault = tmp_path / "vault"
    vault.mkdir()

    p_root = tmp_path / "p"
    _seed_files(p_root, {"frontmatter.schema.yaml": "host kit body\n"})
    (p_root / "regions").mkdir()
    (p_root / "regions" / "frontmatter.schema.yaml.fields").write_text(
        "  kit_field:\n    type: string\n", encoding="utf-8"
    )

    # User host declares only `types`, but the recipe contributes to `fields`.
    (vault / "frontmatter.schema.yaml").write_text(
        "  # BEGIN MANAGED: types\n  - user-type\n  # END MANAGED: types\n",
        encoding="utf-8",
    )

    primitive = _primitive(
        "p", contributes_to=[Contribution(file="frontmatter.schema.yaml", region="fields")]
    )

    with pytest.raises(WikiError) as exc_info:
        compute_adoption_set(vault, [primitive], {"p": p_root})

    msg = str(exc_info.value)
    assert "cannot adopt managed-region host" in msg
    assert "frontmatter.schema.yaml" in msg
    assert "missing markers for region 'fields'" in msg


def test_compute_adoption_set_kit_owned_sidecar_listed(tmp_path: Path) -> None:
    """AC10 — a .proposed at a kit-owned path is surfaced (not adopted)."""

    vault = tmp_path / "vault"
    vault.mkdir()
    primitive_root = tmp_path / "p"
    _seed_files(primitive_root, {"wiki/people/.gitkeep": ""})

    (vault / "wiki" / "people").mkdir(parents=True)
    (vault / "wiki" / "people" / ".gitkeep").write_text("", encoding="utf-8")
    (vault / "wiki" / "people" / ".gitkeep.proposed").write_text(
        "kit-proposed body\n", encoding="utf-8"
    )

    result = compute_adoption_set(vault, [_primitive("p")], {"p": primitive_root})

    assert len(result.host_adoptions) == 1
    assert result.host_adoptions[0].path == "wiki/people/.gitkeep"
    assert result.pre_existing_sidecars == ("wiki/people/.gitkeep.proposed",)


def test_compute_adoption_set_user_territory_sidecar_ignored(tmp_path: Path) -> None:
    """A .proposed outside the rendered closure is ignored entirely."""

    vault = tmp_path / "vault"
    vault.mkdir()
    primitive_root = tmp_path / "p"
    _seed_files(primitive_root, {"wiki/people/.gitkeep": ""})

    (vault / "notes").mkdir()
    (vault / "notes" / "personal.md.proposed").write_text("user sidecar\n", encoding="utf-8")

    result = compute_adoption_set(vault, [_primitive("p")], {"p": primitive_root})

    assert result.pre_existing_sidecars == ()


def test_compute_adoption_set_host_adoptions_sorted_by_path(tmp_path: Path) -> None:
    """AC6 outer ordering: host_adoptions sorted by path regardless of insertion order."""

    vault = tmp_path / "vault"
    vault.mkdir()

    primitive_root = tmp_path / "p"
    _seed_files(
        primitive_root,
        {
            "z-last.md": "z\n",
            "a-first.md": "a\n",
            "m-middle.md": "m\n",
        },
    )
    for relative in ("z-last.md", "a-first.md", "m-middle.md"):
        (vault / relative).write_text(f"user-{relative}\n", encoding="utf-8")

    result = compute_adoption_set(vault, [_primitive("p")], {"p": primitive_root})

    assert [host.path for host in result.host_adoptions] == [
        "a-first.md",
        "m-middle.md",
        "z-last.md",
    ]


def test_compute_adoption_set_regions_sorted_within_each_host(tmp_path: Path) -> None:
    """AC6 inner ordering: each HostAdoption.regions is sorted by region id."""

    vault = tmp_path / "vault"
    vault.mkdir()

    p_root = tmp_path / "p"
    _seed_files(p_root, {"shared.yaml": "host\n"})
    (p_root / "regions").mkdir()
    (p_root / "regions" / "shared.yaml.zeta").write_text("z body\n", encoding="utf-8")
    (p_root / "regions" / "shared.yaml.alpha").write_text("a body\n", encoding="utf-8")
    (p_root / "regions" / "shared.yaml.middle").write_text("m body\n", encoding="utf-8")

    primitive = _primitive(
        "p",
        contributes_to=[
            Contribution(file="shared.yaml", region="zeta"),
            Contribution(file="shared.yaml", region="alpha"),
            Contribution(file="shared.yaml", region="middle"),
        ],
    )

    (vault / "shared.yaml").write_text(
        "  # BEGIN MANAGED: zeta\n"
        "  - z\n"
        "  # END MANAGED: zeta\n"
        "  # BEGIN MANAGED: alpha\n"
        "  - a\n"
        "  # END MANAGED: alpha\n"
        "  # BEGIN MANAGED: middle\n"
        "  - m\n"
        "  # END MANAGED: middle\n",
        encoding="utf-8",
    )

    result = compute_adoption_set(vault, [primitive], {"p": p_root})

    (host,) = result.host_adoptions
    assert [region.region for region in host.regions] == ["alpha", "middle", "zeta"]


def test_compute_adoption_set_symlink_escape_raises(tmp_path: Path) -> None:
    """AC19 — a symlink at a kit-owned path that resolves outside the vault raises."""

    vault = tmp_path / "vault"
    vault.mkdir()

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leaked.md").write_text("user file\n", encoding="utf-8")

    primitive_root = tmp_path / "p"
    _seed_files(primitive_root, {"link.md": "kit\n"})

    # Symlink at the kit-owned path that points outside the vault.
    os.symlink(outside / "leaked.md", vault / "link.md")

    with pytest.raises(WikiError) as exc_info:
        compute_adoption_set(vault, [_primitive("p")], {"p": primitive_root})

    assert "not inside the vault" in str(exc_info.value)


def test_install_vehicle_adopt_constant() -> None:
    """The single-source-of-truth vehicle string for adopt-phase events."""

    assert INSTALL_VEHICLE_ADOPT == "wiki-init-adopt"
