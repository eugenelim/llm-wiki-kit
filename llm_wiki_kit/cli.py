"""The ``wiki`` CLI entry point.

This module wires up the top-level ``wiki`` command and its subcommands.
``init`` is the first real handler to land (RFC-0001 Task 10); every other
subcommand is still a stub that exits with status 1 and a "not yet
implemented" notice. Real handlers land in later tasks per RFC-0001.

The CLI boundary catches :class:`WikiError` and prints ``e.args[0]`` to
``stderr`` with exit code 2 so users see a one-line message instead of a
Python traceback. Stubs use exit 1 (sentinel for "not yet implemented"),
which is a different category from a real error.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_kit import __version__
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.journal import append_event
from llm_wiki_kit.models import (
    Primitive,
    PrimitiveInstallEvent,
    PrimitiveKind,
    Recipe,
    VaultInitEvent,
)
from llm_wiki_kit.primitives import discover_primitives, load_primitive
from llm_wiki_kit.recipes import CORE_PRIMITIVE_NAME, load_recipe, resolve_recipe_primitives
from llm_wiki_kit.render import render_tree

NOT_IMPLEMENTED_EXIT = 1
WIKI_ERROR_EXIT = 2

# Where the kit's bundled assets (``recipes/``, ``core/``, ``templates/``)
# live at runtime. We resolve them as siblings of the installed package via
# ``Path(__file__).parent.parent``. This works for the ``pip install -e .``
# checkout that every contributor uses today; under a real wheel install,
# those directories are NOT yet copied into the wheel (see
# ``pyproject.toml`` — ``hatch.build.targets.wheel.packages`` only lists
# ``llm_wiki_kit``). TODO: package the asset dirs via hatchling and switch
# to ``importlib.resources`` before the first wheel release. Pinning the
# simpler approach now keeps Task 10 unblocked on the packaging work.
_KIT_ROOT: Path = Path(__file__).resolve().parent.parent

# Templates-directory layout per ``docs/architecture/overview.md``: each
# ``PrimitiveKind`` maps to a pluralized subdirectory of ``templates/``.
# ``infrastructure`` is uncountable and matches its enum value directly.
_KIND_DIRS: dict[PrimitiveKind, str] = {
    PrimitiveKind.ONTOLOGY: "ontologies",
    PrimitiveKind.CONTENT_TYPE: "content-types",
    PrimitiveKind.OPERATION: "operations",
    PrimitiveKind.INFRASTRUCTURE: "infrastructure",
}


def _stub(name: str) -> int:
    print(
        f"wiki {name}: not yet implemented (v2 migration in progress, see RFC-0001).",
        file=sys.stderr,
    )
    return NOT_IMPLEMENTED_EXIT


def _kit_paths() -> tuple[Path, Path, Path]:
    """Return ``(recipes_dir, core_dir, templates_dir)`` for the running kit."""

    return _KIT_ROOT / "recipes", _KIT_ROOT / "core", _KIT_ROOT / "templates"


def _build_context(recipe: Recipe, vault_name: str) -> dict[str, str]:
    """Compose the render context for a ``wiki init`` invocation.

    Precedence (lower → higher): recipe ``variables:`` defaults, then
    CLI-derived values (``vault_name`` from the target path's basename,
    ``recipe_name`` from ``recipe.name``). CLI-derived values win because
    ``vault_name`` is necessarily per-install and ``recipe_name`` is
    canonically the recipe's declared ``name``; a recipe author cannot
    override either without breaking the journal's identity contract.
    """

    context: dict[str, str] = {}
    context.update(recipe.variables)
    context["vault_name"] = vault_name
    context["recipe_name"] = recipe.name
    return context


def _primitive_source_dir(primitive: Primitive, core_dir: Path, templates_dir: Path) -> Path:
    """Return the on-disk directory that holds ``primitive``'s ``files/`` tree."""

    if primitive.name == CORE_PRIMITIVE_NAME:
        return core_dir
    return templates_dir / _KIND_DIRS[primitive.kind] / primitive.name


def _cmd_init(args: argparse.Namespace) -> int:
    """Render a fresh vault from a recipe.

    Refuses to run against a non-empty target directory. The RFC's
    "unresolved questions" list flagged an ``--adopt`` flag for adopting
    an existing folder as a vault; the decision at Task 10 is to omit
    that flag entirely for now — the design is non-trivial (every
    pre-existing file needs to be journaled before any kit-owned write
    can land safely) and ``wiki upgrade`` will cover the natural re-run
    case. A future task can add ``--adopt`` once its semantics are
    pinned in an ADR.

    Ordering follows ADR-0002: the journal is the source of truth, so
    ``VaultInitEvent`` and each ``PrimitiveInstallEvent`` are appended
    *before* the corresponding filesystem writes. If a write crashes
    mid-install, the journal still reflects the intent and ``wiki
    doctor`` (Task 12) can reconcile.
    """

    try:
        target = Path(args.path).resolve()

        if target.exists() and target.is_file():
            raise WikiError(f"target path is a file, not a directory: {target}")
        if target.exists() and any(target.iterdir()):
            raise WikiError(
                f"target directory is not empty: {target}\n"
                "wiki init refuses to render over existing files. "
                "Choose an empty directory or remove its contents first."
            )

        recipes_dir, core_dir, templates_dir = _kit_paths()
        recipe = load_recipe(recipes_dir / f"{args.recipe}.yaml")
        catalog: list[Primitive] = [load_primitive(core_dir)]
        catalog.extend(discover_primitives(templates_dir))
        ordered = resolve_recipe_primitives(recipe, catalog)

        target.mkdir(parents=True, exist_ok=True)
        journal_path = target / ".wiki.journal" / "journal.jsonl"
        vault_name = target.name
        context = _build_context(recipe, vault_name)
        now = datetime.now(UTC)

        append_event(
            journal_path,
            VaultInitEvent(
                timestamp=now,
                by="wiki-init",
                vault_name=vault_name,
                recipe=recipe.name,
            ),
        )

        for primitive in ordered:
            append_event(
                journal_path,
                PrimitiveInstallEvent(
                    timestamp=now,
                    by="wiki-init",
                    primitive=primitive.name,
                    version=primitive.version,
                ),
            )
            source = _primitive_source_dir(primitive, core_dir, templates_dir)
            render_tree(
                source / "files",
                target,
                context,
                journal_path,
                by=primitive.name,
            )
    except WikiError as exc:
        print(str(exc), file=sys.stderr)
        return WIKI_ERROR_EXIT

    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    return _stub("add")


def _cmd_upgrade(args: argparse.Namespace) -> int:
    return _stub("upgrade")


def _cmd_doctor(args: argparse.Namespace) -> int:
    return _stub("doctor")


def _cmd_ingest(args: argparse.Namespace) -> int:
    return _stub("ingest")


def _cmd_run(args: argparse.Namespace) -> int:
    return _stub("run")


def _cmd_research(args: argparse.Namespace) -> int:
    return _stub("research")


def _cmd_search(args: argparse.Namespace) -> int:
    return _stub("search")


def _cmd_journal_tail(args: argparse.Namespace) -> int:
    return _stub("journal tail")


def _cmd_journal_grep(args: argparse.Namespace) -> int:
    return _stub("journal grep")


def _cmd_journal_explain(args: argparse.Namespace) -> int:
    return _stub("journal explain")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki",
        description="Build and maintain an LLM-readable markdown wiki.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    init = subparsers.add_parser("init", help="Create a new vault from a recipe.")
    init.add_argument("path", help="Directory to create the vault in.")
    init.add_argument(
        "--recipe", required=True, help="Recipe name (e.g. family, work-os, personal)."
    )
    init.set_defaults(func=_cmd_init)

    add = subparsers.add_parser("add", help="Install a primitive into the current vault.")
    add.add_argument(
        "primitive",
        help="Primitive in the form <kind>:<name> (e.g. content-type:interview).",
    )
    add.set_defaults(func=_cmd_add)

    upgrade = subparsers.add_parser(
        "upgrade", help="Upgrade installed primitives to their latest versions."
    )
    upgrade.add_argument(
        "--primitive",
        help="Restrict the upgrade to a single primitive (default: all installed).",
    )
    upgrade.set_defaults(func=_cmd_upgrade)

    doctor = subparsers.add_parser("doctor", help="Validate vault state against the journal.")
    doctor.set_defaults(func=_cmd_doctor)

    ingest = subparsers.add_parser(
        "ingest", help="Route source material to the right content-type ingester."
    )
    ingest.add_argument("source", help="Path or URL to ingest.")
    ingest.set_defaults(func=_cmd_ingest)

    run = subparsers.add_parser("run", help="Run a named operation.")
    run.add_argument("operation", help="Operation name (e.g. weekly-digest).")
    run.set_defaults(func=_cmd_run)

    research = subparsers.add_parser(
        "research", help="Dispatch a query to a configured research provider."
    )
    research.add_argument("query", help="The research query.")
    research.set_defaults(func=_cmd_research)

    search = subparsers.add_parser("search", help="Search the vault (ripgrep / FTS5 backend).")
    search.add_argument("query", help="The search query.")
    search.set_defaults(func=_cmd_search)

    journal = subparsers.add_parser("journal", help="Read the vault journal.")
    journal_sub = journal.add_subparsers(dest="journal_command", metavar="<subcommand>")
    journal_sub.required = True

    journal_tail = journal_sub.add_parser("tail", help="Show the most recent events.")
    journal_tail.add_argument(
        "-n", "--lines", type=int, default=10, help="Number of events to show."
    )
    journal_tail.set_defaults(func=_cmd_journal_tail)

    journal_grep = journal_sub.add_parser("grep", help="Filter journal events by pattern.")
    journal_grep.add_argument("pattern", help="Pattern to match against event payloads.")
    journal_grep.set_defaults(func=_cmd_journal_grep)

    journal_explain = journal_sub.add_parser(
        "explain", help="Explain a specific journal event in plain language."
    )
    journal_explain.add_argument("event_id", help="Event ID to explain.")
    journal_explain.set_defaults(func=_cmd_journal_explain)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = args.func
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
