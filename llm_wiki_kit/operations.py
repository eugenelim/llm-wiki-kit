"""Shared helpers for resolving operation primitives and their contracts.

Extracted from :mod:`llm_wiki_kit.run` so both ``wiki run`` and
``wiki schedule install`` can reuse the same installed-primitive +
kind check + contract loader. The bodies are byte-identical to the
originals (pure refactor, no behavior change); ``run.py`` re-imports
the three names under their existing identifiers so callers and tests
that referenced ``run._resolve_operation_kind`` etc. continue to work.

Contract pinned in ``docs/specs/wiki-schedule/spec.md`` §"Contracts
with other modules" ("`llm_wiki_kit.run`" bullet).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.models import OperationContract, Primitive, PrimitiveKind
from llm_wiki_kit.primitives import discover_primitives, load_primitive


def _operation_contract_path(operation: str, kit_root: Path) -> Path:
    return kit_root / "templates" / "operations" / operation / "contract.yaml"


def _load_contract(operation: str, kit_root: Path) -> OperationContract:
    """Read and validate ``templates/operations/<operation>/contract.yaml``.

    Raises :class:`WikiError` with the absolute path on a missing
    file (the kit-version-skew case — primitive is installed in the
    journal but its contract file disappeared from disk).
    """

    path = _operation_contract_path(operation, kit_root)
    if not path.is_file():
        raise WikiError(f"operation {operation!r}: no contract.yaml at {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return OperationContract.model_validate(payload)


def _resolve_operation_kind(
    operation: str,
    *,
    kit_root: Path,
    installed_primitive_names: set[str],
) -> None:
    """Verify ``operation`` is installed AND has kind ``operation``.

    Looks the primitive up in the full discovered catalog
    (``core`` + ``templates/``) so a content-type installed under
    the operation name gives a clean kind-mismatch error rather
    than a confusing missing-contract error. Raises
    :class:`WikiError` on either failure.
    """

    if operation not in installed_primitive_names:
        installed_sorted = ", ".join(sorted(installed_primitive_names)) or "(none)"
        raise WikiError(
            f"operation {operation!r} is not installed in this vault. "
            f"Installed primitives: {installed_sorted}"
        )

    core_dir = kit_root / "core"
    templates_dir = kit_root / "templates"
    catalog: list[Primitive] = []
    if core_dir.is_dir():
        catalog.append(load_primitive(core_dir))
    if templates_dir.is_dir():
        catalog.extend(discover_primitives(templates_dir))

    target = next((p for p in catalog if p.name == operation), None)
    if target is None:
        # In the journal but not on disk — kit-version skew.
        # _load_contract will raise the path-bearing error a moment
        # later; raise the same shape here so callers see one
        # consistent message.
        raise WikiError(
            f"operation {operation!r} is installed but not present in "
            f"the kit's catalog (searched {core_dir} and {templates_dir})"
        )
    if target.kind is not PrimitiveKind.OPERATION:
        raise WikiError(
            f"{operation!r} is installed but its kind is {target.kind.value!r}, not 'operation'"
        )
