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
from llm_wiki_kit.doctor import format_issue, run_doctor
from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.ingest import Ambiguous, NoMatch, Routed, route
from llm_wiki_kit.install import install_primitives, validate_contributions
from llm_wiki_kit.journal import append_event, read_events, replay_state
from llm_wiki_kit.models import (
    IngestRoutedEvent,
    Primitive,
    PrimitiveKind,
    Recipe,
    VaultInitEvent,
)
from llm_wiki_kit.primitives import (
    discover_primitives,
    load_primitive,
    resolve_dependencies,
)
from llm_wiki_kit.recipes import CORE_PRIMITIVE_NAME, load_recipe, resolve_recipe_primitives

INSTALL_VEHICLE_INIT = "wiki-init"
INSTALL_VEHICLE_ADD = "wiki-add"
INGEST_VEHICLE = "wiki-ingest"

NOT_IMPLEMENTED_EXIT = 1
WIKI_ERROR_EXIT = 2
DOCTOR_ISSUES_EXIT = 1
INGEST_ROUTE_FAILED_EXIT = 2

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

        # Pre-flight: every primitive's contribution shape must match its
        # on-disk ``regions/`` directory before any state-changing write.
        # ADR-0006 §Mechanics step 6 — fail loudly, not half-installed.
        sources: dict[str, Path] = {
            primitive.name: _primitive_source_dir(primitive, core_dir, templates_dir)
            for primitive in ordered
        }
        for primitive in ordered:
            validate_contributions(primitive, sources[primitive.name])

        target.mkdir(parents=True, exist_ok=True)
        journal_path = target / ".wiki.journal" / "journal.jsonl"
        vault_name = target.name
        context = _build_context(recipe, vault_name)
        now = datetime.now(UTC)

        append_event(
            journal_path,
            VaultInitEvent(
                timestamp=now,
                by=INSTALL_VEHICLE_INIT,
                vault_name=vault_name,
                recipe=recipe.name,
            ),
        )

        # Per-primitive render + the second-pass region aggregator
        # (ADR-0006). ``install_primitives`` runs ``to_install`` ==
        # ``all_installed`` for ``wiki init`` because every primitive in
        # the closure is new to this vault.
        install_primitives(
            to_install=ordered,
            all_installed=ordered,
            sources=sources,
            journal_path=journal_path,
            context=context,
            install_vehicle=INSTALL_VEHICLE_INIT,
            now=now,
        )
    except WikiError as exc:
        print(str(exc), file=sys.stderr)
        return WIKI_ERROR_EXIT

    return 0


def _parse_primitive_spec(spec: str) -> tuple[PrimitiveKind, str]:
    """Split a ``<kind>:<name>`` argument into a validated ``(kind, name)`` pair.

    ``<kind>`` must be one of the four :class:`PrimitiveKind` values in
    its canonical dash form (``ontology``, ``content-type``,
    ``operation``, ``infrastructure``); case-sensitive, per the Task 12
    spec. Anything else is a one-line :class:`WikiError`.
    """

    kind_str, sep, name = spec.partition(":")
    if not sep or not kind_str or not name:
        raise WikiError(f"invalid primitive specifier '{spec}': expected '<kind>:<name>'")
    try:
        kind = PrimitiveKind(kind_str)
    except ValueError as exc:
        valid = ", ".join(k.value for k in PrimitiveKind)
        raise WikiError(f"unknown primitive kind '{kind_str}': expected one of {valid}") from exc
    return kind, name


def _expand_closure(target: Primitive, by_name: dict[str, Primitive]) -> list[Primitive]:
    """Return ``target`` plus its transitive ``requires:`` closure.

    Missing requires raise :class:`WikiError` with the offending name —
    a ``wiki add`` against a catalog the user's kit version doesn't
    carry is a user-facing failure, not an internal one.
    """

    closed: dict[str, Primitive] = {target.name: target}
    pending: list[str] = list(target.requires)
    while pending:
        name = pending.pop()
        if name in closed:
            continue
        primitive = by_name.get(name)
        if primitive is None:
            raise WikiError(
                f"primitive '{target.name}' requires '{name}' which is not in the catalog"
            )
        closed[name] = primitive
        for required in primitive.requires:
            if required not in closed:
                pending.append(required)
    return list(closed.values())


def _cmd_add(args: argparse.Namespace) -> int:
    """Install one primitive (and its requires-closure) into the current vault.

    Operates on the vault rooted at ``Path.cwd()``: the spec scopes
    ``wiki add`` to "the current vault," and the parser deliberately
    takes no path argument. Refuses when there is no
    ``.wiki.journal/journal.jsonl`` to anchor against — ``wiki init``
    is the only way to create a vault.

    The closure is filtered against ``replay_state(...).installed_primitives``
    so a primitive that's already installed is a no-op, and a re-run
    against an already-fully-resolved closure emits no new events. The
    region aggregator still runs against the *full* installed set
    (existing primitives plus the new closure) so a contribution that
    used to live alone in its bucket survives the install — running it
    over only the new additions would clobber the existing body to
    "new-only" (ADR-0006 §Mechanics step 5 plus the Task-12 design
    callout).
    """

    try:
        kind, name = _parse_primitive_spec(args.primitive)

        vault_root = Path.cwd().resolve()
        journal_path = vault_root / ".wiki.journal" / "journal.jsonl"
        if not journal_path.is_file():
            raise WikiError(
                f"not a wiki vault: {vault_root} has no .wiki.journal/journal.jsonl. "
                "Run `wiki init <path> --recipe <name>` first."
            )

        state = replay_state(read_events(journal_path))
        if state.recipe is None or state.vault_name is None:
            raise WikiError(
                f"vault at {vault_root} has no vault.init event; "
                "the journal is incomplete and cannot be extended"
            )

        recipes_dir, core_dir, templates_dir = _kit_paths()
        catalog: list[Primitive] = [load_primitive(core_dir)]
        catalog.extend(discover_primitives(templates_dir))
        by_name: dict[str, Primitive] = {p.name: p for p in catalog}

        target_dir = templates_dir / _KIND_DIRS[kind] / name
        target = load_primitive(target_dir)
        if target.kind != kind:
            raise WikiError(
                f"primitive '{name}' has kind '{target.kind.value}', "
                f"not '{kind.value}' as specified"
            )

        closure_ordered = resolve_dependencies(_expand_closure(target, by_name))
        to_install = [
            primitive
            for primitive in closure_ordered
            if primitive.name not in state.installed_primitives
        ]

        if not to_install:
            # Idempotent re-add: the journal already records every
            # primitive in the closure as installed. No new events, no
            # disk writes — the aggregator pass would emit redundant
            # ``managed_region.write`` events for unchanged bodies.
            return 0

        # The aggregator needs every currently-installed primitive plus
        # the new ones, in topological order, with a source dir for each.
        all_installed_names = set(state.installed_primitives) | {p.name for p in to_install}
        try:
            all_installed_primitives = [by_name[n] for n in all_installed_names]
        except KeyError as exc:
            raise WikiError(
                f"installed primitive '{exc.args[0]}' is not in the kit's "
                "catalog; run `wiki doctor` to inspect"
            ) from exc
        all_installed_ordered = resolve_dependencies(all_installed_primitives)

        sources: dict[str, Path] = {
            primitive.name: _primitive_source_dir(primitive, core_dir, templates_dir)
            for primitive in all_installed_ordered
        }

        # Pre-flight: validate before any state-changing write
        # (ADR-0006 §Mechanics step 6).
        for primitive in to_install:
            validate_contributions(primitive, sources[primitive.name])

        recipe = load_recipe(recipes_dir / f"{state.recipe}.yaml")
        context = _build_context(recipe, state.vault_name)
        now = datetime.now(UTC)

        install_primitives(
            to_install=to_install,
            all_installed=all_installed_ordered,
            sources=sources,
            journal_path=journal_path,
            context=context,
            install_vehicle=INSTALL_VEHICLE_ADD,
            now=now,
        )
    except WikiError as exc:
        print(str(exc), file=sys.stderr)
        return WIKI_ERROR_EXIT

    return 0


def _cmd_upgrade(args: argparse.Namespace) -> int:
    return _stub("upgrade")


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Validate the current vault against its journal and report issues.

    Operates on ``Path.cwd()`` like ``wiki add``. Exit codes split
    cleanly between "found things" (1) and "the run itself failed" (2)
    so a wrapper script (or CI) can distinguish a noisy vault from a
    broken invocation. A reserved ``--json`` flag for machine-readable
    output is deferred to a later task.
    """

    try:
        vault_root = Path.cwd().resolve()
        journal_path = vault_root / ".wiki.journal" / "journal.jsonl"
        if not journal_path.is_file():
            raise WikiError(f"not a wiki vault: {vault_root} has no .wiki.journal/journal.jsonl")

        issues = run_doctor(vault_root, _KIT_ROOT)
    except WikiError as exc:
        print(str(exc), file=sys.stderr)
        return WIKI_ERROR_EXIT

    for issue in issues:
        print(format_issue(issue))

    return DOCTOR_ISSUES_EXIT if issues else 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    """Route ``<source>`` to a content-type primitive and journal the decision.

    Operates on the vault at :func:`Path.cwd`, like ``wiki add`` and
    ``wiki doctor``. The orchestrator is pure (see ``llm_wiki_kit.ingest``);
    this handler is the I/O boundary: load the installed catalog, walk
    routing rules, append one :class:`IngestRoutedEvent`, print a
    one-liner to stdout or stderr, exit. The CLI never invokes Claude or
    fetches the URL — the vault-side ``ingest-<name>/SKILL.md`` does
    that when the user's session picks up the journaled route.
    """

    try:
        vault_root = Path.cwd().resolve()
        journal_path = vault_root / ".wiki.journal" / "journal.jsonl"
        if not journal_path.is_file():
            raise WikiError(
                f"not a wiki vault: {vault_root} has no .wiki.journal/journal.jsonl. "
                "Run `wiki init <path> --recipe <name>` first."
            )

        state = replay_state(read_events(journal_path))

        _, core_dir, templates_dir = _kit_paths()
        catalog: list[Primitive] = [load_primitive(core_dir)]
        catalog.extend(discover_primitives(templates_dir))
        installed = [p for p in catalog if p.name in state.installed_primitives]

        result = route(args.source, installed, as_override=args.as_content_type)

        now = datetime.now(UTC)
        event = _ingest_event_from_result(args.source, result, now)
        append_event(journal_path, event)
    except WikiError as exc:
        print(str(exc), file=sys.stderr)
        return WIKI_ERROR_EXIT

    if isinstance(result, Routed):
        print(
            f"Routed {args.source} -> content-type:{result.content_type}. "
            f"Run `ingest-{result.content_type}` in your Claude session."
        )
        return 0
    if isinstance(result, Ambiguous):
        print(
            f"Ambiguous: {args.source} matched multiple content-types: "
            f"{', '.join(result.candidates)}. Re-run with --as <name>.",
            file=sys.stderr,
        )
        return INGEST_ROUTE_FAILED_EXIT
    # NoMatch
    available = ", ".join(result.available) or "(none installed)"
    print(
        f"No content-type matched {args.source}. Available: {available}. Re-run with --as <name>.",
        file=sys.stderr,
    )
    return INGEST_ROUTE_FAILED_EXIT


def _ingest_event_from_result(
    source: str, result: Routed | Ambiguous | NoMatch, now: datetime
) -> IngestRoutedEvent:
    """Translate a ``RouteResult`` into the journaled event shape.

    Every outcome — single match, ambiguous, no match — produces one
    ``ingest.routed`` line so ``wiki doctor`` and future
    ``journal explain`` can reconstruct what the user tried.
    """

    if isinstance(result, Routed):
        return IngestRoutedEvent(
            timestamp=now,
            by=INGEST_VEHICLE,
            source=source,
            content_type=result.content_type,
            candidates=[result.content_type],
            via=result.via,  # type: ignore[arg-type]
            signals=result.signals,
        )
    if isinstance(result, Ambiguous):
        return IngestRoutedEvent(
            timestamp=now,
            by=INGEST_VEHICLE,
            source=source,
            content_type=None,
            candidates=result.candidates,
            via="auto",
            signals=[],
        )
    return IngestRoutedEvent(
        timestamp=now,
        by=INGEST_VEHICLE,
        source=source,
        content_type=None,
        candidates=[],
        via="auto",
        signals=[],
    )


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
    ingest.add_argument("source", help="Path or URL to ingest, or '-' for stdin.")
    ingest.add_argument(
        "--as",
        dest="as_content_type",
        default=None,
        metavar="<name>",
        help="Override auto-detection with an explicit content-type primitive name.",
    )
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
