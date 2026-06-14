"""T3: a fresh vault's ``frontmatter.schema.yaml`` declares ``workspaces``.

Spec AC-5: the rendered baseline schema declares an optional multi-valued
``workspaces`` field, and no kit code validates a page's ``workspaces:``
value — the field is a discoverable convention, not a kit-enforced
constraint. The "unvalidated" half is pinned here at the schema level: the
field is ``optional: true`` and absent from the ``required:`` list, so a
page omitting it is valid and the kit never rejects an arbitrary value.
(The kit has no page-frontmatter validator at all today.)

Uses a real ``wiki init`` so the assertion is against what actually lands
in a vault, not the shipped template alone.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from llm_wiki_kit.cli import main


def test_fresh_vault_schema_declares_optional_workspaces_field(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    assert main(["init", str(vault), "--recipe", "personal"]) == 0

    schema_text = (vault / "frontmatter.schema.yaml").read_text(encoding="utf-8")
    schema = yaml.safe_load(schema_text)

    assert schema["fields"]["workspaces"] == {
        "type": "list",
        "items": "string",
        "optional": True,
    }
    # Convention-only: the field is optional and never required, so a page
    # without it is valid and the kit enforces no value constraint.
    assert "workspaces" not in schema["required"]
