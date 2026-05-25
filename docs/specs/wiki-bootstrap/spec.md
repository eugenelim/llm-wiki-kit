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
  Claude reads, plus a one-byte file sentinel, no new Python control
  flow); ADR-0001 (SKILL.md is byte-for-byte copied — no Jinja, no
  `format_map`); ADR-0004 (every kit write through `safe_write` — the
  marker sentinel is not a kit write; see §Marker mechanism below);
  AGENTS.md §"Two scopes, one repo" (vault-side only — nothing under
  `llm_wiki_kit/` changes).

## What this is

`wiki-bootstrap` is a vault-side SKILL that runs *inside Claude Code*
after the user runs `wiki init`, closes the gap between "the vault
exists on disk" and "the user has done one useful thing with it." It
is a conversational entry-point: Claude reads the SKILL, walks the
user through the verb table the kit just installed, demos one outcome
verb against the empty vault via `wiki <verb> --help` (side-effect-
free, no journal events), then writes a one-byte marker file at
`.wiki.bootstrap` so the wizard self-suppresses on later opens. The
skill is **not** a CLI command, **not** a new kit module, and **not**
a templated wizard — it is markdown text Claude reads plus a single
filesystem-sentinel write.

This spec does **not** change `wiki init`, the recipe loader, or any
Python module under `llm_wiki_kit/`. It adds one new SKILL directory
under `core/files/skills/wiki-bootstrap/`, one bullet to
`core/files/AGENTS.md`'s skill list, and one new trigger eval. Nothing
about the existing vault layout, the journal schema, the CLI surface,
or `safe_write` changes.

### Tension to name

Charter Principle 5 (library-not-application) says: *Claude is the
application; the kit is the library Claude calls. We don't try to be
the agent, the orchestrator, or the model.* A first-run wizard is
application-shaped — wizards are how applications onboard users.

The resolution this spec proposes rests on **two load-bearing
properties of this SKILL specifically**:

1. **The kit's Python writes nothing for this skill.** The SKILL is
   pure markdown. The kit's code under `llm_wiki_kit/` does not gain
   a `bootstrap` module, a `Wizard` class, or a `wiki bootstrap` CLI
   verb. The library boundary is unchanged. The only write the wizard
   produces — the marker — is a one-byte file Claude's `Write` tool
   writes at vault root; the kit's Python is not in the call chain at
   all.
2. **State is one-bit-of-marker, not a multi-step state machine.**
   The wizard is one conversation. There is no resume token, no
   checkpoint, no "press 1 for verb 1" branching. Aborting mid-flow
   leaves the marker absent, so the next invocation starts over
   cleanly. This is the shape the kit's existing conversational
   SKILLs already use (load, read journal / on-disk state, walk one
   conversation, exit); the wizard is one more SKILL in that shape.

A weaker argument worth naming so it doesn't get mistaken for the
load-bearing one: **the kit already ships conversational SKILLs
triggered by observable vault events.** `wiki-conflict` (a `.proposed`
sidecar exists), `wiki-doctor` (the journal disagrees with disk),
and `wiki-agent` (the user named an agent) are the closest matches
in shape; the wider set of vault-side SKILLs today —
`wiki-conflict`, `wiki-doctor`, `wiki-agent`, `wiki-lock`,
`wiki-search`, `wiki-lint`, `wiki-research`, `ingest` — all share
the property of triggering on a *current-state* condition. The
bootstrap wizard is structurally different: it triggers on a
*temporal* condition ("vault is new") with one-shot semantics. The
precedent shows "conversational SKILLs are an established kit
pattern"; it does not show "first-run onboarding is the same
pattern." This spec leans on properties (1) and (2) above, not on
the precedent alone.

If the wizard needed Python orchestration — interactive TUIs, multi-
step state machines, branching wizards, kit-side personalization
mutations — *that* would breach Principle 5. This spec rejects those
shapes (see §Non-goals).

### What the wizard *does* — the four candidates

The brief names four candidates for what the wizard could do. This
spec ships **one** and defers three with explicit reasoning.

- **(a) Ask the user about their domain and pre-populate seed pages**
  — *deferred*. Domain Q&A → page generation is exactly what the
  kit's existing ingest path already does. A wizard that generates
  pages from a chat conversation is a parallel ingest path with no
  ingester contract behind it, and it puts the wizard on the wrong
  side of Principle 5. The wizard *points at* `wiki ingest` as the
  next step instead.
- **(b) Walk the installed outcome verbs and demo one** — *picked
  (sole value delivery in v1)*. This is the single move that closes
  the README:38-73 gap: the user sees the verb table the kit
  installed for their recipe and runs one verb-shaped command. To
  avoid first-run side effects (writing to `outputs/`, appending
  `OperationRunEvent` rows, producing empty-week artifacts), the
  demo is **always `wiki <verb> --help`** — the help text reads the
  operation's contract `description:` and surfaces what the verb
  would do, without invoking the operation. The user runs the live
  verb themselves when they're ready.
- **(c) Personalize AGENTS.md, CORE.md, or `identity.md`** —
  *deferred*. AGENTS.md and CORE.md are kit-rendered files with
  managed regions. `identity.md` is in
  `llm_wiki_kit/render.py:INTERPOLATED_FILES` and is re-rendered
  from recipe variables on every `wiki upgrade --force-render`;
  any wizard-side edit lands as `.proposed` on the next upgrade and
  hands a brand-new user a three-way conflict the same hour they
  finished bootstrap. The right shape is a kit-side `wiki config
  set <recipe-variable>` surface that journals the change and
  drives the re-render; that surface does not exist today and is
  out of scope for a vault-side SKILL. The `identity.md` file's own
  docstring already instructs "Fill them in by hand" — the wizard
  points the user there as a next step rather than mediating.
- **(d) Just show what's available** — *deferred (subsumed by (b))*.
  This is a strict subset of (b) — listing verbs without demoing one
  is what `wiki outcomes` already does. The wizard's value over
  `wiki outcomes` is the *walk-through plus the demo*.

The MVP is **(b) only**: verb walk-through + one `--help` demo +
marker write. No domain Q&A, no personalization, no file edits to
kit-rendered content.

## Inputs

The skill reads — never writes outside the marker — from the
following sources.

### 1. Recipe shape

The wizard determines what to walk by reading:

- `.wiki.journal/journal.jsonl` — for the `VaultInitEvent.recipe`
  field (`personal` | `family` | `work-os`) and the installed
  primitive set (`PrimitiveInstallEvent` rows). The wizard reads
  the journal directly (the file is plain JSONL); it never appends.
- `wiki outcomes` — the installed verb table (already a shipped
  read-only command per `docs/specs/outcome-named-entry-points/`).
  This is the **only** source of verb names the wizard surfaces.
  The wizard never hard-codes a verb list, and never names a verb
  that `wiki outcomes` does not return.

### 2. Trigger surfaces

The skill is reachable three ways. **All three are equivalent — they
load the same SKILL.md and run the same flow.** None is a "primary"
surface; the multiplicity is the discovery contract.

1. **Natural-language trigger via SKILL description**. The SKILL.md
   frontmatter `description:` field contains the verb-trigger
   fragments below as whole-word phrases (the same shape as
   `outcome-named-entry-points` §Inputs §3 enforces for operation
   SKILLs). The five canonical trigger phrases pinned by the
   acceptance criteria are:
   - "I just made a new vault"
   - "help me get started"
   - "first time using this vault"
   - "what should I do first"
   - "walk me through this vault"
2. **Explicit user invocation**: "Run the wiki-bootstrap skill" /
   "Load `skills/wiki-bootstrap/`". Loads the SKILL by name.
3. **AGENTS.md mention**. The vault-side `core/files/AGENTS.md`
   "Available skills" section gains a `wiki-bootstrap` entry. The
   bullet's text is **self-suppressing in its own prose**: the
   SKILL handles the conditional load, so the AGENTS.md bullet is
   unconditional in shape. Exact wording the AC pins (matches the
   shape of every existing bullet in that section — `- **\`name\`**
   — description.`):

   ``- **`wiki-bootstrap`** — first-run wizard for fresh vaults. Loads on any onboarding-shaped phrase; short-circuits to a brief no-op message if the vault is already bootstrapped.``

   This text tells Claude *how* the skill behaves (short-circuits
   when already done) so a re-read on session N never produces
   wizard noise. The introductory sentence in §"Available skills"
   (today: "This vault ships with seven baseline skills.") gets
   rephrased to a **count-free** form in the same PR — e.g.
   "Available baseline skills, all shipped in every vault:" —
   so future skill additions don't require touching the count.

### 3. Self-suppression marker

The skill is one-shot per vault. The marker is **a one-byte file
sentinel** at vault root:

| Property | Value |
|---|---|
| Path | `<vault>/.wiki.bootstrap` |
| Content | ISO-8601 UTC timestamp, exactly one line, e.g. `2026-05-25T14:23:11Z\n` |
| Written by | Claude's `Write` tool (the wizard's last step); preceded by `Bash rm -f` if a prior entry exists — see §Outputs §2 "Marker write against an existing file." |
| Read by | The wizard itself, via Claude's `Read` tool (read-attempt probe — see "Existence semantics" row below), on every invocation as its first step. |
| Tracked by the kit | No — not under `wiki/`, not under `.wiki.journal/`, not in `INTERPOLATED_FILES`, not a managed-region host. The kit's drift detection does not observe it. |
| Gitignored | Yes — added to the vault's `.gitignore` template (`core/files/.gitignore`) in the same PR. Per-machine SKILL scratch; a committed marker would suppress a teammate's first-run wizard the moment they cloned the vault. |
| Existence semantics | The wizard probes the marker by **attempting to read its contents** (Claude's `Read` tool, or equivalent). Success → "marker present." Any error → "marker absent" and the wizard runs the full flow. This covers, with one probe: the file is missing, is a directory, is a broken symlink, is a symlink loop (`ELOOP`), or is a regular file the running user cannot read. A symlink that resolves to a readable regular file evaluates to "marker present" (the read succeeds). Zero-byte regular files also count as "present" (the timestamp is informational, not load-bearing — see §Edge cases). The read-attempt probe is the only behavior the spec authorizes; `Path.is_file()` / `test -f` are **not** equivalent here because they return "present" for unreadable regular files, which contradicts the spec's intent. |

**Why a file sentinel, not a journal line.** The journal records
*vault state* — what's installed, what's been ingested, what
operations have run. Bootstrap-completion is *SKILL state* —
whether a vault-side conversational skill has run its one-shot flow.
The two are categorically different; the cleanest signal is a
one-bit-of-state file the SKILL owns. The journal-marker alternative
(a `ConfigSetEvent` with `key="bootstrap.completed_at"`) was
considered and rejected:

- It would require `wiki journal append config.set`, which is not
  shipped (the CLI registers only `journal {tail, grep, explain}` —
  see `llm_wiki_kit/cli.py:2756-2815`). A degraded-without-marker
  wizard runs every session forever — a quiet wedge, not a graceful
  degrade.
- It conflates kit-internal bootstrap state with user-set config
  semantics on a `ConfigSetEvent` type that has no key-namespace
  contract.
- Adding a new event type (e.g. `BootstrapCompletedEvent`) would
  cross the "no `llm_wiki_kit/` changes" line for this spec (see
  §Constraints).

The file sentinel sidesteps all three problems. It is also trivially
testable (an integration test reads `<vault>/.wiki.bootstrap`).

**Carve-out from "the journal is the truth."** Charter Principle 2
("the journal is the truth") applies to *vault state* — what pages
exist, what's installed, what operations have run. The marker is
not vault state — it is one SKILL's per-vault scratch. The
asymmetry worth naming concretely: `JournalState.pending_proposals`
*is* journal state because `check_pending_proposals` and the
related drift-walkers in `llm_wiki_kit/doctor.py` read it to
surface drift to the user — kit-side Python is the consumer. (Grep
`pending_proposals` in `llm_wiki_kit/` for the live reader set;
deliberately not citing line numbers because they rot the moment
`doctor.py` is touched.) Bootstrap-completion is read by nothing
other than `wiki-bootstrap/SKILL.md` itself; no `llm_wiki_kit/`
code, no other SKILL, no `wiki doctor` check, ever asks "has
bootstrap completed?" The gating test for "journal vs. file
sentinel" is therefore *the number of distinct file paths
containing a reader of this state*: more than one path → journal;
exactly one path, and that path is the SKILL writing the marker
→ sentinel. The file-path test is the mechanical version of "the
state is consumed by a code path the author of this SKILL does
not control"; the two formulations are equivalent in the cases
this spec contemplates, and the file-path test is easier to
audit.

This framing also explains why `JournalState.ingested_sources`
rides the journal even though its only live consumer today is the
vault-side ingest SKILL (per `docs/adr/0002` — confirmed by
`pending_proposals`-style grep over `llm_wiki_kit/`): the ingest
SKILL is a *different file* from any future SKILL that might want
to know "has this source been ingested?", and the projection in
`replay_state` is the shared surface. Bootstrap-completion has
exactly one writer file path and exactly one reader file path,
and they are the same file — which is the property that lets it
leave the journal.

**Fence against future drift.** A future SKILL author reading this
spec might reason "wiki-bootstrap got a file sentinel; I can use
one too." Two properties must hold for that to be in-bounds:
(i) one-bit-of-state (no multi-byte payload — a timestamp for
human readability is OK; structured data is not), and
(ii) **exactly one file path reads the state, and it is the same
file that writes it** (the file-path test from the carve-out
above). For property (ii), "reader path" means a tracked file in
this repo whose source text references the marker — typically
`SKILL.md` itself. Tools the SKILL invokes (`Bash`, `Read`,
`grep`) don't count; a multi-file SKILL directory counts as one
path if every reader lives in the SKILL's own directory. Any
future sentinel that fails either test goes through the journal
or through an ADR. This spec does not authorize a general
"SKILLs may write file sentinels" pattern.

**Fence is documentation-only at v1.** The two properties above
are spec-text, not a mechanical gate — no ADR codifies them, no
linter enforces them. The enforcement path is human review: a
future spec proposing a sentinel cites this one as precedent, and
a reviewer reads this paragraph and applies the test. If and when
a second SKILL proposes a sentinel, the deciding PR should open an
ADR (`docs/adr/NNNN-skill-private-file-sentinels.md`) that
codifies the two properties as a load-bearing constraint. Naming
the follow-up here so a future maintainer doesn't have to rediscover
that the fence is informal.

### 4. Demo verb selection

At demo time, the wizard:

- Reads `wiki outcomes` and lists every returned verb verbatim.
- If `wiki outcomes` returns **0 verbs**, the wizard skips the demo
  step (degraded behavior — see §Edge cases).
- If `wiki outcomes` returns **1–8 verbs**, the wizard reads each
  aloud with a one-line gloss from the operation contract's
  `description:` field, then asks the user which to demo.
- If `wiki outcomes` returns **>8 verbs**, the wizard prints the
  raw table without per-verb gloss and asks the user to pick one by
  name. The threshold (8) is editorial — picked to keep the
  walk-through readable on screen; recipes today ship 2–3 verbs,
  so the threshold is forward-looking insurance against the
  charter's "dozens of primitives" target. Adjustable in a future
  spec amendment without re-litigating the SKILL.

The wizard never executes a verb live — it always runs `wiki <verb>
--help` (see §Behavior). Live execution is the user's next step,
not the wizard's.

## Outputs

For each first-run invocation, the wizard produces:

### 1. A conversational transcript

The user sees a three-section conversation (see §Three worked
examples for transcripts per recipe). The structure is fixed:

1. **Greeting + recipe summary** — names the recipe, names the
   primitive count installed, points at the journal as the kit's
   source-of-truth.
2. **Verb walk-through + one `--help` demo** — runs `wiki outcomes`,
   reads the verb list (per the §Inputs §4 rules), asks the user
   which to demo, runs `wiki <chosen-verb> --help`, summarizes what
   the verb would do based on the help text. The demo writes zero
   files and appends zero journal events.
3. **Marker write + next-step pointer** — writes the `.wiki.bootstrap`
   sentinel, prints a one-line *"Drop a source under `raw/` and say
   'ingest this' when you're ready"* pointer, and a one-line
   `wiki doctor` reminder.

### 2. One marker file

At the end of the conversation, the wizard writes
`<vault>/.wiki.bootstrap` via Claude's `Write` tool with exactly:

```
<ISO-8601 UTC timestamp>
```

Followed by a single trailing newline. No leading content, no
multiple lines, no JSON. The simplest possible sentinel.

If the wizard cannot write the file (filesystem error, vault root
not writable), it reports the error to the user and exits without
the marker. The next invocation re-runs the wizard. This is the
only documented failure mode.

**Marker write against an existing file.** When the marker path
already holds an entry (in particular: the "Unreadable marker
triggers full wizard" AC scenario, where the read-attempt probe
failed and a full wizard ran to completion), the marker-write
step is **two tool calls**, not one:

1. `Bash rm -f <vault>/.wiki.bootstrap` — unlinks the prior entry
   regardless of its mode.
2. `Write <vault>/.wiki.bootstrap` — creates a fresh regular
   file with the timestamp.

Atomic semantics across the two calls are not required (this is
one-bit-of-state; a torn write loses at worst the timestamp
string, which is informational). If step 1 fails (EACCES on the
parent directory, EBUSY, etc.), the wizard surfaces the error
per the "cannot write the file" branch above; no marker is
written; the next invocation re-runs. The `rm`-then-`Write`
sequence ensures the new marker is owned by the running user
with default umask, regardless of the prior file's mode.

## Behavior

### Happy path — first invocation

1. User runs `wiki init my-vault --recipe personal` and opens Claude
   Code at the vault root.
2. Claude reads `AGENTS.md`, sees the `wiki-bootstrap` entry. The
   bullet's prose tells Claude to load the SKILL and that the SKILL
   itself handles the short-circuit. Claude loads
   `skills/wiki-bootstrap/SKILL.md`.
3. (Alternative entry: the user types one of the trigger phrases.
   The NL trigger fires; the SKILL description matches; Claude
   loads the SKILL.)
4. The SKILL instructs Claude to:
   - Attempt to read `<vault>/.wiki.bootstrap` per the read-attempt
     probe in §Inputs §3. Read fails (file missing, directory,
     broken symlink, symlink loop, unreadable) → marker absent →
     continue. Read succeeds → marker present → re-run path
     (§Re-run after completion).
   - Read `.wiki.journal/journal.jsonl` and find the
     `VaultInitEvent` to learn the recipe name.
   - Run `wiki outcomes` to read the installed verb table.
   - Greet the user, name the recipe, summarize what was installed
     (two sentences max).
5. The wizard walks the verb table per the §Inputs §4 rules, then
   asks: *"Which would you like to see in detail?"*
6. User picks a verb. The wizard runs `wiki <verb> --help` and
   summarizes what the verb would do, referencing the help text's
   description.
7. The wizard closes the conversation:
   - Marker write: Claude `Write`s `<vault>/.wiki.bootstrap` with
     the current UTC timestamp. (If the file already exists from a
     prior `mode 0o000` aborted run, the wizard runs `Bash rm -f
     <vault>/.wiki.bootstrap` first — see §Outputs §2.)
   - Next-step pointer: *"Drop a source under `raw/`, then say
     'ingest the file under raw/'. The `ingest` skill takes it from
     there."*
   - `wiki doctor` reminder: *"Run `wiki doctor` any time you want
     to sanity-check the vault."*
8. The user sees a closing line: *"This vault is bootstrapped. Have
   fun."*

### Re-run after completion (idempotent)

If the user invokes the skill (by any of the three trigger surfaces)
after `.wiki.bootstrap` exists:

1. The SKILL reads the marker, finds the ISO timestamp.
2. The wizard prints exactly one short paragraph:

   > *This vault was bootstrapped on `<date from marker>`. Run
   > `wiki outcomes` to see your verb table; run `wiki doctor` for a
   > health check. To re-see a verb's contract, run
   > `wiki <verb> --help` directly.*

3. The wizard exits. **Zero writes. Zero journal lines. Zero file
   changes.**

This is the **idempotent no-op** path. Per the brief, the choice
between *error*, *no-op*, and *re-personalize* is no-op — error is
hostile, re-personalize doesn't apply (no personalization in v1).

### Edge case — `wiki outcomes` returns no verbs

A recipe that ships no operations with declared outcome verbs (none
ship today — every shipped recipe installs at least one — but the
case is structurally possible if a future recipe lands without
operations). The wizard's verb walk-through degrades:

1. The wizard prints: *"Your recipe doesn't ship operation verbs.
   Bootstrap will skip the demo step. The capture loop (ingest) is
   still the place to start — drop a source under `raw/`."*
2. The wizard proceeds directly to the marker write.

The flow still terminates with a marker, so re-runs short-circuit
as usual.

### Edge case — user aborts mid-flow

The user closes Claude Code halfway through the wizard, or types
"stop" / "never mind." The wizard:

1. Does **not** write the marker.
2. Has not made any other writes (the demo is `--help`-only — no
   side effects).
3. Next invocation re-runs the wizard from the top. There is no
   resume token; restart is the policy (see Constraint 5).

### Edge case — marker exists but is malformed

The marker is supposed to contain one ISO-8601 UTC timestamp. The
wizard's presence probe is a read attempt (see §Inputs §3); a
directory, broken symlink, symlink loop, or unreadable regular
file at that path all evaluate to "absent" (the read fails) and
trigger a full wizard run. The malformed case below applies only
to *readable regular files* whose contents are not a parseable
ISO-8601 line:

1. The wizard treats the file as present (the bootstrap completed
   marker; the timestamp is informational, not load-bearing).
2. The re-run message degrades gracefully — instead of *"bootstrapped
   on `<date>`"* the wizard prints *"bootstrapped (timestamp
   unreadable)"* and otherwise behaves the same.

A malformed marker on a readable regular file is **not** a
re-bootstrap trigger. The user can delete the file by hand if they
actually want to re-bootstrap.

### Error case — journal is corrupt or missing

The wizard reads the journal directly. If the journal file is
missing or unreadable:

1. Wizard prints: *"I can't read this vault's journal. Run `wiki
   doctor` first — the wizard needs the journal to know what was
   installed."*
2. Wizard exits with no writes.

This is the same posture as every other vault-side SKILL: the
journal is the source of truth for installed state; no journal, no
operation.

### Error case — `wiki outcomes` errors

The wizard depends on `wiki outcomes` to enumerate verbs. If the
subcommand exits non-zero (for whatever reason — corrupt journal,
malformed contract, kit version mismatch):

1. Wizard surfaces the stderr verbatim.
2. Suggests `wiki doctor`.
3. Exits with no marker write.

## Invariants

These must hold before, during, and after every invocation:

1. **The kit's Python is unchanged.** Nothing under `llm_wiki_kit/`
   is added, modified, or imported by this spec. The wizard is
   pure markdown + journal reads + shell-out to existing CLI verbs
   + one filesystem write.
2. **The journal grows by zero events.** The wizard reads the
   journal; it never appends. No `ConfigSetEvent`, no new event
   type, no journal interaction beyond reads.
3. **No write outside the marker.** The wizard writes exactly one
   file (`.wiki.bootstrap`) on a successful run, and zero files on
   any aborted or failed run. No other vault file is touched.
4. **No `safe_write` bypass and no managed-region edit.** The
   wizard does not write to any file the kit tracks. `.wiki.bootstrap`
   is outside `wiki/`, outside `.wiki.journal/`, outside
   `INTERPOLATED_FILES`, and is not a managed-region host. The kit's
   write contract is unchanged.
5. **The wizard is one-shot.** Once the marker file exists, the
   wizard short-circuits to the idempotent no-op message. The marker
   is the only state the wizard maintains.
6. **The wizard's verb list matches the installed catalog.** The
   verbs the wizard reads aloud are whatever `wiki outcomes` returns
   at the time of the call. The wizard never hard-codes a verb list,
   never annotates "not installed" verbs, never names cross-recipe
   verbs.
7. **The demo is side-effect-free.** The wizard runs `wiki <verb>
   --help` only. It never runs `wiki <verb>` live. No
   `OperationRunEvent`, no `outputs/` write, no journal append.
8. **Vault-side only.** The skill ships under
   `core/files/skills/wiki-bootstrap/` and is copied into every new
   vault by `wiki init` via the existing core-file copy path. No
   kit-side `.claude/skills/` entry, no kit-side subagent, no
   kit-side CLI verb.

## Contracts with other modules

| Caller | What it calls | What changes |
|---|---|---|
| Claude (vault-side) reading `AGENTS.md` | Loads `skills/wiki-bootstrap/SKILL.md` | New SKILL file. AGENTS.md gains one bullet under "Available skills" with the self-suppressing prose pinned in §Inputs §2. |
| `wiki-bootstrap` SKILL (Claude) | `wiki outcomes` | No code change — calls the shipped subcommand. |
| `wiki-bootstrap` SKILL (Claude) | Reads `.wiki.journal/journal.jsonl` | Direct file read, no kit code involved. |
| `wiki-bootstrap` SKILL (Claude) | `wiki <verb> --help` (one of the installed outcome verbs) | No code change — uses the shipped outcome alias and its inherited `--help` from `wiki run <op> --help`. |
| `wiki-bootstrap` SKILL (Claude) | Claude's `Write` tool on `<vault>/.wiki.bootstrap` | New file at vault root, outside any kit-tracked directory. The kit's drift detection does not observe it. |
| `core/files/AGENTS.md` | n/a | One bullet added under "Available skills" naming `wiki-bootstrap`; introductory count-line rephrased to count-free form. Wording pinned in §Inputs §2. |
| `core/files/.gitignore` | n/a | One line added: `.wiki.bootstrap`. The marker is per-machine SKILL scratch, not committed state. |
| Catalog-load (`primitives.py`) | n/a | No change. `wiki-bootstrap` is a core SKILL, not a primitive — it is copied into every vault by the existing `core/files/skills/` copy mechanism. |
| `wiki doctor` | n/a | No change. `.wiki.bootstrap` lives outside any directory `wiki doctor` walks; it produces no orphan-file noise. |
| Eval suite | `tests/evals/trigger/test_wiki_bootstrap_trigger.py` (new) | One new trigger eval (see §Acceptance criteria for cardinality). |

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
  "Available skills" section contains a bullet matching the
  wording pinned in §Inputs §2 (self-suppressing prose — the
  bullet itself does not gate on bootstrap state). Unit test
  asserts a substring match on the bolded-name-plus-description
  pattern (`` **`wiki-bootstrap`** — first-run wizard for fresh
  vaults. Loads on any onboarding-shaped phrase; short-circuits to
  a brief no-op message if the vault is already bootstrapped.``);
  leading bullet prefix (`- `) and trailing whitespace are
  ignored. Same unit test asserts the introductory sentence is in
  count-free form via **two** regex assertions, both compiled with
  `re.IGNORECASE`:
  1. `\b\d+[\s\-]+baseline[\s\-]+skills?\b` — catches digit-form
     drift ("7 baseline skills", "9 baseline-Skills").
  2. `\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)[\s\-]+baseline[\s\-]+skills?\b`
     — catches word-form drift up to twenty ("seven baseline
     skills", "eight-baseline-Skills"). The bounded vocabulary
     is deliberate; a future spec author shipping the 21st
     baseline skill amends this AC alongside.

  Neither regex matching is the success condition. The earlier
  hand-picked two-substring blocklist would have let "9 baseline
  Skills" or "seven baseline-skills" slip through; the regex pair
  closes those gaps.
- [ ] **Marker gitignored in the vault template.** The vault-
  template `.gitignore` (`core/files/.gitignore`) contains a
  `.wiki.bootstrap` entry. Unit test against the file.
- [ ] **SKILL is copied into a vault by `wiki init`.** After
  `wiki init <tmpdir> --recipe personal`, `<tmpdir>/skills/wiki-bootstrap/SKILL.md`
  is present and byte-equal to `core/files/skills/wiki-bootstrap/SKILL.md`.
  Integration test.
- [ ] **Trigger eval — fresh vault, NL prompt loads the SKILL.**
  Five canonical trigger phrases (see §Inputs §2) drive Claude Code
  via subprocess against **one** freshly-initialized `personal`
  fixture vault. Each phrase asserts `wiki-bootstrap/SKILL.md` is
  the first vault-side SKILL Claude reads. Cardinality is 5
  phrases × 1 recipe = 5 cases; the SKILL is recipe-agnostic by
  Constraint 7 of `outcome-named-entry-points` (and by this spec's
  Invariant 6), so the recipe dimension contributes nothing to the
  trigger-load assertion. Parametrized eval test under
  `tests/evals/trigger/test_wiki_bootstrap_trigger.py`. Canonical
  prompt set:
  - `"I just made a new vault, help me get started."`
  - `"This is my first time using this vault — what should I do?"`
  - `"Walk me through this vault."`
  - `"What should I do first in this vault?"`
  - `"Help me get started with this wiki."`
- [ ] **Flow eval — wizard surfaces recipe-appropriate verbs.** One
  canonical phrase (`"I just made a new vault, help me get
  started."`) drives Claude against each of the three shipped recipes
  (`personal`, `family`, `work-os`). Cardinality is 1 phrase × 3
  recipes = 3 cases. Each case asserts that the transcript names at
  least one verb that `wiki outcomes` returns for that recipe, and
  names no verb that `wiki outcomes` does not return (Invariant 6).
  Same eval file.
- [ ] **Post-bootstrap no-load eval — SKILL short-circuits on
  re-run.** Against a `personal` vault where `.wiki.bootstrap`
  already exists, the same canonical trigger phrase produces a
  transcript whose first SKILL load is `wiki-bootstrap`, **and**
  Claude's response satisfies a short-circuit length bound.
  Bound definition: count non-blank `\n`-separated lines in
  Claude's final response (the model output, not the harness
  transcript); blank lines and trailing whitespace don't count;
  wrapped terminal lines count as one logical line. Bound is
  **≤ 6 non-blank lines** — tight enough to fail if the wizard
  ran the greeting + recipe summary + verb walk-through (which
  the three §Three worked examples transcripts run to 10+ lines
  by the same count), generous enough to allow a brief
  acknowledgment + the 3-line §Re-run paragraph + a closing
  line. Asserts the SKILL did load *and* did not run the full
  wizard. Cardinality is 1 phrase × 1 recipe = 1 case. Same eval
  file.
- [ ] **Marker write — happy path.** A scripted evalkit run that
  drives Claude through the wizard end-to-end against a fresh
  fixture vault produces a `<vault>/.wiki.bootstrap` file whose
  single line parses as ISO-8601 UTC. Integration test against the
  file post-run.
- [ ] **No journal writes.** A scripted happy-path run against a
  fresh fixture vault leaves the journal byte-identical to its
  state at `wiki init` completion (no new lines appended).
  Integration test against the journal hash pre/post.
- [ ] **No vault file writes outside the marker.** A scripted
  happy-path run leaves every vault file other than
  `<vault>/.wiki.bootstrap` byte-identical to its state at
  `wiki init` completion. Integration test against a vault-wide
  file-hash manifest pre/post.
- [ ] **Idempotent re-run.** After the marker is written, a second
  invocation (same vault, same trigger phrase) writes zero files and
  appends zero journal lines. Integration test asserting on file +
  journal byte-stability across the second invocation.
- [ ] **Re-run after partial completion.** A run aborted before the
  marker (simulated by killing the eval subprocess after the verb-
  demo step) leaves the journal AND the marker absent. The next
  invocation re-runs the wizard from the top. Integration test.
- [ ] **No-verbs degradation.** Against a synthetic recipe with
  zero outcome verbs (a test-only fixture), the wizard skips the
  verb walk-through and writes the marker. Integration test.
- [ ] **Demo is side-effect-free.** The wizard's demo step never
  produces an `OperationRunEvent` in the journal, never writes to
  `outputs/`, and never invokes `wiki <verb>` without `--help`.
  Integration test asserting on the journal + `outputs/` directory
  after a scripted run.
- [ ] **Malformed marker is treated as present.** Against a vault
  where `.wiki.bootstrap` exists but contains arbitrary text (not
  an ISO timestamp), the wizard short-circuits to the re-run no-op
  message and degrades the "bootstrapped on …" line to
  "bootstrapped (timestamp unreadable)". Integration test.
- [ ] **Unreadable marker triggers full wizard and gets replaced.**
  Against a vault where `.wiki.bootstrap` exists as a regular
  file with mode `0o000` (no read permission for the current
  user), the wizard runs the full flow (greeting, verb walk-
  through, demo, marker write) — not the re-run no-op path. The
  marker-write step is the two-tool-call sequence pinned in
  §Outputs §2 "Marker write against an existing file":
  `Bash rm -f <vault>/.wiki.bootstrap`, then `Write <vault>/.wiki.bootstrap`.
  The resulting file (a) is owned by the running user, (b) is at
  least user-readable (`mode & 0o400 == 0o400` — the property the
  next read-attempt probe depends on; umask-independent and
  portable), and (c) contains a parseable ISO-8601 timestamp.
  The AC asserts (a)+(b)+(c) directly; it does not assert
  `mode == 0o644` because user umask varies across machines.
  Pins the read-attempt probe (§Inputs §3) against the
  contradicting `Path.is_file()` semantic the spec explicitly
  disclaims. Integration test on POSIX; `skip`-marked on Windows
  where `chmod 000` is not meaningful. Directory / broken-
  symlink / symlink-loop variants are deliberately not separately
  tested — the read-attempt probe collapses them into one
  failure mode, and the cross-platform behavior of those cases
  is not portably asserted.

## Three concrete worked examples, one per recipe

### Personal — `wiki init my-vault --recipe personal`

**User**: I just made a new vault, help me get started.

**Claude** (loads `skills/wiki-bootstrap/SKILL.md`, checks
`.wiki.bootstrap` — absent — reads journal):

> You're in a fresh `personal` vault with 16 primitives installed —
> meetings, people, decisions, food, trips, and a weekly digest
> wired up. The journal at `.wiki.journal/journal.jsonl` is the
> kit's source of truth; every state-changing thing the kit does is
> recorded there.
>
> Your installed outcome verbs (run `wiki outcomes` any time):
>
> - `digest` — summarize the week's activity across the vault.
> - `plan-meals` — produce a weekly meal plan with shopping list.
>
> Want to see one in detail? I'll run `wiki <verb> --help` — no
> side effects, just the contract.

**User**: digest please.

**Claude**: *(runs `wiki digest --help`)*

> `wiki digest` is an alias for `wiki run weekly-digest`. It takes
> a `--window` (an ISO week like `2026-W21`) and writes a digest
> page to `outputs/digests/<window>.md` summarizing what happened
> in that window across the vault.
>
> On day one you don't have anything to summarize yet — the loop
> starts with ingest. Drop a meeting note under `raw/` and say
> "ingest the file under raw/"; the `ingest` skill takes it from
> there, the meeting lands under `wiki/meetings/`, and then
> `wiki digest` has something to read.

**Claude**: *(writes `<vault>/.wiki.bootstrap` with the current
UTC timestamp)*

> This vault is bootstrapped. Drop a source under `raw/` whenever
> you're ready. `wiki doctor` is the health check; load
> `skills/wiki-conflict/` if a `.proposed` ever shows up.

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
> Want to see one in detail?

**User**: plan-meals.

**Claude**: *(runs `wiki plan-meals --help`)*

> `wiki plan-meals` is an alias for `wiki run meal-planning`. It
> takes a `--window` (ISO week) and an optional `--theme` (e.g.
> `"easy weeknight"`), reads `wiki/food/recipes/`, and writes a
> plan to `outputs/meal-plans/<window>.md`.
>
> On day one your `wiki/food/recipes/` is empty — start by pasting
> or dropping a recipe under `raw/` and saying "ingest this
> recipe." Once you have a handful, `wiki plan-meals` has
> something to choose from.

**Claude**: *(writes `<vault>/.wiki.bootstrap`)*

> Bootstrapped. The capture loop starts with ingest: paste or drop
> a recipe / meeting / receipt / medical note under `raw/`, then
> tell me to ingest it. `wiki doctor` is the health check.

### Work-OS — `wiki init work-vault --recipe work-os`

**User**: walk me through this vault.

**Claude** (reads `wiki outcomes`, sees only work-os's installed
verbs — no `digest`):

> You're in a fresh `work-os` vault: 23 primitives covering
> stakeholders, customers, projects, decisions, vendor contracts,
> and the recurring operations that read across them. The journal
> at `.wiki.journal/journal.jsonl` is the source of truth.
>
> Your installed outcome verbs:
>
> - `refresh-stakeholders` — re-walk the per-project stakeholder
>   map from `stakeholder-update` pages.
> - *(other work-os outcome verbs that `wiki outcomes` returns,
>   listed verbatim — the wizard reads the table at run time)*
>
> Want to see one in detail?

**User**: refresh-stakeholders.

**Claude**: *(runs `wiki refresh-stakeholders --help`)*

> `wiki refresh-stakeholders` is an alias for `wiki run
> stakeholder-map-refresh`. It takes a `--project` flag and writes
> a refreshed stakeholder map to
> `outputs/stakeholder-map/<project>.md` based on the
> `stakeholder-update` pages it reads under `wiki/`.
>
> On day one you have no updates yet — drop a Slack thread, an
> email, or a 1:1 note under `raw/` and say "ingest this as a
> stakeholder update." A few of those and the next
> `refresh-stakeholders` will land a useful map.

**Claude**: *(writes `<vault>/.wiki.bootstrap`)*

> Bootstrapped. Drop a stakeholder update, a customer-feedback note,
> or a vendor contract under `raw/` whenever you're ready.
> `wiki doctor` for the health check.

---

These transcripts are illustrative; the SKILL.md authors the exact
prose. The evals (Acceptance Criteria) pin the trigger and the
marker write, not the transcript wording — see §Constraints,
"No wording assertions in evals." The recipe-specific verb list each
transcript names is *derived* from `wiki outcomes` at run time
(Invariant 6); the transcripts above show the verbs that recipe
actually installs today.

## Non-goals

Explicit non-goals — listed so a future PR doesn't drift into
them:

1. **Domain Q&A → seed-page generation.** The kit already ships
   `wiki ingest` as the contract for source → page; the wizard
   points at it rather than parallelizing it. Reconsidered in a
   future spec only if the ingest path proves inadequate for the
   cold-start gap.
2. **Personalizing AGENTS.md, CORE.md, or `identity.md`.** All
   three are kit-rendered, interpolated, or managed-region hosts.
   Owner identity belongs in a future kit-side `wiki config set
   <recipe-variable>` surface that journals the change and drives
   the re-render. Not in scope for a vault-side SKILL.
3. **A `wiki bootstrap` CLI verb.** The wizard is conversation,
   not a CLI surface. Adding a CLI verb would mean the wizard
   lives in Python — exactly the Principle 5 breach this spec
   avoids.
4. **Multi-recipe hand-off.** *(Brief out-of-scope.)* "You started
   with `personal`, want to upgrade to `family`?" is a recipe-
   transition flow, not a bootstrap concern. Future spec if and
   when recipe-transition lands.
5. **Troubleshooting flows inside the wizard.** *(Brief out-of-
   scope.)* `wiki-doctor` and `wiki-conflict` already own triage
   and conflict resolution. The bootstrap wizard points at them
   rather than absorbing them.
6. **A clone-able starter template.** *(Brief out-of-scope.)*
   Starter content (sample meetings, sample recipes) is a
   separate concern from bootstrap; if it lands, it lands as a
   `--with-samples` flag on `wiki init`, not in the wizard.
7. **Resume-after-abort tokens.** The wizard restarts cleanly on
   re-invocation if the marker isn't written. No mid-flow state.
8. **A journal event for bootstrap.** §Inputs §3 explains why the
   marker is a file sentinel, not a journal line.
9. **Live verb execution.** The wizard always demos via
   `wiki <verb> --help`. Live execution is a side-effect operation;
   the user runs it themselves when they're ready.
10. **A TUI / progress bar / interactive prompt.** The wizard is
    Claude conversation. Anything more application-shaped breaches
    Principle 5.
11. **Wording assertions in evals.** The trigger eval pins *which
    SKILL loads*, not what the SKILL says. The post-bootstrap
    no-load eval asserts a *length bound* (≤ 6 non-blank lines,
    per the AC) to verify short-circuit, which is a structural
    assertion, not a wording one. The flow eval asserts the
    wizard *names verbs from* `wiki outcomes`, not specific
    phrasings.
12. **Cross-recipe verb commentary.** The wizard reads only verbs
    `wiki outcomes` returns. It never names verbs from other
    recipes (no "work-os doesn't ship the weekly digest" prose) —
    such annotations hardcode the catalog and break Invariant 6.

## Constraints

What implementation strategies are off the table for this spec:

1. **No new module under `llm_wiki_kit/`.** The wizard is markdown
   text + journal reads + shell-out to existing CLI verbs + one
   filesystem write via Claude's `Write` tool. Zero Python lines.
2. **No new runtime dependency.** Charter Principle 3. The SKILL
   uses only what Claude already has: `Read` (journal + marker
   probe), `Write` (marker create), and `Bash` (for `wiki <verb>`
   shell-outs and `rm -f` on the marker-replacement path).
   `Edit` is not used by this SKILL.
3. **No new CLI verb.** The kit's CLI surface is unchanged. The
   wizard only invokes already-shipped verbs (`wiki outcomes`,
   `wiki <verb> --help`). It does not invoke `wiki journal append`
   (which is unshipped — see §Inputs §3 for the rejected
   alternative).
4. **No new top-level directory.** The SKILL ships at
   `core/files/skills/wiki-bootstrap/`, a path that already exists
   per the established skill layout. The marker lives at vault
   root, an existing path.
5. **No multi-step state machine.** The wizard is one
   conversation. No resume tokens, no checkpoints, no
   "press 1 for verb 1" branching. If the user aborts, the next
   invocation starts over.
6. **No journal-event interaction beyond reads.** The wizard reads
   the journal; it never appends, never proposes a new event type,
   never piggybacks on an existing event type. No `ConfigSetEvent`,
   no `BootstrapCompletedEvent`, no journal append at all.
7. **No interpolation in SKILL.md.** ADR-0001. The SKILL is a
   byte-for-byte copy from `core/files/skills/wiki-bootstrap/SKILL.md`
   into every new vault. Variables like `{vault_name}` are not
   substituted into this SKILL — the SKILL's content is recipe-
   agnostic and reads the vault's journal at run time for any
   recipe-specific information it surfaces.
8. **No `safe_write` bypass.** The marker is **not** a kit write —
   it is a SKILL-state sentinel outside any kit-tracked directory.
   The kit's `safe_write` contract is unchanged. The wizard never
   edits a file the kit tracks (no `AGENTS.md`, no `CORE.md`, no
   `identity.md`, no `wiki/` content, no `.wiki.journal/` content,
   no managed-region host).
9. **No personalization in v1.** The wizard does not collect or
   write owner-shaped data. Identity capture defers to a future
   kit-side `wiki config set` surface (see Non-goal 2).
10. **No live verb execution.** Demos are `wiki <verb> --help` only.
    See Non-goal 9.
11. **No exact-prose assertions in evals.** Per Non-goal 11.
    Structural assertions (which SKILL loaded, whether the marker
    file exists, whether the transcript is ≤ N lines, whether a
    named verb appears in the transcript) are allowed.
12. **No kit-side `.claude/` change.** This is vault-side only.
    Repo-root `.claude/skills/`, `.claude/agents/`, and any
    kit-side artifact under `.claude/` are out of scope.
