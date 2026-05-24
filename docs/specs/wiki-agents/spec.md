# Spec: wiki-agents

> **Living document.** Updated alongside the code. Drift between spec and
> code is a bug — fix the code or the spec in the same PR.

- **Status:** Draft
- **Owner:** `llm_wiki_kit/primitives.py`, `llm_wiki_kit/recipes.py`,
  `llm_wiki_kit/run.py`, `llm_wiki_kit/schedule/`,
  `llm_wiki_kit/doctor.py`, `llm_wiki_kit/cli.py:_cmd_agents`
- **Related:** [RFC-0004](../../rfc/0004-agent-identity-primitives.md),
  [ADR-0010](../../adr/0010-agent-passthrough-via-claude-agent-flag.md),
  [`docs/specs/wiki-run-exec/spec.md`](../wiki-run-exec/spec.md),
  [`docs/specs/wiki-schedule/spec.md`](../wiki-schedule/spec.md),
  [`docs/specs/wiki-agents/plan.md`](plan.md)
- **Constrained by:** ADR-0002 (journal as state truth — additive events
  only), ADR-0005 (Pydantic v2 for disk-bound schemas), ADR-0009
  (headless invocation contract — this spec extends without rewriting),
  ADR-0010 (the `claude --agent <name>` passthrough flag this spec
  emits), [RFC-0004](../../rfc/0004-agent-identity-primitives.md)
  §"Decisions already made" (agent is a new primitive kind, vault-side,
  no kit-side persona embedding, library-not-application),
  [`AGENTS.md` §"Runtime dependencies"](../../../AGENTS.md#runtime-dependencies)
  (no new runtime dep), [`AGENTS.md` §"Two scopes, one
  repo"](../../../AGENTS.md#two-scopes-one-repo) (vault-side
  `.claude/agents/` is distinct from the repo-root kit-development
  scope).

## What this is

`agent` is the fourth primitive kind (alongside `ontology`,
`content-type`, `operation`, `infrastructure`). An agent is a
vault-side markdown file (`AGENT.md`) shipped from
`templates/agents/<name>/files/.claude/agents/<name>/AGENT.md`,
installed by `wiki init` into `<vault>/.claude/agents/<name>/AGENT.md`,
and read by the user's Claude CLI at scheduled-run time via the
`claude --agent <name>` flag pinned in
[ADR-0010](../../adr/0010-agent-passthrough-via-claude-agent-flag.md).
Shared-audience agents under `core/files/agents/` are deferred to
a follow-on RFC — see §Inputs.

The kit's job is fivefold:

1. Recognise `kind: agent` in the primitive catalog, install/upgrade/
   remove it through the existing primitive plumbing (no new install
   event — [RFC-0004 §5](../../rfc/0004-agent-identity-primitives.md#5-new-journal-events-and-field-extensions)).
2. Let recipes declare which agent runs which operation
   (`agents.<name>.runs:` block on `recipes/<name>.yaml`).
3. Resolve an effective agent name at `wiki schedule install` time
   (CLI flag → recipe → operation contract → `None`), validate the
   resolved name against the installed-primitive set
   *pre-transaction* (refusing typos before journaling — see
   [ADR-0010 §Decision step 4](../../adr/0010-agent-passthrough-via-claude-agent-flag.md#decision)),
   and freeze it on the journaled `ScheduleInstalledEvent`.
4. Pass the resolved name through to `claude --agent <name>` at exec
   time (ADR-0010), re-validating against the installed-primitive
   set before invocation to catch mid-life removal between install
   and fire.
5. Surface the binding in `wiki agents`, `wiki schedule list`,
   `wiki doctor`, and (via the journaled `proposed_by_agent` field) in
   the vault-side `wiki-conflict` SKILL's user-facing prose.

The kit **reads zero bytes** of `AGENT.md` at runtime. Frontmatter and
body are for the user's Claude session; the kit's only contract with
the file is "exists at the expected path." This preserves
library-not-application (CHARTER principle 5) without designing a
persona-embedding surface.

`wiki-agents` is not a single CLI verb — it's the cross-cutting surface
that adds `kind: agent` to the existing primitive/recipe/schedule/run/
doctor/conflict pipeline. The boundary is "agents as a primitive kind
that composes with operations at dispatch time," structurally parallel
to how operations compose with skills today.

## Inputs

### Primitive-author surface

Each agent ships as a primitive in the same shape as any other:

```
templates/agents/<name>/
  primitive.yaml             # name, kind: agent, version, description, requires, config
  files/
    .claude/
      agents/
        <name>/
          AGENT.md           # the body the user's Claude reads
```

The source layout lands the file at
`<vault>/.claude/agents/<name>/AGENT.md` through the kit's existing
verbatim file-copy pipeline (`render.render_tree`) — no new path
translation. The `.claude/` prefix in the source tree is the
convention by which kit catalog primitives land artifacts inside the
vault's Claude-Code-discoverable directory (the same place
`wiki init`'s outcome-named slash stubs land at
`<vault>/.claude/commands/`, per `llm_wiki_kit/install.py:453`).

**Shared-audience agents are deferred at v1.** The v1 catalog
ships zero of them — every default in §"Default agent catalog" is
recipe-scoped — so `core/files/agents/` simply does not exist on
disk at v1; discovery tolerates the absent directory the same way
`recipes.discover_recipes` tolerates an absent `recipes/` dir
(`recipes.py:112-113`). The discovery *shape* for shared-audience
agents (with a `primitive.yaml` like recipe-scoped agents, or
without one in the `core/files/skills/` style — the two existing
shapes pull in opposite directions for kind enumeration) is
deliberately not pinned at v1. A follow-on RFC will pin it when
the first shared-audience agent ships; the v1 plumbing only needs
to walk `templates/agents/<name>/primitive.yaml`.

`AGENT.md` frontmatter is **for Claude consumption only** — the kit
does not parse or validate it at v1. The convention shipped with the
default catalog (§"Default agent catalog") follows
[RFC-0004 §1](../../rfc/0004-agent-identity-primitives.md#1-the-agent-primitive-kind):
`name`, `description`, `audience`
(`family | work-os | personal | shared`), `role`, `tone`, `knows:`
(list of vault page paths the agent treats as standing context). Bodies
below the frontmatter are freeform prose. Primitive-author drift in
frontmatter is invisible to the kit at v1; if a future RFC needs the
kit to read it, the field set gets promoted into `primitive.yaml.config`
and the AGENT.md frontmatter becomes the duplicate-for-Claude copy.

### Recipe surface

Recipes (`recipes/<name>.yaml`) gain one optional top-level field:

```yaml
agents:
  household-manager:
    runs:
      - weekly-digest
      - meal-planning
      - follow-up-tracker
  trip-planner:
    runs:
      - trip-prep
```

Schema:

- `agents` — optional `dict[str, AgentBinding]`. Absent or `{}`
  means "no agent bindings declared by this recipe" (today's
  behavior; the recipe loads, the closure walks, but no
  agent-side validation fires over the empty block). The empty
  `runs:` rule below applies only to non-empty `agents:` entries.
- `AgentBinding.runs` — required `list[str]` of operation names.
  An empty `runs:` list is invalid (raises at recipe-load); a recipe
  declaring an agent without any operations is dead weight, and the
  v1 catalog has no use case for a "reserved-for-future" binding on
  the recipe side (the agent primitive can be installed without being
  bound in the recipe — see `decision-companion` in §"Default agent
  catalog").
- Every key in `agents:` must be a primitive name resolved by the
  recipe (`recipes.resolve_recipe_primitives` closure), with
  `kind: agent`. Unknown / wrong-kind names raise `RecipeError`
  at recipe-load time, mirroring today's missing-primitive behavior.
- Every name in any `runs:` list must be a primitive resolved by the
  recipe, with `kind: operation`. Unknown / wrong-kind names raise
  `RecipeError`.
- An operation appears in **at most one** agent's `runs:` list within
  a single recipe. Duplicates raise `RecipeError("operation
  '<op>' is bound to multiple agents in recipe '<recipe>': <a>, <b>;
  one operation may have at most one preferred agent per recipe")`.

### Operation-contract surface

`OperationContract` gains one optional field:

- `preferred_agent: str | None = None` — the operation author's
  fallback agent suggestion. Validates against the standard
  `NAME_PATTERN`. Used when no recipe binding and no CLI flag
  declares an agent.

### CLI surface

Three additive flags / verbs:

```
wiki schedule install <op> [...existing flags] [--agent <name>]
wiki run <op> [...existing flags] [--agent <name>]
wiki run --exec <op> [...existing flags] [--agent <name>]
wiki agents
```

- `--agent <name>` — optional override on `wiki schedule install`,
  `wiki run`, and `wiki run --exec`. Wins over recipe / contract
  resolution. Validates against installed `kind: agent` primitives
  at the call site (refused with `WikiError("agent '<name>' is not
  installed; run 'wiki add agent:<name>' or re-run 'wiki init'")`
  if absent).
- `wiki agents` — new top-level enumeration verb, mirroring the
  shape of the existing `wiki outcomes` verb (`cli.py:2282-2287`):
  one subject, no subcommands, read-only. Emits a tab-separated
  table; no journal write.

`wiki schedule list` (existing, from [`wiki-schedule`](../wiki-schedule/spec.md))
gains one column without a new flag — see §Outputs.

## Outputs

### Models (additive per [ADR-0002](../../adr/0002-journal-as-state-truth.md))

- `PrimitiveKind.AGENT = "agent"` added to the enum in
  `llm_wiki_kit/models.py`.
- `_CATALOG_DIRS` in `llm_wiki_kit/primitives.py` gains `"agents"`.
- `OperationContract` gains `preferred_agent: str | None = None`
  (validates against `NAME_PATTERN`).
- `Recipe` gains
  `agents: dict[str, AgentBinding] = Field(default_factory=dict)`.
  `AgentBinding` is a new `_StrictModel` with one required field
  `runs: list[str] = Field(min_length=1)`.
- `ScheduleInstalledEvent` gains
  `agent: str | None = None` (additive; older lines replay unchanged).
- `PageProposalEvent` gains
  `proposed_by_agent: str | None = None` (additive).
- **One new event class**, `OperationRunByAgentEvent`:

  ```python
  class OperationRunByAgentEvent(_EventBase):
      type: Literal["operation.run_by_agent"] = "operation.run_by_agent"
      operation: str
      agent: str
      event_id: str  # 12-hex id of the paired OperationRunEvent
  ```

  Recorded by `wiki run --exec` *only* when an agent name resolved.
  Also recorded by `wiki run <op>` (dispatch-only) when `--agent` is
  passed explicitly — manual runs get the same audit tag as
  scheduled ones, even though no `claude` invocation carries the
  name on the dispatch-only path.

  No `OperationRunByAgentEvent` is appended when no agent resolves
  (preserves today's no-event-on-no-agent shape; backward compatible).

  Recorded **paired** with the dispatch's `OperationRunEvent`, inside
  the same `journal.transaction(...)`, with `event_id` set to the
  dispatched event's id. The two appends are atomic-or-neither under
  the journal flock (`journal-locking` spec).

The discriminated `Event` union gains `OperationRunByAgentEvent`;
existing classes are unaffected.

### `wiki schedule install` outputs (additive)

When `--agent` is passed or a recipe/contract resolves to a non-`None`
agent:

- `ScheduleInstalledEvent.agent` is set to the resolved name.
- The OS-side artifact's `exec_command` array gains two trailing
  tokens: `"--agent", "<name>"`. So a `wiki schedule install
  weekly-digest --agent household-manager` produces an artifact whose
  exec invokes `<wiki> run --exec weekly-digest --agent
  household-manager`.
- The stdout summary block from
  [`wiki-schedule`](../wiki-schedule/spec.md) §Outputs gains one
  line: `  agent: <name>` between `cadence:` and `artifact:`.

When no agent resolves: `ScheduleInstalledEvent.agent = None`,
`exec_command` is unchanged from
[`wiki-schedule`](../wiki-schedule/spec.md), and no `agent:` line
appears in the stdout summary.

### `wiki schedule list` outputs (additive)

A new **AGENT** column appears between **CADENCE** and **ARTIFACT**:

```
OPERATION     MACHINE      CADENCE      AGENT              ARTIFACT       STATUS
weekly-digest tower.local  SUN 09:00    household-manager  ~/Library/...  ok
meal-planning tower.local  daily 06:30  —                  ~/Library/...  drift:missing-file
```

The column reads `ScheduleInstalledEvent.agent` verbatim; `None`
renders as `—` (U+2014). No schema change; no flag.

### `wiki run [--exec] [--agent]` outputs (additive)

- When `--agent <name>` resolves to a non-`None` value and the
  resolution validates (name installed, `kind: agent`, no later
  `PrimitiveRemoveEvent`): `OperationRunByAgentEvent` is appended
  alongside the existing `OperationRunEvent` inside the same
  `journal.transaction(...)`.
- In `--exec` mode, the kit appends `--agent <name>` to the `claude`
  argv per [ADR-0010 §Decision](../../adr/0010-agent-passthrough-via-claude-agent-flag.md#decision):
  inserted as two tokens immediately before the trailing prompt
  positional. No other ADR-0009 argv shape changes.
- When validation fails (resolved name is not installed): `WikiError`
  with the canonical message above. In `--exec` mode, also append one
  `OperationExecFailedEvent` with `reason="agent-missing"` — a new
  Literal value added to `OperationExecFailedEvent.reason` additively
  per ADR-0002; see §"Contracts with other modules" for the
  enum-extension shape and replay-safety story.
- No new stdout shape beyond what
  [`wiki-run-exec`](../wiki-run-exec/spec.md) already produces.

### `wiki agents` outputs

Tab-separated rows, header first:

```
NAME               RECIPES   OPERATIONS
care-coordinator   family    medical-summary
household-manager  family    weekly-digest, meal-planning, follow-up-tracker
trip-planner       family    trip-prep
```

- **NAME** — primitive name from `PrimitiveInstallEvent.primitive`
  (filtered to `kind: agent` via `_CATALOG_DIRS` discovery at
  install-event time; the kind is recoverable from the installed
  catalog per
  [RFC-0004 §"Resolved before review" #1](../../rfc/0004-agent-identity-primitives.md#resolved-before-review)).
- **RECIPES** — comma-separated, alphabetical list of recipe names
  that reference this agent. The kit walks
  `recipes.discover_recipes(kit_root / "recipes")` and applies the
  two-rule test below to each loaded recipe. A recipe `R`
  contributes iff **either** (a) `R.agents` contains an entry for
  this agent name, **or** (b) this agent name appears in `R`'s
  `primitives:` closure (via `recipes.resolve_recipe_primitives`).
  Rule (b) covers the installed-but-unbound case (e.g.
  `decision-companion` ships in `personal.yaml`'s `primitives:`
  closure with no `agents:` binding). Empty → `—`.
  Repo-catalog-relative — *not* filtered to which recipe the vault
  was initialized from — so a user who
  `wiki add agent:trip-planner`s from the `family` catalog onto a
  `personal` vault still sees the `family` recipe reference.
- **OPERATIONS** — union of: each `runs:` operation across all
  recipes binding the agent, plus operations whose
  `contract.preferred_agent == <name>`. Comma-separated, sorted.
  Empty → `—` (e.g. `decision-companion` ships unbound at v1).

Empty agent set produces only the header line and exits `0`.

### `wiki doctor` outputs (additive)

Two new checks under a new **Agents** section, after **Schedules**:

- **Bindings.** For each schedule entry with `agent` set and `machine_id
  == socket.gethostname()`, verify
  `<vault>/.claude/agents/<agent>/AGENT.md` exists.
  Missing → warning: `schedule for <op> bound to agent '<agent>' but
  AGENT.md missing at <path>; run 'wiki add agent:<agent>' or
  re-run 'wiki init'`.
- **Version drift.** For each agent primitive in `installed_primitives`
  with kind `agent`, look up the most recent `PrimitiveUpgradeEvent`
  for that name and the most recent `OperationRunByAgentEvent`
  referencing it. If the upgrade event is newer (or no run-by-agent
  event has happened since), warn: `agent '<name>' was upgraded
  <from_version> → <to_version> since the last scheduled run; review
  '<vault>/.claude/agents/<name>/AGENT.md' before the next firing
  changes voice`. Suppressed when the agent has never been bound to
  a still-active schedule or run.

Both are **warnings**, not failures — `wiki doctor` exits `0` when
only agent warnings are present (same convention as Schedules per
[`wiki-schedule`](../wiki-schedule/spec.md) §"Doctor integration").

### Conflict-aware UX (vault-side SKILL)

`core/files/skills/wiki-conflict/SKILL.md` is updated so that when it
inspects a `.proposed` sidecar's most recent `PageProposalEvent` and
finds `proposed_by_agent: "<name>"`, it surfaces the agent's name in
the user-facing explanation per
[RFC-0004 §6](../../rfc/0004-agent-identity-primitives.md#6-conflict-aware-ux-naming-the-agent).
The kit-side change is the additive `proposed_by_agent` field on the
event; the rendering is the SKILL's job.

A vault-side `wiki-agent` SKILL.md ships under
`core/files/skills/wiki-agent/SKILL.md` teaching Claude when to
prompt the user about installing or rebinding an agent (per
[RFC-0004 §Outcome](../../rfc/0004-agent-identity-primitives.md#outcome)).
Like every other vault-side SKILL, the kit ships the file and the
user's Claude reads it; the kit does not invoke the SKILL itself.

## Behavior

### Agent install (extends `wiki add` / `wiki init`)

Agent primitives install via the same `PrimitiveInstallEvent` path
operations use. The installer:

1. Walks `templates/agents/<name>/primitive.yaml` (the v1 shape).
   `core/files/agents/` is not walked at v1; shared-audience
   agents are deferred to a follow-on RFC per §Inputs.
2. Copies `files/.claude/agents/<name>/AGENT.md` to
   `<vault>/.claude/agents/<name>/AGENT.md` via the existing
   primitive-install verbatim file-copy path (`render.render_tree`).
   No new path translation: the catalog ships the file under
   `files/.claude/...` so the verbatim copy lands at the matching
   vault-relative path. The kit does not read the file contents.
3. Appends `PrimitiveInstallEvent(primitive=<name>, version=<v>)` —
   identical to operation/content-type/ontology installs. The kind
   is recoverable from `installed_primitives[<name>]` + the catalog
   walk at any later replay.

`wiki upgrade <name>` and `wiki remove agent:<name>` reuse the
existing primitive plumbing without modification — the kind tag does
not affect the install graph beyond `_CATALOG_DIRS` discovery.

### Resolution chain (at `wiki schedule install` time)

The chain runs **once at install time** and freezes its output on the
journaled `ScheduleInstalledEvent.agent`. The chain is:

1. `--agent <name>` from the CLI. If present, validate (must be
   installed `kind: agent`); refuse with `WikiError` if not.
2. Recipe binding. Load the vault's recipe from
   `recipes/<VaultInitEvent.recipe>.yaml` (single lookup — the
   journal records exactly one recipe per vault) and check its
   `agents:` block for an entry whose `runs:` list contains the
   operation. Recipe validation already pins
   one-agent-per-op-per-recipe (CT-5), so at most one binding
   can match within that recipe. If the recipe's `agents:` block
   has no binding for this operation, continue to step 3.
3. Operation contract. Load
   `templates/operations/<op>/contract.yaml`; if
   `preferred_agent: <name>` is set and the name resolves to an
   installed `kind: agent` primitive, use it. If the name is set
   but not installed, **skip silently** (the contract author's
   suggestion doesn't apply to this vault) and continue.
4. Else, the resolved agent is `None`.

The chain's output appears in the install stdout summary as the
`agent:` line documented in §Outputs (when non-`None`); no other
rendering of the resolution source is shipped at v1. A future
verbose flag could surface which step of the chain produced the
name, but no CT pins that today.

### Resolution chain (at `wiki run --exec` time, manual invocation)

Same shape but no schedule context. Walks:

1. `--agent <name>` from CLI.
2. Recipe binding for the operation (per the rules above).
3. Operation contract `preferred_agent`.
4. None.

Validation runs immediately before the `claude` invocation, matching
[ADR-0010 §Decision step 4](../../adr/0010-agent-passthrough-via-claude-agent-flag.md#decision).

### Resolution chain (at `wiki run` dispatch-only time)

Only step 1 applies. If `--agent` is not passed, no agent name is
journaled. The dispatch-only path never walks recipe/contract — there
is no `claude` invocation to pass anything to, and inferring an agent
on a manual hand-off would confuse the audit trail.

### Edge cases

- **Operation appears in both a recipe's `agents:` block and has a
  `preferred_agent` on its contract.** The recipe wins (chain step 2
  precedes step 3). Contract is the author's default; recipe is the
  vault owner's composition.
- **Recipe has a typo in `agents.<name>` (unknown agent).** Hard
  error at recipe-load time, before any install can happen. Matches
  today's recipe-vs-catalog mismatch handling
  ([`recipes.py`](../../../llm_wiki_kit/recipes.py)).
- **Recipe's `agents.X.runs` lists an operation not in the recipe's
  primitives closure.** Hard error at recipe-load time.
- **`OperationContract.preferred_agent` names an agent not installed
  in this vault.** Skipped silently during chain step 3 — the agent
  may be installed in a different vault that uses this same operation
  primitive, or the user opted out. Documented behavior; not a doctor
  warning.
- **Agent removed (`wiki remove agent:<name>`) while a schedule
  references it.** The schedule's journaled `agent` field still says
  `<name>`; at exec time, dispatch validation refuses with
  `WikiError("scheduled run resolved agent '<name>' but it is not
  installed; run 'wiki add agent:<name>' or re-run 'wiki init'")`
  and journals an `OperationExecFailedEvent` with
  `reason="agent-missing"` (additive enum value — see §"Contracts
  with other modules"). The OS-side artifact is not auto-rewritten;
  the user reinstates the agent or uninstalls the schedule.
- **AGENT.md deleted out-of-band while the primitive is installed.**
  Dispatch validation passes (journal still has the install event);
  the `claude --agent <name>` invocation fails at the CLI side with
  its own "agent not found" message. `wiki doctor`'s bindings check
  is the user-facing recovery path.
- **Two recipes in `recipes/*.yaml` bind the same operation to
  different agents.** Schedule install resolution loads only the
  vault's recorded recipe (`VaultInitEvent.recipe`), so only that
  recipe's binding contributes. `wiki agents` enumerates every
  recipe in the repo catalog (per its RECIPES column rule above)
  for transparency, but only one recipe binds at
  schedule-install time.
- **Vault has no `VaultInitEvent` at all** (adopted vault still
  missing the initial event, or a corruption case). Schedule install
  refuses earlier at the standard "not a wiki vault" / "vault at
  <root> has no vault.init event" boundary `cli.py` already enforces;
  resolution never runs. `VaultInitEvent.recipe` itself is a required
  field on the model (`models.py:243`), so there is no "missing
  recipe" branch — every well-formed vault carries a recipe name.
- **Agent name collides with a built-in agent.** Hard error at
  install time via the existing primitive-name-collision check; no
  new code path.

### Error cases

- Argv-shape errors (unknown `--agent` name at install or run time) →
  `WikiError` at the CLI boundary; no journal write at install; in
  `--exec` mode, one `OperationExecFailedEvent` with
  `reason="agent-missing"` and no `OperationRunByAgentEvent`.
- Recipe-load errors (unknown agent name, wrong kind, duplicate
  operation binding, empty `runs:` list) → `RecipeError` at
  `wiki init` / `wiki upgrade` time, before any install.
- Schedule-install with `--agent <missing>` → `WikiError`; no
  `ScheduleInstalledEvent` (zero events per
  [`wiki-schedule`](../wiki-schedule/spec.md) §Invariants).

## Invariants

- One `wiki schedule install` invocation appends **at most one**
  `ScheduleInstalledEvent`. The agent resolution is part of pre-load
  validation: a `--agent <missing>` refusal aborts before any
  journal write, matching the existing pre-load failure shape from
  [`wiki-schedule`](../wiki-schedule/spec.md) §Invariants.
- One `wiki run --exec` invocation appends **at most one**
  `OperationRunByAgentEvent`. Zero events when no agent resolves;
  exactly one when an agent resolves *and* validates. The event is
  paired with the dispatch's `OperationRunEvent` inside the same
  `journal.transaction(...)` — either both are appended or neither.
- One `wiki run` (dispatch-only) invocation appends at most one
  `OperationRunByAgentEvent` (only when `--agent` is passed); the
  paired `OperationRunEvent` shape is unchanged from today.
- `OperationRunByAgentEvent.event_id` always matches an
  `OperationRunEvent.event_id` appended in the same transaction.
  Pairing presupposes the post-Task-17 dispatch path that always
  populates `OperationRunEvent.event_id` (`run.dispatch` sets it
  via `uuid.uuid4().hex[:12]` on every new event; older lines
  pre-dating Task 17 carry `event_id is None` per ADR-0002's
  additive-schema rule, and no `OperationRunByAgentEvent` was ever
  appended alongside them). Replay can join the two by id; a
  `OperationRunByAgentEvent` with no matching
  `OperationRunEvent` is a doctor-flag-worthy corruption (out of
  scope for v1's doctor; a future check may add it). A future
  contributor must not drop the `event_id` assignment in
  `run.dispatch` — the model field stays `str | None` for replay
  compatibility, but the write-path keeps it always-populated.
- `ScheduleInstalledEvent.agent` is set exactly once at install time
  and never auto-rewritten. A recipe edit, agent upgrade, or
  `wiki add agent:<other>` does not retroactively rebind existing
  schedules — the user uninstalls and re-installs to change the
  binding. This is the same "do not auto-migrate" posture
  [`wiki-schedule`](../wiki-schedule/spec.md) §"Hostname rename"
  takes for `machine_id`.
- **The OS-side artifact's `exec_command` is the authoritative
  carrier of the frozen agent name.** At install time the kit
  embeds `["--agent", "<name>"]` (or omits both tokens) in the
  artifact's `exec_command` array. At fire time the OS scheduler
  runs that argv verbatim; the `--agent` flag lands as a CLI flag
  in the kit's `wiki run --exec` invocation and chain step 1
  (CLI flag) consumes it before steps 2–3 can re-resolve from
  current recipe / contract state. The "freeze" is therefore a
  property of the artifact's `exec_command`, not just of the
  journaled `ScheduleInstalledEvent.agent` field. A hand-edited
  plist that strips the flag would re-resolve from current state
  on the next fire — that drift is left to a follow-on
  doctor-fix RFC (out of scope at v1).
- The kit reads zero bytes of `AGENT.md` at runtime. Every read of
  the file is the user's Claude session via the CLI's own discovery,
  driven by `--agent <name>` from the kit's argv. Tests **may**
  parse `AGENT.md` (e.g. CT-25 / PR-7's `test_agent_catalog.py`
  loads the frontmatter via `pyyaml.safe_load` to assert
  well-formedness) — this is a verification-side concern, not a
  runtime read, and is permitted because the kit's production code
  paths still don't touch the file.
- `primitives.is_installed_agent(name, state, kit_root)` is the
  canonical name-and-kind check at the two sites that consume
  `VaultState`:
  schedule-install validation (PR-4) and dispatch-time validation
  (PR-5). CT-12 and CT-15 pin the helper's correctness at those
  call sites. Recipe-load validation (PR-3) is a *distinct*
  validation path — it walks the recipe's `primitives:` closure
  before any install has happened, so no `VaultState` exists to
  pass to the helper; CT-3 / CT-4 / CT-5 pin the closure-walk check
  separately. The single-helper rule across the two `VaultState`
  sites is a code-organization discipline enforced by review,
  not a runtime invariant. The helper lives in `primitives.py`
  alongside the existing kind helpers to avoid a new module
  boundary.
- The journal's `Event` union is the only place a new event type is
  added; the discriminator-based parser dispatches on the literal
  `type` field per ADR-0005.
- Existing journal lines (pre-RFC-4) replay unchanged: every new
  field has a default, every new event type is additive. ADR-0002
  §Negative's additive-schema rule covers the migration.

## Contracts with other modules

- **`llm_wiki_kit/models.py`** — additive only:
  - `PrimitiveKind.AGENT = "agent"`.
  - `OperationContract.preferred_agent: str | None = None` (validated
    against `NAME_PATTERN`).
  - `Recipe.agents: dict[str, AgentBinding] = Field(default_factory=dict)`.
  - `AgentBinding` (new `_StrictModel`): `runs: list[str] =
    Field(min_length=1)`. Names validated against `NAME_PATTERN`.
  - `ScheduleInstalledEvent.agent: str | None = None`.
  - `PageProposalEvent.proposed_by_agent: str | None = None`.
  - `OperationRunByAgentEvent` class (new).
  - `OperationExecFailedEvent.reason` enum gains `"agent-missing"`
    as an accepted Literal value (additive enum extension).
  - `Event` discriminated union gains `OperationRunByAgentEvent`.
- **`llm_wiki_kit/primitives.py`** —
  - `_CATALOG_DIRS` gains `"agents"`.
  - One new helper: `is_installed_agent(name: str, state: VaultState,
    kit_root: Path) -> bool` — true iff `name in
    state.installed_primitives` AND the primitive's declared kind in
    the kit-side catalog at `kit_root / "templates"` is
    `PrimitiveKind.AGENT`. The `kit_root` argument is required because
    `VaultState.installed_primitives` is `dict[str, str]` (name →
    version) and does not carry kind information — the helper recovers
    the kind by walking the catalog via `discover_primitives`. Same
    `kit_root` convention as `list_agents`,
    `recipes.installed_outcome_verbs`, `cli._kit_paths`, and
    `operations._load_contract`. A future helper
    `is_installed_kind(name, kind, state, kit_root)` could generalize
    to other kinds.
  - One new enumeration function:
    `list_agents(vault_root: Path, kit_root: Path) -> list[AgentRow]`
    where `AgentRow` is a frozen dataclass
    `(name: str, recipes: list[str], operations: list[str])`. The
    `kit_root` argument follows the existing convention used by
    `recipes.installed_outcome_verbs`, `cli._kit_paths`, and
    `operations._load_contract` — it points at the repo-side
    catalog root (the directory containing `recipes/`,
    `templates/`, and `core/`). Driven by `_cmd_agents`.
- **`llm_wiki_kit/recipes.py`** —
  - `resolve_recipe_primitives` (or its callers) gains a post-closure
    validation pass over `recipe.agents`: every key resolves to a
    `kind: agent` primitive in the closure; every operation in
    each `runs:` list resolves to a `kind: operation` primitive; no
    operation appears in two agents' `runs:` lists.
  - `Recipe.agents` is the only schema change; readers that never
    touched `agents` see the same shape they always saw.
- **`llm_wiki_kit/run.py`** —
  - `dispatch()` (and the helper that paired with it for `--exec`)
    gains agent resolution + validation. `_build_argv` gains the
    optional two-token `--agent <name>` insert per ADR-0010.
  - The `--agent` CLI flag is parsed in `cli.py:_cmd_run` and
    threaded through.
  - In dispatch-only mode, only the CLI flag is honored; the
    resolution chain doesn't fire.
- **`llm_wiki_kit/schedule/__init__.py`** —
  - `install(...)` gains an `agent: str | None` keyword (the
    pre-resolved name from the CLI flag, or `None` to walk the
    chain). The resolution chain runs inside `install()`'s
    pre-transaction validation block, so a `--agent <missing>`
    refusal aborts before `journal.transaction()` opens.
  - The OS-side artifact's `exec_command` array is extended with
    `["--agent", "<name>"]` when the resolved agent is non-`None`;
    unchanged otherwise.
  - `list_schedules()` is unchanged in shape; its return type's
    `ScheduleStatus` already carries `ScheduleInstalledEvent`'s
    fields, so the new `agent` field is reflected without code
    change.
- **`llm_wiki_kit/cli.py`** —
  - New `wiki agents` top-level verb (no subcommand), handler
    `_cmd_agents`. Mirrors the `wiki outcomes` verb shape.
  - `wiki schedule install`, `wiki run`, `wiki run --exec` accept
    `--agent <name>` (argparse-only addition; no new dispatch
    surface).
  - `wiki schedule list` output gains the AGENT column.
- **`llm_wiki_kit/doctor.py`** — gains a `_check_agents(state,
  vault_root)` function called after `_check_schedules`. Emits
  warnings only (never failures), matching the existing
  `wiki doctor` warning convention.
- **[`docs/specs/wiki-journal-readers/spec.md`](../wiki-journal-readers/spec.md)**
  — the summary-fields table for `wiki journal tail` / `wiki journal
  grep` gains rows for the new and extended events this spec
  introduces. PR-1 adds the
  `operation.run_by_agent` row (paired with the
  `OperationRunByAgentEvent` model class). PR-4 amends the
  `schedule.installed` row when `ScheduleInstalledEvent.agent` lands;
  PR-6 amends the `page.proposal` row when
  `PageProposalEvent.proposed_by_agent` lands. The journal-readers
  spec calls out "adding a new event class without a row in this
  table is a spec change" — drift between the table and
  `_EVENT_SUMMARY_FIELDS` is a bug, and this cross-spec amendment
  carries the discipline forward.
- **`core/files/skills/wiki-conflict/SKILL.md`** — updated to read
  `PageProposalEvent.proposed_by_agent` and name the agent in
  user-facing conflict prose (vault-side change, not kit code).
- **`core/files/skills/wiki-agent/SKILL.md`** — new SKILL teaching
  Claude when to prompt the user about installing or rebinding
  agents.

## Acceptance criteria

The contract tests below define "done". Construction tests live in
`plan.md`.

- [ ] **CT-1: `PrimitiveKind.AGENT` is recognized by discovery.** A
  `templates/agents/household-manager/primitive.yaml` with `kind:
  agent` is enumerated by `primitives.discover_primitives()`; the
  returned primitive has `kind == PrimitiveKind.AGENT`. Discovery
  loads what the manifest declares; cross-checking the parent
  directory name against the declared kind is a primitive-author
  concern, not a discovery-time invariant — `agent` follows the
  same today-permissive kind-vs-directory posture every other
  kind has (see `llm_wiki_kit/primitives.py:50-67`'s
  `_CATALOG_DIRS` comment).
- [ ] **CT-2: agent primitive installs through the existing
  `PrimitiveInstallEvent` path.** `wiki add agent:household-manager`
  on a freshly-initialized vault (a) appends exactly one
  `PrimitiveInstallEvent(primitive="household-manager",
  version="0.1.0")`, (b) writes
  `<vault>/.claude/agents/household-manager/AGENT.md` with bytes
  matching the catalog source, (c) appends no
  `OperationRunByAgentEvent`, (d) exits `0`. No new install-event
  discriminator is introduced.
- [ ] **CT-3: recipe `agents:` block validates against the closure.**
  A recipe whose `agents.household-manager.runs` lists
  `weekly-digest` validates when both `household-manager` and
  `weekly-digest` are in its `primitives:` closure. The same recipe
  with `weekly-digest` removed from `primitives:` raises
  `RecipeError` whose message names both the operation and the
  agent.
- [ ] **CT-4: recipe `agents:` block rejects unknown / wrong-kind
  agents.** A recipe declaring `agents.weekly-digest.runs:
  [meal-planning]` (where `weekly-digest` is a `kind: operation`
  primitive) raises `RecipeError` containing `kind: agent expected`.
- [ ] **CT-5: recipe rejects an operation bound to two agents.** A
  recipe whose `agents:` block has both `household-manager.runs:
  [weekly-digest]` and `trip-planner.runs: [weekly-digest]` raises
  `RecipeError` whose message names both agents and the operation.
- [ ] **CT-6: recipe rejects empty `runs:` list.** `agents.X.runs: []`
  raises a Pydantic `ValidationError` (via `min_length=1`) at
  recipe-load.
- [ ] **CT-7: `OperationContract.preferred_agent` validates against
  `NAME_PATTERN`.** Valid names load; `"Household_Manager"` (capital
  / underscore) is rejected at contract-load.
- [ ] **CT-8: resolution chain — CLI flag wins.** Given a vault on
  the `family` recipe with `agents.household-manager.runs:
  [weekly-digest]` and `weekly-digest`'s contract declaring
  `preferred_agent: household-manager`, `wiki schedule install
  weekly-digest --agent trip-planner` produces a
  `ScheduleInstalledEvent` with `agent="trip-planner"` (and the
  OS-side artifact embeds `--agent trip-planner`).
- [ ] **CT-9: resolution chain — recipe wins over contract.** Same
  vault, no CLI flag. The contract names `care-coordinator` as
  `preferred_agent`; the recipe binds `weekly-digest` to
  `household-manager`. The journaled `agent` is `household-manager`.
- [ ] **CT-10: resolution chain — contract used when no recipe
  binding.** Vault on the `personal` recipe (which has no
  `agents:` block at v1 for `weekly-digest`); contract declares
  `preferred_agent: personal-coordinator`. The journaled `agent` is
  `personal-coordinator`.
- [ ] **CT-11: resolution chain — None when nothing declares.**
  Vault with no recipe agent binding, no `preferred_agent` on the
  contract, no `--agent` flag. The journaled `agent` is `None` and
  the OS-side artifact's `exec_command` is the existing four-token
  shape (`[wiki, run, --exec, <op>]`).
- [ ] **CT-12: schedule install refuses missing agent name.** `wiki
  schedule install weekly-digest --agent ghost` on a vault where no
  `kind: agent` primitive named `ghost` is installed raises
  `WikiError` whose message contains `agent 'ghost' is not
  installed`; no `ScheduleInstalledEvent` is appended.
- [ ] **CT-13: contract's `preferred_agent` for an uninstalled agent
  is skipped silently.** Vault with `weekly-digest` installed and
  `weekly-digest.contract.preferred_agent: not-installed`, no
  recipe binding for the op, no CLI flag. The journaled `agent` is
  `None`; no `WikiError`, no warning.
- [ ] **CT-14: `--agent` passes through to `claude` via ADR-0010.**
  In an `--exec` dry-run that captures the built argv (per
  `wiki-run-exec`'s test seam), `wiki run --exec weekly-digest
  --agent household-manager` produces an argv whose token list
  contains `"--agent", "household-manager"` immediately before the
  trailing prompt positional. With `--agent` omitted and no
  resolution, the same shape contains no `--agent` token.
- [ ] **CT-15: agent-missing at exec time journals
  `OperationExecFailedEvent`.** When the journaled
  `ScheduleInstalledEvent.agent` references an agent later removed
  (`wiki remove agent:<name>`), the next `wiki run --exec` for the
  scheduled op (a) raises `WikiError` whose message starts with
  `scheduled run resolved agent '<name>' but it is not installed`,
  (b) appends one `OperationExecFailedEvent` with
  `reason="agent-missing"` and `exit_code` reflecting the kit-side
  refusal (no subprocess invoked), (c) appends no
  `OperationRunByAgentEvent`.
- [ ] **CT-16: `OperationRunByAgentEvent` is paired with the
  dispatch event.** A successful `wiki run --exec weekly-digest`
  with an installed agent (a) appends both `OperationRunEvent` and
  `OperationRunByAgentEvent` inside the same
  `journal.transaction(...)` (one `LockAcquiredEvent` /
  `LockReleasedEvent` pair bracketing both), (b) the paired
  `OperationRunEvent.event_id is not None` and the two events
  share the same `event_id` value, (c) the order on disk is
  `OperationRunEvent` then `OperationRunByAgentEvent` (the
  dispatch event must precede the audit tag).
- [ ] **CT-17: dispatch-only `wiki run --agent` journals the audit
  tag without walking the chain.** With a recipe binding for
  `weekly-digest`'s agent in place, `wiki run weekly-digest`
  (no `--exec`, no `--agent`) appends only an `OperationRunEvent`
  (no `OperationRunByAgentEvent`). Adding `--agent some-other`
  appends both events with `agent="some-other"` (the chain does
  not override the explicit flag).
- [ ] **CT-18: `wiki agents` reports installed agents.** On a
  vault with `household-manager`, `trip-planner`, and
  `care-coordinator` installed under the `family` recipe,
  `wiki agents` prints three rows with NAME/RECIPES/OPERATIONS
  populated; `decision-companion` (when installed but unbound)
  prints with OPERATIONS=`—`. Empty vault prints only the header.
- [ ] **CT-19: `wiki agents` unions RECIPES across catalog
  relationships.** A recipe contributes to the RECIPES column for
  an agent name if **either** (a) the recipe's `agents:` block
  binds that agent name to any operation, **or** (b) the agent's
  primitive appears in the recipe's `primitives:` closure even
  without an `agents:` binding (e.g. `decision-companion` in
  `personal.yaml`'s `primitives:` list with no entry in the
  recipe's `agents:` block). With `weekly-digest` bound to
  `personal-coordinator` in `personal.yaml` and the same
  `personal-coordinator` agent primitive also listed in (a
  hypothetical) `family.yaml`'s `primitives:` closure but unbound
  there, `wiki agents` reports `personal-coordinator`'s RECIPES
  column as `family, personal` (sorted alphabetically) and its
  OPERATIONS column as the union across the binding-carrying
  recipes (sorted).
- [ ] **CT-20: `wiki schedule list` shows the AGENT column.** After
  installing two schedules — one with an agent, one without — the
  list output has the AGENT column populated for the first and
  `—` for the second.
- [ ] **CT-21: `wiki doctor` bindings warning.** With a schedule
  bound to agent `household-manager` and
  `<vault>/.claude/agents/household-manager/AGENT.md` deleted
  out-of-band, `wiki doctor` exits `0` and stdout contains both
  the agent name and the suggested fix (`wiki add
  agent:household-manager`). Stderr is empty.
- [ ] **CT-22: `wiki doctor` version-drift warning.** After
  `wiki upgrade household-manager` (which appends a
  `PrimitiveUpgradeEvent`) and no `OperationRunByAgentEvent` for
  that agent since, `wiki doctor` exits `0` and stdout contains
  the agent name, the old/new versions from the upgrade event,
  and the bound operations.
- [ ] **CT-23: `PageProposalEvent.proposed_by_agent` round-trips.**
  Appending a `PageProposalEvent` with `proposed_by_agent="X"`
  and reading it back via `model_validate_json` produces the same
  field value. Pre-RFC-4 lines without the field replay with
  `proposed_by_agent is None`.
- [ ] **CT-24: additive event schema replays cleanly.** Three
  sub-clauses, each pinned by a distinct construction test (see
  `plan.md` for the per-PR assignments):
  - **CT-24a:** a literal pre-RFC-4 journal — restricted to
    event types whose Pydantic shape this spec (and any future
    additive-schema change) leaves *byte-stable* — replays
    under the extended discriminated `Event` union and
    produces a `VaultState` whose `model_dump_json()` is
    byte-identical to a frozen reference snapshot captured
    pre-RFC-4. **The fixture's contract is event-type
    *byte-stability*, not a closed enumeration of event types**:
    every event type the kit ships must respect the same rule —
    if a future spec extends a type's Pydantic shape (adds a
    field with default, even though replay-safe), the fixture
    excludes that type from then on. The v1 fixture exercises
    this contract by including `operation.run` lines that lack
    the `event_id` field Task 17 added (i.e. pre-Task-17 lines)
    plus the `primitive.{install,upgrade,remove}`, `vault.init`,
    `vault.git_initialized`, and `lock.*` events whose shapes
    are unchanged by this spec; `page.proposal` and
    `schedule.installed` are excluded because this spec extends
    their shapes. Every other event type in the union is
    *byte-stable at v1* (`managed_region.*`, `ingest.routed`,
    `source.ingest`, `page.{write,adopted,conflict_resolved}`,
    `operation.exec_failed` — additive enum-value extension
    only, no field change — `research.query`, `lint.run`,
    `config.set`, `schedule.uninstalled`); they may appear in
    the fixture, and a future contributor extending any of
    them must drop that type from the fixture to keep the
    snapshot valid. Provenance pinned in `plan.md` PR-1: the
    snapshot is a static file checked into
    `tests/fixtures/journals/`, captured pre-RFC-4 once and
    frozen. The test loads fixture + snapshot, replays under
    the extended union, asserts byte-equality. Pins
    additive-schema replay — not merely "no parser error" —
    so the union extension can't silently change `VaultState`
    derivation for legacy journals. *Lands in PR-1's
    `test_models_agent_kind.py`.*
  - **CT-24b:** a literal pre-RFC-4 `schedule.installed` line
    that lacks the `agent` field replays under the extended
    `ScheduleInstalledEvent` with `agent is None`. *Lands in
    PR-4's `test_schedule_install_agent.py`.*
  - **CT-24c:** a literal pre-RFC-4 `page.proposal` line that
    lacks the `proposed_by_agent` field replays under the
    extended `PageProposalEvent` with `proposed_by_agent is
    None`. *Lands in PR-6's `test_models_page_proposal_agent.py`.*
- [ ] **CT-25: default catalog ships.** `templates/agents/` contains
  the eight primitives listed in §"Default agent catalog" below;
  each has a valid `primitive.yaml` (`kind: agent`,
  `version: 0.1.0`), and each `files/.claude/agents/<name>/AGENT.md` is
  well-formed (the test parses its YAML frontmatter via
  `pyyaml.safe_load` to assert syntactic validity — kit *runtime*
  reads zero bytes of the file; this is a verification-side
  check). The CT does **not** assert anything about
  `core/files/agents/`'s presence or absence (CT-26 covers
  discovery-side absent-tolerance separately).

- [ ] **CT-26: discovery tolerates a missing agent-catalog
  directory.** Build a `tmp_path` containing a `templates/`
  subdirectory with at least one *non-agent* kind directory
  (e.g. `templates/operations/<name>/primitive.yaml`) and **no**
  `templates/agents/` subdirectory; call
  `discover_primitives(tmp_path / "templates")` and assert it
  returns successfully (no exception) with **zero** entries
  whose `kind == PrimitiveKind.AGENT`. Pins the existing
  absent-directory tolerance of `primitives.discover_primitives`
  (matches the `recipes.discover_recipes` precedent at
  `recipes.py:112-113`); deliberately *unit-level* against the
  single argument the function takes — the `core/files/agents/`
  absent-state is a different walk and is not part of this CT.
  Future shared-audience-agents work will add a sibling CT
  when the discovery shape for `core/files/agents/` is pinned.

## Non-goals

Per [RFC-0004 §Non-goals](../../rfc/0004-agent-identity-primitives.md#non-goals)
and surfaced here so reviewers can hold the boundary:

- **Multi-agent coordination / agents-calling-agents.** One identity
  per scheduled invocation at v1; coordination is a follow-on RFC.
- **Identity learning.** Agents are static files; persona feedback
  loops are out of scope.
- **Replacing skills with identities.** Agents *compose* with skills
  at dispatch time; SKILLs are unchanged.
- **Hosting personas externally** (registry, marketplace, shared
  identity bundles). The kit ships files; users can fork.
- **Reading `AGENT.md` body contents in kit code.** The kit reads
  only the file's existence. Frontmatter and body are for Claude's
  consumption.
- **Changes to the RFC-0003 scheduling/executor surface beyond the
  additive `--agent` flag and additive journal fields.**
- **Discovery-time kind-vs-directory enforcement.** The kit's
  today-permissive posture (declared `kind:` in `primitive.yaml` is
  the source of truth; the parent directory name is not
  cross-checked at discovery for any kind) applies to `agent`
  unchanged. Tightening this would touch every kind together and
  belongs in a follow-on RFC; this spec ships no new enforcement.
- **Auto-rebinding schedules when a recipe / contract / install
  changes.** The journaled `agent` is frozen at install time.
- **Per-agent config on the agent primitive itself.** Per
  [RFC-0004 §"Resolved before review" #4](../../rfc/0004-agent-identity-primitives.md#resolved-before-review),
  agent-specific config lives in vault pages
  (`identity.md`, `dashboards/*.md`), not on the AGENT.md or
  primitive.yaml.
- **CLI-side fallback for older `claude` versions lacking
  `--agent`.** Pinned out per [ADR-0010 §Decision](../../adr/0010-agent-passthrough-via-claude-agent-flag.md#decision).
  Users on older CLIs get the no-agent default.

## Constraints

- **No new top-level repo directory.** `templates/agents/` is added
  under the existing `templates/` directory; `core/files/agents/`
  is **not** created at v1 (shared-audience agents are deferred per
  §Inputs). The repo-root `.claude/agents/` (kit-development
  subagents) is unaffected — vault-side and kit-side scopes do not
  mix per [`AGENTS.md` §"Two scopes, one repo"](../../../AGENTS.md#two-scopes-one-repo).
- **No new module boundary under `llm_wiki_kit/`.** The new code
  lives in existing modules: agent discovery in `primitives.py`,
  recipe-side validation in `recipes.py`, resolution + argv in
  `run.py` and `schedule/__init__.py`, doctor checks in
  `doctor.py`, CLI plumbing in `cli.py`. A new `llm_wiki_kit/agents.py`
  module would split logic the existing modules already own.
- **No new runtime dependency.** `pyyaml` + `pydantic>=2` + stdlib
  remain the runtime closure. The agent kind ships zero new
  third-party imports.
- **No new abstraction layer.** No factory, registry, or locator for
  agent resolution. The chain is a function with four branches; it
  does not warrant a class hierarchy.
- **No new public CLI verb beyond `wiki agents`.** A top-level
  enumeration verb mirroring `wiki outcomes` — one subject, no
  subcommands. A future RFC may layer CRUD onto it (`wiki agents
  install <op> <agent>`, etc.), at which point the bare verb either
  remains the enumeration form or gets a `list` subcommand
  promotion; v1 ships the bare verb. The `wiki outcomes` precedent
  is `cli.py:2282-2287`.
- **No kit-side reading or parsing of `AGENT.md` bodies.**
  Frontmatter is for Claude; the kit reads neither. If a future
  feature needs metadata, the field gets promoted into
  `primitive.yaml.config` — not the other way around.
- **No bypass of the existing primitive installer for agent files.**
  Vault-side `AGENT.md` writes route through the same path
  operations and content-types use; no new write-helper exemption
  (the schedule module's `write_os_artifact` is unrelated — agents
  install into the vault, not into OS state).
- **No retro-edit of existing journal events.** Every model change
  is additive (new field with default, or new event class). ADR-0002
  §Negative's additive-schema rule covers the migration.
- **No new ADR.** ADR-0010 already pins the `--agent` argv shape.
  This spec implements it; further ADRs would only land if a load-
  bearing decision surfaces during implementation.

## Default agent catalog

The eight v1 agents (per [RFC-0004 §8](../../rfc/0004-agent-identity-primitives.md#8-default-identities-per-recipe)).
Each ships at `templates/agents/<name>/` with `primitive.yaml`
(`kind: agent`, `version: 0.1.0`) and
`files/.claude/agents/<name>/AGENT.md`. Recipe bindings ship in the same
PR that adds the agents (the `family.yaml`, `work-os.yaml`, and
`personal.yaml` recipes gain `agents:` blocks).

**`family` (3 agents):**

- `household-manager` — runs `weekly-digest`, `meal-planning`,
  `follow-up-tracker`.
- `trip-planner` — runs `trip-prep`.
- `care-coordinator` — runs `medical-summary`. (Bound only when
  `medical-summary` is opt-in installed; the `family.yaml` recipe
  does ship `medical-summary` per its current closure, so the
  binding lands by default. A user who declines medical can `wiki
  remove agent:care-coordinator`.)

**`work-os` (3 agents):**

- `stakeholder-steward` — runs `stakeholder-map-refresh`,
  `status-synthesis`.
- `renewals-watch` — runs `renewal-reminders`.
- `customer-listener` — runs `action-item-rollup`.

**`personal` (2 agents):**

- `personal-coordinator` — runs `weekly-digest`,
  `follow-up-tracker`, `meal-planning`.
- `decision-companion` — ships installed, **bound to no operation**
  at v1 (reserved for a future `decision-review` operation;
  `wiki agents` shows `OPERATIONS=—`).
