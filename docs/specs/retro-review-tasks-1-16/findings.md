# Retrospective review — v2 migration tasks 1–16

- **Date:** 2026-05-16
- **Reviewers:** `adversarial-reviewer` + `quality-engineer` subagents (dispatched in parallel per work-loop §Parallel-dispatch)
- **Scope:** Integrated state of `main` after RFC-0001 tasks 1–16. Excludes RFC-0002 adoption tooling.
- **Branch:** `eugenelim/retro-review-tasks-1-16` (this file lives here; fix PRs branch from `main` directly).

## Severity definitions (from the review brief)

- **Blocker** — must fix before task 17 starts. Contract violation, broken invariant, missing acceptance criterion from the RFC, or a defect that will cascade through later tasks. Each Blocker gets a fix PR (or, if too large, a new spec deferred to Phase F).
- **Concern** — fix opportunistically; the migration can continue around it. Filed as GitHub issues with `retro-review-2026-05` label.
- **Nit** — style / doc polish. Batch into a single cleanup PR after migration ships, or drop.

Findings carry stable IDs:
- `B`/`C`/`N` from the adversarial reviewer.
- `qB`/`qC`/`qN` from the quality-engineer reviewer.
- Re-triaged Blockers from quality findings carry their original `qB*` id.

## Counts after merge + re-triage

- **Blockers:** 3 (F-B1, F-B2, F-B3a). Fix PRs opened. F-B3b deferred to a new spec.
- **Concerns:** 24 (B4, B5, C1–C10, qB1, qB3, qC1–qC11; qB2 absorbed into F-B3b spec; B6 folded into F-B1's fix PR). Tracked in **issue #23** with one checkbox per finding, all labelled `retro-review-2026-05`.
- **Nits:** 12 (N1–N7, qN1–qN5). Queued for a single cleanup PR; not actioned in this session.

## Fix PRs and tracking

| Finding   | Status   | Reference                                                                   |
|-----------|----------|-----------------------------------------------------------------------------|
| F-B1 + B6 | Fix PR   | PR #22 (`eugenelim/retro-fix-managed-region-resolve-baseline`)              |
| F-B2      | Fix PR   | PR #21 (`eugenelim/retro-fix-wiki-resolve-cli`)                             |
| F-B3a     | Fix PR   | PR #20 (`eugenelim/retro-fix-wiki-lock-skill-notice`)                       |
| F-B3b     | New spec | Deferred — `new-spec` for journal-locking opens in next session (Phase F)   |
| Concerns  | Tracker  | Issue #23 (label `retro-review-2026-05`)                                    |

## Task-17-cleared decision

**Task 17 is CLEARED conditionally.** None of the three retained Blockers gates task 17 (orchestrator / operation runner) by *type signature* — task 17 doesn't touch `safe_write_region`, doesn't ship a new vault-side skill, and doesn't depend on `wiki resolve` as a routine path. The three Blockers must have fix PRs **opened** (not necessarily merged) before task 17 begins; this preserves the work-loop discipline that drift gets *recorded* and *closed* rather than ignored, without serialising task 17 behind merge.

The downgrades (B4, B5, qB1, qB2, qB3 to Concerns) are deliberate, justified per finding below, and each carries an opened GitHub issue so task 17 cannot accidentally inherit them as silent debt.

---

## Blockers (fix PRs in flight)

### F-B1 — Managed-region drift never re-baselines after `resolve_proposal`, producing an infinite proposal loop

**Source:** adversarial B1 (+ folds B6 into the same fix PR).

**Citation:** `llm_wiki_kit/write_helper.py:105-149` and `:196-235`; `docs/adr/0004-drift-detection-and-proposal-flow.md` step 6.

**What's wrong:** ADR-0004 step 6 promises that after `resolve_proposal`, "subsequent `safe_write` calls against `path` see no drift." For page writes this holds because `resolve_proposal` appends a `PageWriteEvent` and `_baseline_hash` reads `PageWriteEvent`. For managed-region writes, the drift path emits a `PageProposalEvent` for the whole file but no `ManagedRegionWriteEvent`. `resolve_proposal` then emits another `PageWriteEvent`, not a `ManagedRegionWriteEvent` — so `_managed_region_baseline_hash` still returns the pre-drift hash on the very next `safe_write_region` call. The kit will emit a new proposal every install/upgrade until the user manually edits the region back. Folded sub-finding B6: `doctor.check_managed_region_drift` double-reports the same condition as both `managed-region-drift` and `pending-proposal` for the enclosing file.

**Why Blocker:** Cascades through every `wiki init`/`wiki add` once a user edits a shared file (e.g. `frontmatter.schema.yaml`). Region writes run on every install in the kit's current shape; the next family-recipe install plus one user edit makes the vault permanently noisy.

**Fix shape:** Have `resolve_proposal` accept an optional region descriptor and emit a `ManagedRegionWriteEvent` per `(file, region)` reconciled — or add a dedicated `resolve_managed_region_proposal`. In `doctor.check_managed_region_drift`, skip `(file, region)` pairs whose enclosing `file` is in `state.pending_proposals`. Document the new contract in ADR-0004 alongside step 6.

**Fix PR:** `eugenelim/retro-fix-managed-region-resolve-baseline` — opened.

### F-B2 — Vault-side `wiki-conflict` skill calls a `wiki resolve` CLI subcommand that does not exist

**Source:** adversarial B2.

**Citation:** `core/files/skills/wiki-conflict/SKILL.md:69,99,102,120`; `core/files/AGENTS.md:61`; `llm_wiki_kit/cli.py:504-591` (no `resolve` subparser).

**What's wrong:** Every fresh `wiki init --recipe <r>` ships `wiki-conflict/SKILL.md` into the user's vault today. The first time a user hits a `.proposed` sidecar, their Claude session runs `wiki resolve <path>` and `argparse` prints `invalid choice: 'resolve'`. The skill also documents `--keep` and `--accept` flags. ADR-0004 step 6 names `write_helper.resolve_proposal(path, content, by, journal_path)` as the underlying bypass — the CLI surface that the skill drives just isn't wired.

**Why Blocker:** User-facing functional break in shipped vaults. Drift-detection's whole story leans on a recovery path the user can't actually execute.

**Fix shape:** Add `wiki resolve <path>` to `build_parser`, with `--keep` / `--accept` / stdin paths, wired to `write_helper.resolve_proposal`. Integration test: write a file, edit it, `safe_write` produces a `.proposed`, `wiki resolve --accept` consumes the sidecar and journals both events.

**Fix PR:** `eugenelim/retro-fix-wiki-resolve-cli` — opened.

### F-B3 — Vault-side `wiki-lock` skill is unimplementable: events not modelled, CLI absent, runtime lock absent

**Source:** adversarial B3 (composes with quality qB2 — concurrent-writer corruption).

**Citation:** `core/files/skills/wiki-lock/SKILL.md` (entire); `core/files/skills/wiki-doctor/SKILL.md:34`; `core/files/AGENTS.md:128-153`; `llm_wiki_kit/models.py:250-266` (no lock event class); `llm_wiki_kit/cli.py:504-591` (no `wiki lock` subparser); `llm_wiki_kit/journal.py:73` (no `flock`). ADR-0002 §Negative line 98-100 names `operation.lock` as a mitigation that doesn't exist in code.

**What's wrong:** Multi-file operation skills (`weekly-digest`, `meal-planning`, etc.) tell their loaders to acquire the lock first — there's no CLI to acquire it. Concurrent `wiki` invocations corrupt the journal silently because no `fcntl.flock` wraps `append_event`.

**Why Blocker (and partial deferral):** The user-visible piece (a SKILL.md that names CLI verbs that don't exist) ships today and is the kit's flagship "multi-step operations are safe" promise. The runtime piece (real `flock` + lock event types + `wiki lock acquire/release` + doctor stale-lock check) is a coherent design problem too large for a single fix PR.

**Split:**

- **F-B3a (this session):** Document the gap in-place. Add a one-line "Phase D not yet shipped — see issue #<id>" header to `wiki-lock/SKILL.md`, the doctor SKILL.md stale-lock paragraph, and the `core/files/AGENTS.md` lock-workflow mentions. Also append a note to ADR-0002 §Negative that the named mitigation is not yet implemented and is tracked at issue #<id>. This unblocks task 17 by removing the "documented but broken" trap from vaults shipped between now and Phase F.
- **F-B3b (deferred to Phase F via `new-spec`):** Real implementation. A standalone spec `docs/specs/journal-locking/spec.md` covers: `fcntl.flock` in `append_event`, `LockAcquired`/`LockReleased` event types, `wiki lock acquire|release` CLI, doctor stale-lock check, ADR-0002 amendment naming the actual contract. **Not opened in this session** — flagged here so the work loop sees it on next plan.

**Fix PR:** `eugenelim/retro-fix-wiki-lock-skill-notice` (F-B3a) — opened. F-B3b: spec to be opened in next session (out of scope for this session per the brief's "If a Blocker is too large for one fix PR, open a spec via new-spec skill instead").

---

## Concerns (filed as issues with `retro-review-2026-05`)

### From adversarial review

- **B4** — `.github/workflows/check-sync.yml` and `scripts/check-sync.sh` / `scripts/sync-shared.sh` reference deleted v1 paths (`shared/**`, `vault-templates/**`); also: RFC-0001 §"Pre-flight" called for `archive/v1-*/` but the v1 tree was deleted in-flight. **Downgrade rationale:** the workflow only fires on PRs touching the missing paths, so it doesn't actively block anything; clean-up + RFC amendment can come in a follow-up.
- **B5** — Wheel install ships no `recipes/`, no `core/`, no `templates/`. `pyproject.toml:44-45` packages only `llm_wiki_kit`; `_KIT_ROOT` (`cli.py:60`) resolves to `site-packages/` in a wheel. **Downgrade rationale:** only blocks the v2.0.0 PyPI release; `pip install -e .[dev]` for the maintainer journey works. Becomes a release Blocker before Phase E completes.
- **B6** — Folded into F-B1's fix PR (same root cause, same fix surface).
- **C1** — `PageConflictResolvedEvent` has no `region` field; managed-region resolves can't record per-region audit. Additive schema change per ADR-0002 §Negative.
- **C2** — `.obsidianignore` writes bypass `safe_write` (`write_helper.py:278-285`); user edits are silently lost on next kit write. Either journal it or document non-journaled status in ADR-0004 §Negative.
- **C3** — `Routed.via` is `str`, `IngestRoutedEvent.via` is `Literal["auto","as_flag"]`; `cli.py:457` bridges with `# type: ignore[arg-type]`. Tighten the `Routed` dataclass.
- **C4** — RFC-0001 vs reality: "archive v1 tree under `archive/v1-*/`" — repo has no `archive/`. Amend RFC to record what actually happened, or schedule a move task.
- **C5** — `docs/architecture/overview.md:40,104` lists a `conflict.py` module that was never created; `install.py` is missing from the overview. Doc drift.
- **C6** — `doctor.KIT_OWNED_FILES` is a static tuple; any vault-root file the kit ships (e.g. `identity.md`) outside the tuple is invisible to the orphan check. Derive from journaled writes instead.
- **C7** — Skill files ship promissory docs for `wiki upgrade`, `wiki run`, `wiki search`, `wiki research`, `wiki journal *`, `wiki doctor --strict`, `wiki journal repair`, `wiki journal lock release --force`. All Phase D/E. Either add a header note (same shape as F-B3a) or hide behind "Once available:".
- **C8** — `journal.append_event` does one `fh.write(line)` with no contract documentation around concurrent readers/replayers. Tighten the docstring + ADR-0002 §Negative or buffer the line through `os.write`.
- **C9** — `recipes/work-os.yaml:34` lists `core` explicitly while `family.yaml` / `personal.yaml` deliberately omit it; convention mismatch.
- **C10** — Many content-type primitives lack `routing:` blocks (`interview`, `action-item`, `customer-feedback`, `decision`, `stakeholder-update`). Either document the manual-only intent or add a `manual_only: true` sentinel to `PrimitiveRouting`.

### From quality-engineer review

- **qB1** — `journal.append_event` has no `fsync`. A crash between write and disk flush loses an intent event. **Downgrade rationale:** kit doesn't run during high-volume scheduled writes yet; `wiki doctor` recovers from missing-event cases; ADR-0002 §Negative already names this as accepted trade-off. Reopen as Blocker before Phase D (scheduled ops) lands.
- **qB2** — No `fcntl.flock` on the journal append path; concurrent writers corrupt the journal. Composes with F-B3 (lock infrastructure). **Tracked under the F-B3b new-spec.**
- **qB3** — `safe_write` against a path outside vault root raises bare `ValueError` (Python tracebacks leak through the CLI boundary). One-line fix in `_relative_to_vault`. **Downgrade rationale:** affects developer experience for primitive authors, not end-users yet; clean follow-up.
- **qC1** — No `--verbose`/`WIKI_DEBUG` surface; `WikiError` handlers print one line.
- **qC2** — `ValidationError._format` drops Pydantic's `input` / `ctx` fields — the most diagnostic part of a validation failure.
- **qC3** — `safe_write` writes the file *then* appends the event; ADR-0002 §Decision says "appends one validated event before touching disk." Contract drift between Decision text and implementation. Either reorder code or amend the ADR's Decision wording to match (and replace the Mitigated framing in §Negative).
- **qC4** — `_baseline_hash` / `_managed_region_baseline_hash` re-read the journal on every `safe_write`; install pipelines are O(events × writes). Introduce a `JournalReader` cache shared across one CLI invocation.
- **qC5** — `read_events` raises hard on the first malformed line; `wiki doctor` can't run on a corrupt journal — which is exactly the recovery case it exists for. Add a `stop_on_corruption` mode and surface the corruption as a doctor `Issue`.
- **qC6** — `safe_write` to an existing file with no prior `PageWriteEvent` silently overwrites (current pinned-by-test behaviour, with the safety net deferred to `wiki init`'s empty-dir guard). `wiki add` does not enforce that guard. Treat unjournaled existing files as drift (write `.proposed` and emit a proposal).
- **qC7** — `templates/content-types/*/regions/frontmatter.schema.yaml.fields` snippets duplicate the `when: type == <name>` shape 12 times with no validator; a missing `when:` clause produces a frontmatter rule that fires on every page. Add a `test_all_content_type_snippets_carry_matching_when_clause` parametrised over the 12 content-types.
- **qC8** — `_KIT_ROOT` is module-level state monkey-patched by every integration test; the planned move to `importlib.resources` breaks 8 test files. Introduce a `_kit_paths()` helper and grep-guard against direct references.
- **qC9** — `_relative_to_vault` doesn't `.resolve()` the absolute path; symlinks and `..` segments confuse drift detection (two different journaled `path` values for the same on-disk file).
- **qC10** — `doctor.KIT_OWNED_DIRS` is a hard-coded tuple `("skills", "_templates", "wiki")`; new top-level dirs (`outputs/digests/`, `outputs/meal-plans/`) won't be flagged for orphans. Derive from `state.page_writes`.
- **qC11** — `IngestRoutedEvent` is written by `wiki ingest` but `replay_state` ignores it — no command consumes it today. Pin the round-trip with a test so a future maintainer doesn't quietly remove the model field.

---

## Nits (queued for a single cleanup PR)

- **N1** — `cli.py:457` `# type: ignore[arg-type]` (paired with C3).
- **N2** — `recipes/personal.yaml` ships `owner_*` defaults as empty strings; `wiki init` produces literal `` placeholders in `identity.md` until user edits.
- **N3** — `discover_primitives` is lenient on missing manifests; `discover_recipes` is fatal. Align the strictness.
- **N4** — `models.py:24-25` `NAME_PATTERN` not applied to `IngestRoutedEvent.content_type`.
- **N5** — `personal.yaml` has "deliberately excluded" framing; family / work-os don't. Consistency.
- **N6** — `_KIT_ROOT` TODO (`cli.py:55-59`) tied to B5.
- **N7** — `doctor.py:231` issue sort key includes `detail` which is usually empty. Acceptable; cosmetic.
- **qN1** — `install._snippet_filename` `..`-guard is asymmetric across `file` and `region`.
- **qN2** — `journal._summarize` returns only the first validation error; multi-field failures lose context.
- **qN3** — Test name `test_safedict_preserves_format_spec_on_missing_key` misrepresents the (correct, intentional) drop-spec behaviour.
- **qN4** — Catalog-load duplicated verbatim in `_cmd_init`, `_cmd_add`, `_cmd_upgrade`. Extract `_load_catalog()`.
- **qN5** — Withdrawn by reviewer on second read.

---

## Process notes

- Both reviewers ran in a single parallel-dispatch call per work-loop §Parallel-dispatch.
- All findings were spot-checked against the cited code before triage. Specifically verified: F-B1 (the two `append_event` call sites in `write_helper.py`), F-B2 (`build_parser` subparser list), qC3 (the write-then-append ordering in `safe_write`).
- "Re-run iteratively until clean" gate: both reviewers self-reported internal consistency on their first pass; no second round needed.
