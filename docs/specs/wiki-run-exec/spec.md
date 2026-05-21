# Spec: wiki-run-exec

> **Living document.** Updated alongside the code. Drift between spec and
> code is a bug — fix the code or the spec in the same PR.

- **Status:** Draft
- **Owner:** `llm_wiki_kit/run.py`, `llm_wiki_kit/cli.py:_cmd_run`
- **Related:** [RFC-0003](../../rfc/0003-scheduling-and-autonomous-execution.md),
  [`docs/specs/task-17-wiki-run/spec.md`](../task-17-wiki-run/spec.md),
  [`docs/specs/wiki-schedule/spec.md`](../wiki-schedule/spec.md)
- **Constrained by:** ADR-0002 (journal as state truth), ADR-0004
  (safe-write), [`task-17-wiki-run/spec.md`](../task-17-wiki-run/spec.md)
  (the dispatch contract this spec extends),
  [RFC-0003](../../rfc/0003-scheduling-and-autonomous-execution.md)
  §"Decisions already made" (shim executor, no SDK, conflict-aware
  refusal), [`AGENTS.md` §"Runtime dependencies"](../../../AGENTS.md#runtime-dependencies).

## What this is

`wiki run --exec <operation>` is an opt-in extension of the existing
[`wiki run`](../task-17-wiki-run/spec.md) dispatch boundary. After the
standard dispatch sequence (validate args, journal one
`OperationRunEvent(status="dispatched")`, print the SKILL pointer), the
`--exec` flag causes the kit to additionally:

1. Refuse cleanly if the vault has unresolved drift conflicts inside
   the scoped walk (see §"Conflict-refusal walk scope" below).
2. Locate a user-installed `claude` CLI binary.
3. Invoke it in headless mode against the operation's SKILL, streaming
   stdout / stderr to a per-run log under
   `.wiki.journal/exec-logs/<event-id>.log`.
4. On non-zero exit, journal an `OperationExecFailedEvent` and write a
   per-failure markdown file under `inbox/scheduled-failures/<dispatch-event-id>.md`
   (each file is wholly kit-authored, never re-edited; the user resolves
   by deleting the file).

The kit ships no LLM (CHARTER principle: library-not-application); the
shim executor is the **delegation boundary** between the kit and the
user's local Claude binary. It is opt-in per invocation; the
human-attended `wiki run <op>` (no `--exec`) is unchanged.

## Inputs

CLI invocation:

```
wiki run <operation> [args ...] --exec
wiki run <operation> [args ...] --exec --claude-binary <path>
wiki run <operation> [args ...] --exec --skill-path <path>
```

- `<operation>`, `[args ...]` — exactly as the existing
  [`task-17-wiki-run`](../task-17-wiki-run/spec.md) contract. **No
  changes to argument parsing, REMAINDER handling, kebab/snake
  normalisation, or contract validation.**
- `--exec` — boolean flag. When present, triggers the post-dispatch
  exec sequence. When absent, behavior is byte-identical to the
  existing spec.
- `--claude-binary <path>` — optional explicit override of the Claude
  binary location. Resolution order when `--exec` is set:
  1. `--claude-binary` argument (verbatim path; must be executable).
  2. `WIKI_CLAUDE_BINARY` environment variable (verbatim path; must be
     executable).
  3. `shutil.which("claude")`.
  4. None of the above → `WikiError` with install-instructions
     pointer. The dispatch event is **still journaled** at status
     `dispatched`; the exec-failure event is **not** journaled
     (the failure happened before exec started — no exec attempt
     was made). The kit prints the dispatch line, then a stderr
     warning, then exits non-zero. Rationale: the user still has a
     valid dispatch record they can re-attempt manually.
- `--skill-path <path>` — optional explicit override of the SKILL
  file location. Default resolution:
  `<vault_root>/.claude/skills/<contract.skill or operation>/SKILL.md`
  — i.e. `contract.skill` when non-empty, falling back to the operation
  name itself (matching [task-17 CT-13](../task-17-wiki-run/spec.md)'s
  SKILL-name fallback). When the resolved path doesn't exist, raise
  `WikiError` with the resolved path and a suggestion to pass
  `--skill-path`.
- Vault root: `Path.cwd()`. Must contain `.wiki.journal/journal.jsonl`
  (same gate as plain `wiki run`).

### Environment variables

The kit reads three `WIKI_*` env vars when `--exec` is set. All have
defaults; none is required.

- `WIKI_CLAUDE_BINARY` — explicit path to the Claude binary, second
  in the resolution order described above (after `--claude-binary`,
  before `shutil.which("claude")`).
- `WIKI_EXEC_TIMEOUT` — integer seconds before the subprocess is
  SIGTERM'd. Default `1800` (30 minutes). After a 5-second grace
  period the kit escalates to SIGKILL.
- `WIKI_EXEC_LOG_RETENTION_DAYS` — integer days. Logs under
  `.wiki.journal/exec-logs/*.log` older than this are deleted at
  the start of every `--exec` invocation. Default `30`. Set to
  `0` to keep logs forever (the walk runs but matches nothing).

## Outputs

### Dispatch phase

Unchanged from [`task-17-wiki-run`](../task-17-wiki-run/spec.md). One
`OperationRunEvent` per surviving invocation. The dispatch event's
`by` is `"wiki-run"`; this spec does not change that. The downstream
exec events carry `by="wiki-run-exec"` so a `journal grep` can
attribute the exec to its delegate clearly.

### Exec phase (only when `--exec` is set and dispatch succeeded)

- **Conflict-refusal path.** Before invoking `claude`, the kit walks
  the scoped vault tree (see §"Conflict-refusal walk scope" below) for
  `.proposed` sidecars. If any exist:
  1. Append `OperationExecFailedEvent(exit_code=-1,
     reason="conflict-refused", stderr_tail="",
     conflict_sidecars=[<vault-relative path>, …], log_path=None)`.
     The `stderr_tail` field is empty because no subprocess ran;
     the sidecar list lives in its own dedicated field.
  2. Write the per-failure file via the same `safe_write` first-write
     path described in §"Per-failure file format" below. The dispatch
     event id is single-use, so the file is new and `safe_write`'s
     drift-detection has nothing to compare against; the write
     produces a `PageWriteEvent` (and, in the construction-time-
     impossible re-write case, a `PageProposalEvent`).
  3. Print the refusal line to stderr; exit non-zero.
  - No `claude` subprocess is spawned.

- **Happy path.** With no `.proposed` sidecars in scope:
  1. Resolve the Claude binary (per §Inputs resolution order).
  2. Resolve the SKILL path (per §Inputs).
  3. Create `.wiki.journal/exec-logs/` if absent (additive write; the
     directory is gitignored — see `wiki-schedule/spec.md` §Constraints
     for the parallel `.wiki.journal/` precedent). Rotate logs whose
     mtime is more than `WIKI_EXEC_LOG_RETENTION_DAYS` days old
     (default 30) — best-effort delete; failures logged but do not
     abort. See §"Log rotation" below.
  4. Build the argv via `_build_argv(claude_binary, skill_path,
     vault_root, dispatch_event_id, parsed_args)`. The exact argv
     shape is **not pinned in this spec** — the Claude headless CLI
     vocabulary is a moving target, deferred to a follow-on ADR per
     [RFC-0003 §"Unresolved questions"](../../rfc/0003-scheduling-and-autonomous-execution.md#unresolved-questions).
     The contract here is structural: `_build_argv` returns
     `list[str]` whose `[0]` is the absolute path to the Claude
     binary, and whose remaining elements communicate the SKILL
     path, the vault root, the dispatch event id, and the parsed
     args. Spawn via `subprocess.run(argv, …)`.
     stdout/stderr both redirected to
     `.wiki.journal/exec-logs/<dispatch-event-id>.log` (truncate-mode,
     UTF-8 — one log per dispatch; new run, new file). Timeout:
     configurable via `WIKI_EXEC_TIMEOUT` env var (default 1800
     seconds = 30 min). On timeout, the subprocess is terminated
     (SIGTERM, then SIGKILL after a 5-second grace) and the timeout
     is recorded as an exec failure (`exit_code=-2`,
     `reason="timeout"`).
  5. On `returncode == 0`:
     - Print one stdout line:
       `Exec succeeded for <op> (exit 0, <duration>s, log: <path>).`
     - **No second journal event** — the dispatch event already
       records the run. A future RFC may add an
       `OperationExecSucceededEvent` if observability needs it;
       deferred per spec §"Non-goals".
     - Exit `0`.
  6. On `returncode != 0`:
     - Append one `OperationExecFailedEvent`:
       ```
       type: "operation.exec_failed"
       timestamp: <UTC now>
       by: "wiki-run-exec"
       operation: "<operation>"
       dispatch_event_id: "<the dispatch event's id>"
       exit_code: <int>
       reason: "non-zero-exit" | "timeout" | "conflict-refused"
       stderr_tail: "<last 4 KB of stderr, UTF-8 lossy>"
       log_path: ".wiki.journal/exec-logs/<id>.log" (relative)
       ```
     - Write the per-failure file (see §"Per-failure file format"
       below).
     - Print the failure line to stderr; exit non-zero.

### Conflict-refusal walk scope

The walk for `**/*.proposed` sidecars is bounded to the directories
the kit considers vault content:

- **Included:** every direct child of `vault_root` whose name does
  not start with `.` (e.g. `wiki/`, `inbox/`, `outputs/`,
  `attachments/`). This single rule already excludes dot-prefixed
  directories like `.wiki.journal/`, `.git/`, `.obsidian/`, and
  `.claude/`; no extra dot-prefix list is needed.
- **Explicit nested exclusion:** `inbox/scheduled-failures/` is
  pruned during the walk (it lives under the included `inbox/`).
  This is the only non-redundant entry — the kit's own scratch
  must not trigger refusal.
- **Excluded if present:** any directory or file matched by
  `.obsidianignore` at the vault root, using **exact-prefix
  matching against vault-relative paths, no negation** (same
  subset of `.obsidianignore` semantics the kit already uses
  elsewhere — Obsidian's published grammar). `.gitignore` is
  **not** honored — vault content under `.gitignore` (e.g.
  `attachments/`) can still carry conflicts the user needs to
  resolve before a scheduled run mutates them.

The walk is breadth-first. It does **not** short-circuit — it
collects up to 20 sidecar paths so the event and per-failure file
can list them, then stops. The event's `conflict_sidecars` field
carries the collected paths verbatim (vault-relative POSIX form).
The per-failure file renders them as a bullet list. If more than
20 sidecars exist, the kit notes `(…N more)` after the 20th in
both the event body's per-failure file and any user-visible
prose. No 4 KB byte cap — the 20-path count is the single bound.

Rationale for the scope: prevents the deadlock loop where a sidecar
created by an earlier refusal's failure-file write triggers the next
refusal. Per-failure files live under
`inbox/scheduled-failures/` (excluded above); rotated logs live under
`.wiki.journal/exec-logs/` (excluded above). A user-edited
`inbox/scheduled-failures/<id>.md` that produced a `.proposed`
sidecar remains user-visible via `wiki doctor` but does not block
exec.

### Per-failure file format

Each `OperationExecFailedEvent` is paired with one new markdown file
at `inbox/scheduled-failures/<dispatch-event-id>.md`. The file is
created via the in-vault `safe_write` path. Per-dispatch-id file
names mean no two failures collide (each dispatch event id is
single-use). If the file already exists on disk — only possible if a
prior failure's file was preserved across a manual replay —
`safe_write` will treat the second write as a normal update and
produce a `.proposed` sidecar on hash drift, which the walk-scope
excludes from triggering further refusals.

The body is rendered from one of two templates, picked by `reason`:

- **`reason in {"non-zero-exit", "timeout"}`** (subprocess spawned):

  ```markdown
  # Scheduled exec failure

  - **Operation:** weekly-digest
  - **Dispatched:** 2026-05-21T09:00:00Z (event 01J0…)
  - **Failed:** 2026-05-21T09:29:58Z (event 01J0…)
  - **Reason:** timeout (exit -2, duration 1798s)
  - **Log:** [`.wiki.journal/exec-logs/01J0….log`](../../.wiki.journal/exec-logs/01J0….log)
  - **Last non-empty stderr line:** `claude: rate limit exceeded; retry after 60s`

  Resolve by reading the log, fixing the underlying cause, and either
  deleting this file or running the operation manually (`wiki run
  weekly-digest`). The next scheduled run fires normally regardless
  of whether this file is removed.
  ```

- **`reason == "conflict-refused"`** (subprocess never spawned):

  ```markdown
  # Scheduled exec refused: unresolved conflicts

  - **Operation:** weekly-digest
  - **Dispatched:** 2026-05-21T09:00:00Z (event 01J0…)
  - **Refused:** 2026-05-21T09:00:01Z (event 01J0…)
  - **Reason:** conflict-refused — `.proposed` sidecars present in scope.
  - **Sidecars found:**
    - `wiki/notes/foo.md.proposed`
    - `wiki/food/recipes/bar.md.proposed`

  Resolve each sidecar via the `wiki-conflict` SKILL (or delete
  manually), then delete this file. The next scheduled run will
  proceed.
  ```

  Conflict-refused failures have `log_path == None`, empty
  `stderr_tail`, and no duration — the bullet list of sidecars
  comes from the journaled `conflict_sidecars` field (same paths
  the event recorded).

"Last non-empty stderr line" is computed by splitting `stderr_tail`
on `\n`, dropping empty trailing strings, and taking the last
remaining element (or the empty string if none). User-resolution is
"delete the file"; the kit does not read these files back. A `wiki
doctor` count of `inbox/scheduled-failures/*.md` files surfaces the
backlog (orthogonal to the journal-event count in
[`wiki-schedule`](../wiki-schedule/spec.md) §"Doctor integration").

### Log rotation

On every `--exec` invocation, before spawning Claude, the kit walks
`.wiki.journal/exec-logs/` and deletes any `*.log` file whose
`stat().st_mtime` is more than `WIKI_EXEC_LOG_RETENTION_DAYS` days
old (default 30). Failures (permission denied, file vanished mid-
walk) are logged to stderr but do not abort. Rotation runs at most
once per `--exec` invocation. No journal events are emitted for log
deletions — they're cache-housekeeping, not state changes.

## Behavior

### `--exec` happy path

1. Dispatch phase runs to completion per
   [`task-17-wiki-run`](../task-17-wiki-run/spec.md). Suppose the
   dispatch is `OperationRunEvent(status="dispatched", event_id=E1)`.
2. The kit walks `vault_root` for `**/*.proposed`. If any: §"Exec
   phase / Conflict-refusal path" above.
3. The kit resolves the Claude binary. If not found: print the
   install-pointer warning, exit non-zero. No exec event journaled
   (no exec attempt was made).
4. The kit resolves the SKILL path. If the default doesn't exist
   and no `--skill-path` was supplied: raise `WikiError`. No exec
   event journaled.
5. The kit ensures `.wiki.journal/exec-logs/` exists (mkdir + add a
   `.gitignore` entry on first creation if not already in vault
   `.gitignore`).
6. `subprocess.run` with the args above. The dispatch event's id is
   passed to `claude` via `--input` so the SKILL can chain its
   work to the same event.
7. On success: stdout line, exit 0. **No second event.**
8. On failure (non-zero exit / timeout): journal
   `OperationExecFailedEvent`, append failure-page bullet, exit
   non-zero.

### Edge cases

- **`--exec` without an operation contract `skill:` field set.** The
  dispatch SKILL pointer already defaults to `<operation>` per
  task-17 spec CT-13. The exec phase uses the same fallback for the
  `--skill <path>` argument: `<vault_root>/.claude/skills/<op>/SKILL.md`.
- **`--exec` against a SKILL that doesn't exist on disk.** Refuse
  with `WikiError` *before* spawning Claude. Dispatch event is
  already journaled. No exec event.
- **`--exec` combined with `--help` (any form).** The existing
  `--help` short-circuit (task-17 CT-14) wins — print help, exit 0,
  no dispatch, no exec. `--exec` is consumed without effect.
- **`--exec` combined with `invalid_args` dispatch.** The dispatch
  phase journals `status="invalid_args"` and returns exit
  `WIKI_ERROR_EXIT` per task-17 spec. The exec phase **does not
  run** — invalid args mean the SKILL has nothing to act on. No
  exec event.
- **`.proposed` sidecar under `.wiki.journal/`** (vault-internal
  scratch). Excluded from the walk by design — see §"Conflict-refusal
  walk scope". Same for `.git/`, `.obsidian/`, `.claude/`, and
  `inbox/scheduled-failures/`. False positives there are the kit's
  own scratch, not user content.
- **Subprocess timeout fires after Claude has already journaled
  partial work.** Tolerated. The exec failure event records the
  timeout; any `PageWriteEvent`s Claude emitted before SIGTERM
  remain in the journal (the journal is append-only;
  [ADR-0004](../../adr/0004-drift-detection-and-proposal-flow.md)
  drift detection handles half-written pages on next run). The
  failure page bullet notes "partial work may exist; review log".
- **Concurrent `--exec` for two operations against the same
  vault.** Both attempts hold the journal lock for their dispatch
  appends but **not** for the duration of the subprocess. This is
  intentional: holding the lock across a 30-min Claude run would
  starve every other journal writer. Two scheduled execs that
  overlap will race on any pages they both touch; ADR-0004 drift
  detection is the safety net. Documented under spec §"Non-goals"
  for explicit recognition.
- **Vault `.gitignore` doesn't include `.wiki.journal/exec-logs/`.**
  The kit appends the entry on first log creation via the same
  additive-write helper used by `_ensure_obsidianignore` (per
  [`safe-write-ordering`](../safe-write-ordering/spec.md)). Pending
  audit; plan step 5 confirms the seam.

### Error cases

- Claude binary not found → `WikiError`; dispatch event remains;
  no exec event. Exit non-zero.
- SKILL file not found → `WikiError`; dispatch event remains;
  no exec event. Exit non-zero.
- Subprocess failures (non-zero exit, timeout) → journaled as
  `OperationExecFailedEvent`. Exit non-zero.
- `safe_write` drift on a per-failure file
  (`inbox/scheduled-failures/<id>.md`) is impossible by construction
  — each file is named after a single-use dispatch event id and
  written exactly once. If the user manually re-creates a file with
  the same name (rare), `safe_write` produces a `.proposed` sidecar
  that the walk-scope excludes from triggering further refusals.

## Invariants

- One `--exec` invocation appends **at most two `operation.*`
  events** — zero or one `OperationRunEvent` (per task-17's
  invariants) and zero or one `OperationExecFailedEvent` — **plus**
  whatever `PageWriteEvent` / `PageProposalEvent` the per-failure
  file write through `safe_write` produces (typically one
  `PageWriteEvent` per failure; one `PageProposalEvent` in the
  construction-time-impossible re-write case). The
  `OperationExecFailedEvent` is appended iff a `claude` subprocess
  was actually spawned and exited non-zero, or the conflict-refusal
  path fired.
- The dispatch event is always journaled before the exec
  subprocess spawns. The exec failure event is always journaled
  after the subprocess exits (or after the conflict-refusal check
  fires). Events appear in chronological order in the journal.
- `OperationExecFailedEvent.dispatch_event_id` always references an
  immediately-prior `OperationRunEvent` in the same invocation's
  journal slice. Cross-invocation references are not permitted.
- The exec subprocess is invoked with `cwd=vault_root` and the
  parent process's environment **unchanged** at v1. Per-platform
  env scrubbing (`PATH`, `HOME`, `LC_*`, `XDG_*`, `APPDATA`,
  Claude-specific vars, etc.) is deferred to the follow-on ADR that
  pins the Claude headless CLI flags (per
  [RFC-0003 §"Unresolved questions"](../../rfc/0003-scheduling-and-autonomous-execution.md#unresolved-questions))
  — getting the right allow-list cross-platform requires knowing
  which env vars Claude actually reads, which the kit doesn't own.
  v1 documents the pass-through; the ADR upgrades to scrubbing if
  warranted.
- No filesystem writes outside the journal append, the exec log,
  the failure page, and the additive `.gitignore` entry. No vault
  page writes from this module — page writes come from `claude`
  itself, via the kit's `safe_write` invoked by SKILL code.
- `--exec`-less behavior is **byte-identical** to the existing
  task-17 contract. The CT-N items from
  [`task-17-wiki-run/spec.md`](../task-17-wiki-run/spec.md)
  continue to pass unchanged.

## Contracts with other modules

- **`cli.py:_cmd_run`** — gains two new argparse flags (`--exec`,
  `--claude-binary`, `--skill-path`). The REMAINDER consumption of
  op-args is unchanged; these flags sit *before* the operation
  name. Example: `wiki run --exec --claude-binary /opt/claude
  weekly-digest --window=2026-W20`.
- **`llm_wiki_kit/run.py`** — `dispatch()` signature is unchanged.
  A new top-level orchestrator `dispatch_and_exec()` is added:
  ```python
  def dispatch_and_exec(
      operation: str,
      raw_args: list[str],
      *,
      vault_root: Path,
      kit_root: Path,
      journal_path: Path,
      now: datetime,
      claude_binary: Path | None,
      skill_path_override: Path | None,
      timeout_seconds: int,
  ) -> ExecResult
  ```
  Internally: calls `dispatch()`, then if `DispatchResult.status
  == "dispatched"`, runs the exec sequence. `ExecResult` wraps the
  `DispatchResult` and adds `exec_status: Literal["skipped",
  "succeeded", "failed_conflict", "failed_binary_missing",
  "failed_skill_missing", "failed_exit", "failed_timeout"]` and
  optional `exec_event_id: str | None`. Inner helpers
  (`_locate_claude`, `_locate_skill`, `_walk_proposed_sidecars`,
  `_run_subprocess`, `_append_failure_event`) are pure and tested
  directly.
- **`llm_wiki_kit/models.py`** — additive per ADR-0002. One new
  class:
  ```python
  class OperationExecFailedEvent(_EventBase):
      type: Literal["operation.exec_failed"] = "operation.exec_failed"
      operation: str
      dispatch_event_id: str
      exit_code: int
      reason: Literal["non-zero-exit", "timeout", "conflict-refused",
                       "binary-missing", "skill-missing"]
      stderr_tail: str = ""
      log_path: str | None = None
      conflict_sidecars: list[str] = Field(default_factory=list)
  ```
  `conflict_sidecars` is empty for every reason except
  `conflict-refused`; older journal lines (none exist yet at v1)
  replay unchanged under ADR-0002's additive-schema rule.
  The `reason="binary-missing"` and `reason="skill-missing"` values
  are reserved for future use — v1 spec'd above says these failures
  do **not** journal an exec event. The reserved variants exist so
  a future spec amendment can opt into journaling them without
  another model change.
- **`llm_wiki_kit/journal.py`** — read by the exec sequence (to find
  the dispatch event id it just wrote — `append_event` returns the
  event with its assigned id), written via `append_event` for the
  optional failure event.
- **`llm_wiki_kit/write_helper.py`** — `safe_write` (the in-vault
  path) for each per-failure file under
  `inbox/scheduled-failures/<dispatch-event-id>.md`. No managed
  regions, no new helper — each file is single-write by
  construction.
- **The vault-side SKILL** — receives the dispatch event id via
  `--input`. The SKILL contract is unchanged; spec'd separately
  in the vault-side `wiki-schedule` SKILL.md (out of scope here).

## Acceptance criteria

The contract tests below define "done". Construction tests live in
plan files for the schedule + exec PRs.

- [ ] **CT-1: `--exec` happy path.** Given an installed
  `weekly-digest`, a `<vault>/.claude/skills/weekly-digest/SKILL.md`,
  and a fake `claude` binary on `PATH` that exits 0, `wiki run
  --exec weekly-digest --window=2026-W20` (a) appends exactly one
  `OperationRunEvent(status="dispatched")`, (b) spawns the binary
  with argv whose `[0]` is the absolute path of the fake `claude`
  binary and whose remaining elements reference both the SKILL
  path and the dispatch event id (asserted via a script that echoes
  its argv to a fixture file; the exact shape is pinned by CT-13's
  follow-on ADR), (c) writes
  `.wiki.journal/exec-logs/<dispatch-id>.log`, (d) appends **no**
  exec event, (e) exits `0`.
- [ ] **CT-2: `--exec` with `invalid_args` skips the exec phase.**
  `wiki run --exec weekly-digest --frobnicate=x` against a contract
  with no `frobnicate` field appends one `OperationRunEvent(status=
  "invalid_args")`, spawns no subprocess, journals no exec event,
  exits `WIKI_ERROR_EXIT`.
- [ ] **CT-3: claude binary not found.** With no `claude` on PATH,
  no `--claude-binary`, and no `WIKI_CLAUDE_BINARY`, `wiki run
  --exec weekly-digest --window=2026-W20` appends the dispatch
  event, prints an install-pointer warning to stderr, journals
  **no** exec event, exits non-zero.
- [ ] **CT-4: SKILL file missing.** With Claude present but no
  `<vault>/.claude/skills/weekly-digest/SKILL.md` and no
  `--skill-path`, the call appends the dispatch event, raises
  `WikiError` naming the resolved path, journals no exec event,
  exits non-zero.
- [ ] **CT-5: `--skill-path` override.** With the SKILL stored at
  a non-default location, `--skill-path <path>` causes the kit to
  pass that path to `claude` (asserted via the argv-echo fixture).
- [ ] **CT-6: conflict refusal.** With one `.proposed` sidecar in
  scope under `vault_root` (e.g. `wiki/notes/foo.md.proposed`),
  `wiki run --exec weekly-digest --window=2026-W20` (a) appends the
  dispatch event, (b) appends one
  `OperationExecFailedEvent(reason="conflict-refused", exit_code=-1)`,
  (c) writes `inbox/scheduled-failures/<dispatch-id>.md` via
  `safe_write`, (d) spawns no subprocess, (e) exits non-zero.

- [ ] **CT-6a: walk-scope excludes own scratch.** With a `.proposed`
  sidecar under any of `.wiki.journal/`, `.git/`, `.obsidian/`,
  `.claude/`, or `inbox/scheduled-failures/`, **and no sidecars
  elsewhere**, `wiki run --exec weekly-digest --window=2026-W20`
  proceeds to spawn the subprocess (no refusal event, no failure
  file).

- [ ] **CT-6b: walk-scope honors `.obsidianignore`.** With a
  `.proposed` sidecar under a directory matched by
  `.obsidianignore`, the call proceeds to spawn the subprocess.
- [ ] **CT-7: subprocess non-zero exit.** With Claude present and
  a stub binary that exits `137`, the call (a) appends the dispatch
  event, (b) spawns the binary, (c) appends one
  `OperationExecFailedEvent(reason="non-zero-exit", exit_code=137)`
  whose `dispatch_event_id` matches the dispatch event's id, (d)
  writes `inbox/scheduled-failures/<dispatch-id>.md` via
  `safe_write`, (e) writes the full log to
  `.wiki.journal/exec-logs/<id>.log`, (f) exits non-zero.
- [ ] **CT-8: subprocess timeout.** With `WIKI_EXEC_TIMEOUT=1` and
  a stub binary that sleeps 10 seconds, the call terminates the
  subprocess and journals
  `OperationExecFailedEvent(reason="timeout", exit_code=-2)`. Exit
  non-zero.
- [ ] **CT-9: byte-identity for non-`--exec` invocations.** The 16
  contract tests in
  [`task-17-wiki-run/spec.md`](../task-17-wiki-run/spec.md) (CT-1
  through CT-16) all pass unchanged after this spec's
  implementation.
- [ ] **CT-10: `OperationExecFailedEvent` additive schema replays.**
  A literal pre-extension journal that contains no
  `operation.exec_failed` events replays under the extended Pydantic
  model unchanged.
- [ ] **CT-11: per-failure file invariants.** Two failures from two
  distinct `--exec` invocations produce exactly two files under
  `inbox/scheduled-failures/`, named after their respective
  `dispatch_event_id`. Every file's body contains the operation
  name, the reason, and the dispatch event id. **For
  `non-zero-exit` / `timeout` failures**, the body also contains
  the exit code, the relative log path, and a "Last non-empty
  stderr line:" field whose value matches the final non-empty line
  of the journaled `stderr_tail`. **For `conflict-refused`
  failures**, the body lists the offending sidecar paths from the
  journaled `conflict_sidecars` field, contains neither a log link
  nor a duration, and the journaled event has `stderr_tail == ""`
  and `conflict_sidecars != []`. A user who deletes one file does
  not affect the other.
- [ ] **CT-12: stderr_tail is bounded.** A stub binary that emits
  100 KB of stderr produces a journaled `stderr_tail` of exactly
  the last 4 KB (or fewer if the binary emitted less). UTF-8
  decode errors fall back to lossy decode (no crash).
- [ ] **CT-13: argv structure (deferred to follow-on ADR).**
  `_build_argv(claude_binary, skill_path, vault_root,
  dispatch_event_id, parsed_args)` returns a `list[str]` whose
  `[0]` is the absolute path of `claude_binary`. The remaining
  shape — exact flag names, JSON wrapping of args, env-var vs.
  argv placement of the dispatch event id — is pinned by a
  follow-on ADR that documents the Claude headless CLI minimum
  version (per
  [RFC-0003 §"Unresolved questions"](../../rfc/0003-scheduling-and-autonomous-execution.md#unresolved-questions)).
  This CT is **BLOCKED on that ADR**; v1 ships a placeholder
  `_build_argv` whose output is sufficient to drive a stub binary
  that records its argv. Reviewers: confirm this deferral is
  acceptable before implementation lands.

- [ ] **CT-14: no `OperationExecSucceededEvent`.** After a
  successful `--exec`, the journal slice for the invocation
  contains exactly one event with `type=="operation.run"` and
  zero with `type=="operation.exec_succeeded"`. Pins spec
  §"Non-goals".

- [ ] **CT-15: log rotation.** With a 31-day-old
  `.wiki.journal/exec-logs/old.log` and a fresh `--exec`
  invocation, the old file is deleted before the subprocess
  spawns. A 29-day-old file is preserved.

- [ ] **CT-16: SKILL-name fallback at the exec layer.** Given a
  contract with no `skill:` field set and no `--skill-path`
  override, the kit resolves the SKILL path to
  `<vault_root>/.claude/skills/<operation>/SKILL.md` and passes
  that path to `claude` (asserted via the argv-echo fixture from
  CT-5). Matches [task-17 CT-13](../task-17-wiki-run/spec.md)
  fallback behavior.

- [ ] **CT-17: failure-file write does not loop refusal.** A
  refusal that writes
  `inbox/scheduled-failures/<id>.md` (which is itself a new file
  under `inbox/scheduled-failures/`) does **not** cause the next
  `--exec` invocation to refuse — `inbox/scheduled-failures/` is
  in the unconditional walk-scope exclusion list.

## Non-goals

- **An `OperationExecSucceededEvent`.** Symmetry with the failure
  event is tempting, but the dispatch event already records the
  attempt and a future `journal explain` can correlate it with
  downstream `PageWriteEvent`s emitted by the SKILL. Adding a
  success event doubles journal volume for the common case
  without new information. Future RFC if observability needs
  surface.
- **SDK-based execution.** Out of scope per RFC-0003 §"Decisions
  already made". Adding `anthropic` as a runtime dep would need
  its own ADR.
- **Cost / token tracking.** The kit does not record API spend.
  Users who want that hook can wrap `wiki run --exec` in a script
  that reads the exec log.
- **Streaming exec output to the operator's terminal.** v1 sends
  all output to the log file. A future `--tail` or `--no-log`
  flag could change this; deferred.
- **Holding the journal lock for the duration of the subprocess.**
  Documented under spec §"Edge cases" — overlapping execs are
  expected to be rare; ADR-0004 drift detection is the safety
  net.
- **Recovering partial work from a timed-out exec.** Whatever
  Claude already journaled and wrote stays in the journal /
  drift-detection flow. The kit does not roll back partial work.
- **Auto-retrying failed execs.** A scheduled run that failed
  fails. The user (or a future scheduling-retry RFC) decides
  when to re-attempt.
- **A `wiki run --dry-run` flag.** The dispatch boundary is
  already a no-side-effect read of the contract; a dry-run mode
  would only differ from the current behavior by suppressing the
  journal append, which is an explicit non-goal of the dispatch
  contract (task-17 §Non-goals).
- **Vault-side SKILL contract changes.** This spec passes the
  dispatch event id and parsed args through to Claude; the SKILL
  contract for *what to do with them* is described in the
  vault-side `wiki-schedule` SKILL.md (out of scope here).

## Constraints

- No new runtime dependency. `subprocess`, `shutil.which`,
  `pathlib`, `os.environ` are all stdlib.
- No new top-level repo directory. All code changes land in
  `llm_wiki_kit/run.py`, `llm_wiki_kit/cli.py`, and
  `llm_wiki_kit/models.py`.
- No bypass of `journal.append_event` for the new event type.
- No bypass of `write_helper.safe_write` for the failure-page
  append.
- No new public CLI verb. `wiki run` gains three additive flags
  (`--exec`, `--claude-binary`, `--skill-path`) and no new
  subcommand.
- No daemon process. The exec subprocess is one-shot per
  invocation; the kit waits for it and exits.
- No retro-edit of existing journal events. The model changes are
  additive (one new event class).
- No change to the dispatch-event shape. `OperationRunEvent` is
  untouched; the new exec event references the dispatch event by
  id, not the other way around.
- No new ADR — the load-bearing decisions trace back to
  [RFC-0003](../../rfc/0003-scheduling-and-autonomous-execution.md).
  A follow-up ADR would only land if the subprocess-invocation
  shape surfaces a decision worth pinning (e.g. the headless-flag
  vocabulary if it stabilises).
