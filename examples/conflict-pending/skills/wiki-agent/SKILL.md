---
name: wiki-agent
description: "Help the user install, rebind, or stop using an agent — the `kind: agent` primitive that the kit passes via `claude --agent <name>` at scheduled-run time. Load this skill whenever the user names an agent (\"the household-manager\", \"who runs my weekly digest\", \"why is `--agent` missing\"), or when `wiki agents` / `wiki schedule list` / `wiki doctor` surface an agent binding the user wants to change. The kit ships eight default agents under three recipes; this skill bridges between what the user wants (\"a different voice for my Sunday digest\") and the verbs that effect it (`wiki add agent:<name>`, `wiki schedule install <op> --agent <name>`, and the v1 manual `rm -r <vault>/.claude/agents/<name>/` for removal until the dedicated `wiki remove` verb ships)."
license: MIT
---

# wiki-agent

The kit's `kind: agent` primitives are vault-side personas: each is
a markdown file at `<vault>/.claude/agents/<name>/AGENT.md` that
Claude reads when the kit invokes `claude --agent <name>` at a
scheduled or `wiki run --exec` time. The user owns *which* agent
runs *which* operation; this skill is how you help them set that.

## When to load this skill

Trigger phrases — the user named an agent or asked about identity:

- "Who runs my weekly digest?"
- "Can I have a different voice for `<operation>`?"
- "Install the `<agent-name>` agent."
- "Why does `wiki agents` show this binding?"
- "Rebind `<operation>` to `<other-agent>`."
- "What agents are available?"
- "Stop using this agent."
- "What does the `household-manager` actually do?"

Also load when the kit surfaces an agent the user might not have
known about:

- `wiki agents` output mentioning an agent the user didn't install
  deliberately (came in via the recipe).
- `wiki schedule list` showing an AGENT column the user didn't
  set with `--agent`.
- `wiki doctor` warning about a missing `AGENT.md` or a
  version-drift between an agent upgrade and the last
  `OperationRunByAgentEvent`.
- A conflict where `wiki-conflict` SKILL names an agent the user
  wants to change.

## When NOT to load it

- The user is editing operations, not agents. Operations are the
  *verbs* (`weekly-digest`, `meal-planning`); agents are the
  *who*. Edit the operation's `contract.yaml` directly.
- The user is asking about a vault-side SKILL (a `core/files/skills/<name>/SKILL.md`).
  Agents and SKILLs both shape Claude's behavior, but agents are
  per-invocation identities passed via `claude --agent`; SKILLs
  are read by Claude's own discovery from `.claude/`.
- The user is asking about kit-development subagents in the repo
  root's `.claude/agents/`. Those are for working on the kit
  itself, not for user vaults. Per AGENTS.md §"Two scopes, one
  repo," never mix.

## The mental model

Each agent is one file: `<vault>/.claude/agents/<name>/AGENT.md`.
Frontmatter declares `name`, `description`, `audience`
(`family | work-os | personal`), `role`, `tone`, and `knows:`
(vault pages the agent treats as standing context). Body is
freeform prose Claude reads at run time.

The kit reads zero bytes of `AGENT.md`. The kit's only
responsibility is:

1. Install / remove the file (via the same `PrimitiveInstallEvent`
   path as any primitive).
2. Resolve which agent runs an operation (CLI `--agent` flag →
   recipe `agents.<name>.runs:` binding → operation contract
   `preferred_agent:` → none).
3. Pass the resolved name to `claude --agent <name>` when the
   operation runs.

The agent's *behavior* is what the user's Claude session does when
it reads the file. That's a user-side concern, not a kit-side one.

## How to help

When the user wants to **see what's installed**:

```
wiki agents
```

Prints a tab-separated table with NAME / RECIPES / OPERATIONS.
Empty OPERATIONS column (`—`) means the agent ships installed
but isn't bound to an operation — `decision-companion` is the
default example.

When the user wants to **install a new agent** (one that ships
in the catalog but isn't in this recipe's closure):

```
wiki add agent:<name>
```

Runs through the same install path as any primitive. Lands the
`AGENT.md` under `<vault>/.claude/agents/<name>/AGENT.md`.

When the user wants to **rebind a scheduled operation** to a
different agent:

```
wiki schedule uninstall <operation>
wiki schedule install <operation> --agent <new-agent>
```

The journaled `ScheduleInstalledEvent.agent` field is frozen at
install time — there is no `wiki schedule rebind`. Uninstall and
reinstall is the only path. Confirm with the user before the
uninstall lands; the OS-side artifact gets dropped.

When the user wants to **try an agent ad-hoc** before binding it
to a schedule:

```
wiki run --exec <operation> --agent <name>
```

The CLI `--agent` flag wins the resolution chain — even when the
recipe binds the operation to a different agent. Use this to A/B
the voice before committing.

When the user wants to **edit an agent's voice or knowledge**:

Edit `<vault>/.claude/agents/<name>/AGENT.md` directly. The kit
ships the file but doesn't track its content — what the agent
says is yours. Do **not** edit `templates/agents/<name>/files/.claude/agents/<name>/AGENT.md`
in the kit source — that's the catalog source, not the vault
copy. (Unless the user is in fact modifying the catalog, in
which case they're a kit contributor, not a vault user.)

When the user wants to **stop using an agent**:

Delete the agent's directory from the vault:

```
rm -r <vault>/.claude/agents/<name>/
```

The kit's spec calls for a dedicated `wiki remove agent:<name>`
verb (see `docs/specs/wiki-agents/spec.md` §Edge cases) that
journals a `PrimitiveRemoveEvent`, but the verb is not in the
shipped CLI today — the manual `rm -r` is the user-side recovery
path. If a schedule still references the now-deleted agent, the
next `wiki run --exec` for that schedule will refuse to invoke
`claude` (the dispatch validation fails when the agent file
isn't present). Warn the user before they delete: they likely
want to either keep the agent or rebind the schedule first via
the `wiki schedule install --agent` flow above.

## The eight defaults

At v1 the kit ships eight agents across three recipes:

- **`family`** — `household-manager`, `trip-planner`,
  `care-coordinator`.
- **`work-os`** — `stakeholder-steward`, `renewals-watch`,
  `customer-listener`.
- **`personal`** — `personal-coordinator`, `decision-companion`
  (installed but unbound).

A user who initialized with one recipe but wants an agent from
another can always `wiki add agent:<name>` to pull it in — the
catalog is repo-wide, not recipe-scoped.

## Failure modes

- **`wiki schedule install <op> --agent <name>` refuses with
  "agent '<name>' is not installed."** The agent isn't in the
  vault. Suggest `wiki add agent:<name>` first, or check
  `wiki agents` for what's installed.
- **`wiki agents` shows an agent with `OPERATIONS=—`.** Either
  the agent is `decision-companion` (intentionally unbound) or
  the recipe binds the agent without any operations in its
  `runs:` list. The latter is a recipe-author bug; flag it.
- **`wiki doctor` warns "agent '<name>' was upgraded … since the
  last scheduled run".** The agent's `AGENT.md` may have changed
  voice. Open the file with the user, read the diff in the
  catalog source (`templates/agents/<name>/files/.claude/agents/<name>/AGENT.md`),
  and decide whether to keep the new voice or roll back via
  `wiki upgrade --to <old-version>` (out of scope at v1; today
  the user edits the vault-side `AGENT.md` directly).
- **The kit invokes `claude --agent <name>` but the user's
  `claude` CLI doesn't recognize the flag.** Older `claude`
  versions lack `--agent`. The authoritative surface for "is
  your `claude` CLI new enough" is `wiki doctor`'s schedule
  section — per ADR-0009 the kit deliberately doesn't hard-code
  a version string here. Surface `wiki doctor` if a scheduled
  run fails with a `claude` CLI error mentioning the flag.
