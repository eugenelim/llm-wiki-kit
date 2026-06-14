# Scoping a session to a workspace (the enter-workspace contract)

> **Status:** explanation (Diátaxis). This documents a *contract*, not a CLI
> verb. There is **no `wiki workspace enter` command** — scoping a session to a
> workspace lens is prompt composition over the existing `wiki run --exec`
> path. See [`docs/specs/workspace-primitive/spec.md`](../../specs/workspace-primitive/spec.md).

A [workspace](../../specs/workspace-primitive/spec.md) is a named, filtered
*lens* over a single vault: a `scope` (which notes the lens covers), a shipped
Obsidian Bases `.base` view, an optional `bootstrap` note, an optional set of
`operations`, and an optional `agent` that **references an existing** agent
primitive. "Entering" a workspace means starting a Claude session whose
attention is scoped to that lens.

## How scoping works

Entering a workspace is **prompt composition only** — it rides the headless
`claude -p` argv pinned by
[ADR-0009](../../adr/0009-headless-claude-p-invocation.md) and
[ADR-0010](../../adr/0010-agent-passthrough-via-claude-agent-flag.md), exactly
as `wiki run --exec` builds it today
(`run.py::_build_argv`; `wiki run --exec` enters via `cli.py::_cmd_run_exec`).

To scope a session to a lens, a driver (a future UI, or the user invoking
`wiki run --exec` directly) composes the **prompt body** from two pieces:

1. the workspace's `bootstrap` note, injected verbatim; and
2. the scope, expressed as a natural-language instruction — "work only with
   notes whose `workspaces:` frontmatter contains `<name>`", pointing the
   session at the lens's `.base` view.

The optional workspace `agent` is passed through the **existing** `--agent`
flag (ADR-0010). **No new flag and no new CLI verb are introduced**, and the
kit never parses `claude` stdout for semantics (ADR-0009).

## The argv

With a workspace that declares `agent: personal-coordinator`, the argv is
byte-identical in shape to what `wiki run --exec` builds — only the prompt
body carries the lens context:

```
claude -p --add-dir /vaults/my-wiki --permission-mode dontAsk --output-format json --agent personal-coordinator WORKSPACE_PROMPT
```

A workspace with no `agent` drops the `--agent <name>` pair and is otherwise
identical — the same no-agent shape ADR-0009 already pins for vaults that
declare no agent.

`WORKSPACE_PROMPT` above stands in for the composed prompt body (bootstrap +
scope). Per ADR-0009, the prompt body is **not** part of any kit contract — it
is free to evolve. What this document pins is the argv *flags*: scoping a
session to a workspace adds nothing to the argv beyond the prompt body and the
already-existing optional `--agent` pass-through.
