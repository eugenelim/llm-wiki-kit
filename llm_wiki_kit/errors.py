"""Kit-side exceptions.

ADR-0005 requires every kit error to be a ``WikiError`` subclass so the CLI
boundary can catch one base type and render a human-readable message instead
of leaking a Python traceback. ``ValidationError`` wraps Pydantic's structured
errors; ``JournalCorruptError`` is raised by ``journal.read_events`` when a
JSONL line fails to parse or validate.
"""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError


class WikiError(Exception):
    """Base class for every error the kit raises to the CLI boundary."""


class ValidationError(WikiError):
    """Human-readable wrapper around ``pydantic.ValidationError``.

    Renders one line per field error in the form
    ``Invalid <thing> at <dotted.path>: <message>``.
    """

    def __init__(self, thing: str, pydantic_error: PydanticValidationError) -> None:
        self.thing = thing
        self.pydantic_error = pydantic_error
        super().__init__(self._format(thing, pydantic_error))

    @staticmethod
    def _format(thing: str, pydantic_error: PydanticValidationError) -> str:
        lines: list[str] = []
        for err in pydantic_error.errors():
            loc = ".".join(str(part) for part in err.get("loc", ()))
            msg = err.get("msg", "invalid value")
            if loc:
                lines.append(f"Invalid {thing} at {loc}: {msg}")
            else:
                lines.append(f"Invalid {thing}: {msg}")
        return "\n".join(lines) if lines else f"Invalid {thing}"


class JournalCorruptError(WikiError):
    """Raised on the first malformed line in ``.wiki.journal/journal.jsonl``.

    Carries the 1-based line number so ``wiki doctor`` and ``wiki journal``
    can point the user (or Claude) at the exact line to repair.
    """

    def __init__(self, line: int, reason: str) -> None:
        self.line = line
        self.reason = reason
        super().__init__(f"Journal corrupt at line {line}: {reason}")


class ManagedRegionError(WikiError):
    """Raised by ``managed_regions`` on malformed input or missing regions.

    Covers nesting, unmatched / unclosed markers, duplicate region ids in
    the same file (ADR-0003 §Consequences: region ids are part of the
    public contract), and ``update`` calls naming a region the file
    doesn't contain.
    """


class PrimitiveError(WikiError):
    """Raised by ``primitives`` for non-schema failures.

    Schema failures (a malformed ``primitive.yaml`` field) flow through
    :class:`ValidationError` so Pydantic's structured errors stay legible.
    This class covers the kit-side concerns the migration plan calls out:
    a missing primitive directory or manifest, malformed YAML, a closed
    set passed to :func:`primitives.resolve_dependencies` that references
    a primitive it doesn't contain, a duplicate primitive name in the
    same set, and ``requires:`` cycles.
    """
