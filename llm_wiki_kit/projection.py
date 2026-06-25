"""The projection port — the single mechanical write path into a vault.

RFC-0010 decouples *authoring* (what content to produce — a skill's job)
from *projection* (validating it against the faceted schema, resolving
where it lands, and writing it through drift detection + the journal —
the kit's job). This module is the closed, mechanical half: any skill,
kit-native or foreign, hands a finished Markdown artifact (YAML
frontmatter + body) to :func:`project` (reached from the shell as
``wiki project``) and the kit lands it.

The port owns *only* the mechanical chain — parse, validate against the
vault's ``frontmatter.schema.yaml``, resolve a destination, then
:func:`write_helper.safe_write`. The reasoning half — deciding whether a
page belongs in the vault, whether it contradicts an existing page, and
which facts or tasks to propagate — stays the authoring skill's job; it
needs LLM judgment the port cannot mechanize. See
``docs/specs/projection-port/spec.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from llm_wiki_kit.errors import WikiError
from llm_wiki_kit.write_helper import WriteResult, safe_write

# Attribution string for the journal ``by`` field — the writer's identity,
# matching the vehicle constants every other kit writer uses
# (``INGEST_VEHICLE``, ``RESEARCH_VEHICLE``). A caller naming a more
# specific source passes ``by=`` to override it.
PROJECT_VEHICLE = "wiki-project"

# ``genre`` → role folder under ``wiki/``. RFC-0009 /
# ``role-folders-and-containers``: the produced vault has exactly four
# role folders and *kind is the subtype facet, never a folder*. So routing
# keys on ``genre`` (the page's role), never on ``subtype``: a meeting
# (``record``) and a recipe (``record``) both home in ``library/``.
# Container-scoped pages (``efforts/<type>/<instance>/``) are not reachable
# by genre — the caller passes ``--at`` for those.
ROLE_FOLDERS: dict[str, str] = {
    "profile": "people",
    "moc": "atlas",
    "note": "library",
    "record": "library",
    "update": "library",
    "decision": "library",
    "reference": "library",
    "log": "library",
    "contract": "library",
}


@dataclass(frozen=True)
class SchemaFacets:
    """The closed vocabularies the port validates a frontmatter against.

    Loaded from a vault's ``frontmatter.schema.yaml`` by :func:`load_schema`.
    ``subtypes`` is the growable managed-region list; the rest are fixed.
    """

    required: list[str]
    genres: list[str]
    subtypes: list[str]
    statuses: list[str]
    provenances: list[str]


@dataclass(frozen=True)
class ProjectResult:
    """Outcome of a :func:`project` call.

    ``result`` is :data:`write_helper.WriteResult.WRITTEN` on a clean write
    or ``.PROPOSAL`` when drift routed the content to a ``.proposed``
    sidecar. ``dest_rel`` is the vault-relative posix destination.
    """

    result: WriteResult
    dest_rel: str
    dest_abs: Path


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split a ``---``-delimited artifact into ``(frontmatter, body)``.

    Strict, unlike ``search._read_page_metadata``: a missing block,
    an unterminated block, non-mapping frontmatter, or YAML that
    ``yaml.safe_load`` rejects (which includes unsafe tags such as
    ``!!python/object``) each raise :class:`WikiError` rather than
    degrading to an empty dict. The body is returned verbatim.
    """

    if not text.startswith("---\n"):
        raise WikiError("artifact has no YAML frontmatter block (must start with '---')")
    rest = text[4:]
    end = rest.find("\n---\n")
    if end == -1:
        raise WikiError("artifact frontmatter block is not terminated by a '---' line")
    block = rest[:end]
    body = rest[end + len("\n---\n") :]
    try:
        loaded = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise WikiError(f"artifact frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise WikiError("artifact frontmatter must be a YAML mapping")
    return loaded, body


def load_schema(vault_root: Path) -> SchemaFacets:
    """Read and parse the vault's ``frontmatter.schema.yaml``.

    The ``subtypes`` managed-region markers are YAML comments, so
    ``yaml.safe_load`` yields the plain value list with no marker leakage.
    """

    schema_path = vault_root / "frontmatter.schema.yaml"
    if not schema_path.is_file():
        raise WikiError(f"no frontmatter.schema.yaml at vault root {vault_root}")
    try:
        data = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise WikiError(f"frontmatter.schema.yaml is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise WikiError("frontmatter.schema.yaml must be a YAML mapping")

    def _str_list(key: str) -> list[str]:
        value = data.get(key)
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    return SchemaFacets(
        required=_str_list("required"),
        genres=_str_list("genres"),
        subtypes=_str_list("subtypes"),
        statuses=_str_list("statuses"),
        provenances=_str_list("provenance"),
    )


def validate_frontmatter(frontmatter: Mapping[str, object], schema: SchemaFacets) -> None:
    """Reject a frontmatter that violates the faceted schema.

    Raises :class:`WikiError` on the first failure: a missing/empty
    required facet, or a ``genre``/``status``/``provenance``/``subtype``
    value outside its closed vocabulary. A new ``subtype`` is *not* minted
    here — it goes through RFC-0009's human-accept journal gate, so an
    unknown one is rejected.
    """

    for facet in schema.required:
        if facet not in frontmatter or frontmatter[facet] in (None, ""):
            raise WikiError(f"frontmatter missing required facet: {facet!r}")

    # The four enum facets are structurally required by the port — ``genre``
    # drives destination routing, and the schema models all four — so their
    # presence is checked here independently of the vault schema's
    # ``required:`` list. A schema that mis-renders ``required`` then yields a
    # clean WikiError rather than a bare KeyError downstream.
    for facet, allowed, label in (
        ("genre", schema.genres, "genres"),
        ("status", schema.statuses, "statuses"),
        ("provenance", schema.provenances, "provenance values"),
        ("subtype", schema.subtypes, "known subtypes"),
    ):
        if facet not in frontmatter:
            raise WikiError(f"frontmatter missing required facet: {facet!r}")
        value = str(frontmatter[facet])
        if value not in allowed:
            raise WikiError(f"{facet} {value!r} is not in the schema's allowed {label}")


def resolve_vault_path(raw: str, vault_root: Path, *, label: str = "path") -> tuple[str, Path]:
    """Resolve ``raw`` to ``(vault-relative posix, absolute Path)``, confined.

    The one confinement implementation in the kit (moved here from the
    former ``cli._resolve_out_path`` so ``wiki project`` and
    ``wiki research --out`` share it). Rejects absolute paths, ``..``
    escapes, and symlinks that resolve out of the vault tree:
    ``Path.resolve(strict=False)`` follows symlinks in any existing prefix
    even when the leaf doesn't exist yet, and the resolved location must be
    the vault root or a descendant. ``label`` names the offending input in
    the error message (``"--out path"``, ``"--at destination"``, …).
    """

    candidate = Path(raw)
    if candidate.is_absolute():
        raise WikiError(f"{label} must be relative to the vault root: got {raw!r}")
    abs_path = (vault_root / candidate).resolve(strict=False)
    resolved_root = vault_root.resolve()
    try:
        rel = abs_path.relative_to(resolved_root)
    except ValueError as exc:
        raise WikiError(
            f"{label} must resolve under the vault root: "
            f"{raw!r} resolves to {abs_path}, outside {resolved_root}"
        ) from exc
    return rel.as_posix(), abs_path


def resolve_destination(
    genre: str, artifact_name: str, at: str | None, vault_root: Path
) -> tuple[str, Path]:
    """Resolve where a page lands: explicit ``--at``, else ``genre`` routing.

    With ``at`` set, the explicit destination wins (confined through
    :func:`resolve_vault_path`). Otherwise the page homes in
    ``wiki/<role>/<basename>`` where ``<role>`` is :data:`ROLE_FOLDERS` for
    ``genre`` and ``<basename>`` is ``Path(artifact_name).name`` — the
    basename is reduced to its final component (stripping any directory
    parts) and the assembled candidate is *also* confined, so a crafted
    basename cannot escape the role folder. The role folder must already
    exist (only ``wiki init`` / ontology seeds mint one).
    """

    if at is not None:
        return resolve_vault_path(at, vault_root, label="--at destination")

    slug = Path(artifact_name).name
    if slug in ("", ".", ".."):
        raise WikiError(
            f"cannot derive a page name from artifact basename {artifact_name!r}; pass --at"
        )
    if genre not in ROLE_FOLDERS:
        raise WikiError(f"no role-folder route for genre {genre!r}; pass --at")
    role = ROLE_FOLDERS[genre]
    if not (vault_root / "wiki" / role).is_dir():
        raise WikiError(f"vault has no wiki/{role}/ role folder for genre {genre!r}; pass --at")
    return resolve_vault_path(f"wiki/{role}/{slug}", vault_root, label="destination")


def _reserialize(frontmatter: dict[str, object], body: str) -> str:
    """Re-emit a frontmatter block (preserving key order) + verbatim body.

    The frontmatter is re-dumped in canonical YAML form: every key and
    value is preserved *semantically* (and key order, via
    ``sort_keys=False``), but the byte layout is not — quoting style and
    scalar representation normalize on the round-trip. The body is
    byte-identical. Only invoked on an ``--as`` override; absent one, the
    artifact is written verbatim.
    """

    dumped = yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    return f"---\n{dumped}---\n{body}"


def project(
    artifact_path: Path,
    vault_root: Path,
    journal_path: Path,
    *,
    at: str | None = None,
    subtype: str | None = None,
    by: str | None = None,
) -> ProjectResult:
    """Project a finished artifact into the vault through the write contract.

    Parse the artifact's frontmatter + body → optionally set/override the
    ``subtype`` facet (``--as``) → validate against the vault schema →
    resolve the destination → :func:`write_helper.safe_write` (drift
    detection + journal event). Any validation or resolution failure raises
    :class:`WikiError` *before* the write, so a rejected projection leaves
    the vault and journal byte-unchanged.

    On a ``subtype`` override the frontmatter block is re-serialized (key
    order preserved, body verbatim); absent an override the artifact is
    written byte-for-byte.
    """

    try:
        text = artifact_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WikiError(f"cannot read artifact {artifact_path}: {exc}") from exc

    frontmatter, body = parse_frontmatter(text)
    if subtype is not None:
        frontmatter["subtype"] = subtype
        text = _reserialize(frontmatter, body)

    schema = load_schema(vault_root)
    validate_frontmatter(frontmatter, schema)

    genre = str(frontmatter["genre"])
    dest_rel, dest_abs = resolve_destination(genre, artifact_path.name, at, vault_root)

    result = safe_write(dest_abs, text, by=by or PROJECT_VEHICLE, journal_path=journal_path)
    return ProjectResult(result=result, dest_rel=dest_rel, dest_abs=dest_abs)
