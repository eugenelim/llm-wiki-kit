"""The ``wiki`` CLI entry point.

This module wires up the top-level ``wiki`` command and its subcommands. At
this stage in the v2 migration (Task 2), every subcommand is a stub: argparse
accepts the arguments so ``--help`` is usable and CI can exercise the
dispatcher, but the handler exits with status 1 and a "not yet implemented"
notice. Real handlers land in later tasks per RFC-0001.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from llm_wiki_kit import __version__

NOT_IMPLEMENTED_EXIT = 1


def _stub(name: str) -> int:
    print(
        f"wiki {name}: not yet implemented (v2 migration in progress, see RFC-0001).",
        file=sys.stderr,
    )
    return NOT_IMPLEMENTED_EXIT


def _cmd_init(args: argparse.Namespace) -> int:
    return _stub("init")


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
