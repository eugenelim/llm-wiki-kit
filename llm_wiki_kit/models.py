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

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

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


class Contribution(_StrictModel):
    """A primitive's write into a managed region of a shared file (ADR-0003)."""

    file: str
    region: str


class Primitive(_StrictModel):
    """The schema of a ``primitive.yaml`` manifest."""

    name: str = Field(pattern=NAME_PATTERN)
    kind: PrimitiveKind
    version: str = Field(pattern=SEMVER_PATTERN)
    description: str
    requires: list[str] = Field(default_factory=list)
    contributes_to: list[Contribution] = Field(default_factory=list)
    config: dict[str, object] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------


class Recipe(_StrictModel):
    """The schema of a ``recipes/<name>.yaml`` file."""

    name: str = Field(pattern=NAME_PATTERN)
    version: str = Field(pattern=SEMVER_PATTERN)
    description: str
    primitives: list[str]
    variables: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Operation contract
# ---------------------------------------------------------------------------


class OperationContract(_StrictModel):
    """The schema of an operation primitive's ``contract.yaml``."""

    name: str = Field(pattern=NAME_PATTERN)
    description: str
    period: str | None = None
    skill: str | None = None
    inputs: dict[str, object] = Field(default_factory=dict)
    outputs: dict[str, object] = Field(default_factory=dict)


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


class PrimitiveInstallEvent(_EventBase):
    type: Literal["primitive.install"] = "primitive.install"
    primitive: str
    version: str


class PrimitiveRemoveEvent(_EventBase):
    type: Literal["primitive.remove"] = "primitive.remove"
    primitive: str


class PrimitiveUpgradeEvent(_EventBase):
    type: Literal["primitive.upgrade"] = "primitive.upgrade"
    primitive: str
    from_version: str
    to_version: str


class ManagedRegionWriteEvent(_EventBase):
    type: Literal["managed_region.write"] = "managed_region.write"
    file: str
    region: str
    content_hash: str
    hash_algo: str = "sha256"


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


class PageProposalEvent(_EventBase):
    type: Literal["page.proposal"] = "page.proposal"
    path: str
    proposed_path: str
    hash: str
    hash_algo: str = "sha256"


class PageConflictResolvedEvent(_EventBase):
    type: Literal["page.conflict_resolved"] = "page.conflict_resolved"
    path: str
    hash: str
    hash_algo: str = "sha256"


class OperationRunEvent(_EventBase):
    type: Literal["operation.run"] = "operation.run"
    operation: str
    status: str
    period: str | None = None
    produced_pages: list[str] = Field(default_factory=list)


class ResearchQueryEvent(_EventBase):
    type: Literal["research.query"] = "research.query"
    query: str
    provider: str
    result_path: str | None = None


class LintRunEvent(_EventBase):
    type: Literal["lint.run"] = "lint.run"
    status: str
    issues: int = 0


class ConfigSetEvent(_EventBase):
    type: Literal["config.set"] = "config.set"
    key: str
    value: str


Event = Annotated[
    VaultInitEvent
    | PrimitiveInstallEvent
    | PrimitiveRemoveEvent
    | PrimitiveUpgradeEvent
    | ManagedRegionWriteEvent
    | SourceIngestEvent
    | PageWriteEvent
    | PageProposalEvent
    | PageConflictResolvedEvent
    | OperationRunEvent
    | ResearchQueryEvent
    | LintRunEvent
    | ConfigSetEvent,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Vault state (derived by replay)
# ---------------------------------------------------------------------------


class VaultState(_StrictModel):
    """Snapshot computed by ``journal.replay_state(events)`` (ADR-0002).

    Pydantic because tests serialize it across module boundaries; nothing
    here is meant to be edited by hand.
    """

    vault_name: str | None = None
    recipe: str | None = None
    installed_primitives: dict[str, str] = Field(default_factory=dict)
    page_writes: dict[str, PageWriteEvent] = Field(default_factory=dict)
    pending_proposals: dict[str, PageProposalEvent] = Field(default_factory=dict)
    ingested_sources: dict[str, SourceIngestEvent] = Field(default_factory=dict)
    recent_operations: dict[str, OperationRunEvent] = Field(default_factory=dict)
    recent_research: list[ResearchQueryEvent] = Field(default_factory=list)
