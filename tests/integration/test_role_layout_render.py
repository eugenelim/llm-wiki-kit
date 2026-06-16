"""T6 end-to-end: the catalog seeds only the four roles, and RFC-0008 is untouched.

Two goal-based guards over the shipped artifacts:

1. **No kind/lifecycle/area folder is seeded by any primitive.** A grep over
   every primitive's `files/wiki/**` seed tree must find none of the removed
   ontology-kind, content-type-kind, or lifecycle/area folder names — only the
   four role folders, the `efforts/<type>/` registries, and the `identity`
   companion. (Container `_assets/`/`_working/` bulk sinks are permitted but
   none is seeded today.)
2. **RFC-0008 lenses are byte-unchanged.** The shipped `.base` files render
   verbatim into a vault and the rendered schema still carries `workspaces`.

Spec: ``docs/specs/role-folders-and-containers/spec.md`` (AC "no kind/lifecycle
/area folder"; "RFC-0008 untouched").
"""

from __future__ import annotations

from pathlib import Path

from llm_wiki_kit.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "templates"
WORKSPACES_DIR = TEMPLATES_DIR / "workspaces"

# Every folder name the four-role layout forbids as a *seeded* wiki folder.
FORBIDDEN_SEED_FOLDERS = {
    # removed entity-kind ontologies
    "customers",
    "vendors",
    "food",
    "medical",
    "domains",
    # removed content-type kind folders
    "meetings",
    "actions",
    "decisions",
    "interviews",
    "customer-feedback",
    "receipts",
    "tax",
    "stakeholder-updates",
    "vendor-contracts",
    # lifecycle / area / synthesis subfolders
    "records",
    "sources",
    "drafts",
    "archive",
    "someday",
    "upcoming",
    "past",
    "areas",
}

# The only wiki folder names any primitive may seed.
ALLOWED_WIKI_FOLDERS = {
    "people",
    "efforts",
    "library",
    "atlas",
    "identity",
    # container registries nested under efforts/
    "trips",
    "cases",
    "projects",
}


def test_no_primitive_seeds_a_forbidden_folder() -> None:
    offenders: list[str] = []
    for wiki_dir in TEMPLATES_DIR.glob("*/*/files/wiki"):
        for path in wiki_dir.rglob("*"):
            if path.is_dir() and path.name in FORBIDDEN_SEED_FOLDERS:
                offenders.append(str(path.relative_to(TEMPLATES_DIR)))
    assert not offenders, f"primitives seed forbidden folders: {sorted(offenders)}"


def test_every_seeded_wiki_folder_is_a_role_or_container() -> None:
    """Defensive complement: every seeded wiki/ folder name is on the allow-list."""
    unexpected: list[str] = []
    for wiki_dir in TEMPLATES_DIR.glob("*/*/files/wiki"):
        for path in wiki_dir.rglob("*"):
            if path.is_dir() and path.name not in ALLOWED_WIKI_FOLDERS:
                unexpected.append(str(path.relative_to(TEMPLATES_DIR)))
    assert not unexpected, f"unexpected seeded wiki folders: {sorted(unexpected)}"


def test_rfc_0008_base_lenses_render_byte_unchanged(tmp_path: Path) -> None:
    """The shipped .base lenses render verbatim (RFC-0008 untouched)."""
    vault = tmp_path / "v"
    assert main(["init", str(vault), "--recipe", "personal", "--no-git"]) == 0

    for base_src in WORKSPACES_DIR.glob("*/files/*.base"):
        rendered = vault / base_src.name
        assert rendered.is_file(), f"missing rendered {base_src.name}"
        assert rendered.read_bytes() == base_src.read_bytes(), (
            f"{base_src.name} rendered with different bytes than the template"
        )


def test_rendered_schema_still_carries_workspaces(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    assert main(["init", str(vault), "--recipe", "personal", "--no-git"]) == 0
    schema = (vault / "frontmatter.schema.yaml").read_text(encoding="utf-8")
    assert "workspaces:" in schema, "rendered schema lost the workspaces field"
