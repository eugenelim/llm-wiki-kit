---
name: wiki-bootstrap
description: "First-run wizard for fresh vaults. Load whenever the user signals they're new to this vault — 'I just made a new vault, help me get started', 'this is my first time using this vault', 'what should I do first', 'walk me through this vault', or any onboarding-shaped phrase along those lines. The wizard reads the journal to learn the recipe, walks the installed outcome verbs from `wiki outcomes`, glosses one verb by reading its underlying skill's SKILL.md (read-only — never invokes `wiki <verb>`), and writes a one-byte sentinel at `<vault>/.wiki.bootstrap` so later sessions short-circuit to a brief no-op. Recipe-agnostic — works against `personal`, `family`, `work-os`, or any future recipe."
license: MIT
---

# wiki-bootstrap

A first-run wizard. One conversation, three sections:

1. Greet + summarize what the kit just installed.
2. Walk the outcome verbs and gloss one by reading its underlying
   skill.
3. Write a one-byte marker so the wizard self-suppresses on later
   sessions.

The wizard reads the journal, the `wiki outcomes` table, and one
operation skill's `SKILL.md`. It writes exactly one file
(`<vault>/.wiki.bootstrap`) on a successful run, and zero files
otherwise. It never appends to the journal, never edits any
kit-tracked file, and never invokes `wiki <verb>` in any mode.

## When to load this skill

Three trigger surfaces — all equivalent, all load this SKILL:

1. **Natural-language onboarding phrases.** The user signals they're
   new to this vault. Canonical phrases (this is the contract the
   eval pins; other phrases work too if they convey the same intent):
   - "I just made a new vault"
   - "help me get started"
   - "first time using this vault"
   - "what should I do first"
   - "walk me through this vault"
2. **Explicit invocation.** *"Run the wiki-bootstrap skill"* /
   *"Load `skills/wiki-bootstrap/`"*.
3. **`AGENTS.md` mention.** The vault's `AGENTS.md` lists this
   skill in "Available skills" and tells Claude to load it on any
   onboarding-shaped phrase; the SKILL itself handles the
   short-circuit when the vault is already bootstrapped, so the
   bullet is unconditional in shape.

## When NOT to load it

- The vault is already bootstrapped (the marker file exists). On a
  re-trigger, the SKILL itself short-circuits to the re-run
  paragraph — see "Re-run path" below. Loading is fine; the
  short-circuit means it costs almost nothing.
- The user is asking *how to* run a specific verb. That's the
  underlying operation skill's job (e.g. `skills/weekly-digest/`
  for `wiki digest`). Bootstrap glosses verbs; it does not teach
  them.
- The user is in a vault that isn't `wiki init`-created. The journal
  read will fail and the wizard exits — see "Failure modes."

## Step 1 — Probe the marker

Attempt to read `<vault>/.wiki.bootstrap` with the `Read` tool.

- **Read succeeds** (file exists and is readable) → marker is
  present → go to "Re-run path" below.
- **Read fails** for any reason (file missing, is a directory,
  broken symlink, symlink loop, unreadable regular file) → marker
  is absent → continue with Step 2.

The read-attempt is the entire presence check. Do not stat the
file, do not use `Bash test -f`, do not branch on file type. A
single `Read` call yields the answer.

## Step 2 — Read the recipe from the journal

`Read <vault>/.wiki.journal/journal.jsonl`. Each line is a JSON
object; find the `VaultInitEvent` (the line with
`"type": "vault.init"`). It contains the recipe name and the list
of `PrimitiveInstallEvent` rows tells you the primitive count.

**If the journal is missing or unreadable** — surface a one-line
message:

> *I can't read this vault's journal. Run `wiki doctor` first — the
> wizard needs the journal to know what was installed.*

…then stop without writing the marker.

## Step 3 — Greet the user

In two sentences:

1. Name the recipe and the primitive count.
2. Point at the journal as the kit's source of truth.

Example:

> You're in a fresh `personal` vault with 16 primitives installed —
> meetings, people, decisions, food, trips, and a weekly digest
> wired up. The journal at `.wiki.journal/journal.jsonl` is the
> kit's source of truth; every state-changing thing the kit does is
> recorded there.

## Step 4 — Walk the installed outcome verbs

Run `Bash wiki outcomes`. The output is a three-column table
(`verb`, `operation`, `skill`). Parse and retain each row's three
columns — Step 5 needs the verb → skill mapping.

- **Zero verbs returned** → surface a one-line note: *"Your recipe
  doesn't ship operation verbs. Bootstrap will skip the demo step.
  The capture loop (ingest) is still the place to start — drop a
  source under `raw/`."* Then jump to Step 6 (marker write).
- **1–8 verbs** → read each verb's name aloud, one per line, then
  ask: *"Which would you like to see in detail?"* If the user does
  not pick, default to the first verb in the table.
- **More than 8 verbs** → print the table verbatim (no per-verb
  gloss) and ask: *"Pick one by name."*

**If `wiki outcomes` exits non-zero** — surface the stderr verbatim,
suggest `wiki doctor`, and stop without writing the marker.

## Step 5 — Gloss one verb (read-only)

Once the user picks a verb (or you defaulted):

1. From the parsed `wiki outcomes` rows, map the chosen verb to its
   `skill` column value.
2. `Read <vault>/skills/<skill>/SKILL.md`.
3. Parse the YAML frontmatter `description:` field.
4. Surface a one-line gloss to the user — the first sentence of the
   description usually works; the goal is "what does this verb
   produce."

Add a follow-up sentence pointing at the cold-start move:

> On day one you don't have anything to summarize yet — the loop
> starts with ingest. Drop a source under `raw/` and say "ingest
> the file under `raw/`"; the `ingest` skill takes it from there.

**Hard rule.** Do not run `wiki <verb>`. Do not run
`wiki <verb> --help`. Do not run `wiki run <op>` for the operation
behind the verb. The demo is read-only — the only allowed read
target is `<vault>/skills/<skill>/SKILL.md`.

## Step 6 — Write the marker

Final step. Two cases:

- **No prior marker file at the path** — `Write <vault>/.wiki.bootstrap`
  with the current UTC timestamp in ISO-8601 form, one line, a
  trailing newline. Example content: `2026-05-25T14:23:11Z\n`. No
  JSON, no leading content, no multi-line body.
- **A prior marker exists** (e.g. an unreadable `0o000` file from an
  aborted earlier run) — two tool calls:
  1. `Bash rm -f <vault>/.wiki.bootstrap`
  2. `Write <vault>/.wiki.bootstrap`

**If the write fails** (filesystem error, vault root not writable,
`rm -f` denied), surface the error to the user verbatim and stop.
The next invocation re-runs the full wizard.

## Step 7 — Close the conversation

Three short lines:

> This vault is bootstrapped. Drop a source under `raw/` whenever
> you're ready; say "ingest this" and the `ingest` skill takes it
> from there. Run `wiki doctor` any time you want to sanity-check
> the vault.

Stop.

## Re-run path — marker already present

When Step 1 finds the marker, parse its ISO-8601 timestamp and
print exactly one short paragraph:

> This vault was bootstrapped on `<date from marker>`. Run `wiki
> outcomes` to see your verb table; run `wiki doctor` for a health
> check. To re-see a verb's gloss, read `skills/<skill>/SKILL.md`
> for the skill behind the verb.

If the marker exists but its contents are not a parseable ISO-8601
line, replace `<date from marker>` with `(timestamp unreadable)`
and print the rest the same way. The malformed marker is still a
marker — do **not** re-run the wizard, do **not** rewrite the file.

**Zero writes. Zero journal lines. Zero tool calls beyond `Read`
on the marker itself.** This is the idempotent no-op.

## Failure modes

- **Journal missing / unreadable** — surface the one-line "I can't
  read this vault's journal" message above; stop without writing
  the marker.
- **`wiki outcomes` exits non-zero** — surface the stderr verbatim;
  suggest `wiki doctor`; stop without writing the marker.
- **Marker write fails** — surface the filesystem error; stop. Next
  invocation re-runs.
- **User aborts mid-flow** (closes Claude Code, says "stop") — no
  marker is written; the demo step writes nothing of its own
  (Steps 1–5 are read-only). The next invocation starts over from
  Step 1.

## Why the marker is a file sentinel, not a journal line

The journal records *vault state* — what's installed, what's been
ingested, what operations have run. The marker records *SKILL
state* — whether this conversational SKILL has run its one-shot
flow. The two are different categories. The marker has exactly one
reader (this SKILL) and exactly one writer (this SKILL), so it
doesn't need to ride the shared journal projection. See
`docs/specs/wiki-bootstrap/spec.md` §Inputs §3 for the full
reasoning and the fence against future SKILLs reaching for the
same pattern without meeting the same gate.
