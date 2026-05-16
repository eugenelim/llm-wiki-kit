# ADR-0004: Drift detection and proposal sidecars instead of overwrites

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** maintainer
- **Related:** RFC-0001, ADR-0002, ADR-0003, `docs/architecture/overview.md` ("Three layers of write safety")

## Context

The kit writes to files inside a user's vault under several scenarios:

- Initial render at `wiki init` — files that don't exist yet.
- Primitive install / upgrade — files that the kit wrote previously,
  possibly with user edits since.
- Source ingest — new wiki pages produced from a source document.
- Operation runs — generated pages like the weekly digest.

A vault is also routinely edited by the user directly (notes during a
meeting, fixes to a recipe ingredient list, personal annotations on a
medical record). The kit and the user write to overlapping paths.

Naïve write semantics produce one of three failure modes:

1. **Last writer wins** — the kit overwrites user edits, or vice versa.
   The most common cause of users abandoning automation tools.
2. **Skip if exists** — the kit refuses to write to any file that
   exists. Then upgrades, re-ingests, and operation re-runs can't update
   anything.
3. **Bespoke merge per command** — every CLI subcommand decides its own
   semantics. Inconsistency surfaces as bugs and forces users to learn
   five behaviors.

The charter principle "Don't auto-write to user-edited content" is non-
negotiable. The constraint is to find a single safe-write semantics that
covers all four scenarios above without either silently overwriting or
refusing to upgrade.

A separate consideration: in any conflict case, the user benefits from
Claude's help. The kit's job is to *detect* drift and *stage* the
conflict; resolving it should be a conversation, not a mechanical merge.

## Decision

> **Every kit write to a user vault goes through `safe_write(path, content, by, journal)`.
> It hashes the on-disk file, compares to the latest `PageWrite` event
> for that path in the journal, writes directly on match, and falls
> through to a `<path>.proposed` sidecar plus `PageProposal` event on
> mismatch. The user resolves via the `wiki-conflict` skill.**

Mechanics:

1. `safe_write` computes the on-disk hash (`sha256`) of `path`. If the
   file doesn't exist, treat the hash as empty.
2. It walks the journal backward to find the latest `PageWrite` event
   whose `path` matches. If none, this is a first write — go to step 4.
3. If the on-disk hash matches the journaled hash, the user hasn't
   touched it since — safe to overwrite. Go to step 4.
4. Direct write: write `content` to `path`, compute the new hash,
   append a `PageWrite` event recording `path`, `hash`, `by`
   (the primitive or operation responsible), timestamp. Return
   `WriteResult.WRITTEN`.
5. If the hashes diverge, the user edited the file. Write `content` to
   `<path>.proposed` (the sidecar), append a `PageProposal` event with
   the same fields plus a `proposed_path`. Return `WriteResult.PROPOSAL`.
   The CLI surface prints a one-line prompt telling the user to run the
   `wiki-conflict` skill.
6. When the user runs the vault-side `wiki-conflict` skill, Claude
   reads `path`, `path.proposed`, the journal context, and (where
   available) the originating source, and helps the user produce a
   final version — which may be the proposed content, the user's edited
   content, or a third merged version. On confirmation, the skill calls
   `write_helper.resolve_proposal(path, content, by, journal_path)`.
   `resolve_proposal` writes `content` directly to `path` (bypassing
   the step-1-to-3 drift check because the user has already reviewed
   both versions and confirmed), deletes the `<path>.proposed` sidecar
   if present, and appends two events: a `PageWrite` with the merged
   hash — which becomes the new baseline, so subsequent `safe_write`
   calls against `path` see no drift — and a `PageConflictResolved` for
   audit.

This same path applies to managed regions (ADR-0003): when a managed
region's content has changed on disk vs. its previous journaled
`managed_region.write` event, the whole shared file falls through the
proposal path. When the user resolves the proposal via
`resolve_proposal`, the resolved file is parsed for every region the
journal has ever recorded for that path, and one
`ManagedRegionWriteEvent` is emitted per known region — re-baselining
the region-scoped lookup that `safe_write_region` uses, so subsequent
region writes of the same file see no drift (the same contract step 6
states for plain `safe_write`).

`safe_write` is the *only* sanctioned write path for kit code that
touches a user's vault, with one documented exception:
`resolve_proposal` (step 6) bypasses the drift check because conflict
resolution is the explicit user-mediated acknowledgement that on-disk
state should be overwritten with the merged content. Nothing else
calls `Path.write_text()` against a vault path. Tests use `tmp_path`
and can call `write_text` freely.

## Consequences

### Positive

- **No silent overwrites.** Every user edit either survives untouched
  or surfaces as an explicit conflict. The charter's "honesty over
  capability" principle is enforceable.
- **Single semantics across all commands.** `init`, `add`, `upgrade`,
  `ingest`, `run` all route through the same write helper. Users learn
  one behavior.
- **Claude does the merge.** The kit doesn't try to be smart about
  prose merging. The proposal sidecar is just "here are both versions";
  the `wiki-conflict` skill turns it into a conversation.
- **The journal is the trust anchor.** Drift detection is "did this
  hash change?" — a question the journal can answer in O(1) per path
  with a small index.

### Negative

- **Sidecars accumulate if the user ignores them.** Mitigated: the
  kit warns at every invocation when sidecars exist, and `wiki doctor`
  reports them.
- **One extra fs hash per write.** Negligible (sha256 on a typical
  markdown file is <1ms).
- **First-time installs over an existing folder are noisy.** If the
  user is converting an existing pile of markdown into a kit-managed
  vault, every existing file looks like "drift" relative to no journal
  baseline. Mitigated: `wiki init` over a non-empty folder either
  refuses (default) or runs an explicit `--adopt` path that journals
  every existing file as a `PageWrite` at adoption time.
- **A 0-byte file is a valid hash.** The kit treats a hash-empty
  baseline as "no prior knowledge," which collapses to the same write
  path. Edge handled in tests.

### Neutral / monitor

- The hash algorithm is `sha256`. If a faster hash (e.g., `blake2b`)
  becomes the obvious choice, switching is a one-line change because
  the algorithm is stored in the `PageWrite` event payload, not assumed.
- If sidecar accumulation becomes a real UX problem, evaluate
  auto-archiving sidecars older than 30 days under
  `.wiki.journal/proposals-archive/`. (Already in the migration plan
  as the recovery path for vaults without git.)

## Alternatives considered

### Alt 1: Three-way merge using git

If the user has git, we could compute a true three-way merge: kit's
last known content (from the journal), current on-disk content, kit's
new proposed content. Loses because:

- Not all users have git. The kit is suggested-not-required for git.
- Prose merges are reliably awful even when git is present.
- We'd still surface conflicts to the user — just with more code.
- The journal already gives us the "base" content via the most recent
  `PageWrite` hash; the proposal flow gives us the "ours" and "theirs."
  Claude is a better merge UI than `<<<< ====` markers.

### Alt 2: Last-writer-wins

The default of most automation tools. Trivially loses against the
charter. Non-starter.

### Alt 3: Skip-if-exists

The kit refuses to overwrite anything. Trivially loses against
"primitive upgrades need to update files."

### Alt 4: Per-command write semantics

Every CLI command decides its own behavior. Loses because users learn
five inconsistent behaviors, and the bug surface multiplies.

### Alt 5: Hash-locked file (refuse on drift, require explicit `--force`)

Surfaces conflicts loudly but doesn't help the user resolve them.
A worse UX than proposal sidecars — the user has to choose between
losing their edits and losing the kit's update without a third path.

## Revisions

- **2026-05-16** — Step 6 extended for managed-region resolves
  (retro-review #F-B1). The 2026-05-15 wording only re-baselined the
  page-level lookup (`PageWriteEvent`), which left
  `safe_write_region`'s region-scoped lookup (`ManagedRegionWriteEvent`)
  pointing at the pre-drift hash — so every follow-up region write
  re-proposed in an infinite loop. `resolve_proposal` now also emits
  one `ManagedRegionWriteEvent` per region ever recorded for the
  resolved file, with the hash of that region's body in the merged
  content. Paired fix in `doctor.check_managed_region_drift` skips
  files with an outstanding `page.proposal` so a single drifted region
  no longer surfaces as both `managed-region-drift` and
  `pending-proposal` (retro-review #B6).
- **2026-05-15** — Step 6 (conflict resolution) tightened during the
  Task 5 implementation. Original wording said the merged content was
  "written via `safe_write` again (which now matches because the user
  just saw it)", but neither plausible flow (skill writes the merge
  first, or `safe_write` is called first) actually produces a matching
  baseline — the journaled hash is still the kit's pre-drift version,
  so `safe_write` would loop and emit another proposal. Revised flow
  names `write_helper.resolve_proposal` as the documented `safe_write`
  bypass and splits the resolution into one `PageWrite` (re-establishes
  the baseline) plus one `PageConflictResolved` (audit). No change to
  the overall decision, event-class shapes, or any other step.

## References

- [Three-way merge](https://en.wikipedia.org/wiki/Merge_(version_control)#Three-way_merge)
  — the conceptual model the proposal flow approximates via Claude.
- ADR-0002 (journal) — `PageWrite`, `PageProposal`,
  `PageConflictResolved` event types.
- ADR-0003 (managed regions) — shares this proposal path for managed
  shared files.
- Migration RFC `docs/rfc/0001-v2-architecture.md` (Task 5)
