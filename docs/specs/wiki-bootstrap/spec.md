# Spec: wiki-bootstrap

> **Living document.** Updated alongside the code. Drift between spec
> and code is a bug — fix the code or the spec in the same PR.

- **Status:** Draft
- **Owner:** `core/files/skills/wiki-bootstrap/SKILL.md` (vault-side
  skill, copied into every new vault by `wiki init`); `core/files/AGENTS.md`
  (the vault contract that surfaces the skill on first read).
- **Related:** `docs/specs/outcome-named-entry-points/spec.md` (the
  `wiki outcomes` table and verb-trigger fragments the wizard surfaces);
  `core/files/skills/wiki-doctor/SKILL.md`,
  `core/files/skills/wiki-conflict/SKILL.md`,
  `core/files/skills/wiki-agent/SKILL.md` (tone, length, and structural
  references for vault-side conversational skills);
  `docs/CHARTER.md` §Mission and Principle 5 ("library-not-application"
  — the tension this spec names directly).
- **Constrained by:** Charter Principle 3 (no new runtime dependency);
  Charter Principle 5 (library-not-application — the wizard is markdown
  Claude reads, not new Python control flow); ADR-0001 (SKILL.md is
  byte-for-byte copied — no Jinja, no `format_map`); ADR-0002 (no new
  journal-event types — uses existing `ConfigSetEvent`); ADR-0004
  (every kit write through `safe_write`); AGENTS.md §"Two scopes, one
  repo" (vault-side only — nothing under `llm_wiki_kit/` changes).

## What this is

`wiki-bootstrap` is a vault-side SKILL that runs *inside Claude Code*
after the user runs `wiki init`, closes the gap between "the vault
exists on disk" and "the user has done one useful thing with it." It
is a conversational entry-point: Claude reads the SKILL, walks the
user through the verb table the kit just installed, demos one outcome
end-to-end against the empty vault, optionally captures owner-shaped
identity into the recipe's seed page when the recipe ships one, and
marks the vault bootstrapped so the wizard self-suppresses on later
opens. The skill is **not** a CLI command, **not** a new kit module,
and **not** a templated wizard — it is markdown text Claude reads
plus journal reads against existing event types.

This spec does **not** change `wiki init`, the recipe loader, or any
Python module under `llm_wiki_kit/`. It adds one new SKILL directory
under `core/files/skills/wiki-bootstrap/`, one bullet to
`core/files/AGENTS.md`'s skill list, and one new trigger eval. Nothing
about the existing vault layout, the journal schema, or the CLI
surface changes.

### Tension to name

Charter Principle 5 (library-not-application) says: *Claude is the
application; the kit is the library Claude calls. We don't try to be
the agent, the orchestrator, or the model.* A first-run wizard is
application-shaped — wizards are how applications onboard users.

The resolution this spec proposes — and a precedent the kit has
already set — is that **a SKILL.md authored as prose and read by
Claude is not an application layer**. It is one of the kit's library
artifacts: declarative text the kit ships, interpreted by the agent
that already owns the conversation. Three observations make this
clear:

1. **Every other vault-side SKILL is conversational.** `wiki-conflict`
   walks the user through a three-way merge. `wiki-doctor` triages
   categories with the user. `wiki-agent` walks the user through agent
   selection. The kit already ships conversational SKILLs as a routine
   pattern; the agent runs them, not the kit. `wiki-bootstrap` adds
   one more SKILL to the same shape — no new pattern, no new layer.
2. **The kit's Python writes nothing for this skill.** The SKILL is
   pure markdown. The kit's code under `llm_wiki_kit/` does not gain
   a `bootstrap` module, a `Wizard` class, or a `wiki bootstrap` CLI
   verb. The library boundary is unchanged.
3. **Outcome-named entry points already opened this door.** The
   shipped `outcome-named-entry-points` spec exposes verbs via three
   surfaces (CLI alias, slash stub, NL trigger fragment) — all
   declarative metadata + mechanical routers. `wiki-bootstrap` is
   strictly downstream of that: the wizard's job is to surface the
   verbs the user already has.

The tension is real, but the line holds: the kit ships text; Claude
interprets it; the kit gains no presentation layer. If the wizard
needed Python orchestration — interactive TUIs, multi-step state
machines, branching wizards — that *would* breach Principle 5. This
spec rejects that shape (see §Non-goals).

### What the wizard *does* — the four candidates

The brief names four candidates for what the wizard could do. This
spec ships the minimum of two and defers two with explicit reasoning.

- **(a) Ask the user about their domain and pre-populate seed pages**
  — *deferred*. Domain Q&A → page generation is exactly what the
  kit's existing ingest path already does (the user drops or pastes
  source material; the ingester writes a typed page). A wizard that
  generates pages from a chat conversation is a parallel ingest path
  with no ingester contract behind it, and it puts the wizard on the
  wrong side of Principle 5 (now the SKILL is doing what ingesters
  exist to do). The wizard *points at* `wiki ingest` as the next step
  instead.
- **(b) Walk the installed outcome verbs and demo one** — *picked
  (primary value delivery)*. This is the single move that closes the
  README:38-73 gap: the user sees the verb table the kit installed
  for their recipe and runs one verb against their empty vault. Even
  with no content, demoing `wiki digest` produces a coherent "no
  meetings yet — here is where they will land" output that teaches
  the loop without requiring the user to have ingested anything yet.
- **(c) Personalize AGENTS.md or CORE.md** — *deferred*. AGENTS.md
  and CORE.md are kit-rendered files with managed regions; editing
  them puts the user on the wrong side of every drift-detection PR
  the kit ships. Owner-shaped identity belongs in the recipe's
  identity-shaped seed page (today: `identity.md` in `personal`).
  The wizard offers to fill that page when the recipe ships one and
  otherwise skips personalization.
- **(d) Just show what's available** — *deferred (subsumed by (b))*.
  This is a strict subset of (b) — listing verbs without demoing one
  is what `wiki outcomes` already does. The wizard's value over
  `wiki outcomes` is the *walk-through*, not the listing.

The MVP is **(b) + a thin sliver of (c)** — verb walk-through, demo
one, optionally personalize the recipe's identity-shaped seed page if
one is installed. No domain Q&A, no AGENTS.md edits, no multi-step
state machine.

## Inputs

The skill reads — never writes from — the following.

### 1. Recipe shape

The wizard determines what to walk by reading:

- `.wiki.journal/journal.jsonl` — for the `VaultInitEvent.recipe`
  field (`personal` | `family` | `work-os`), the installed primitive
  set (`PrimitiveInstallEvent` rows), and the bootstrap-completion
  marker (see §Self-suppression).
- `wiki outcomes` — the installed verb table (already a shipped
  read-only command per `docs/specs/outcome-named-entry-points/`).
- `identity.md` at vault root (when present) — the recipe's owner
  seed page. Today only `personal` ships this; `family` and `work-os`
  do not. The wizard's personalization branch is conditional on the
  file's presence at vault root, not on the recipe name.

### 2. Trigger surfaces

The skill is reachable three ways. **All three are equivalent — they
load the same SKILL.md and run the same flow.** None is a "primary"
surface; the multiplicity is the discovery contract.

1. **Natural-language trigger via SKILL description**. The SKILL.md
   frontmatter `description:` field contains the verb-trigger
   fragments below as whole-word phrases (the same shape as
   `outcome-named-entry-points` §Inputs §3 enforces for operation
   SKILLs). Required phrases:
   - "I just made a new vault"
   - "help me get started"
   - "first time using this vault"
   - "what should I do first"
   - "walk me through this vault"
2. **Explicit user invocation**: "Run the wiki-bootstrap skill" /
   "Load `skills/wiki-bootstrap/`". Loads the SKILL by name.
3. **AGENTS.md mention**. The vault-side `core/files/AGENTS.md`
   "Available skills" section gains a `wiki-bootstrap` entry with a
   *"Load this first if you haven't bootstrapped this vault yet."*
   line. Claude reading AGENTS.md on first vault open sees the
   pointer; the SKILL's own self-suppression check (§Self-suppression)
   prevents reload-noise on later opens.

### 3. Self-suppression marker

The skill is one-shot per vault. The marker is a `ConfigSetEvent`
(existing event type — no new event type per Constraint 6) with:

| Field | Value |
|---|---|
| `type` | `"config.set"` |
| `key` | `"bootstrap.completed_at"` |
| `value` | ISO-8601 UTC timestamp, e.g. `"2026-05-25T14:23:11Z"` |
| `by` | `"wiki-bootstrap"` |

At skill-load time, the wizard reads `.wiki.journal/journal.jsonl`
(via `wiki journal grep --type config.set` or by direct file read —
both are read-only against the journal) and looks for any line
matching `key="bootstrap.completed_at"`. If present, the wizard
short-circuits to the idempotent re-run path (§Behavior, "Re-run
after completion"). If absent, the wizard runs the wizard flow.

## Outputs

For each first-run invocation, the wizard produces:

### 1. A conversational transcript

The user sees a four-section conversation (see §Three worked
examples for transcripts per recipe). The structure is fixed:

1. **Greeting + recipe summary** — names the recipe, names the
   primitive count installed, points at the journal as the
   source-of-truth.
2. **Verb walk-through** — runs `wiki outcomes` (or reads the
   installed-verb set directly), reads the verbs aloud with a
   one-line gloss per verb, asks which one to demo.
3. **Live demo of one verb** — runs the selected verb (or
   `--help` against it if the demo would write to disk and the
   user declines). Explains the empty-vault output and what the
   next ingest step would look like.
4. **Optional identity personalization** — if `identity.md` is
   present at vault root, offers to fill in owner name / role /
   timezone. If the user accepts, the wizard edits the page via
   Claude's `Edit` tool (the user owns the page after init; drift
   is expected and resolved through the normal `wiki-conflict`
   path on the next kit upgrade — see §Edge cases).

### 2. One `ConfigSetEvent` journal line

At the end of the conversation, the wizard appends one
`ConfigSetEvent` (the marker in §Inputs §3). The append path is the
existing `wiki journal append config.set bootstrap.completed_at
<ISO timestamp>` CLI surface — the same surface `wiki-doctor`'s
spec references for `wiki journal append page.delete`.

**Dependency note.** `wiki journal append` is a Phase D/E CLI
surface flagged as not-yet-shipped in `core/files/skills/wiki-doctor/SKILL.md`
and `core/files/skills/wiki-conflict/SKILL.md`. The implementation
PR for `wiki-bootstrap` is therefore blocked on `wiki journal
append config.set` shipping first (or in the same release). Until
then, the wizard's marker step degrades to a clear failure message:
*"`wiki journal append` is not yet available; the wizard will run
again next time."* — i.e. the wizard remains idempotent in the
not-yet-shipped state by failing-closed on the marker.

### 3. Optional `identity.md` edit (personal recipe only at v1)

If the user accepts personalization and the recipe ships `identity.md`,
the wizard edits the file in place via Claude's `Edit` tool. The
edit is *user-confirmed* line-by-line (Claude proposes the diff,
the user accepts). The kit's existing drift detection picks this
up on the next `wiki upgrade` — if the user re-renders the recipe,
the kit's proposed identity content lands as `.proposed`, and the
user resolves via `wiki-conflict`. This is the standard
ADR-0004 flow — no new mechanism, no bypass of `safe_write`.

## Behavior

### Happy path — first invocation

1. User runs `wiki init my-vault --recipe personal` and opens Claude
   Code at the vault root.
2. Claude reads `AGENTS.md`, sees the `wiki-bootstrap` "load this
   first" pointer, and loads `skills/wiki-bootstrap/SKILL.md`.
3. (Alternative entry: the user types "I just made a new vault,
   help me get started." The NL trigger phrase fires; the SKILL
   description matches; Claude loads the SKILL.)
4. The SKILL instructs Claude to:
   - Read `.wiki.journal/journal.jsonl` and search for
     `key="bootstrap.completed_at"`. Not found → continue.
   - Read `VaultInitEvent` to learn the recipe name.
   - Run `wiki outcomes` to read the installed verb table.
   - Greet the user, name the recipe, summarize what was installed
     (two sentences max).
5. The wizard walks the verb table:
   - One line per verb (verb name, one-line gloss from the
     operation contract's `description:`).
   - Asks: *"Which would you like to try first?"*
6. User picks a verb. The wizard runs it against the (empty) vault:
   - If the verb writes to disk and the user has not yet ingested
     anything, the wizard runs `wiki <verb> --help` to demo the
     surface, plus explains the would-be output by referencing the
     operation contract's `outputs:` field.
   - If the user has already ingested content (rare on day 1 but
     possible), the wizard runs the verb live.
7. The wizard offers personalization:
   - If `identity.md` exists, asks: *"Want to fill in your name,
     role, and timezone now? It takes 30 seconds and lives in
     `identity.md`."*
   - User answers. If yes, wizard collects three fields, proposes
     the diff against `identity.md`, user confirms, wizard writes
     via `Edit`.
   - If no, wizard moves on.
8. The wizard ends with:
   - Next-step pointer: *"Drop a source under `raw/`, then say
     'ingest the file under raw/'. The `ingest` skill takes it from
     there."*
   - One-line `wiki doctor` reminder: *"Run `wiki doctor` any time
     you want to sanity-check the vault."*
   - The marker append: `wiki journal append config.set
     bootstrap.completed_at <ISO-8601 UTC timestamp>`.
9. The user sees a closing line: *"This vault is bootstrapped. Have
   fun."*

### Re-run after completion (idempotent)

If the user invokes the skill (by any of the three trigger surfaces)
after `bootstrap.completed_at` is set:

1. The SKILL reads the journal, finds the marker.
2. The wizard prints exactly one short paragraph (≤ 60 words):

   > *This vault was bootstrapped on `<date>`. Run `wiki outcomes`
   > to see your verb table, or edit `identity.md` to update your
   > personalization. To re-demo a verb, just run it
   > (e.g. `wiki digest`).*

3. The wizard exits. No writes. No re-personalization. No new
   journal lines.

This is the **idempotent no-op** path. Per the brief, the choice
between *error*, *no-op*, and *re-personalize* is no-op — error is
hostile, re-personalize is destructive of user edits.

### Edge case — `wiki outcomes` returns no verbs

A recipe that ships no operations with declared outcome verbs (none
ship today — every shipped recipe installs `weekly-digest`/`digest`
at minimum — but the case is structurally possible if a future
recipe lands without operations). The wizard's verb walk-through
degrades:

1. The wizard prints: *"Your recipe doesn't ship operation verbs.
   Bootstrap will skip the demo step. The capture loop (ingest) is
   still the place to start — drop a source under `raw/`."*
2. The wizard skips to identity personalization, then to the
   marker write.

The flow still terminates with a marker, so re-runs short-circuit
as usual.

### Edge case — `identity.md` is missing or already personalized

The wizard reads `identity.md` (when present). Two sub-cases:

- **Missing**: the recipe does not ship identity (today: `family`,
  `work-os`). The wizard skips personalization without comment.
- **Already personalized**: the recipe shipped `identity.md` but
  the user (or a previous bootstrap-aborted-mid-flight) already
  filled in non-empty values. The wizard detects this by reading
  the file and checking whether any of `owner_name`, `owner_role`,
  `owner_timezone` lines contain non-empty values. If yes, the
  wizard prints *"Your identity page is already filled in. Skipping
  personalization."* and moves on.

The wizard never overwrites non-empty identity fields without
explicit user confirmation, and the spec forbids a bulk re-prompt
flow (see §Constraints, "No re-personalization on re-run").

### Edge case — user aborts mid-flow

The user closes Claude Code halfway through the wizard, or types
"stop" / "never mind." The wizard:

1. Does **not** append the `bootstrap.completed_at` marker.
2. Leaves any in-progress identity edit on disk as-is (Claude's
   `Edit` is per-line transactional; partial edits are coherent
   markdown, not corrupt files).
3. Next invocation re-runs the wizard from the top (because the
   marker isn't set). The wizard re-detects an already-personalized
   identity page and skips that section.

There is no resume token. Per Constraint 5 ("no multi-step state
machine"), the wizard restarts cleanly each time.

### Edge case — verb declared but skill load fails during demo

The wizard tries to demo a verb whose operation primitive is
shipped but whose contract is malformed (a primitive-author-time
failure that should not reach users — but a real vault on a bad
catalog version could see it). The wizard:

1. Catches the error message verbatim (`WikiError: ...`).
2. Surfaces the error to the user.
3. Suggests `wiki doctor`.
4. **Does not** append the marker — the wizard's job is not done.

### Edge case — `wiki journal append` not yet shipped

Per §Outputs §2, `wiki journal append config.set` is a dependency.
If it exits with `not yet implemented`:

1. The wizard prints: *"The marker step needs `wiki journal append`,
   which isn't shipped in your kit version. The wizard will run
   again next time — that's expected for v2.0.0.dev."*
2. The wizard does **not** retry. No marker is written.
3. Next invocation re-runs the wizard from the top (idempotent by
   absence).

This is the only documented failure mode where the user-visible
behavior is "the wizard ran but the marker wasn't recorded." The
spec accepts it; tighter coupling to `wiki journal append`'s ship
date would block this PR for no clear gain.

### Error case — journal is corrupt or missing

The wizard reads the journal directly. If the journal file is
missing or unreadable:

1. Wizard prints: *"I can't read this vault's journal. Run `wiki
   doctor` first — the wizard needs the journal to know what was
   installed."*
2. Wizard exits with no writes.

This is the same posture as every other vault-side SKILL: the
journal is the source of truth; no journal, no operation.

## Invariants

These must hold before, during, and after every invocation:

1. **The kit's Python is unchanged.** Nothing under `llm_wiki_kit/`
   is added, modified, or imported by this spec. The wizard is
   pure markdown + journal reads + shell-out to existing CLI verbs.
2. **The journal grows by at most one event per successful run.**
   The wizard appends exactly one `ConfigSetEvent` on a
   complete-with-marker run, zero on any aborted or failed run.
3. **No new event type.** `ConfigSetEvent` already exists in
   `llm_wiki_kit/models.py:572`. The wizard uses it as-is.
4. **No silent overwrite of user content.** Identity personalization
   is offered, not assumed; the user confirms each diff. Any later
   kit re-render of `identity.md` lands as `.proposed` via the
   existing drift-detection path.
5. **The wizard is one-shot.** Once the marker is set, the wizard
   short-circuits to the idempotent no-op message. The marker is
   the only state the wizard maintains.
6. **The wizard's content matches the installed catalog.** The
   verb table the wizard reads aloud is whatever `wiki outcomes`
   returns at the time of the call. The wizard never hard-codes a
   verb list — it derives from the installed primitives.
7. **No `safe_write` bypass.** Identity edits go through Claude's
   `Edit` tool against a user-owned page; the marker is appended
   through the existing `wiki journal append` surface. The kit's
   `safe_write` contract is unchanged.
8. **Vault-side only.** The skill ships under
   `core/files/skills/wiki-bootstrap/` and is copied into every new
   vault by `wiki init` via the existing core-file copy path. No
   kit-side `.claude/skills/` entry, no kit-side subagent.

## Contracts with other modules

| Caller | What it calls | What changes |
|---|---|---|
| Claude (vault-side) reading `AGENTS.md` | Loads `skills/wiki-bootstrap/SKILL.md` | New SKILL file. AGENTS.md gains one bullet under "Available skills". |
| `wiki-bootstrap` SKILL (Claude) | `wiki outcomes` | No code change — calls the shipped subcommand. |
| `wiki-bootstrap` SKILL (Claude) | Reads `.wiki.journal/journal.jsonl` | Direct file read, no kit code involved. |
| `wiki-bootstrap` SKILL (Claude) | `wiki journal append config.set bootstrap.completed_at <ts>` | **Dependency**: requires `wiki journal append` to ship. Tracked under retro-review concern C7 (issue #23) — the same gap `wiki-doctor` / `wiki-conflict` flag. |
| `wiki-bootstrap` SKILL (Claude) | `wiki <verb> --help` (one of the installed outcome verbs) | No code change — uses the shipped outcome alias. |
| `wiki-bootstrap` SKILL (Claude) | Claude's `Edit` tool on `identity.md` | Direct file edit (user-owned page). The kit's drift detection observes the edit at the next `wiki upgrade`. |
| `core/files/AGENTS.md` | n/a | One bullet added under "Available skills" naming `wiki-bootstrap` with a "load this first" note. |
| Catalog-load (`primitives.py`) | n/a | No change. `wiki-bootstrap` is a core SKILL, not a primitive — it is copied into every vault by the existing `core/files/skills/` copy mechanism. |
| `wiki doctor` | n/a | No change. `wiki doctor` already validates the journal; it does not need a `wiki-bootstrap`-shaped check. |
| Eval suite | `tests/evals/trigger/test_wiki_bootstrap_trigger.py` (new) | One new trigger eval, parametrized over the three shipped recipes and the five trigger phrases. |

## Acceptance criteria

These translate directly into tests. A reviewer should be able to
read this list and write the test file from it without re-reading
the rest of the spec.

- [ ] **SKILL file exists and is well-formed.** `core/files/skills/wiki-bootstrap/SKILL.md`
  has YAML frontmatter with `name: wiki-bootstrap`, a `description:`
  string, and `license: MIT`. The description contains every
  required trigger phrase listed in §Inputs §2 as a whole-word
  substring. Unit test against the file.
- [ ] **AGENTS.md surfaces the skill.** `core/files/AGENTS.md`'s
  "Available skills" section contains a bullet naming
  `wiki-bootstrap` with the literal phrase "load this first" (or
  equivalent — pinned in the test). Unit test against the file.
- [ ] **SKILL is copied into a vault by `wiki init`.** After
  `wiki init <tmpdir> --recipe personal`, `<tmpdir>/skills/wiki-bootstrap/SKILL.md`
  is present and byte-equal to `core/files/skills/wiki-bootstrap/SKILL.md`.
  Integration test.
- [ ] **Trigger eval — fresh vault, NL prompt loads the SKILL.**
  For each shipped recipe (`personal`, `family`, `work-os`) and
  each canonical trigger phrase (see §Inputs §2, five phrases),
  drive Claude Code via subprocess against a freshly-initialized
  fixture vault. Assert `wiki-bootstrap/SKILL.md` is the first
  vault-side SKILL Claude reads. Parametrized eval test under
  `tests/evals/trigger/test_wiki_bootstrap_trigger.py`. Canonical
  prompt set:
  - `"I just made a new vault, help me get started."`
  - `"This is my first time using this vault — what should I do?"`
  - `"Walk me through this vault."`
  - `"What should I do first in this vault?"`
  - `"Help me get started with this wiki."`
- [ ] **Marker write — happy path.** A scripted evalkit run that
  drives Claude through the wizard end-to-end against a fresh
  fixture vault produces exactly one `config.set` journal line
  with `key="bootstrap.completed_at"` and a parseable ISO-8601 UTC
  timestamp value. Integration test against the journal post-run.
- [ ] **Idempotent re-run.** After the marker is appended, a
  second invocation (same vault, same trigger phrase) produces
  the short no-op message (≤ 60 words), appends **zero** journal
  lines, and writes **zero** files. Integration test asserting on
  journal byte-stability + transcript shape.
- [ ] **Re-run after partial completion.** A run aborted before
  the marker (simulated by killing the eval subprocess after the
  verb-demo step) leaves the journal at the pre-run length. The
  next invocation re-runs the wizard from the top. Integration
  test.
- [ ] **No-verbs degradation.** Against a synthetic recipe with
  zero outcome verbs (a test-only fixture), the wizard skips the
  verb walk-through, runs identity (if present), and writes the
  marker. Integration test.
- [ ] **Identity personalization — opt-in only.** A scripted run
  where the user declines personalization leaves `identity.md`
  byte-stable. Integration test against the file's hash pre/post.
- [ ] **Identity personalization — already-filled detection.**
  Against a `personal` vault where the user pre-filled
  `owner_name` in `identity.md` before bootstrap, the wizard
  detects the existing value and skips re-prompting (per
  §Edge cases). Integration test.
- [ ] **Drift after personalization.** After the wizard edits
  `identity.md`, running `wiki upgrade --force-render` produces
  `identity.md.proposed` (the kit's re-rendered version), not a
  silent overwrite. Integration test confirming the existing
  drift-detection path.
- [ ] **`wiki journal append` unavailable — graceful degrade.**
  A scripted run against a kit version where
  `wiki journal append config.set` exits with
  `not yet implemented` produces the documented degrade message
  and **does not** append a marker. Integration test using a stub
  CLI that returns the expected stderr. (May be marked `xfail`
  until `wiki journal append` ships; the test pins the contract
  either way.)
- [ ] **Tone and length.** The wizard's transcript is ≤ 80 lines
  for the happy path against a fresh `personal` vault and ≤ 60
  words for the no-op re-run. Integration test asserting on
  recorded transcript length.

## Three concrete worked examples, one per recipe

### Personal — `wiki init my-vault --recipe personal`

**User**: I just made a new vault, help me get started.

**Claude** (loads `skills/wiki-bootstrap/SKILL.md`, reads journal):

> You're in a fresh `personal` vault with 16 primitives installed —
> meetings, people, decisions, food, trips, and a weekly digest
> wired up. The journal at `.wiki.journal/journal.jsonl` is the
> kit's source of truth; everything you and I do here is recorded
> there.
>
> Your installed outcome verbs (run `wiki outcomes` any time):
>
> - `digest` — summarize the week's activity across the vault.
> - `plan-meals` — produce a weekly meal plan with shopping list.
>
> Want to try one? `digest` is the safe demo — it runs against
> whatever you've ingested so far, which on day one is nothing,
> so the output is the empty-week shape.

**User**: yes, try digest.

**Claude**: *(runs `wiki digest --window 2026-W21`)*

> Output went to `outputs/digests/2026-W21.md`. It's mostly empty
> headers right now — *"No meetings this week. No decisions this
> week."* — but that's how it's supposed to look on day one. When
> you ingest meeting notes (drop one under `raw/` and say "ingest
> the file under raw/"), they'll land in `wiki/meetings/`, and
> next time you run `digest`, the empty headers fill in.
>
> Want to set up your identity page? It takes 30 seconds and
> lives at `identity.md` — name, role, timezone. The kit uses
> none of it directly, but it's where Claude looks first when an
> operation needs to know who you are.

**User**: sure — Eugene, software engineer, America/Los_Angeles.

**Claude**: *(edits `identity.md`)*

> Done. I'll wrap up by marking this vault bootstrapped so the
> wizard doesn't run again next time.

*(runs `wiki journal append config.set bootstrap.completed_at 2026-05-25T14:23:11Z`)*

> This vault is bootstrapped. Drop a source under `raw/` and say
> "ingest this" whenever you're ready. `wiki doctor` is the health
> check; load `skills/wiki-conflict/` if a `.proposed` ever shows
> up.

### Family — `wiki init our-vault --recipe family`

**User**: this is my first time using this vault — what should I do?

**Claude**:

> You're in a fresh `family` vault: 20 primitives installed
> covering people, meals, medical records, trips, vendors, and
> the household operations that read across them. The journal
> records every state-changing action.
>
> Your installed outcome verbs:
>
> - `digest` — weekly digest across the household.
> - `plan-meals` — meal plan + shopping list for the coming week.
>
> Want to try one? `plan-meals` is the family-shape demo — it
> reads your `wiki/food/recipes/` and proposes a week, even when
> you have very few recipes yet.

**User**: plan-meals please.

**Claude**: *(runs `wiki plan-meals --window 2026-W22 --help`)*

> The contract takes a `--window` (an ISO week like `2026-W22`)
> and an optional `--theme` (e.g. `"easy weeknight"`). Against an
> empty `wiki/food/recipes/`, the operation will tell you it has
> nothing to propose — which is the right signal to ingest a few
> recipes first (drop a recipe paste or URL under `raw/` and say
> "ingest this").
>
> The `family` recipe doesn't ship an `identity.md` seed page —
> household identity is per-person, and personalization comes
> later when you add people-shaped content. So I'll skip that
> step.
>
> Marking the vault bootstrapped.

*(runs `wiki journal append config.set bootstrap.completed_at 2026-05-25T15:11:02Z`)*

> Done. The capture loop starts with ingest: paste or drop a
> recipe / meeting / receipt / medical note under `raw/`, then
> tell me to ingest it. `wiki doctor` is the health check.

### Work-OS — `wiki init work-vault --recipe work-os`

**User**: walk me through this vault.

**Claude**:

> You're in a fresh `work-os` vault: 23 primitives covering
> stakeholders, customers, projects, decisions, vendor contracts,
> and the recurring operations that read across them. The journal
> at `.wiki.journal/journal.jsonl` is the source of truth.
>
> Your installed outcome verbs:
>
> - `digest` *(not installed in this recipe)* — work-OS doesn't
>   ship the weekly digest; status-synthesis is the closer fit.
>   *(Claude reads `wiki outcomes` and lists only the actually-installed verbs.)*
> - `refresh-stakeholders` — re-walk the per-project stakeholder
>   map from `stakeholder-update` pages.
> - *(other work-os outcome verbs surfaced by `wiki outcomes`,
>   listed verbatim from the installed catalog.)*
>
> Want to try one? `refresh-stakeholders` against `--project pluto`
> demos the work-os shape — even with no `stakeholder-update`
> pages yet, the operation tells you what it would write.

**User**: yes.

**Claude**: *(runs `wiki refresh-stakeholders --project pluto`)*

> Output landed at `outputs/stakeholder-map/pluto.md`. It's a
> scaffold today — no updates have been ingested. The next move
> is to paste or drop a Slack update / email / one-on-one note
> under `raw/` and say "ingest this as a stakeholder update."
>
> `work-os` doesn't ship `identity.md`. Skipping personalization.
>
> Marking the vault bootstrapped.

*(runs `wiki journal append config.set bootstrap.completed_at 2026-05-25T16:02:44Z`)*

> Done. Drop a stakeholder update, a customer-feedback note, or a
> vendor contract under `raw/` whenever you're ready. `wiki doctor`
> for the health check.

---

These transcripts are illustrative; the SKILL.md authors the
exact prose. The eval (Acceptance Criteria) pins the trigger and
the marker write, not the transcript wording — see §Constraints,
"No wording assertions in evals."

## Non-goals

Explicit non-goals — listed so a future PR doesn't drift into
them:

1. **Domain Q&A → seed-page generation.** Asking the user about
   their work / household / hobbies and writing wiki pages from
   the conversation. The kit already ships `wiki ingest` as the
   contract for source → page; the wizard points at it rather
   than parallelizing it. Reconsidered in a future spec only if
   the ingest path proves inadequate for the cold-start gap.
2. **Personalizing AGENTS.md or CORE.md.** Both are kit-rendered
   contract files with managed regions. Owner identity lives in
   the recipe's identity-shaped seed page (`identity.md` today).
3. **A `wiki bootstrap` CLI verb.** The wizard is conversation,
   not a CLI surface. Adding a CLI verb would mean the wizard
   lives in Python — exactly the Principle 5 breach this spec
   avoids.
4. **Multi-recipe hand-off.** *(Brief out-of-scope.)* "You
   started with `personal`, want to upgrade to `family`?" is a
   recipe-transition flow, not a bootstrap concern. Future spec
   if and when recipe-transition lands.
5. **Troubleshooting flows inside the wizard.** *(Brief
   out-of-scope.)* `wiki-doctor` and `wiki-conflict` already own
   triage and conflict resolution. The bootstrap wizard points at
   them rather than absorbing them.
6. **A clone-able starter template.** *(Brief out-of-scope.)*
   Starter content (sample meetings, sample recipes) is a
   separate concern from bootstrap; if it lands, it lands as a
   `--with-samples` flag on `wiki init`, not in the wizard.
7. **Resume-after-abort tokens.** The wizard restarts cleanly on
   re-invocation if the marker isn't set. No mid-flow state.
8. **A second journal-event type for bootstrap.** The existing
   `ConfigSetEvent` is sufficient. Per Constraint 6 of
   `outcome-named-entry-points`, no new event types.
9. **Re-personalization on re-run.** Once the marker is set, the
   wizard never re-prompts for identity. The user edits
   `identity.md` directly if they want to change it.
10. **A TUI / progress bar / interactive prompt.** The wizard is
    Claude conversation. Anything more application-shaped breaches
    Principle 5.
11. **Wording assertions in evals.** The trigger eval pins *which
    SKILL loads*, not what the SKILL says. The SKILL's text is
    authored prose that can evolve without breaking evals.

## Constraints

What implementation strategies are off the table for this spec:

1. **No new module under `llm_wiki_kit/`.** The wizard is
   markdown text + journal reads + shell-out to existing CLI
   verbs. Zero Python lines.
2. **No new runtime dependency.** Charter Principle 3. The SKILL
   uses only what Claude already has (Read, Edit, Bash for `wiki
   <verb>`).
3. **No new CLI verb.** The kit's CLI surface is unchanged. The
   wizard only invokes already-shipped verbs (`wiki outcomes`,
   `wiki <verb>`, `wiki journal append`).
4. **No new top-level directory.** The SKILL ships at
   `core/files/skills/wiki-bootstrap/`, a path that already
   exists per the established skill layout.
5. **No multi-step state machine.** The wizard is one
   conversation. No resume tokens, no checkpoints, no
   "press 1 for verb 1" branching. If the user aborts, the next
   invocation starts over.
6. **No new journal-event type.** `ConfigSetEvent` already
   exists. The marker uses it as-is.
7. **No interpolation in SKILL.md.** ADR-0001. The SKILL is a
   byte-for-byte copy from `core/files/skills/wiki-bootstrap/SKILL.md`
   into every new vault. Variables like `{vault_name}` are not
   substituted into this SKILL — the SKILL's content is recipe-
   agnostic and reads the vault's journal at run time for any
   recipe-specific information it surfaces.
8. **No bypass of `safe_write` for kit writes.** The marker
   append goes through `wiki journal append` (which uses the
   journal's existing transactional append). Identity edits go
   through Claude's `Edit` against a user-owned page.
9. **No personalization of files with managed regions.** The
   wizard never writes to `AGENTS.md`, `CORE.md`,
   `frontmatter.schema.yaml`, or any other managed-region host.
10. **No wording assertions in evals.** Per §Non-goals §11. The
    trigger eval pins *the SKILL that loads*, not the SKILL's
    prose.
11. **No kit-side `.claude/` change.** This is vault-side only.
    Repo-root `.claude/skills/`, `.claude/agents/`, and any
    kit-side artifact under `.claude/` are out of scope.
