# Plan: wiki-agents

> **Implementation plan paired with `spec.md`.** The spec says *what*;
> the plan says *how, in what order, with what verification*.

- **Status:** Drafting
- **Spec:** [`docs/specs/wiki-agents/spec.md`](spec.md)
- **Owner:** maintainer

## Approach

Eight PRs land RFC-0004 in dependency order: the model surface first
(new kind enum, new event, additive fields), then the catalog +
recipe plumbing that gives those models a place to come from, then
the schedule-time resolution chain that produces a journaled agent
value, then the exec-time pass-through that consumes it, then the
discovery surface (`wiki agents` + doctor checks), then the
default catalog (PR-7a) and finally the vault-side SKILL updates
(PR-7b) that rewire `wiki-conflict`'s prose and ship the new
`wiki-agent` SKILL.

Each PR is one Claude Code session. Commit messages follow the
conventional-commits convention per
[`docs/CONVENTIONS.md` § Commit messages](../../CONVENTIONS.md#commit-messages):
`feat(agents):`, `fix(agents):`, etc.

Why this order: every later task consumes the previous one's surface.
The agent kind and journal events must exist before recipe validation
can reference them; recipe validation must work before
`wiki schedule install` can resolve from a recipe; the schedule's
journaled `agent` field must exist before doctor can check it; and
the default catalog can only be authored once all the
validation/install paths it exercises are green. PR-1 (model
surface) is a prerequisite for PR-2: PR-2's discovery tests assert
`kind == PrimitiveKind.AGENT`, so the enum value must land first.
PRs 1 → 2 → 3 → 4 → 5 → 6 → 7a → 7b are strictly sequential;
supervisor-mode parallelism does not apply within this plan because
every step consumes the previous step's surface.

**Mapping to RFC-0004 §"Migration path":** the RFC numbered seven
tasks; this plan numbers eight (the RFC's last task splits into
7a / 7b here per the C12 concern from the pre-EXECUTE reviewer).
RFC §"Migration path" task 1 → plan PR-1; RFC task 2 (additive
fields on `ScheduleInstalledEvent` and `PageProposalEvent`) is
distributed across plan PR-4 (`ScheduleInstalledEvent.agent` lands
where it's consumed) and plan PR-6 (`PageProposalEvent.proposed_by_agent`
lands alongside the doctor checks that observe it); RFC task 3 →
plan PR-2; RFC task 4 → plan PR-3; RFC task 5 → plan PR-4 + PR-5
(the schedule and run halves of the executor surface); RFC task 6
→ plan PR-6; RFC task 7 → plan PR-7a + PR-7b. The reshuffle puts
each additive field next to its first consumer, which makes each
PR self-contained for review.

**Structural temptations declined.** This plan's analog to the
work-loop's "tempted but declined" register is the spec's §Constraints
section (`spec.md` §Constraints), which lists: no new
`llm_wiki_kit/agents.py` module, no registry / locator abstraction
for resolution, no kit-side reading of `AGENT.md`, no fallback
`--system-prompt-file` invocation, no `wiki agents <verb>` CRUD
surface, no new runtime dep, no new top-level repo directory. Each
is justified in spec.md.

## Pre-conditions

- [RFC-0004](../../rfc/0004-agent-identity-primitives.md) Accepted — done.
- [ADR-0010](../../adr/0010-agent-passthrough-via-claude-agent-flag.md)
  Accepted — done (pins the `claude --agent <name>` argv shape).
- [`wiki-schedule`](../wiki-schedule/spec.md) implemented — done
  (`ScheduleInstalledEvent` exists; this plan adds the `agent`
  field to it).
- [`wiki-run-exec`](../wiki-run-exec/spec.md) implemented — done
  (`_build_argv`, `OperationRunEvent.event_id`,
  `OperationExecFailedEvent` exist; this plan extends them
  additively).
- `templates/agents/` directory created — PR-7a lands the catalog
  primitives and the directory itself; PR-2 only adds the
  `"agents"` entry to `_CATALOG_DIRS` and relies on the existing
  `discover_primitives` absent-directory tolerance (matches the
  `recipes.discover_recipes` precedent at `recipes.py:112-113`).
  `core/files/agents/` is **not** created at v1: shared-audience
  agents don't ship until a follow-on RFC defines their
  discovery shape (see plan §"Out of scope").

## Steps

1. **`PrimitiveKind.AGENT` + `OperationRunByAgentEvent` round-trip
   cleanly through the journal.**
   - **Depends on:** none.
   - **CT → construction test map:**

     |Spec CT|Construction test                                            |File                              |
     |-------|-------------------------------------------------------------|----------------------------------|
     |CT-24a |`test_pre_rfc4_journal_without_event_id_replays_byte_identical`|`test_models_agent_kind.py`     |
     |—      |`test_operation_run_by_agent_event_roundtrips_through_json`  |`test_models_agent_kind.py`       |

   - **Tests:** new `tests/unit/test_models_agent_kind.py`:
     - `test_primitive_kind_agent_enum_value_exists` —
       `PrimitiveKind.AGENT` enum value exists and stringifies to
       `"agent"`;
     - `test_operation_run_by_agent_event_roundtrips_through_json`
       — `OperationRunByAgentEvent(operation="x", agent="y",
       event_id="abc123abc123")` round-trips through
       `model_validate_json` → `model_dump_json`;
     - `event_id` is required (Pydantic rejects construction
       without it);
     - the discriminated `Event` union accepts the new type by
       its literal `"operation.run_by_agent"` discriminator;
     - `test_pre_rfc4_journal_without_event_id_replays_byte_identical`
       — CT-24a: load
       `tests/fixtures/journals/pre_rfc4_journal.jsonl` (a
       literal pre-RFC-4 journal respecting CT-24a's
       *byte-stability* restriction: every event type included
       must be one whose Pydantic shape this spec leaves
       unchanged; in particular **no** `page.proposal` and
       **no** `schedule.installed` lines, since this spec
       extends both. The v1 fixture exercises the contract by
       including pre-Task-17 `operation.run` lines plus
       `primitive.{install,upgrade,remove}`, `vault.init`,
       `vault.git_initialized`, and `lock.*` events; the other
       event types in the `Event` union are also byte-stable
       at v1 (enumerated in `spec.md` CT-24a) and may appear)
       plus the frozen
       reference snapshot `tests/fixtures/journals/pre_rfc4_state.json`
       (captured pre-RFC-4 by running `journal.replay_state`
       over the fixture once and committed). Replay the fixture
       under the extended discriminated `Event` union and assert
       `state.model_dump_json() == reference_text` byte-for-byte.
       The contract is byte-stability of every event type
       present in the fixture: a future spec extending any
       included type's Pydantic shape must drop that type from
       the fixture (and regenerate the snapshot if needed) to
       keep this test honest. Catches additive-schema replay
       regressions — not just "no parse error."
   - **Approach:** extend `llm_wiki_kit/models.py`:
     - Add `AGENT = "agent"` to `PrimitiveKind`.
     - Add `OperationRunByAgentEvent` class beside the existing
       operation events.
     - Extend the `Event` annotated union.
     No catalog-side or installer-side changes in this PR — the
     enum value is unrecognized by `_CATALOG_DIRS` until PR-2
     lands. This keeps the model change isolated and replay-safe.

2. **Agent catalog discovery: `_CATALOG_DIRS["agents"]` enumerates
   `templates/agents/<name>/primitive.yaml`.**
   - **Depends on:** Step 1.
   - **CT → construction test map:**

     |Spec CT|Construction test                                          |File                                  |
     |-------|-----------------------------------------------------------|--------------------------------------|
     |CT-1   |`test_discover_primitives_recognizes_agent_kind_directory` |`test_primitives_agent_kind.py`       |
     |CT-2   |`test_wiki_add_agent_installs_via_existing_primitive_event`|`tests/integration/test_install_agent.py`|
     |CT-26  |`test_discover_primitives_tolerates_missing_agents_catalog_dir`|`test_primitives_agent_kind.py`   |

   - **Tests:** new `tests/unit/test_primitives_agent_kind.py`:
     - `test_discover_primitives_recognizes_agent_kind_directory`
       — CT-1: `discover_primitives(tmp_path)` with a stub
       `templates/agents/household-manager/primitive.yaml`
       (`kind: agent`) returns a primitive whose `kind ==
       PrimitiveKind.AGENT`;
     - `test_discover_primitives_rejects_kind_directory_mismatch_for_agent`
       — a `templates/operations/household-manager/primitive.yaml`
       with `kind: agent` is rejected by the existing
       kind-vs-directory mismatch the same way other mismatches
       are today (no new code path);
     - `test_discover_primitives_tolerates_missing_agents_catalog_dir`
       — CT-26: build a `tmp_path` containing `templates/` with
       at least one non-agent kind directory
       (e.g. `templates/operations/foo/primitive.yaml`) and
       **no** `templates/agents/`; call
       `discover_primitives(tmp_path / "templates")` and assert
       success with zero `kind == PrimitiveKind.AGENT` entries.
       Matches the existing absent-dir tolerance in
       `primitives.discover_primitives` (mirrors
       `recipes.discover_recipes`'s missing-directory return at
       `recipes.py:112-113`);
     - `test_is_installed_agent_returns_true_after_install_event`
       — `is_installed_agent("household-manager", state)` returns
       `True` after a `PrimitiveInstallEvent` for
       `household-manager` (the catalog walk recovers the kind
       from `installed_primitives` + the discovered catalog).
     And `tests/integration/test_install_agent.py`:
     - `test_wiki_add_agent_installs_via_existing_primitive_event`
       — CT-2: end-to-end `wiki add agent:household-manager`
       against a `tmp_path` vault appends exactly one
       `PrimitiveInstallEvent` (no new install discriminator)
       and writes `<vault>/.claude/agents/household-manager/AGENT.md`
       byte-identical to the catalog source.
   - **Approach:** extend `llm_wiki_kit/primitives.py`:
     - Add `"agents"` to `_CATALOG_DIRS`.
     - Add `is_installed_agent(name, state)` helper (reused by
       PRs 3, 4, 5).
     - Do **not** ship an empty `core/files/agents/` directory.
       `discover_primitives` already tolerates a missing catalog
       directory (see the `recipes.discover_recipes` precedent —
       `recipes.py:112-113` returns `[]` rather than raising); the
       same shape applies here. The directory lands organically
       in a future RFC that ships shared-audience agents.
     - The end-to-end install path is exercised by
       `tests/integration/test_install_agent.py` above (CT-2);
       no new install-event discriminator is introduced.

3. **Recipe `agents:` block validates, closes, and rejects malformed
   bindings.**
   - **Depends on:** Step 2.
   - **CT → construction test map:**

     |Spec CT|Construction test                                              |File                              |
     |-------|---------------------------------------------------------------|----------------------------------|
     |CT-3   |`test_recipe_agents_block_validates_closure_happy_path`        |`test_recipes_agents.py`          |
     |CT-3   |`test_recipe_agents_missing_operation_raises_recipe_error`     |`test_recipes_agents.py`          |
     |CT-4   |`test_recipe_agents_wrong_kind_agent_raises_recipe_error`      |`test_recipes_agents.py`          |
     |CT-5   |`test_recipe_agents_duplicate_operation_binding_raises`        |`test_recipes_agents.py`          |
     |CT-6   |`test_recipe_agents_empty_runs_list_raises_validation_error`   |`test_recipes_agents.py`          |
     |CT-7   |`test_operation_contract_preferred_agent_validates_name_pattern`|`test_models_preferred_agent.py` |
     |—      |`test_recipe_with_empty_agents_block_roundtrips`               |`test_recipes_agents.py`          |
     |—      |`test_existing_recipes_load_with_empty_agents_blocks`          |`test_recipes_agents.py`          |

   - **Tests:** new `tests/unit/test_recipes_agents.py`:
     - `test_recipe_agents_block_validates_closure_happy_path` —
       CT-3 (happy half): a recipe with
       `agents.household-manager.runs: [weekly-digest]` validates
       when both names are in its closure;
     - `test_recipe_agents_missing_operation_raises_recipe_error`
       — CT-3 (failure half): removing `weekly-digest` from
       `primitives:` raises `RecipeError` naming both the agent
       and the operation;
     - `test_recipe_agents_wrong_kind_agent_raises_recipe_error`
       — CT-4: an `agents:` key resolving to a `kind: operation`
       primitive raises `RecipeError` containing `kind: agent
       expected`;
     - `test_recipe_agents_duplicate_operation_binding_raises` —
       CT-5: two agents both listing the same op in their
       `runs:` raises `RecipeError` naming both agents and the
       operation;
     - `test_recipe_agents_empty_runs_list_raises_validation_error`
       — CT-6: `agents.X.runs: []` raises a Pydantic
       `ValidationError` (via `min_length=1`) before recipe-side
       closure even runs;
     - `test_recipe_with_empty_agents_block_roundtrips` — pins
       that `agents: {}` is a no-op: the recipe loads, closure
       walks succeed, no validation runs over the empty block;
     - `test_existing_recipes_load_with_empty_agents_blocks` —
       loads each of `recipes/family.yaml`,
       `recipes/work-os.yaml`, `recipes/personal.yaml` after the
       PR-3 YAML edits (which add an empty `agents: {}`) and
       asserts every existing recipe test continues to pass.
     And `tests/unit/test_models_preferred_agent.py`:
     - `test_operation_contract_preferred_agent_validates_name_pattern`
       — CT-7: valid names load; `"Household_Manager"` (capital
       / underscore) is rejected at contract-load.
   - **Approach:** extend `llm_wiki_kit/models.py` with
     `AgentBinding(_StrictModel)` and `Recipe.agents:
     dict[str, AgentBinding]`. Extend `recipes.py`'s closure step
     (or add a post-closure validator function) to check
     agent/operation membership and uniqueness. Extend
     `models.py:OperationContract` with `preferred_agent: str |
     None = None`. Update the family/work-os/personal recipes'
     YAML in this PR to ship empty `agents:` blocks (so the
     loader code paths are exercised by every existing recipe
     test); the bindings themselves land in PR-7 alongside the
     agent catalog so all the tests pass top-down.

4. **`wiki schedule install`'s resolution chain emits a frozen
   `agent` value on the journaled event.**
   - **Depends on:** Step 3.
   - **CT → construction test map:**

     |Spec CT|Construction test                                                                 |File                                       |
     |-------|----------------------------------------------------------------------------------|-------------------------------------------|
     |CT-8   |`test_schedule_install_cli_agent_flag_wins_resolution`                           |`test_schedule_install_agent.py`           |
     |CT-9   |`test_schedule_install_recipe_binding_wins_over_contract_preferred`              |`test_schedule_install_agent.py`           |
     |CT-10  |`test_schedule_install_contract_preferred_agent_used_when_recipe_silent`         |`test_schedule_install_agent.py`           |
     |CT-11  |`test_schedule_install_resolves_to_none_when_nothing_declares`                   |`test_schedule_install_agent.py`           |
     |CT-12  |`test_schedule_install_refuses_missing_agent_name_via_cli_flag`                  |`test_schedule_install_agent.py`           |
     |CT-13  |`test_schedule_install_skips_uninstalled_contract_preferred_silently`            |`test_schedule_install_agent.py`           |
     |CT-20  |`test_schedule_list_renders_agent_column` (CT-20 lands here, not in PR-6)         |`test_schedule_list.py` amendment          |
     |CT-24b |`test_pre_rfc4_schedule_installed_event_without_agent_field_replays`             |`test_schedule_install_agent.py`           |

   - **Tests (construction):**
     - `tests/unit/test_schedule_install_agent.py`:
       - `test_schedule_install_cli_agent_flag_wins_resolution` —
         CT-8: vault with both a recipe binding and a contract
         `preferred_agent` for `weekly-digest`; `wiki schedule
         install weekly-digest --agent <other>` writes
         `agent="<other>"` on the event and `--agent <other>` in
         the OS artifact's `exec_command`. Uses the existing
         `_resolve_emitter` stub from
         [`wiki-schedule`](../wiki-schedule/spec.md)'s test seam.
       - `test_schedule_install_recipe_binding_wins_over_contract_preferred`
         — CT-9.
       - `test_schedule_install_contract_preferred_agent_used_when_recipe_silent`
         — CT-10.
       - `test_schedule_install_resolves_to_none_when_nothing_declares`
         — CT-11: the OS artifact's `exec_command` is the
         existing four-token shape; the `agent:` line is absent
         from the stdout summary.
       - `test_schedule_install_refuses_missing_agent_name_via_cli_flag`
         — CT-12: refusal aborts before
         `journal.transaction()` opens, so zero events of any
         type are appended (extends
         [`wiki-schedule`](../wiki-schedule/spec.md)'s pre-load
         failure invariant).
       - `test_schedule_install_skips_uninstalled_contract_preferred_silently`
         — CT-13.
       - `test_schedule_install_artifact_exec_command_includes_agent_flag`
         — pins the two-token append (`["--agent", "<name>"]`)
         to the `exec_command` array; with no agent, the array
         is unchanged.
       - `test_pre_rfc4_schedule_installed_event_without_agent_field_replays`
         — CT-24b: a literal pre-RFC-4 `schedule.installed` JSON
         line without the `agent` field replays under the
         extended Pydantic model with `agent is None`. No new
         migration code; just verifies additive-schema replay.
     - `tests/unit/test_schedule_list.py` amendment:
       - `test_schedule_list_renders_agent_column` — CT-20: two
         installed schedules, one with agent, one without; the
         emitted table has the AGENT column populated for the
         first row and `—` (U+2014) for the second.
   - **Approach:** extend `llm_wiki_kit/schedule/__init__.py`:
     - Add `agent: str | None = None` keyword to
       `install(...)`.
     - Add a `_resolve_agent(operation, vault_state, recipe,
       contract, cli_agent) -> str | None` helper (private
       module function — does **not** justify a new module).
     - Validate the resolved name via `is_installed_agent`
       *before* `journal.transaction()` opens. WikiError on
       miss; zero events.
     - Emit the artifact's `exec_command` with the two-token
       append when `agent` is non-`None`.
     - Append `agent` to `ScheduleInstalledEvent` constructor
       call.
     - Update `_cmd_schedule_install` in `cli.py` to accept
       `--agent <name>` and thread the value through.
     - Update `list_schedules`'s rendering in
       `_cmd_schedule_list` to show the AGENT column.

5. **`wiki run [--exec] [--agent]` resolves, validates, journals
   `OperationRunByAgentEvent`, and passes `--agent` to `claude`.**
   - **Depends on:** Step 4.
   - **CT → construction test map:**

     |Spec CT|Construction test                                                          |File                                  |
     |-------|---------------------------------------------------------------------------|--------------------------------------|
     |CT-14  |`test_build_argv_inserts_agent_flag_before_prompt_positional`             |`test_run_exec_agent.py`              |
     |CT-15  |`test_run_exec_agent_missing_journals_exec_failed_event`                   |`test_run_exec_agent.py`              |
     |CT-16  |`test_run_exec_pairs_run_event_with_run_by_agent_event_under_one_lock`     |`test_run_exec_agent.py`              |
     |CT-17  |`test_run_dispatch_only_honors_cli_agent_flag_without_chain_walk`          |`test_run_dispatch_agent.py`          |

   - **Tests (construction):**
     - `tests/unit/test_run_exec_agent.py`:
       - `test_build_argv_inserts_agent_flag_before_prompt_positional`
         — CT-14: the argv constructed by `_build_argv` contains
         `["--agent", "household-manager"]` immediately before
         the trailing prompt positional (per ADR-0010). With
         no agent, the same call produces the ADR-0009 shape
         unchanged.
       - `test_run_exec_agent_missing_journals_exec_failed_event`
         — CT-15: install a schedule with an agent, then `wiki
         remove agent:<name>`; the next `wiki run --exec`
         simulation appends one `OperationExecFailedEvent` with
         `reason="agent-missing"` and zero
         `OperationRunByAgentEvent`s.
       - `test_run_exec_pairs_run_event_with_run_by_agent_event_under_one_lock`
         — CT-16: assert (a) both events appended inside one
         `LockAcquiredEvent` / `LockReleasedEvent` pair, (b)
         same `event_id`, (c) `OperationRunEvent` precedes
         `OperationRunByAgentEvent` on disk.
     - `tests/unit/test_run_dispatch_agent.py`:
       - `test_run_dispatch_only_honors_cli_agent_flag_without_chain_walk`
         — CT-17: vault with a recipe binding for
         `weekly-digest`; `wiki run weekly-digest` (no `--exec`,
         no `--agent`) appends only an `OperationRunEvent`. The
         same call with `--agent some-other` appends both
         events with `agent="some-other"` (the chain does not
         override the explicit flag).
   - **Approach:** extend `llm_wiki_kit/run.py`:
     - Add `agent: str | None = None` parameter to `dispatch()`
       and the `--exec` helper.
     - Add a `_resolve_agent_for_run(...)` helper mirroring
       schedule's chain (operation contract + recipe binding +
       CLI flag); skip the recipe step in dispatch-only mode.
     - Validate the resolved name via `is_installed_agent`
       under the same transaction as the dispatch append. On
       failure: append `OperationExecFailedEvent(reason=
       "agent-missing", ...)` and `WikiError`.
     - Extend `_build_argv` with the two-token `--agent`
       append per ADR-0010. Mirrors the
       `wiki-run-exec` spec §"Contracts with other modules"
       `_build_argv` signature.
     - Add `--agent <name>` to the argparse surface in
       `cli.py:_cmd_run`.
     - Add `"agent-missing"` to
       `OperationExecFailedEvent.reason`'s Literal set (additive
       enum-value extension per ADR-0002).
     - Amend `wiki-run-exec/spec.md` §"Contracts with other
       modules" in the same PR: the `_build_argv` signature
       gains `agent: str | None = None`; the reason enum gains
       `"agent-missing"`. Drift between this spec and that one
       is a bug.

6. **`wiki agents` lists installed agents; `wiki doctor`
   reports binding drift and version drift as warnings.**
   - **Depends on:** Step 5.
   - **CT → construction test map:**

     |Spec CT|Construction test                                                |File                              |
     |-------|-----------------------------------------------------------------|----------------------------------|
     |CT-18  |`test_agents_lists_installed_with_recipes_and_operations`       |`test_cmd_agents.py`              |
     |CT-19  |`test_agents_unions_recipes_via_block_and_closure`              |`test_cmd_agents.py`              |
     |CT-21  |`test_doctor_warns_on_missing_agent_md_file`                    |`test_doctor_agents.py`           |
     |CT-22  |`test_doctor_warns_on_agent_upgrade_since_last_run`              |`test_doctor_agents.py`           |
     |CT-23  |`test_page_proposal_event_proposed_by_agent_roundtrips`         |`test_models_page_proposal_agent.py`|
     |CT-24c |`test_pre_rfc4_page_proposal_without_proposed_by_agent_replays` |`test_models_page_proposal_agent.py`|

   - **Tests (construction):**
     - `tests/unit/test_models_page_proposal_agent.py`:
       - `test_page_proposal_event_proposed_by_agent_roundtrips`
         — CT-23: `PageProposalEvent(path="x.md",
         proposed_path="x.md.proposed", hash="abc",
         proposed_by_agent="household-manager")` round-trips
         through `model_validate_json` / `model_dump_json`.
       - `test_pre_rfc4_page_proposal_without_proposed_by_agent_replays`
         — CT-24c: a literal pre-RFC-4 `page.proposal` JSON line
         without the `proposed_by_agent` field replays with
         `proposed_by_agent is None` under the extended
         Pydantic model.
     - `tests/unit/test_cmd_agents.py`:
       - `test_agents_lists_installed_with_recipes_and_operations`
         — CT-18: fixture vault with three installed agents under
         the `family` recipe; assert three rows + header + sorted
         operations + empty-OPERATIONS rendered as `—` for an
         agent (decision-companion) that's installed but unbound.
       - `test_agents_unions_recipes_via_block_and_closure` —
         CT-19: pins the two-rule RECIPES contribution
         (`agents:` block membership OR `primitives:` closure
         membership). The shipped catalog at v1 doesn't
         naturally exercise rule (b) (every default agent's
         RECIPES set matches its `agents:` block membership),
         so this test ships a fixture kit_root under
         `tests/fixtures/repo/` containing
         `tests/fixtures/repo/recipes/test_cross_recipe.yaml`
         (lists `personal-coordinator` in `primitives:` without
         an `agents:` binding) and points
         `list_agents(vault_root, kit_root=tests/fixtures/repo)`
         at the fixture root; asserts the two-rule union.
       - `test_agents_empty_vault_prints_only_header` —
         covers the no-agents-installed case.
     - `tests/unit/test_doctor_agents.py`:
       - `test_doctor_warns_on_missing_agent_md_file` — CT-21:
         install schedule binding `household-manager`, delete the
         AGENT.md, assert doctor exits `0`, stdout has the agent
         name and the fix hint, stderr empty.
       - `test_doctor_warns_on_agent_upgrade_since_last_run` —
         CT-22: append a `PrimitiveUpgradeEvent` for the agent
         and zero `OperationRunByAgentEvent`s since; assert
         warning shape (versions + bound operations).
       - `test_doctor_silent_when_no_agents_bound` — pins the
         negative path (zero schedule entries reference an
         agent → no warnings).
   - **Approach:**
     - Add `_cmd_agents` to `cli.py`; register a new top-level
       `agents` verb (no subcommand), mirroring the existing
       `wiki outcomes` shape at `cli.py:2282-2287`.
     - Implement `primitives.list_agents(vault_root, kit_root) ->
       list[AgentRow]` — lives in `primitives.py` next to
       `is_installed_agent` (same module to avoid a new
       boundary). `kit_root` is the conventional name for the
       repo-side catalog root throughout the codebase
       (`recipes.installed_outcome_verbs(vault_root, kit_root)`,
       `cli._kit_paths(args.kit_root)`,
       `operations._load_contract(operation, kit_root)`). `AgentRow`
       is a small dataclass: `name: str`, `recipes: list[str]`,
       `operations: list[str]`.
     - Extend `doctor.py` with `_check_agents(state,
       vault_root)`; called after `_check_schedules`. Output
       formatting mirrors the existing doctor warning shape.
     - Add `PageProposalEvent.proposed_by_agent` field to
       `models.py`.

7a. **Default agent catalog ships the eight v1 agents and three
    recipe `agents:` blocks.**
   - **Depends on:** Step 6.
   - **CT → construction test map:**

     |Spec CT|Construction test                                            |File                                       |
     |-------|-------------------------------------------------------------|-------------------------------------------|
     |CT-25  |`test_agent_catalog_primitive_yaml_well_formed` + `test_agent_md_frontmatter_parses` + `test_eight_default_agents_present`|`test_agent_catalog.py`|
     |—      |`test_init_family_recipe_installs_three_default_agents`      |`tests/integration/test_init_family_recipe_agents.py`|
     |—      |`test_init_work_os_recipe_installs_three_default_agents`     |`tests/integration/test_init_work_os_recipe_agents.py`|
     |—      |`test_init_personal_recipe_installs_two_default_agents`      |`tests/integration/test_init_personal_recipe_agents.py`|

   - **Tests:**
     - new `tests/unit/test_agent_catalog.py`:
       - `test_agent_catalog_primitive_yaml_well_formed` — every
         `templates/agents/<name>/primitive.yaml` has
         `kind: agent` and `version` matching `SEMVER_PATTERN`;
       - `test_agent_md_frontmatter_parses` — every
         `files/agents/<name>/AGENT.md`'s YAML frontmatter
         parses via `pyyaml.safe_load` (verification-side read
         per spec §Invariants — kit runtime still reads zero
         bytes);
       - `test_eight_default_agents_present` — the eight names
         listed in spec §"Default agent catalog" all exist;
         spurious entries are flagged.
     - new `tests/integration/test_init_family_recipe_agents.py`:
       - `test_init_family_recipe_installs_three_default_agents`
         — `wiki init --recipe family <tmp_path>` produces a
         vault whose `.claude/agents/` directory contains
         `household-manager/AGENT.md`,
         `trip-planner/AGENT.md`, and
         `care-coordinator/AGENT.md`; each byte-identical to
         the catalog source. `wiki agents` on the same vault
         prints three rows with operations bound per spec
         §"Default agent catalog".
     - integration tests for `work-os` and `personal` recipes
       mirror the `family` test above (two more files).
   - **Approach:**
     - Author the eight agent primitives under
       `templates/agents/<name>/`. Each `AGENT.md` follows the
       frontmatter convention in spec §Inputs (`audience`,
       `role`, `tone`, `knows:`) and a short freeform body.
     - Add populated `agents:` blocks to `recipes/family.yaml`,
       `recipes/work-os.yaml`, `recipes/personal.yaml` per spec
       §"Default agent catalog" (replacing the empty `agents: {}`
       blocks PR-3 shipped). `decision-companion` ships
       installed (in `personal.yaml`'s `primitives:` closure)
       but unbound (no entry in `agents.decision-companion`).

7b. **Vault-side SKILL updates wire conflict-aware UX and ship the
    `wiki-agent` SKILL.**
   - **Depends on:** Step 7a (needs the catalog so the SKILL
     integration tests can exercise it against a populated vault).
     PR-7b ships **no kit production code changes** (no
     `llm_wiki_kit/` edits); the two new `tests/unit/test_skill_*.py`
     files are kit-side Python that verifies the shipped
     vault-side SKILLs are well-formed.
   - **CT → construction test map:** none of the spec's contract
     tests fall here — PR-7b is SKILL-prose authoring, and the
     prose is verified by `pyyaml.safe_load` plus a string-presence
     check, not by a behavioral CT. PR-6's CT-23 already pins the
     kit-side `PageProposalEvent.proposed_by_agent` field the
     SKILL reads.
   - **Tests:**
     - new `tests/unit/test_skill_wiki_conflict_agent_aware.py`:
       - `test_wiki_conflict_skill_frontmatter_parses` — the SKILL
         file's frontmatter parses via `pyyaml.safe_load`;
       - `test_wiki_conflict_skill_mentions_proposed_by_agent` —
         a literal substring check that the SKILL body contains
         the bareword `proposed_by_agent` (the journal field
         name; the SKILL author writes prose like "if the
         `PageProposalEvent` carries a non-null
         `proposed_by_agent`, render the agent name in the
         user-facing conflict prompt"). Pinning the field name
         rather than a phrase keeps the SKILL author free to
         word the prose naturally while the test guarantees the
         field is referenced.
     - new `tests/unit/test_skill_wiki_agent.py`:
       - `test_wiki_agent_skill_frontmatter_parses`;
       - `test_wiki_agent_skill_names_trigger_phrases` — pins
         the SKILL's discoverability cues per
         [RFC-0004 §Outcome](../../rfc/0004-agent-identity-primitives.md#outcome).
   - **Approach:**
     - Author `core/files/skills/wiki-agent/SKILL.md` per
       [RFC-0004 §Outcome](../../rfc/0004-agent-identity-primitives.md#outcome).
     - Update `core/files/skills/wiki-conflict/SKILL.md` to
       inspect the most recent `PageProposalEvent` for a
       conflicted path and surface `proposed_by_agent` (when
       non-`None`) in the user-facing prose, per
       [RFC-0004 §6](../../rfc/0004-agent-identity-primitives.md#6-conflict-aware-ux-naming-the-agent).
     - Re-run the full CT suite on a freshly-initialized vault
       per recipe (each recipe's integration test from PR-7a)
       to confirm the conflict UX reads the journaled
       `proposed_by_agent` correctly end-to-end.

## Verification gate

Each PR runs the standard gate sequence per
[`AGENTS.md` § Commands you'll need](../../../AGENTS.md#commands-youll-need):

```
ruff check llm_wiki_kit tests
ruff format --check llm_wiki_kit tests
mypy llm_wiki_kit tests
pytest -m 'not slow'
```

End-to-end verification (post PR-7):

- All 28 contract-test checks from `spec.md` pass:
  CT-1 through CT-23, CT-25, CT-26 (25 numbered behaviors)
  plus CT-24's three sub-clauses CT-24a/b/c (each verified
  by its own test, distributed across PR-1 / PR-4 / PR-6).
- `wiki init --recipe family <tmp_path>` produces a vault whose
  `.claude/agents/` contains the three family-shipped agents.
- `wiki schedule install weekly-digest` on that vault journals
  `agent="household-manager"` (resolved from the recipe binding)
  and emits an OS-side artifact whose `exec_command` includes
  `--agent household-manager`.
- `wiki agents` lists `care-coordinator`, `household-manager`,
  `trip-planner` with their bound operations.
- `wiki doctor` is clean on that vault. Deleting
  `<vault>/.claude/agents/household-manager/AGENT.md` flips
  doctor to a warning naming the agent and the fix command,
  while still exiting `0`.
- Removing `household-manager` (`wiki remove
  agent:household-manager`) and re-running the scheduled exec
  (simulated) produces an `OperationExecFailedEvent` with
  `reason="agent-missing"` and surfaces a clear `WikiError`
  message — no `claude` subprocess is invoked.

## Risks

- **Resolution chain ambiguity across multiple recipes.** A
  multi-recipe environment (the kit's repo carries three; future
  forks may carry more) creates the question "whose binding
  applies?" Spec resolves this via `VaultInitEvent.recipe`, which
  is a required `str` field on the journal model
  (`llm_wiki_kit/models.py:243`) — every well-formed vault carries
  exactly one recorded recipe. Mitigation: PR-4's CT-9 / CT-10 /
  CT-11 pin the recipe-binding behavior; the
  no-`VaultInitEvent`-at-all corruption case routes through
  `cli.py`'s existing "vault at &lt;root&gt; has no vault.init event"
  refusal, before agent resolution runs.
- **`OperationRunByAgentEvent` pairing under the journal flock.**
  The two events must be appended inside one `journal.transaction()`
  so partial writes can't orphan the audit tag. Mitigation: PR-5's
  CT-16 explicitly asserts the lock-pair bracket; the test runs
  the same `journal.transaction()` shape `wiki-schedule` uses
  and inherits its locking guarantees.
- **Agent-name validation runs at three distinct sites.** Each
  pass guards a different failure mode; consolidation would lose
  load-bearing coverage:
  1. **Recipe-load time (PR-3).** `recipes.py` walks the closure
     and rejects `agents.<unknown>`, agents pointing at non-agent
     primitives, operations missing from the closure, and
     duplicate-binding errors. Catches typos at `wiki init
     --recipe <name>` / `wiki upgrade` time — before any install
     can happen.
  2. **Install time (PR-4).** `schedule.install` validates the
     resolved name (from CLI flag, recipe, or contract) against
     `installed_primitives` *pre-transaction*. Catches "agent
     name passed but never installed in this vault" before
     journaling. ADR-0010 §Decision was amended alongside this
     spec/plan work to acknowledge this pass.
  3. **Dispatch time (PR-5).** `run.dispatch` re-validates the
     name immediately before the `claude` subprocess. Catches
     "agent removed between install and fire" — a vault can
     `wiki remove agent:<name>` against a live schedule. Per
     ADR-0010.
  The three passes are not redundant: they guard recipe-internal
  typos, post-recipe vault-state drift, and mid-life removal
  respectively. A future contributor reading PR-5's validation
  code must not consolidate it into PR-4's pass — the schedule's
  journaled `agent` field is frozen at install but the agent
  primitive can still be removed afterward.
- **Recipe edits during a live vault.** A user editing
  `recipes/family.yaml` after `wiki init` does not auto-rebind
  existing schedules. The journaled `agent` is frozen. Mitigation:
  spec §Invariants documents this; `wiki doctor` (PR-6) surfaces
  the version-drift warning when an agent upgrade happens since
  the last run, which is the user-facing nudge to re-check
  bindings.
- **`wiki-conflict` SKILL frontmatter brittleness.** The SKILL is
  authored prose; PR-7's tests only assert well-formedness, not
  exact prose. Mitigation: the SKILL update is small (one
  conditional prose branch reading `proposed_by_agent`); the
  vault-side change isn't load-bearing for kit-side CI.
- **Coupling to RFC-0003 work that's just landed.** RFC-0003's
  `ScheduleInstalledEvent` and the schedule install transaction
  shape are pre-conditions for PR-4. Mitigation: those landed in
  PRs #87–#95 already; the spec's "Constrained by" line cites
  them, and PR-4's tests reuse the `_resolve_emitter` test seam
  the schedule plan established.

## Out of scope

- **Multi-agent coordination** — agents calling agents. Pinned out
  by [RFC-0004 §Non-goals](../../rfc/0004-agent-identity-primitives.md#non-goals);
  follow-on RFC.
- **Identity learning** — agents updating their own AGENT.md from
  feedback. Static files only at v1.
- **Reading `AGENT.md` body contents in kit code.** The kit reads
  only the file's existence. Frontmatter and body are for Claude's
  consumption.
- **Auto-rebinding schedules** when a recipe / contract / install
  changes. The journaled `agent` is frozen at install time;
  re-binding is `uninstall` + `install`.
- **A `wiki agents <verb>` top-level surface** (`wiki agents
  install <op> <agent>`, etc.). The `--agent` flag is additive on
  the existing `schedule install` / `run` verbs; a dedicated
  `agents` verb is a future RFC if discoverability suffers.
- **`shared`-audience default agents.** v1 ships zero of these;
  `core/files/agents/` is not created on disk at v1 and discovery
  tolerates the absent directory per the existing
  `recipes.discover_recipes` precedent. The discovery *shape* for
  shared-audience agents (whether they ship with a `primitive.yaml`
  like recipe-scoped agents, or without one in the
  `core/files/skills/` style) is deliberately left for a follow-on
  RFC to pin when the first shared-audience agent actually ships.
- **CLI-side fallback for older `claude` versions** lacking
  `--agent`. Pinned out by
  [ADR-0010](../../adr/0010-agent-passthrough-via-claude-agent-flag.md#consequences).
- **Frontmatter validation by the kit.** A future RFC may promote
  `audience`, `role`, `tone`, `knows` into `primitive.yaml.config`
  if the kit needs them; v1 leaves them in AGENT.md for Claude
  only.
