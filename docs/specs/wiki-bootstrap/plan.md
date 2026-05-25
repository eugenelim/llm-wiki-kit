# Plan: wiki-bootstrap

> **Implementation plan paired with `spec.md`.** The spec says *what*;
> the plan says *how, in what order, with what verification*.

- **Status:** Drafting
- **Spec:** [`docs/specs/wiki-bootstrap/spec.md`](spec.md)
- **Owner:** maintainer

## Approach

One PR, six sequential tasks. The work is **vault-side artifacts +
recipe-vault test fixtures + their tests** — no `llm_wiki_kit/`
Python changes, no new CLI surface, no journal-schema change (per
spec §Constraints 1, 3, 6). The implementation surface is small:
one new SKILL directory, one bullet appended to `core/files/AGENTS.md`
plus an audit + intro rephrase, one line added to `core/files/.gitignore`,
three new `tests/evals/conftest.py` fixtures (`personal_vault`,
`family_vault`, `work_os_vault`), and three test files exercising the
spec's 16 acceptance criteria.

The dependency arrow is **artifacts → conftest fixtures → unit tests →
integration test → wizard-behavior evals → trigger/flow/post-bootstrap
evals**. T1 (artifacts) and T2 (conftest fixtures) are sequential
preconditions; once both land, T3/T4/T5/T6 fan out cleanly — they
share no source files and no parametrize tables. The plan is
documented sequentially for clarity; supervisor mode is a fit after
T1+T2 if execution time matters.

This PR amends the spec in the same commit. Two amendments were
driven by plan-review iterations:

1. **AC 12 instrument dropped.** The "kill the eval subprocess after
   the verb-demo step" instrument was replaced with the equivalence
   "every pre-marker step is read-only (Invariants 2, 3, 7), so
   post-demo state == post-init state." Citation was tightened
   per iteration-2 Blocker 1.
2. **Demo mechanism changed from `wiki <verb> --help` to reading the
   verb's vault-side SKILL.md.** Iteration-2 Blocker 2 verified that
   `wiki run <op> --help` prints argparse-generated help from the
   `wiki run` subparser (`llm_wiki_kit/cli.py:1590-1597`), **not**
   the operation's contract `description:` — the help mechanism the
   prior draft relied on is structurally absent. The wizard now
   reads `<vault>/skills/<skill>/SKILL.md` directly (skill name
   from `wiki outcomes`'s verb → skill mapping) and surfaces a
   gloss from the SKILL frontmatter description. Invariant 7,
   Constraint 10, AC 14, Non-goal 9, and all three worked
   transcripts updated accordingly.

Verification mode picks per task:

- **T1** is **goal-based** — the artifact is SKILL prose; T3 is
  the verification of record. The repo does not currently lint
  `core/files/skills/*.md`; the unit tests in T3 are the gate.
- **T2** is **goal-based** — the conftest factories produce vaults
  that can be `wiki outcomes`'d; their correctness is the positive
  evidence in T5/T6.
- **T3** is **TDD** — unit tests against the artifacts.
- **T4** is **TDD** — one integration test against `wiki init`.
- **T5** and **T6** are **eval-driven** — they spawn Claude Code
  via `tests/evalkit/` against fixture vaults. Slow, marked
  `pytest.mark.eval`, gated behind `ANTHROPIC_API_KEY` and
  `skip_if_no_claude`. They run on CI in the dedicated Evals
  workflow.

### Declined patterns (commitments for REVIEW)

- **Tempted to interpolate the SKILL.md with `{recipe_name}` /
  `{vault_name}`.** Declined per spec §Constraints 7 / ADR-0001.
- **Tempted to add a `wiki bootstrap` CLI verb.** Declined per
  spec §Non-goal 3 / §Constraints 3.
- **Tempted to journal the marker via a new `BootstrapCompletedEvent`
  type.** Declined per spec §Constraints 6.
- **Tempted to ship a `wiki-bootstrap` subagent under
  `.claude/agents/`.** Declined per spec §Constraints 12.
- **Tempted to pre-populate seed pages from the wizard.** Declined
  per spec §Non-goal 1 / §Non-goal 2.
- **Tempted to add a `wiki doctor` check that warns "vault is not
  bootstrapped".** Declined per spec §Contracts table. Would put
  a second reader on the marker and breach the file-path gating
  rule.
- **Tempted to extract a `vault_manifest_hash` helper between T5's
  vault-wide hash check and existing byte-hash assertions.**
  Declined: the assertion fits in five lines inline per test; a
  shared helper would tempt later tests to share it without
  thinking about the exclusion set.
- **Tempted to fold T5 (wizard behavior) and T6 (trigger/flow
  evals) into one eval file.** Declined: T5 asserts on
  side-effect-free demo + marker semantics; T6 asserts on
  SKILL-load discovery. Different assertion families.
- **Tempted to enhance `wiki run <op> --help` to include the
  contract description so the wizard could use `wiki <verb> --help`
  as the demo mechanism.** Declined: separate concern (would
  modify `llm_wiki_kit/cli.py`'s run subparser, out of scope for
  a vault-side-only PR per spec §Constraints 1). The wizard's
  SKILL.md-read approach is cleaner anyway — the SKILL description
  is purpose-written for the agent audience, the contract
  description is purpose-written for the CLI-help audience.
- **Tempted to author a `wiki-agent` bullet from a freeform
  one-liner during the T1.2 AGENTS.md audit.** Declined: the bullet
  prose mirrors `core/files/skills/wiki-agent/SKILL.md`'s
  frontmatter description (truncated to one line so the bullet
  shape matches the others); copy from there rather than invent.

## Pre-conditions

- Spec [`docs/specs/wiki-bootstrap/spec.md`](spec.md) merged into
  `main` (PR #109 squash-commit `417d739`). This PR amends the
  spec in the same commit (see §Approach).
- `wiki outcomes` ships per
  `docs/specs/outcome-named-entry-points/spec.md`. It returns a
  three-column table (`verb`, `operation`, `skill`); the wizard
  reads this output to map verb → skill for the demo step.
- Today's shipped verbs are `digest` (via `weekly-digest` operation
  → skill `weekly-digest`), `plan-meals` (via `meal-planning`
  operation → skill `meal-planning`), and `refresh-stakeholders`
  (via `stakeholder-map-refresh` operation → skill
  `stakeholder-map-refresh`). The three shipped recipes install
  verbs as follows: `personal` and `family` both ship
  `weekly-digest` + `meal-planning` → verbs `{digest, plan-meals}`
  for both; `work-os` ships `stakeholder-map-refresh` only → verb
  `{refresh-stakeholders}`. The `personal` ↔ `family` overlap is a
  real spec property; the flow eval (T6.2) handles it by dropping
  the `family` case for v1 (zero marginal coverage over the
  `personal` case — re-add when `family` ships a unique verb).
- `wiki <verb> --help` is **not** used by this plan. Per
  `llm_wiki_kit/cli.py:1590-1597`, `wiki run <op> --help` prints
  argparse-generated help from the `wiki run` subparser
  (operation-agnostic flag list), not the operation's contract
  `description:`. The wizard demos by reading
  `<vault>/skills/<skill>/SKILL.md` instead. If a future spec
  enhances `wiki run <op> --help` to include the contract
  description, a follow-up plan amendment can revisit.
- `tests/evalkit/__init__.py` (the package) ships with
  `run_claude`, `skip_if_env_unset`, `skip_if_no_claude`,
  `ordered_skill_reads`, and `assert_skill_loaded`. T2.1 lands a
  new `ordered_tool_calls(result) -> list[ToolUse]` helper
  (with `ToolUse = NamedTuple("ToolUse", [("name", str), ("input", dict)])`);
  T5 cases 3, 4, 5 are the consumers (case 3 asserts the
  no-verbs branch skipped the demo; case 4's merged
  `test_demo_is_side_effect_free` asserts both the positive
  Read-of-SKILL.md and the negative `wiki <verb>` evidence;
  case 5 asserts the malformed-marker short-circuit didn't
  call `wiki outcomes`).
- `tests/evals/conftest.py` exposes `build_vault`, `build_eval_kit`,
  `eval_kit_root`, `minimal_vault`, `weekly_digest_vault`,
  `meal_planning_vault`, `stakeholder_map_refresh_vault`,
  `research_cited_vault`, `research_dispatch_vault`, and
  `conflict_pending_vault`. It does **not** expose recipe-level
  vault fixtures (`personal_vault` / `family_vault` /
  `work_os_vault`); T2 adds them. Existing seed builders pass
  `--no-git` to `wiki init` for the reason recorded in
  `tests/evals/conftest.py`'s `build_weekly_digest_vault`
  docstring (session-scoped fixtures fire before the
  function-scoped autouse `GIT_AUTHOR_*` env fixture; a default
  git-init would hit the missing-identity failure on a hermetic CI
  runner); T2's new builders use the same flag for the same
  reason.
- `core/files/AGENTS.md` lists 7 baseline skills in its bullet
  list today but `core/files/skills/` ships 8 directories
  (`wiki-agent` is missing from the bullets — pre-existing drift
  surfaced by iteration-1 plan review Blocker 1). T1 closes this
  gap in the same edit that adds the `wiki-bootstrap` bullet.
- `core/files/skills/` is the byte-for-byte SKILL copy source for
  `wiki init`. The copy walk is
  `llm_wiki_kit/cli.py:_cmd_init` over `<kit_root>/core/files/skills/`.
- Trigger-phrase uniqueness against existing SKILLs: the five
  canonical phrases (`I just made a new vault`, `help me get
  started`, `first time using this vault`, `what should I do
  first`, `walk me through this vault`) do not appear as whole-
  word substrings in any existing `core/files/skills/*/SKILL.md`
  description. T3 ships a meta-check (`test_trigger_phrases_unique_across_existing_skills`)
  that pins this in CI.

**Strict task ordering: T1 → T2 → T3 || T4 || T5 || T6.**

## Steps

### T1 — Vault-side artifacts ship and `wiki init` copies them

1. **`core/files/skills/wiki-bootstrap/SKILL.md` exists with valid
   frontmatter and the required trigger phrases.**
   - **Depends on:** none.
   - **Verification mode:** Goal-based.
   - **Tests:** T3.1, T3.2 cover this artifact.
   - **Approach:** create `core/files/skills/wiki-bootstrap/SKILL.md`
     with YAML frontmatter (`name: wiki-bootstrap`, `description:
     <prose containing every required trigger phrase as a whole-
     word substring>`, `license: MIT`) and a body covering:
     - **When to load this skill** — three trigger surfaces (NL
       description, explicit invocation, AGENTS.md mention).
     - **First step: probe the marker** — read-attempt against
       `<vault>/.wiki.bootstrap`, branch on success (re-run path)
       vs. failure (full wizard).
     - **Walk the verbs** — `Bash wiki outcomes` to read the verb
       table; parse the three-column output (verb, operation,
       skill); follow the spec §Inputs §4 rules (0 verbs → skip
       demo with explanatory message; 1–8 verbs → read aloud
       with a gloss; >8 verbs → table without per-verb gloss +
       ask by name).
     - **Demo one verb (read-only, no `wiki <verb>` shell)** —
       map the user's chosen verb to its skill name via the
       parsed `wiki outcomes` output; `Read
       <vault>/skills/<skill>/SKILL.md`; parse the frontmatter
       `description:` field; surface a one-line gloss to the
       user. The wizard never invokes `wiki <verb>` in any
       mode. **Precondition the SKILL author must verify in
       this PR:** the three shipped operation skills
       (`weekly-digest`, `meal-planning`, `stakeholder-map-refresh`)
       have a frontmatter `description:` that supports a useful
       one-line gloss. The source files live at
       `templates/operations/<op>/files/skills/<skill>/SKILL.md`
       (verified: `templates/operations/weekly-digest/files/skills/weekly-digest/SKILL.md`
       etc.) — `wiki init` flattens them into the vault's
       top-level `skills/` directory. Read each source SKILL.md's
       frontmatter `description:`; if any reads as pure trigger-
       phrase boilerplate (e.g. "Load this skill when…" without
       a what-it-does sentence), extend that SKILL.md description
       in the same PR with a leading what-it-does sentence the
       wizard can quote. The eval (T5.4) asserts the wizard
       reads SKILL.md, not that the quoted gloss is non-empty —
       but a vault where the demo produces dead air is a failure
       of the SKILL contract, not the wizard.
     - **Write the marker** — `Write <vault>/.wiki.bootstrap`
       with the current UTC ISO-8601 timestamp; if the path
       holds a prior entry, `Bash rm -f` first per spec
       §Outputs §2.
     - **Closing prose** — next-step `wiki ingest` pointer +
       `wiki doctor` reminder.
     - **Failure modes** — spec §Edge cases and §Error cases;
       each surfaces a one-line user-facing message and exits
       without the marker.
     - **Re-run paragraph** — the exact text spec §Behavior
       "Re-run after completion" describes, ≤ 6 non-blank lines.
     SKILL is byte-for-byte (no Jinja, no `{}` placeholders);
     recipe-agnostic prose throughout.
   - **Verify:** T3.1 (`test_skill_md_frontmatter_well_formed`) +
     T3.2 (`test_skill_md_description_contains_trigger_phrases`).
2. **`core/files/AGENTS.md` lists every shipped SKILL with the
   pinned `wiki-bootstrap` wording, in a count-free intro form.**
   - **Depends on:** step 1.
   - **Verification mode:** Goal-based.
   - **Tests:** T3.3, T3.4, T3.5.
   - **Approach:** edit `core/files/AGENTS.md`:
     - Replace the introductory line `"This vault ships with seven
       baseline skills."` with a count-free form (e.g. `"Available
       baseline skills, all shipped in every vault:"`). Update any
       follow-up prose that references the count.
     - **Audit the bullet list against `core/files/skills/`** and
       add any missing bullet — specifically `wiki-agent`, which
       ships under `core/files/skills/wiki-agent/` but is absent
       from the bullet list today. Source the bullet's prose
       from `core/files/skills/wiki-agent/SKILL.md`'s frontmatter
       `description:` (truncated to a one-line summary matching
       the shape of the other bullets); do not invent freeform
       prose.
     - Append (or insert alphabetically) the `wiki-bootstrap`
       bullet:
       ``- **`wiki-bootstrap`** — first-run wizard for fresh vaults.
       Loads on any onboarding-shaped phrase; short-circuits to a
       brief no-op message if the vault is already bootstrapped.``
   - **Verify:** T3.3 + T3.4 + T3.5.
3. **`core/files/.gitignore` ignores `.wiki.bootstrap`.**
   - **Depends on:** none.
   - **Verification mode:** Goal-based.
   - **Tests:** T3.6.
   - **Approach:** append a two-line entry to
     `core/files/.gitignore`:
     ```
     # Bootstrap marker (per-machine SKILL scratch; see
     # docs/specs/wiki-bootstrap/spec.md §Inputs §3).
     .wiki.bootstrap
     ```
   - **Verify:** T3.6.
4. **`wiki init` copies the new SKILL into the vault.**
   - **Depends on:** step 1.
   - **Verification mode:** Goal-based.
   - **Tests:** T4.1.
   - **Approach:** no code change — the existing
     `cli.py:_cmd_init` copy walk over
     `<kit_root>/core/files/skills/` picks up the new directory
     automatically. Verify manually by `wiki init --no-git` into
     a tmp directory and `ls skills/wiki-bootstrap/`; T4 turns
     this into a deterministic parametrized test.
   - **Verify:** T4.1.

### T2 — `tests/evals/conftest.py` exposes recipe-level vault fixtures

1. **`build_personal_vault`, `build_family_vault`, `build_work_os_vault`
   factories produce vaults from each shipped recipe; seed and
   per-test fixtures wrap them. `bootstrapped_personal_vault`
   wraps `personal_vault` with a pre-written marker.**
   - **Depends on:** T1 (the `wiki-bootstrap` SKILL must ship in
     `core/files/` so the recipe vaults include it from init).
   - **Verification mode:** Goal-based.
   - **Tests:** exercised by T5 + T6.
   - **Approach:** extend `tests/evals/conftest.py` (matching the
     existing `build_weekly_digest_vault` / `_seed_weekly_digest`
     / `weekly_digest_vault` triple shape):
     - Three module-level builder functions:
       `build_personal_vault(kit_root, parent)`,
       `build_family_vault(kit_root, parent)`,
       `build_work_os_vault(kit_root, parent)`. Each runs
       `wiki init <parent>/<recipe>-vault --recipe <recipe> --no-git`
       and returns the vault path. The `--no-git` rationale is
       in `tests/evals/conftest.py`'s
       `build_weekly_digest_vault` docstring.
     - Three session-scoped seed fixtures: `_seed_personal(...)`,
       `_seed_family(...)`, `_seed_work_os(...)`. Each calls its
       builder and returns the seed vault path.
     - Three function-scoped fixtures: `personal_vault(tmp_path,
       _seed_personal)`, `family_vault(...)`, `work_os_vault(...)`.
       Each copies the seed vault into `tmp_path` for a fresh
       writable per-test vault.
     - One function-scoped fixture
       `bootstrapped_personal_vault(personal_vault)` — takes
       `personal_vault` and writes `<vault>/.wiki.bootstrap`
       with a fixed-but-valid ISO-8601 timestamp before
       yielding. **Add a fixture docstring:** `"""Personal vault
       with a valid marker file. Used by T5.2
       (test_idempotent_rerun_writes_nothing) and T6.3
       (test_post_bootstrap_short_circuits) for short-circuit
       re-run testing. Do NOT use for replacement-flow coverage
       — T5.6 (test_unreadable_marker_*) writes its own
       mode-0o000 marker inline."""` — keeps a future test
       author from reaching for this fixture for the wrong
       purpose AND surfaces who the consumers are.
     - One function-scoped fixture `no_verbs_vault(tmp_path,
       _seed_minimal)` for T5.3 — see step 2 below.
     - One module-level helper `ordered_tool_calls(result) ->
       list[ToolUse]` in `tests/evalkit/__init__.py`. T5 cases
       3, 4, and 5 parse tool-call logs (three call sites
       satisfying the helper-extraction threshold) —
       ship the helper rather than inline. Define the return
       type as a `NamedTuple` so callers read by name, not
       index:
       ```python
       class ToolUse(NamedTuple):
           name: str
           input: dict[str, Any]
       ```
       The helper walks `result.events`, extracts `content`
       blocks where `type == "tool_use"`, and returns a list
       ordered by appearance. Stream-JSON content blocks are
       `dict[str, Any]` with keys `"name"` / `"input"` (see
       `tests/evalkit/__init__.py:_skill_name_from_tool_use`
       which reads them via `block.get("name")`), so the
       construction is
       `[ToolUse(block["name"], block["input"]) for block in ...]`.
       Callers then read `tu.name` and `tu.input["command"]`
       (for Bash) or `tu.input["file_path"]` (for Read/Write)
       — no positional unpacking footguns.
   - **Verify:** the fixtures import and the T5/T6 tests use them
     successfully.
2. **`no_verbs_vault` fixture for AC 13.**
   - **Depends on:** step 1.
   - **Verification mode:** Goal-based.
   - **Tests:** exercised by T5's `test_no_verbs_degradation`.
   - **Approach:** **the kit's `wiki outcomes` reads operation
     contracts from `<kit_root>/templates/operations/<name>/contract.yaml`,
     not from any in-vault path** (iteration-2 plan review
     Blocker 3 verified this — `llm_wiki_kit/recipes.py`'s
     `installed_outcome_verbs` resolves contracts via
     `kit_root`). Stripping in-vault contracts has zero effect.
     **Route chosen: the existing `_seed_minimal` builder.** The
     `minimal` baseline at `tests/evals/conftest.py:48-50`
     installs no primitives; every eval factory in the file
     adds primitives explicitly via `wiki add`. A `minimal`
     vault therefore has `wiki outcomes` returning an empty
     set, which is exactly the AC 13 condition. `no_verbs_vault`
     is a thin function-scoped fixture that copies the existing
     `_seed_minimal` seed into `tmp_path` and yields. No
     contract surgery, no tmp-kit-root override, no fixture
     fragility. If a future revision adds outcome-declaring
     operations to `minimal`'s closure, the EXECUTE-time one-
     line check `wiki outcomes` (against a `minimal_vault`)
     fails the fixture-build sanity assertion, surfacing the
     drift; the recovery path is the contract-strip fallback —
     `shutil.copytree`-the real kit, rewrite operation
     contracts to set `outcomes: []`, then call
     `cli.main(["init", str(vault), "--recipe", "minimal", "--no-git"], kit_root=tmp_kit_root)`
     directly (kwarg, not argv flag; matches the existing
     `build_vault` pattern at `tests/evals/conftest.py:76`).
     The fallback is named here so a future maintainer doesn't
     re-derive it, but the v1 fixture uses Route A.
   - **Verify:** T5.3 (`test_no_verbs_degradation`) passes: the
     wizard's tool-call log does not contain any
     `Bash(wiki digest)` / `Bash(wiki plan-meals)` /
     `Bash(wiki refresh-stakeholders)` invocation (the wizard
     never calls `wiki <verb>` at all per Invariant 7), and the
     marker file is written.

### T3 — Unit tests for vault-side artifacts pass

1. **`tests/unit/test_wiki_bootstrap_artifacts.py` exists and
   passes the well-formedness, AGENTS.md audit, gitignore, and
   trigger-phrase-uniqueness assertions.**
   - **Depends on:** T1.
   - **Verification mode:** TDD.
   - **Tests** (each pytest function; pure file reads, no fixtures,
     no subprocesses):
     1. **`test_skill_md_frontmatter_well_formed`** — open
        `core/files/skills/wiki-bootstrap/SKILL.md`; parse YAML
        frontmatter; assert `name == "wiki-bootstrap"`,
        `license == "MIT"`, `description` is a non-empty string.
     2. **`test_skill_md_description_contains_trigger_phrases`** —
        parametrized over the spec's five canonical trigger
        phrases. Each phrase must appear as a whole-word
        substring (regex `\b<phrase>\b`, case-insensitive) in the
        SKILL's frontmatter description.
     3. **`test_agents_md_contains_wiki_bootstrap_bullet`** —
        assert the pinned substring appears in
        `core/files/AGENTS.md`, ignoring leading `- ` and
        trailing whitespace.
     4. **`test_agents_md_intro_is_count_free`** — assert
        neither regex matches (both `re.IGNORECASE`):
        - `\b\d+[\s\-]+baseline[\s\-]+skills?\b`.
        - `\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)[\s\-]+baseline[\s\-]+skills?\b`.
     5. **`test_agents_md_lists_every_baseline_skill`** — first
        assert the literal string `"## Available skills"`
        appears in the file (catches a future rename of the
        section heading that would silently empty the audit;
        per iteration-2 plan review Nit 10). Then parse the
        section delimited by `## Available skills` and the next
        `## ` heading. For each directory under
        `core/files/skills/`, assert
        `` **`<name>`** `` appears in the parsed section.
        Catches the pre-existing `wiki-agent` drift and any
        future drift in the same shape.
     6. **`test_gitignore_contains_wiki_bootstrap_entry`** —
        assert a line equal to `.wiki.bootstrap` (rstrip
        whitespace) appears in `core/files/.gitignore`.
     7. **`test_trigger_phrases_unique_across_existing_skills`**
        — walk every `core/files/skills/*/SKILL.md` other than
        `wiki-bootstrap/SKILL.md`; for each canonical trigger
        phrase, assert no other SKILL's frontmatter
        `description:` contains it as a whole-word substring
        (case-insensitive). Catches a future collision.
   - **Approach:** new file at
     `tests/unit/test_wiki_bootstrap_artifacts.py`; pattern
     matches `tests/unit/test_outcome_verbs.py`'s catalog-walk
     style.
   - **Verify:** `pytest tests/unit/test_wiki_bootstrap_artifacts.py`
     green. 11 cases (5 parametrized + 6 standalone) in the
     fast-lane matrix.

### T4 — `wiki init` SKILL-copy integration test passes

1. **`tests/integration/test_wiki_bootstrap_install.py::test_wiki_init_copies_wiki_bootstrap_skill`
   asserts byte-equality across all three recipes.**
   - **Depends on:** T1.
   - **Verification mode:** TDD.
   - **Tests:**
     - **`test_wiki_init_copies_wiki_bootstrap_skill`** — using
       `tmp_path`, run `wiki init <tmp_path>/vault --recipe
       <recipe> --no-git`; assert
       `<tmp_path>/vault/skills/wiki-bootstrap/SKILL.md` exists;
       assert SHA-256 hash equals the SHA-256 of
       `core/files/skills/wiki-bootstrap/SKILL.md`. Parametrize
       over `personal`, `family`, `work-os`.
   - **Approach:** new file matching existing integration-test
     pattern.
   - **Verify:** 3 parametrized cases in the fast-lane matrix.

### T5 — Wizard behavior eval covers ACs 8–16 (consolidated)

1. **`tests/evals/test_wiki_bootstrap_behavior.py` covers the
   wizard-behavior ACs end-to-end.**
   - **Depends on:** T1 + T2.
   - **Verification mode:** eval.
   - **Consolidation note (per §Risks §1):** ACs 8+9+10 (marker
     write, no journal append, no other vault writes) drive
     Claude through the same conversation; consolidated into one
     `test_happy_path_postconditions` with three assertions
     sharing one Claude spawn. AC 12 (re-run after partial
     completion) is verified transitively by the happy-path
     test per the spec's iteration-2 amendment (a fresh-init
     vault IS the post-partial-abort state, byte-equal by
     Invariants 2/3/7); no separate test case. Total T5 cases:
     **6** (down from 9 in iteration-1 after the AC 11/12
     consolidation and the iter-3 demo-case merge).
   - **`allowed_tools` rationale.** The wizard needs `Read`
     (marker probe + journal + verb-skill's SKILL.md), `Glob`
     (general discovery), `Bash(wiki outcomes)` (the only
     `wiki` invocation — `wiki <verb>` is never called per
     Invariant 7), `Bash(rm -f .wiki.bootstrap)` (marker
     replacement on the AC-15 path), and `Write` (marker
     creation). Cases that exercise the full wizard
     (`happy_path_postconditions`, `no_verbs_degradation`,
     `demo_reads_skill_md`, `unreadable_marker`) get the full
     grant
     `["Read", "Glob", "Bash(wiki outcomes)", "Bash(rm -f *)", "Write"]`.
     Re-run / no-op cases that expect zero writes
     (`idempotent_rerun_writes_nothing`,
     `malformed_marker_is_treated_as_present`) get
     `["Read", "Glob"]` — over-broad grants would let a
     regression pass silently.
   - **Tests** (each `pytest.mark.eval`, gated):
     1. **`test_happy_path_postconditions`** (ACs 8, 9, 10, 12)
        — fresh `personal_vault`; trigger phrase `"I just made
        a new vault, help me get started."`;
        `allowed_tools=["Read", "Glob", "Bash(wiki outcomes)", "Bash(rm -f *)", "Write"]`;
        after the run assert
        (a) `<vault>/.wiki.bootstrap` exists with one parseable
        ISO-8601 UTC line (AC 8),
        (b) `<vault>/.wiki.journal/journal.jsonl` byte-equal to
        pre-run (AC 9),
        (c) every file under the vault root other than
        `.wiki.bootstrap` is byte-equal to pre-run (AC 10 —
        exclusion set `{".wiki.bootstrap"}`).
        AC 12 is covered transitively: the fixture is the
        post-partial-abort equivalence class per the spec
        amendment.
     2. **`test_idempotent_rerun_writes_nothing`** (AC 11) —
        `bootstrapped_personal_vault`; trigger phrase as above;
        `allowed_tools=["Read", "Glob"]`; assert zero files
        changed and zero journal lines appended.
     3. **`test_no_verbs_degradation`** (AC 13) —
        `no_verbs_vault`;
        `allowed_tools=["Read", "Glob", "Bash(wiki outcomes)", "Bash(rm -f *)", "Write"]`;
        assert (a) the wizard skips the demo step — no
        `Bash(wiki digest)` / `Bash(wiki plan-meals)` /
        `Bash(wiki refresh-stakeholders)` invocation in the
        tool-call log (the wizard never calls `wiki <verb>`
        per Invariant 7, but this assertion adds positive
        evidence the demo branch was skipped), and (b) the
        marker file is written.
     4. **`test_demo_is_side_effect_free`** (AC 14, merged) —
        fresh `personal_vault`; prompt steers Claude to demo a
        verb; one Claude spawn, four post-run assertions
        collected via an inline accumulator so first-failure-
        wins doesn't mask co-occurring regressions:
        ```python
        failures: list[str] = []
        tool_calls = ordered_tool_calls(result)
        # (a) positive evidence — SKILL.md read
        if not any(tu.name == "Read" and "/skills/" in tu.input.get("file_path", "")
                   for tu in tool_calls):
            failures.append("no Read of skills/<skill>/SKILL.md")
        # (b) negative evidence — no wiki <verb> (in any
        # form: sugared, un-sugared, or with extra args).
        # Catches `wiki digest`, `wiki  digest`, `wiki digest 2>&1`,
        # `cd /vault && wiki digest`, AND the underlying
        # `wiki run weekly-digest` form (spec Invariant 7 forbids
        # any path that triggers the operation, sugared or not).
        verb_re = re.compile(
            r"\bwiki\s+(?:run\s+)?"
            r"(digest|plan-meals|refresh-stakeholders|"
            r"weekly-digest|meal-planning|stakeholder-map-refresh)\b"
        )
        for tu in tool_calls:
            if tu.name == "Bash" and verb_re.search(tu.input.get("command", "")):
                failures.append(f"wiki <verb> invoked: {tu.input['command']!r}")
        # (c) no OperationRunEvent. `if line.strip()` filters
        # the trailing newline + any stray blank line that
        # `journal.read_events` would tolerate but `json.loads("")`
        # would crash on.
        if any(json.loads(line).get("type") == "operation.run"
               for line in (vault / ".wiki.journal/journal.jsonl").read_text().splitlines()
               if line.strip()):
            failures.append("OperationRunEvent appeared in journal")
        # (d) outputs/ absent or empty
        outputs = vault / "outputs"
        if outputs.is_dir() and any(outputs.iterdir()):
            failures.append("outputs/ has contents")
        assert not failures, "demo regressions: " + "; ".join(failures)
        ```
        `allowed_tools=["Read", "Glob", "Bash(wiki outcomes)", "Bash(rm -f *)", "Write"]`.
        The verb-match regex (`\bwiki\s+(?:run\s+)?(digest|plan-meals|refresh-stakeholders|weekly-digest|meal-planning|stakeholder-map-refresh)\b`)
        catches the sugared verbs (`wiki digest`, etc.) AND the
        un-sugared operation names (`wiki run weekly-digest`,
        etc.) — Invariant 7 forbids any path that triggers the
        operation. Also catches `wiki  digest` (multiple
        whitespace via `\s+`), `cd /vault && wiki digest`
        (word boundary at the start of `wiki`), and
        `wiki digest 2>&1` (word boundary after the verb).
        Same regex is reused in case 3 (no-verbs degradation —
        the wizard skips the demo entirely, so the regex
        matches zero times against an empty alternation set;
        the assertion shape stays the same).
        Merged from iteration-2's two-case split because both
        prior cases drove Claude through the same conversation
        with the same prompt and the same allowed-tools set —
        the iteration-2 reviewer's Concern 7 flagged that
        ~$0.50 of eval budget bought "legibility" without
        catching any regression the merged form misses. The
        four assertions cover the same correctness properties:
        a regression to live `wiki <verb>` invocation fails
        (b); a regression to journaling fails (c); a regression
        to writing under `outputs/` fails (d); a regression
        that skips SKILL.md entirely fails (a). If a future
        failure mode emerges that the merged form can't
        distinguish, split then.
     5. **`test_malformed_marker_is_treated_as_present`** (AC
        15) — `personal_vault` with `.wiki.bootstrap`
        containing `"garbage not iso"`; `allowed_tools=["Read", "Glob"]`;
        assert (a) Claude response ≤ 6 non-blank lines
        (short-circuit), (b) tool-call log contains zero
        `Bash(wiki outcomes)` invocations, (c) marker
        byte-stable.
     6. **`test_unreadable_marker_triggers_full_wizard_and_replacement`**
        (AC 16) — POSIX-only
        (`pytest.mark.skipif(sys.platform == "win32", reason="chmod 000 not meaningful on Windows")`);
        `personal_vault` with `.wiki.bootstrap` written then
        `os.chmod(0o000)`'d;
        `allowed_tools=["Read", "Glob", "Bash(wiki outcomes)", "Bash(rm -f *)", "Write"]`;
        assert (a) the full flow ran (Claude response > 6
        non-blank lines), (b) new marker owned by running user
        (`stat.st_uid == os.getuid()`), (c) new marker at-least
        user-readable (`stat.st_mode & 0o400 == 0o400`),
        (d) new marker contains a parseable ISO-8601 timestamp.
   - **Tool-call log parsing.** Cases 3, 4, and 5 inspect
     Claude's tool-call log via the `ordered_tool_calls(result)`
     helper
     T2.1 commits to landing in `tests/evalkit/__init__.py`
     (three call sites — the threshold rule fires). The helper
     walks `result.events`, extracts `content` blocks where
     `type == "tool_use"`, and returns a list of
     `(name, input)` tuples (`name` is `"Bash"` / `"Read"` /
     `"Write"`; `input` is the block's input dict — callers
     read `input["command"]` for Bash, `input["file_path"]` for
     Read/Write).
   - **Approach:** new file at
     `tests/evals/test_wiki_bootstrap_behavior.py`. Transcript
     line-count assertions parse the model response by
     `len([line for line in response.splitlines() if line.strip()])`.
   - **Verify:** `pytest tests/evals/test_wiki_bootstrap_behavior.py -m eval`
     green. 6 eval cases (case 6 POSIX-skip on Windows).

### T6 — Trigger, flow, and post-bootstrap evals cover ACs 5–7

1. **`tests/evals/trigger/test_wiki_bootstrap_trigger.py` covers
   the SKILL-load assertions.**
   - **Depends on:** T1 + T2.
   - **Verification mode:** eval.
   - **Cardinality decision (per iteration-2 plan review C6):**
     5 trigger + 2 flow (personal + work-os; family dropped) +
     1 post-bootstrap = **8 eval cases** (down from 9 in the
     iteration-1 plan, down from 15 in the iteration-0 draft).
     `family_vault` is dropped because `family` ships the same
     verb set as `personal` (`{digest, plan-meals}`); the
     exact-equality assertion is identical between them, and
     `personal`'s case discriminates a wizard that hard-codes
     verbs from `wiki outcomes`'s output identically. When
     `family` ships a unique verb, re-add the case.
   - **Tests:**
     1. **`test_trigger_phrase_loads_wiki_bootstrap`** (AC 5) —
        parametrized over the five canonical trigger phrases
        against one `personal_vault`. `allowed_tools=["Read", "Glob"]`.
        Assert `evalkit.ordered_skill_reads(result)[0] ==
        "wiki-bootstrap"`. Five cases.
     2. **`test_wizard_surfaces_recipe_appropriate_verbs`** (AC
        5) — parametrized over **two** shipped recipes
        (`personal_vault`, `work_os_vault` — `family` dropped
        per the cardinality decision above) using the canonical
        prompt `"I just made a new vault, help me get
        started."`.
        `allowed_tools=["Read", "Glob", "Bash(wiki outcomes)", "Bash(rm -f *)", "Write"]`
        (the flow eval drives the full wizard including the
        marker write; per iteration-2 plan review C5, an
        incomplete grant blocks the wizard's final step and
        produces flaky transcripts).
        Each case:
        - reads `wiki outcomes` from the vault to get the
          expected verb set;
        - extracts the set of verbs Claude names in the model
          response, using a regex with optional backtick
          wrapping: `(?:`)?(?P<verb>{verb_alternation})(?:`)?\b`
          where `{verb_alternation}` is the pipe-joined list of
          verbs `wiki outcomes` returned for the recipe (catches
          `digest`, `` `digest` ``, etc.);
        - asserts the extracted set **equals** the expected set
          (exact equality). Discriminating power lives on
          `work-os` (whose `{refresh-stakeholders}` set is
          unique); `personal`'s case pins the common path.
        Two cases.
     3. **`test_post_bootstrap_short_circuits`** (AC 7) —
        `bootstrapped_personal_vault`; canonical trigger phrase;
        `allowed_tools=["Read", "Glob"]`; assert
        (a) `evalkit.ordered_skill_reads(result)[0] ==
        "wiki-bootstrap"` (SKILL loaded), (b) Claude response ≤
        6 non-blank lines. One case.
   - **Prompts module:** the parametrize tables live in
     `tests/evals/trigger/_wiki_bootstrap_prompts.py` as two
     named tuples (`BootstrapTriggerPhrase(phrase: str)` and
     `BootstrapRecipePrompt(recipe: str, fixture_name: str,
     prompt: str)`); imports nothing from `tests.evalkit`. The
     fast-lane meta-check
     `test_trigger_phrases_unique_across_existing_skills`
     (T3.7) loads this module to ensure every spec §Inputs §2
     trigger phrase appears in the
     `BootstrapTriggerPhrase` table.
   - **Approach:** new file mirroring
     `test_outcome_verbs_trigger.py`'s shape; SKILL name read
     from frontmatter via the existing `_skill_name` helper
     pattern.
   - **Verify:** `pytest tests/evals/trigger/test_wiki_bootstrap_trigger.py -m eval`
     green. 8 eval cases.

## Verification gate

```
# Unit (fast-lane)
pytest tests/unit/test_wiki_bootstrap_artifacts.py            # ACs 1, 2, 3

# Integration (fast-lane)
pytest tests/integration/test_wiki_bootstrap_install.py       # AC 4

# Eval (Evals workflow, gated behind ANTHROPIC_API_KEY)
pytest tests/evals/trigger/test_wiki_bootstrap_trigger.py -m eval    # ACs 5, 6, 7
pytest tests/evals/test_wiki_bootstrap_behavior.py -m eval           # ACs 8-16

# Mechanical gates
ruff check llm_wiki_kit tests
ruff format --check llm_wiki_kit tests
mypy llm_wiki_kit tests
pytest -m 'not slow'
```

The spec's 16 acceptance criteria map to tests as follows:

| Spec AC | Test file | Test function | Cases |
|---|---|---|---|
| 1. SKILL well-formed | test_wiki_bootstrap_artifacts.py | test_skill_md_frontmatter_well_formed | 1 |
| 1. (cont.) trigger phrases | " | test_skill_md_description_contains_trigger_phrases | 5 |
| 2. AGENTS.md bullet | " | test_agents_md_contains_wiki_bootstrap_bullet | 1 |
| 2. (cont.) count-free intro | " | test_agents_md_intro_is_count_free | 1 |
| 2. (cont.) every-skill audit | " | test_agents_md_lists_every_baseline_skill | 1 |
| (plan-added — no spec AC) trigger-phrase uniqueness sanity | " | test_trigger_phrases_unique_across_existing_skills | 1 |
| 3. Marker gitignored | " | test_gitignore_contains_wiki_bootstrap_entry | 1 |
| 4. wiki init copies SKILL | test_wiki_bootstrap_install.py | test_wiki_init_copies_wiki_bootstrap_skill | 3 |
| 5. Trigger eval | test_wiki_bootstrap_trigger.py | test_trigger_phrase_loads_wiki_bootstrap | 5 |
| 6. Flow eval | " | test_wizard_surfaces_recipe_appropriate_verbs | 2 (personal + work-os) |
| 7. Post-bootstrap no-load | " | test_post_bootstrap_short_circuits | 1 |
| 8, 9, 10, 12. Happy path + partial-completion transitive | test_wiki_bootstrap_behavior.py | test_happy_path_postconditions | 1 |
| 11. Idempotent re-run | " | test_idempotent_rerun_writes_nothing | 1 |
| 13. No-verbs degradation | " | test_no_verbs_degradation | 1 |
| 14. Demo is read-only | " | test_demo_is_side_effect_free | 1 |
| 15. Malformed marker | " | test_malformed_marker_is_treated_as_present | 1 |
| 16. Unreadable marker | " | test_unreadable_marker_triggers_full_wizard_and_replacement | 1 (POSIX) |

**Total: 28 test cases (14 fast-lane + 14 eval).** Fast-lane =
11 unit cases in T3 (1 + 5 parametrized + 1 + 1 + 1 + 1 + 1) + 3
parametrized integration cases in T4 = 14. Eval = 6 from T5
(`test_demo_is_side_effect_free` is one case rather than two
after the iter-3 merge) + 8 from T6 (5 trigger + 2 flow + 1
post-bootstrap, after the `family`-vault drop) = 14. Eval cost:
14 × $0.25 = $3.50 per run (down from $3.75 in iteration-2,
when the demo case was still split).

## Risks

- **CI cost / eval-spawn budget.** 14 eval cases at default
  `EVAL_MAX_BUDGET_USD = 0.25` is ~$3.50 per Evals workflow run;
  pre-bootstrap baseline is ~$2.50 per run, so this PR increases
  per-run cost by ~40%. Wall-clock ~14 × 60-180s serial; CI
  parallelism cuts this. The iteration-2 plan had 15 cases; the
  iter-3 merge of the demo case (one Claude spawn, four
  assertions instead of two cases) cut one case worth $0.25
  per run. **Risk is documented, not
  mitigated; further consolidation knobs are exhausted for v1.**
- **Eval flakiness against live Claude.** Mitigation: positive-
  evidence assertions (SKILL load, tool-call presence, file
  presence) rather than asserting Claude's prose. **The line-
  count bound (≤ 6 non-blank lines) lives in `spec.md` AC 7;
  widening under flake pressure requires a spec amendment +
  spec-mode adversarial-reviewer round-trip — plan for that cost.**
- **Trigger-phrase overlap with future SKILLs.** T3.7 pins
  uniqueness in CI; a future colliding SKILL fails this test.
- **`no_verbs_vault` fixture brittleness.** Two routes named
  in T2.2; choice deferred to EXECUTE based on whether
  `minimal_vault` ships zero outcome verbs. Route A is
  near-zero work; Route B requires copying `kit_root` to tmp
  and rewriting contracts. Either way the fixture is
  test-only — no production source changes.
- **`Bash rm -f` cross-platform.** AC 16 POSIX-only; Windows
  skipped. Forward-looking risk if the kit targets native
  Windows.
- **AC 6 flow-eval discriminating power lives on `work-os`
  alone.** Documented; `family` dropped from cardinality.
  Single-recipe coverage is a known trade-off documented in
  T6.2's "cardinality decision" subsection. If `family` ships a
  unique verb in a future recipe revision, T6.2 re-adds the
  case in a follow-up PR.
- **Spec-amendment temptation mid-execute.** The work-loop's
  *Design tests up front* path applies if EXECUTE surfaces a
  corner case: stop, amend the spec, re-run the spec-mode
  reviewer, resume.

## Out of scope

Items the spec already deferred:

- **A `wiki bootstrap` CLI verb** — spec §Non-goal 3.
- **Multi-recipe hand-off** — spec §Non-goal 4.
- **Troubleshooting flows inside the wizard** — spec §Non-goal 5.
- **A clone-able starter template / sample seed pages** — spec
  §Non-goal 6.
- **Resume-after-abort tokens** — spec §Non-goal 7.
- **Live verb execution in the demo step** — spec §Non-goal 9.
- **`wiki <verb>` invocation in any mode** — spec §Constraint 10
  (the demo is read-only SKILL.md, not `--help`).
- **Personalization of any kit-rendered file** — spec §Non-goal 2.
- **A `BootstrapCompletedEvent` journal type** — spec §Non-goal 8 /
  §Constraints 6.

Items deferred by this plan:

- **An ADR codifying the file-sentinel discipline.** Spec §Inputs
  §3 fence subsection notes the follow-up explicitly.
- **A Windows-native marker-replacement path.** Spec AC 16 is
  POSIX-only.
- **Re-adding `family_vault` to the flow eval.** Drops back in
  when `family` ships a unique verb that `personal` doesn't —
  re-add the case via a follow-up PR.
- **Enhancing `wiki run <op> --help` to surface the contract
  description.** Would be a separate spec (modifies
  `cli.py:_cmd_run`'s help short-circuit at line 1590-1597 to
  enrich the help output). Out of scope for a vault-side-only
  PR.
