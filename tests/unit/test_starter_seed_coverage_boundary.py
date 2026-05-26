"""AC8 — static AST scan asserts the library boundary.

Spec: ``docs/specs/starter-seed-coverage/spec.md``.
Plan: ``docs/specs/starter-seed-coverage/plan.md`` §Steps step 7.

The scan walks ``starters/check_coverage.py`` once to build an
import-alias table, then asserts three properties hold across the
file:

(a) No import of ``llm_wiki_kit.write_helper``,
    ``llm_wiki_kit.journal``, or any module name matching
    ``*safe_write*``.
(b) No call to ``subprocess.*`` (resolved through the alias table)
    whose first positional argument is a list literal starting with
    ``"wiki"`` (or a bare ``"wiki"`` string).
(c) No call to ``cli.main`` (resolved through the alias table) whose
    first positional argument is a list literal starting with a
    string in the disallowed-verb set.

Known floor of detection (named in plan §Risks R3): dynamic argv
(``["wi" + "ki", …]``), ``getattr``-style indirection
(``getattr(cli, "main")(…)``), and ``__getattribute__`` access are
**not** covered. The AC is a tripwire, not a fence.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_COVERAGE_PY = REPO_ROOT / "starters" / "check_coverage.py"

DISALLOWED_VERBS = frozenset(
    {"init", "add", "adopt", "ingest", "run", "doctor", "upgrade", "resolve", "schedule"}
)
# Match module names like ``llm_wiki_kit.journal`` / ``write_helper`` /
# ``foo.safe_write_region`` but NOT a future unrelated module like
# ``research.journal_formatter`` (where ``journal`` happens to be a
# substring of an attribute name, not the module). The pattern is
# anchored to dot-boundaries.
_FORBIDDEN_MODULE_RE = re.compile(r"(^|\.)(journal|write_helper|[^.]*safe_write[^.]*)(\.|$)")


def _resolve_full_module_for_import(node: ast.Import | ast.ImportFrom) -> list[tuple[str, str]]:
    """Return ``[(local_name, source_module), ...]`` for a single import node.

    Handles both ``import X`` and ``from M import N as A``. Star imports
    return an empty list — they are detected separately and rejected by
    the (no-star-imports) assertion.
    """

    out: list[tuple[str, str]] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            out.append((bound, alias.name))
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname or alias.name
            out.append((bound, f"{module}.{alias.name}"))
    return out


def _build_alias_table(tree: ast.AST) -> dict[str, str]:
    """Return ``{local_name: source_module}`` for every top-level import."""

    table: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            for local, source in _resolve_full_module_for_import(node):
                table[local] = source
    return table


def _has_star_import(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == "*" for alias in node.names):
                return True
    return False


def _function_call_resolves_to(node: ast.Call, table: dict[str, str]) -> str | None:
    """Resolve a ``Call.func`` to a dotted source path, via the alias table.

    Examples (with ``table = {"subprocess": "subprocess", "r": "subprocess.run",
    "cli": "llm_wiki_kit.cli", "c": "llm_wiki_kit.cli"}``):

    * ``subprocess.run(...)`` → ``"subprocess.run"``
    * ``r(...)`` → ``"subprocess.run"``
    * ``cli.main(...)`` → ``"llm_wiki_kit.cli.main"``
    * ``c.main(...)`` → ``"llm_wiki_kit.cli.main"``
    * Anything else → ``None``.
    """

    func = node.func
    # Case: plain `name(...)` — alias resolves the full path.
    if isinstance(func, ast.Name):
        return table.get(func.id)
    # Case: `module.attr(...)`
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        root = func.value.id
        source = table.get(root)
        if source is None:
            return None
        return f"{source}.{func.attr}"
    return None


def _first_arg_starts_with(call: ast.Call, candidate_values: frozenset[str] | set[str]) -> bool:
    """Return ``True`` iff the first positional arg is a list-or-tuple
    literal whose first element is a string in ``candidate_values``, or
    a bare string literal in ``candidate_values``."""

    if not call.args:
        return False
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value in candidate_values
    if isinstance(first, ast.List | ast.Tuple) and first.elts:
        head = first.elts[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return head.value in candidate_values
    return False


def test_check_coverage_respects_library_boundary() -> None:
    source = CHECK_COVERAGE_PY.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CHECK_COVERAGE_PY))

    # Star-import assertion — uniform diagnostic with (a)/(b)/(c).
    assert not _has_star_import(tree), (
        "check_coverage.py uses 'from X import *'; AC8 requires explicit imports"
    )

    alias_table = _build_alias_table(tree)

    # (a) No forbidden import source modules. Module/attribute names
    # are matched at dot-boundaries (see ``_FORBIDDEN_MODULE_RE``) so a
    # future unrelated module containing the substring ``journal`` does
    # not false-positive.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not _FORBIDDEN_MODULE_RE.search(alias.name), (
                    f"AC8(a): check_coverage.py imports {alias.name!r} "
                    "(matches forbidden module pattern)"
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not _FORBIDDEN_MODULE_RE.search(module), (
                f"AC8(a): check_coverage.py uses 'from {module} import ...' "
                "(matches forbidden module pattern)"
            )
            for alias in node.names:
                assert not _FORBIDDEN_MODULE_RE.search(alias.name), (
                    f"AC8(a): check_coverage.py imports {alias.name!r} "
                    f"from {module!r} (matches forbidden module pattern)"
                )

    # (b) and (c): walk every Call node, resolve via alias table.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        resolved = _function_call_resolves_to(node, alias_table)
        if resolved is None:
            continue

        # (b) subprocess.* with first argv element "wiki".
        if resolved.startswith("subprocess.") or resolved == "subprocess":
            assert not _first_arg_starts_with(node, frozenset({"wiki"})), (
                f"AC8(b): check_coverage.py invokes subprocess with "
                f"'wiki' as the first argv element via {resolved!r}; "
                "the check must not spawn user-vault-bound CLI subcommands"
            )

        # (c) cli.main with disallowed verb.
        if resolved.endswith(".cli.main") or resolved == "llm_wiki_kit.cli.main":
            assert not _first_arg_starts_with(node, DISALLOWED_VERBS), (
                f"AC8(c): check_coverage.py invokes {resolved!r} with a "
                f"disallowed verb as the first argv element; the check is "
                f"allowed to import cli but not to drive vault-bound subcommands"
            )
