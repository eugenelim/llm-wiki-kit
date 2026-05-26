"""Pydantic v2 models for everything in the kit that crosses disk.

ADR-0005 names the rule: every type read from or written to disk lives here,
in-memory plumbing stays in plain dataclasses or function signatures. The
journal's ``Event`` is a Pydantic discriminated union with one class per
event type so the JSONL parser can dispatch on a single literal field.

The event taxonomy lines up with the namespaces called out in
``docs/architecture/overview.md`` (``vault.*``, ``primitive.*``,
``managed_region.*``, ``source.*``, ``page.*``, ``operation.*``,
``research.*``, ``lint.*``, ``config.*``). New event types are added by
appending one class and one entry to ``Event``; defaults are required on
new fields so older journal lines keep replaying (ADR-0002).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, RootModel, model_validator

# Load-bearing for ``git_init.initialize_git``'s commit-message argv — the
# recipe name is interpolated into ``"Initialize wiki vault from <recipe>
# recipe"`` and passed as a single argv element to ``git commit -m`` with
# ``shell=False``. The ``[a-z][a-z0-9-]*`` pattern keeps the name shell-safe
# without quoting concerns. Any future relaxation must audit
# ``llm_wiki_kit/git_init.py`` per ``docs/specs/wiki-init-git/spec.md``
# §Behavior step 6.
NAME_PATTERN = r"^[a-z][a-z0-9-]*$"
SEMVER_PATTERN = r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$"


class _StrictModel(BaseModel):
    """Base for every disk-bound model.

    ``extra="forbid"`` catches typos in hand-edited YAML before they become
    silent no-ops; that's why the migration plan picks Pydantic in the first
    place (ADR-0005).
    """

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Primitive
# ---------------------------------------------------------------------------


class PrimitiveKind(StrEnum):
    ONTOLOGY = "ontology"
    CONTENT_TYPE = "content-type"
    OPERATION = "operation"
    INFRASTRUCTURE = "infrastructure"
    AGENT = "agent"


class Contribution(_StrictModel):
    """A primitive's write into a managed region of a shared file (ADR-0003)."""

    file: str
    region: str


class PrimitiveRouting(_StrictModel):
    """Auto-routing rules for ``wiki ingest`` (Task 16).

    Only meaningful on content-type primitives. Every list is optional; an
    empty ``PrimitiveRouting`` is the same as having no ``routing:`` block at
    all — the primitive is only reachable via ``wiki ingest --as <name>``.

    Pattern semantics: ``filename_patterns``, ``url_domains``, and
    ``url_path_patterns`` are matched with ``fnmatch`` (case-insensitive).
    ``file_extensions`` are compared case-insensitively against the
    suffix including the leading dot (``".pdf"``, not ``"pdf"``).
    """

    file_extensions: list[str] = Field(default_factory=list)
    filename_patterns: list[str] = Field(default_factory=list)
    url_domains: list[str] = Field(default_factory=list)
    url_path_patterns: list[str] = Field(default_factory=list)


#: Supported ``primitive.yaml`` schema version range. The kit reads exactly
#: ``schema_version: 1`` today (per ``docs/specs/primitive-sideload/spec.md``
#: §"Schema versioning (v1 freeze)"). A future major bump may add ``2`` and
#: read both during a stated deprecation window; the error message in
#: :meth:`Primitive._enforce_schema_version` cites this constant verbatim.
SUPPORTED_PRIMITIVE_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})


class Primitive(_StrictModel):
    """The schema of a ``primitive.yaml`` manifest.

    A primitive instance carries three loader-populated pieces of metadata
    that do not appear in ``primitive.yaml``:

    * :attr:`source` — ``"bundled"`` for primitives loaded from the kit's
      own ``templates/`` tree, ``"sideload:<package>"`` for primitives
      discovered via the ``wiki-primitive`` entry-point group
      (``docs/specs/primitive-sideload/spec.md`` §"Contracts with other
      modules"). Excluded from ``model_dump()`` output so the journal
      and any other declarative-shape serialiser sees only what the
      author wrote.
    * :attr:`_source_dir` — the on-disk directory containing this
      primitive's ``primitive.yaml`` (and its ``files/``, ``regions/``,
      ``contract.yaml``, …). Populated by the loader; consumers that
      build a ``sources`` mapping for the install pipeline read it
      directly so the same code path handles bundled and sideloaded
      primitives identically.
    * :attr:`_dropped_fields` — names of unknown top-level fields
      stripped during :meth:`from_sideload` construction (always empty
      for bundled primitives, which load via ``extra='forbid'`` and
      would have raised). Surfaced by ``wiki doctor`` as a soft
      warning.
    """

    name: str = Field(pattern=NAME_PATTERN)
    kind: PrimitiveKind
    version: str = Field(pattern=SEMVER_PATTERN)
    description: str
    requires: list[str] = Field(default_factory=list)
    contributes_to: list[Contribution] = Field(default_factory=list)
    routing: PrimitiveRouting | None = None
    config: dict[str, object] = Field(default_factory=dict)
    # Schema versioning per ``docs/specs/primitive-sideload/spec.md``
    # §"Schema versioning". Field default keeps every existing
    # ``primitive.yaml`` parseable without touching disk; the validator
    # below rejects any value the current kit does not support, with a
    # message symmetric between bundled and sideloaded sources.
    schema_version: int = 1
    # Loader-populated source attribution. ``exclude=True`` keeps it out
    # of ``model_dump()`` so the journal's primitive-install events
    # continue to serialise primitives as their declarative shape. The
    # default of ``"bundled"`` means a primitive constructed directly
    # via ``Primitive.model_validate(...)`` (today's bundled-load path)
    # is correctly tagged without any loader change.
    #
    # The Pattern constraint rejects any out-of-vocabulary value at
    # parse time, defending against a hand-edited bundled
    # ``primitive.yaml`` that accidentally (or maliciously) ships a
    # ``source:`` line. The loader path overrides the value after
    # construction so the post-validation field is always correct in
    # practice, but the pattern surfaces the typo before the override
    # silently swallows it.
    source: str = Field(
        default="bundled",
        exclude=True,
        pattern=r"^(bundled|sideload:[A-Za-z0-9][A-Za-z0-9._-]*)$",
    )

    # PrivateAttr so the field is not part of the Pydantic schema at
    # all — the loader sets it after construction, and consumers read
    # it directly. None for primitives constructed via ``model_validate``
    # without a follow-up loader assignment (mostly tests); the install
    # pipeline tolerates None by falling back to the
    # ``templates/<kind>/<name>`` shape per ``_primitive_source_dir``.
    _source_dir: Path | None = PrivateAttr(default=None)
    _dropped_fields: tuple[str, ...] = PrivateAttr(default=())

    @model_validator(mode="after")
    def _enforce_schema_version(self) -> Self:
        if self.schema_version not in SUPPORTED_PRIMITIVE_SCHEMA_VERSIONS:
            supported = ", ".join(str(v) for v in sorted(SUPPORTED_PRIMITIVE_SCHEMA_VERSIONS))
            raise ValueError(
                f"primitive.yaml schema_version {self.schema_version} is not "
                f"supported by this kit; supported: {supported}"
            )
        return self

    @model_validator(mode="after")
    def _routing_only_on_content_types(self) -> Self:
        if self.routing is not None and self.kind is not PrimitiveKind.CONTENT_TYPE:
            raise ValueError(
                f"primitive '{self.name}' declares routing but kind is "
                f"'{self.kind.value}'; routing is only valid on content-type primitives"
            )
        return self

    @classmethod
    def from_sideload(
        cls,
        data: dict[str, Any],
        *,
        source: str,
    ) -> Primitive:
        """Construct a sideloaded primitive with ``extra='ignore'`` semantics.

        Parallel constructor to :meth:`model_validate` for primitives
        discovered via the ``wiki-primitive`` entry-point group
        (``docs/specs/primitive-sideload/spec.md`` §"Source-scoped
        extra-field policy"). Computes the set of unknown top-level
        and nested field names against the known schema, strips them
        from a shallow copy of ``data``, then delegates to
        :meth:`model_validate` against the stripped dict so the
        existing field validators (kind enum, schema_version,
        routing-on-content-type) all fire identically. Dropped names
        are captured on the instance as ``_dropped_fields`` so
        ``wiki doctor`` can surface them as a soft warning.

        The pre-strip-then-validate shape is what preserves the
        single-hierarchy invariant the spec pins: the nested
        ``Contribution`` and ``PrimitiveRouting`` classes remain
        ``_StrictModel``s with ``extra='forbid'``, and the call sites
        that do ``isinstance(c, Contribution)`` keep working without
        a parallel ``ContributionLax`` class.
        """

        if not isinstance(data, dict):
            raise TypeError(
                f"Primitive.from_sideload expected a mapping, got {type(data).__name__}"
            )

        primitive_fields = set(cls.model_fields)
        contribution_fields = set(Contribution.model_fields)
        routing_fields = set(PrimitiveRouting.model_fields)

        dropped: list[str] = []
        for key in sorted(data.keys()):
            if key not in primitive_fields:
                dropped.append(key)

        # ``raw_contributes`` and ``raw_routing`` are inspected only for
        # nested unknown-field capture and downstream pre-stripping. The
        # checks below use ``isinstance(... , list/dict)`` rather than
        # ``or []`` / ``or {}`` so explicit ``contributes_to: null`` or
        # ``routing: null`` flows through to Pydantic unchanged — the
        # validator there decides whether ``None`` is acceptable for the
        # field, which preserves bundled-vs-sideload validation symmetry
        # on the same on-disk file.
        raw_contributes = data.get("contributes_to")
        if isinstance(raw_contributes, list):
            for index, entry in enumerate(raw_contributes):
                if isinstance(entry, dict):
                    for nested_key in sorted(entry.keys()):
                        if nested_key not in contribution_fields:
                            dropped.append(f"contributes_to[{index}].{nested_key}")

        raw_routing = data.get("routing")
        if isinstance(raw_routing, dict):
            for nested_key in sorted(raw_routing.keys()):
                if nested_key not in routing_fields:
                    dropped.append(f"routing.{nested_key}")

        stripped: dict[str, Any] = {k: v for k, v in data.items() if k in primitive_fields}
        if isinstance(raw_contributes, list):
            stripped["contributes_to"] = [
                {k: v for k, v in entry.items() if k in contribution_fields}
                if isinstance(entry, dict)
                else entry
                for entry in raw_contributes
            ]
        if isinstance(raw_routing, dict):
            stripped["routing"] = {k: v for k, v in raw_routing.items() if k in routing_fields}

        primitive = cls.model_validate(stripped)
        primitive.source = source
        primitive._dropped_fields = tuple(dropped)
        return primitive


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------


class AgentBinding(_StrictModel):
    """One entry inside a recipe's ``agents:`` block.

    ``runs`` is the required list of operation primitive names this
    agent is the preferred dispatcher for in the recipe. The
    ``min_length=1`` constraint pins ``docs/specs/wiki-agents/spec.md``
    CT-6: an empty list is a recipe-author bug (a recipe declaring an
    agent with no operations is dead weight) and Pydantic rejects it
    at recipe-load time, *before* the closure-walk validator
    (CT-3 / CT-4 / CT-5) runs. The two validation layers are distinct
    and must not be consolidated — load-shape vs. recipe-semantics.

    Names inside ``runs`` are pattern-validated against
    :data:`NAME_PATTERN` at the Pydantic layer per ``spec.md``
    §"Contracts with other modules". This catches authoring typos
    (capitals, underscores) at recipe-load before the closure walk
    runs; the closure walk then cross-checks each name against the
    resolved catalog. The two checks are complementary — Pydantic
    rejects illegal shapes, the closure walk rejects unbound names.
    """

    runs: list[Annotated[str, Field(pattern=NAME_PATTERN)]] = Field(min_length=1)


class Recipe(_StrictModel):
    """The schema of a ``recipes/<name>.yaml`` file."""

    name: str = Field(pattern=NAME_PATTERN)
    version: str = Field(pattern=SEMVER_PATTERN)
    description: str
    primitives: list[str]
    variables: dict[str, str] = Field(default_factory=dict)
    # Additive per ADR-0002: absent or ``{}`` is the v2.0.0 baseline
    # ("no agent bindings"). The closure-walk validator in
    # :mod:`llm_wiki_kit.recipes` cross-checks every key and every
    # operation against the recipe's resolved primitives closure; see
    # ``docs/specs/wiki-agents/spec.md`` §Inputs §"Recipe surface".
    agents: dict[str, AgentBinding] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Operation contract
# ---------------------------------------------------------------------------


class OperationInputSpec(_StrictModel):
    """Per-input declaration inside an operation's ``contract.yaml``.

    Captures the on-disk shape used across the shipped catalog:
    every input has a ``type`` tag; the rest is optional. Field set
    pinned in ``docs/specs/task-17-wiki-run/spec.md`` §Contracts.

    ``type`` values seen in production: ``string``, ``iso_week``,
    ``list``, ``integer``, ``int`` (alias for integer), ``boolean``,
    and ``page`` (used by ``trip-prep``). Unknown values are
    accepted at the schema level; coercion in
    :mod:`llm_wiki_kit.run` decides what to do with them.

    ``default: None`` (Python ``None``, either from an absent
    ``default:`` key or an explicit ``default: null``) means "no
    default applied" — see spec §Behavior step 8.
    """

    type: str
    description: str | None = None
    default: object | None = None
    optional: bool = False
    items: str | None = None


class OperationContract(_StrictModel):
    """The schema of an operation primitive's ``contract.yaml``.

    ``outcomes`` declares human-readable verbs that map back to this
    operation (per ``docs/specs/outcome-named-entry-points/spec.md``
    §Inputs §1). Each verb is validated by
    :func:`llm_wiki_kit.primitives.is_well_formed_outcome_verb` at
    catalog-load time and surfaces via three derived surfaces (CLI
    alias, Claude Code slash stub, SKILL trigger fragment). An
    omitted or empty ``outcomes:`` field is the v2.0.0 baseline —
    the operation is reachable only through ``wiki run <name>``.
    """

    name: str = Field(pattern=NAME_PATTERN)
    description: str
    period: str | None = None
    skill: str | None = None
    outcomes: list[str] = Field(default_factory=list)
    inputs: dict[str, OperationInputSpec] = Field(default_factory=dict)
    outputs: dict[str, object] = Field(default_factory=dict)
    # Optional per-contract default fire time for the wiki-schedule verb's
    # default cadence (see ``docs/specs/wiki-schedule/spec.md`` §Inputs).
    # Zero-padded HH:MM, 00:00-23:59. ``None`` falls back to the
    # ``DEFAULT_TIME_BY_PERIOD`` table in ``schedule/dsl.py``. Additive per
    # ADR-0002 §Negative — existing contracts that omit the field validate
    # unchanged.
    default_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    # Optional operation-author hint for the agent resolution chain
    # (``docs/specs/wiki-agents/spec.md`` §"Resolution chain"). Used at
    # step 3 of the chain when no CLI flag and no recipe binding
    # resolve. ``None`` is the v2.0.0 baseline — the operation author
    # makes no agent suggestion. Names validate against ``NAME_PATTERN``
    # at contract-load (CT-7); cross-checking against the installed
    # primitive set happens at chain-resolution time, not here.
    preferred_agent: str | None = Field(default=None, pattern=NAME_PATTERN)


# ---------------------------------------------------------------------------
# Research providers config (ADR-0003 managed region body)
# ---------------------------------------------------------------------------


class ProviderConfig(_StrictModel):
    """One provider's block inside ``research-providers.yaml``.

    Each ``infrastructure:research-*`` primitive contributes one of
    these into the ``providers`` managed region of the shared config.
    ``api_key_env`` is schema-optional so future providers (e.g. Task
    19's Semantic Scholar, which works without a key) can omit it;
    per-provider code (e.g. Perplexity's ``dispatch``) enforces its
    own requirement. See ``docs/specs/task-18-research-perplexity/spec.md``
    §"ProviderConfig schema".
    """

    api_key_env: str | None = None
    endpoint: str | None = None
    model: str | None = None
    cost_signal: Literal["free", "low", "medium", "high"] | None = None
    strengths: list[str] = Field(default_factory=list)


class ResearchProvidersConfig(RootModel[dict[str, ProviderConfig]]):
    """The shape of the ``providers`` managed region in ``research-providers.yaml``.

    A flat mapping ``<provider_slug>: ProviderConfig`` — no wrapping
    ``providers:`` key. The dispatcher reads only the managed-region
    body (via ``managed_regions.parse``) and YAML-loads that slice;
    text outside the markers is preserved on disk (ADR-0003) but
    ignored here.

    The root-model shape means any string key becomes a candidate
    provider slug. Unknown *inner* keys on a ``ProviderConfig`` block
    (e.g. ``endpiont:`` typo) are rejected by ``_StrictModel``'s
    ``extra="forbid"``; an unknown slug whose implementation isn't
    registered is caught separately by the dispatcher's
    "no implementation" path.
    """

    def slugs(self) -> list[str]:
        """Return installed provider slugs in sorted order."""

        return sorted(self.root.keys())


# ---------------------------------------------------------------------------
# Journal events
# ---------------------------------------------------------------------------


class _EventBase(_StrictModel):
    """Fields every journal event carries."""

    timestamp: datetime
    by: str


class VaultInitEvent(_EventBase):
    type: Literal["vault.init"] = "vault.init"
    vault_name: str
    recipe: str
    schema_version: int = 1


class VaultGitInitializedEvent(_EventBase):
    """Recorded when ``wiki init`` initializes a git repo for the vault.

    The event is appended between ``git init`` and ``git add -A`` /
    ``git commit`` so its journal line is captured by the initial
    commit's tree, leaving ``git status --porcelain`` empty after a
    successful ``wiki init``. Carries no ``commit_sha`` or ``branch``
    — see ``docs/specs/wiki-init-git/spec.md`` §Outputs for the
    rationale (recording the SHA would require either two commits or
    a journal-ahead-of-HEAD state).
    """

    type: Literal["vault.git_initialized"] = "vault.git_initialized"
    schema_version: int = 1


class PrimitiveInstallEvent(_EventBase):
    """Recorded when the install pipeline lands a primitive's files into a vault.

    ``source`` is additive per ADR-0002 / ``docs/specs/primitive-
    sideload/spec.md``. The kit's JSON serialiser writes the field on
    every install (``"source": null`` for bundled, ``"source":
    "sideload:<package>"`` for sideloaded) — older journal lines
    written before this field landed lack the key entirely and replay
    cleanly via the model's ``None`` default, so the field is
    backward-compatible at replay even though it does add bytes to
    newly-written lines. The label is what lets ``wiki doctor`` hint at
    the previously-installed package after a sideload uninstall (spec
    AC17). The field does *not* extend ``by`` semantics — ``by``
    continues to name the install vehicle (``"wiki-init"`` /
    ``"wiki-add"``), matching every other event in the journal.
    """

    type: Literal["primitive.install"] = "primitive.install"
    primitive: str
    version: str
    source: str | None = None


class PrimitiveRemoveEvent(_EventBase):
    type: Literal["primitive.remove"] = "primitive.remove"
    primitive: str


class PrimitiveUpgradeEvent(_EventBase):
    type: Literal["primitive.upgrade"] = "primitive.upgrade"
    primitive: str
    from_version: str
    to_version: str


class PrimitiveForceRenderEvent(_EventBase):
    """Audit row recorded by ``wiki upgrade --force-render``.

    Marker event for "the runner re-walked this primitive's closure to
    heal a partial install" — distinct from :class:`PrimitiveUpgradeEvent`
    so a grep over ``primitive.force_render`` rows surfaces only
    re-render runs, not catalog-version bumps. No version transition is
    recorded (``version`` is the installed version, unchanged across the
    run). The class participates in the discriminated ``Event`` union as
    a pure audit row — ``replay_state`` treats it as a no-op (no
    contribution to ``VaultState.installed_primitives`` or any other
    derived field). See ``docs/specs/wiki-upgrade-force-render/spec.md``.
    """

    type: Literal["primitive.force_render"] = "primitive.force_render"
    primitive: str
    version: str


class ManagedRegionWriteEvent(_EventBase):
    type: Literal["managed_region.write"] = "managed_region.write"
    file: str
    region: str
    content_hash: str
    hash_algo: str = "sha256"


class ManagedRegionAdoptedEvent(_EventBase):
    """Region-scope seed baseline for a pre-existing managed-region host file.

    Payload mirrors :class:`ManagedRegionWriteEvent` (``file``,
    ``region``, ``content_hash``, ``hash_algo``); the discriminator
    differs so ``safe_write_region``'s adopt-aware predicate (PR-B)
    can route differing-content kit writes to the proposal branch.
    The aggregator (ADR-0006) treats this as a normal baseline via
    ``_managed_region_baseline_hash``'s class-agnostic walk. See
    ADR-0008 §Decision sub-choice 3.
    """

    type: Literal["managed_region.adopted"] = "managed_region.adopted"
    file: str
    region: str
    content_hash: str
    hash_algo: str = "sha256"


class IngestRoutedEvent(_EventBase):
    """Recorded by ``wiki ingest`` after the orchestrator picks a route.

    Written on every outcome — single match, ambiguous, and no match —
    so ``wiki doctor`` and (future) ``journal explain`` can reconstruct
    what the user tried. Successful synthesis is recorded separately
    by :class:`SourceIngestEvent` after the vault-side ingester writes
    its pages.
    """

    type: Literal["ingest.routed"] = "ingest.routed"
    source: str
    content_type: str | None = None
    candidates: list[str] = Field(default_factory=list)
    via: Literal["auto", "as_flag"] = "auto"
    signals: list[str] = Field(default_factory=list)


class SourceIngestEvent(_EventBase):
    type: Literal["source.ingest"] = "source.ingest"
    source: str
    source_hash: str
    content_type: str
    produced_pages: list[str] = Field(default_factory=list)


class PageWriteEvent(_EventBase):
    type: Literal["page.write"] = "page.write"
    path: str
    hash: str
    hash_algo: str = "sha256"


class PageAdoptedEvent(_EventBase):
    """Seed baseline for a pre-existing kit-owned file under ``wiki init --adopt``.

    Payload mirrors :class:`PageWriteEvent` (``path``, ``hash``,
    ``hash_algo``); the discriminator differs so ``safe_write``'s
    adopt-aware predicate (PR-B) and ``wiki journal tail`` can
    distinguish "kit adopted the user's existing bytes" from "kit
    wrote this file." See ADR-0008 §Decision sub-choice 3 and
    ``docs/specs/wiki-init-adopt/spec.md`` §Outputs Journal events.
    """

    type: Literal["page.adopted"] = "page.adopted"
    path: str
    hash: str
    hash_algo: str = "sha256"


class PageProposalEvent(_EventBase):
    """Recorded when ``safe_write`` lands a ``.proposed`` sidecar.

    ``proposed_by_agent`` is additive per ADR-0002 / RFC-0004 wiki-agents
    PR-6: when a scheduled / agent-bound dispatch produces the proposal,
    the resolved agent name is journaled here so the vault-side
    ``wiki-conflict`` SKILL can name the agent in the user-facing prose
    (see ``docs/specs/wiki-agents/spec.md`` §"Conflict-aware UX (vault-side
    SKILL)"). ``None`` is both the pre-RFC-4 baseline (no field on the
    JSON line) and the explicit "no agent declared" outcome — replay
    treats them identically. Pattern-validated against ``NAME_PATTERN``
    for symmetry with other agent-name fields; the kit does not
    cross-check against the installed-primitive set here (consumers
    that care about kind/install do so at their own boundary).
    """

    type: Literal["page.proposal"] = "page.proposal"
    path: str
    proposed_path: str
    hash: str
    hash_algo: str = "sha256"
    proposed_by_agent: str | None = Field(default=None, pattern=NAME_PATTERN)


class PageConflictResolvedEvent(_EventBase):
    type: Literal["page.conflict_resolved"] = "page.conflict_resolved"
    path: str
    hash: str
    hash_algo: str = "sha256"
    # Optional managed-region label for per-region audit (retro-review C1).
    # ``None`` for whole-file resolves; older journal lines replay unchanged
    # under ADR-0002 §Negative's additive-schema rule.
    region: str | None = None


class OperationRunEvent(_EventBase):
    """Recorded by ``wiki run`` on every invocation that gets past the
    contract-load step (``docs/specs/task-17-wiki-run/spec.md``).

    ``args``, ``error``, and ``event_id`` are additive extensions per
    ADR-0002 §Negative's additive-schema rule — all have defaults so
    older journal lines (Task 3) keep replaying unchanged. ``status``
    is a Literal-bounded enum: pre-Task-17 lines could only have
    carried ``"dispatched"`` (no other emitter existed), so the
    narrowing rejects no legitimate legacy value.

    ``event_id`` is populated by ``run.dispatch`` via
    ``uuid.uuid4().hex[:12]`` for every new event. Older journal
    lines (no ``event_id`` key) replay with ``event_id is None``;
    the wiki-run-exec spec is the only consumer at v1 and tolerates
    that absence. See ``docs/specs/wiki-run-exec/spec.md`` §"Event
    identity".
    """

    type: Literal["operation.run"] = "operation.run"
    operation: str
    status: Literal["dispatched", "invalid_args"]
    period: str | None = None
    produced_pages: list[str] = Field(default_factory=list)
    args: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    event_id: str | None = None


class OperationRunByAgentEvent(_EventBase):
    """Audit tag recorded alongside ``OperationRunEvent`` when an agent name resolved.

    Appended by ``wiki run --exec`` (and dispatch-only ``wiki run`` when
    ``--agent`` is passed explicitly) inside the same
    ``journal.transaction(...)`` as the paired ``OperationRunEvent``, so
    the two events land atomic-or-neither under the journal flock. The
    ``event_id`` carries the paired ``OperationRunEvent.event_id`` so
    replay can join them; see ``docs/specs/wiki-agents/spec.md``
    §Invariants.

    No event is appended when no agent resolves — preserves the
    no-event-on-no-agent shape for backward compatibility (ADR-0002
    §Negative's additive-schema rule covers the migration).
    """

    type: Literal["operation.run_by_agent"] = "operation.run_by_agent"
    operation: str
    agent: str
    event_id: str


class OperationExecFailedEvent(_EventBase):
    """Recorded by ``wiki run --exec`` when the subprocess attempt fails.

    Four failure shapes (see ``docs/specs/wiki-run-exec/spec.md``
    §Outputs):

    - ``non-zero-exit`` — Claude exited with a non-zero return code.
    - ``timeout`` — the subprocess was killed after
      ``WIKI_EXEC_TIMEOUT`` seconds. ``exit_code`` is the sentinel
      ``-2``.
    - ``conflict-refused`` — the kit refused to spawn the subprocess
      because the vault has unresolved ``.proposed`` sidecars.
      ``exit_code`` is ``-1``, ``stderr_tail`` is empty, sidecar
      paths live in ``conflict_sidecars``.
    - ``agent-missing`` — the resolved agent name (CLI flag, recipe
      binding, schedule artifact's frozen ``--agent``, or contract
      ``preferred_agent``) is not installed as a ``kind: agent``
      primitive at exec time. The kit refuses to spawn; ``exit_code``
      is ``-3``, ``stderr_tail`` and ``log_path`` are unset. Added
      additively per ADR-0002 by ``docs/specs/wiki-agents/spec.md``
      §Outputs and amended into ``wiki-run-exec/spec.md``
      §"Contracts with other modules" in the same PR.

    Two reserved reasons (``binary-missing``, ``skill-missing``)
    appear in the Literal but are **not emitted at v1** — those
    failure modes raise ``WikiError`` before reaching the journal
    append. ``_append_failure_event`` enforces this with a
    ``RuntimeError`` guard.
    """

    type: Literal["operation.exec_failed"] = "operation.exec_failed"
    operation: str
    dispatch_event_id: str
    exit_code: int
    reason: Literal[
        "non-zero-exit",
        "timeout",
        "conflict-refused",
        "binary-missing",
        "skill-missing",
        "agent-missing",
    ]
    stderr_tail: str = ""
    log_path: str | None = None
    conflict_sidecars: list[str] = Field(default_factory=list)


class ResearchQueryEvent(_EventBase):
    """Recorded by ``wiki research`` on every dispatch attempt.

    Task 18 extended the original shape with two optional fields with
    defaults so older journal lines keep replaying (ADR-0002 additive-
    schema invariant). See ``docs/specs/task-18-research-perplexity/spec.md``
    §"To the journal".
    """

    type: Literal["research.query"] = "research.query"
    query: str
    provider: str
    result_path: str | None = None
    model: str | None = None
    status: Literal["ok", "error"] = "ok"


class LintRunEvent(_EventBase):
    type: Literal["lint.run"] = "lint.run"
    status: str
    issues: int = 0


class ConfigSetEvent(_EventBase):
    type: Literal["config.set"] = "config.set"
    key: str
    value: str


class ScheduleInstalledEvent(_EventBase):
    """Recorded by ``wiki schedule install`` after the OS-side artifact is
    written and activation returns success.

    Field shapes pinned in ``docs/specs/wiki-schedule/spec.md`` §"Journal
    events" / §"Contracts with other modules". Additive per ADR-0002 — older
    journal lines (no ``schedule.*`` events) replay unchanged.
    """

    type: Literal["schedule.installed"] = "schedule.installed"
    operation: str
    machine_id: str
    cadence_dsl: str
    os_artifact_path: str
    exec_command: list[str]
    # Additive per ADR-0002 / RFC-0004 wiki-agents PR-4: the agent name
    # resolved at install time via the CLI flag → recipe → contract chain
    # (``docs/specs/wiki-agents/spec.md`` §"Resolution chain"). ``None``
    # is both the pre-RFC-4 baseline (no field on the JSON line) and the
    # explicit "no agent declared" outcome of the chain; replay treats
    # them identically. Frozen at install time — recipe or catalog
    # changes after install do not auto-rebind. Pattern-validated against
    # ``NAME_PATTERN`` for symmetry with other agent-name fields; the
    # name is also re-validated against the installed-primitive set
    # pre-transaction by ``schedule.install``.
    agent: str | None = Field(default=None, pattern=NAME_PATTERN)


class ScheduleUninstalledEvent(_EventBase):
    """Recorded by ``wiki schedule uninstall``.

    ``removed_artifact`` records whether the kit successfully deleted the
    OS-side file (``True``) or found it already missing/drifted (``False``);
    both cases append exactly one event and exit ``0``. See
    ``docs/specs/wiki-schedule/spec.md`` §Outputs ``uninstall``.
    """

    type: Literal["schedule.uninstalled"] = "schedule.uninstalled"
    operation: str
    machine_id: str
    removed_artifact: bool


class LockAcquiredEvent(_EventBase):
    """Recorded when a multi-event operation takes the journal-wide lock.

    ``reason`` is the free-text label that surfaces in ``wiki journal tail``
    so a user can see what's running. The journal-locking spec
    (``docs/specs/journal-locking/spec.md``) names this event as the
    enter-side bracket emitted by ``journal.transaction()``.
    """

    type: Literal["lock.acquired"] = "lock.acquired"
    reason: str | None = None


class LockReleasedEvent(_EventBase):
    """Recorded when ``journal.transaction()`` (or ``wiki lock release``) exits.

    ``reason`` is optional and defaults to ``None``. ``wiki lock acquire``
    sets it to ``"stale lock reclaimed"`` on the audit pair emitted when
    a dead-PID holder is reclaimed (spec §Edge cases, "Lock held by a
    dead PID"). Ordinary release paths leave it ``None``.
    """

    type: Literal["lock.released"] = "lock.released"
    reason: str | None = None


Event = Annotated[
    VaultInitEvent
    | VaultGitInitializedEvent
    | PrimitiveInstallEvent
    | PrimitiveRemoveEvent
    | PrimitiveUpgradeEvent
    | PrimitiveForceRenderEvent
    | ManagedRegionWriteEvent
    | ManagedRegionAdoptedEvent
    | IngestRoutedEvent
    | SourceIngestEvent
    | PageWriteEvent
    | PageAdoptedEvent
    | PageProposalEvent
    | PageConflictResolvedEvent
    | OperationRunEvent
    | OperationRunByAgentEvent
    | OperationExecFailedEvent
    | ResearchQueryEvent
    | LintRunEvent
    | ConfigSetEvent
    | LockAcquiredEvent
    | LockReleasedEvent
    | ScheduleInstalledEvent
    | ScheduleUninstalledEvent,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Vault state (derived by replay)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeldLock:
    """Snapshot of the journal lock's current holder.

    Populated by ``replay_state`` from a ``LockAcquiredEvent`` and cleared
    by a ``LockReleasedEvent``. ``acquired_at`` is the holding event's
    timestamp — ``wiki doctor`` compares it against ``WIKI_LOCK_STALE_HOURS``
    to surface stale locks (see ``docs/specs/journal-locking/spec.md``
    plan step 6).

    Frozen because replay treats it as a value, not an aggregate; mutations
    would let consumer code silently change derived state.
    """

    by: str
    acquired_at: datetime
    reason: str | None = None


class VaultState(_StrictModel):
    """Snapshot computed by ``journal.replay_state(events)`` (ADR-0002).

    Pydantic because tests serialize it across module boundaries; nothing
    here is meant to be edited by hand.
    """

    vault_name: str | None = None
    recipe: str | None = None
    installed_primitives: dict[str, str] = Field(default_factory=dict)
    page_writes: dict[str, PageWriteEvent] = Field(default_factory=dict)
    # Latest ``PageAdoptedEvent`` per vault-relative path. NOT a "currently
    # sticky-adopt" view: a later ``PageWriteEvent`` for the same path does
    # NOT pop the entry — callers needing "is the latest baseline a write or
    # an adopt?" must walk the journal (e.g. via the PR-B
    # ``_latest_baseline_event_kind`` helper). Callers needing "every path
    # the kit has ever claimed as territory" use ``set(page_writes) |
    # set(adopted_pages)`` (see ``doctor.check_orphans``). ADR-0008
    # §Decision sub-choice 3 and ``docs/specs/wiki-init-adopt/spec.md``
    # §Contracts pin this shape.
    adopted_pages: dict[str, PageAdoptedEvent] = Field(default_factory=dict)
    # In-memory only. Tuple keys (``(file, region)``) round-trip natively
    # through ``model_dump``/``model_validate`` but NOT through
    # ``model_dump_json``/``model_validate_json``: Pydantic v2 encodes a
    # tuple key as a comma-joined string (``"f.yaml,types"``) and rejects
    # the same shape on read (``Input should be a valid array``). Spec
    # §Contracts pins this as derived state — reconstruct via
    # ``replay_state`` from the journal events. ``exclude=True`` enforces
    # the "not serialized" contract so a future ``wiki doctor --json``
    # snapshot (or any other dump) can never silently emit a half-valid
    # representation of populated ``adopted_regions``.
    adopted_regions: dict[tuple[str, str], ManagedRegionAdoptedEvent] = Field(
        default_factory=dict, exclude=True
    )
    pending_proposals: dict[str, PageProposalEvent] = Field(default_factory=dict)
    ingested_sources: dict[str, SourceIngestEvent] = Field(default_factory=dict)
    recent_operations: dict[str, OperationRunEvent] = Field(default_factory=dict)
    recent_research: list[ResearchQueryEvent] = Field(default_factory=list)
    held_lock: HeldLock | None = None
