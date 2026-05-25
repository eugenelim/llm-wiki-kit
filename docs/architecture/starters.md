# Starters — projection of the kit into clone-able vaults

> **Audience.** Maintainers and contributors. For user-facing starter
> docs, see [`starters/README.md`](../../starters/README.md).

The `starters/` directory ships pre-rendered, ready-to-use Obsidian
vaults that a user can clone without installing the kit. This page
explains what they *are* (a kit-produced artifact, not a parallel
codebase), how they are produced, and the contract that keeps them
honest.

## The projection invariant

A starter under `starters/<recipe>/` — and the conflict-pending
worked example under `docs/guides/how-to/_examples/conflict-pending/`
— is **a deterministic projection of the kit**, not a fork of it.
Specifically, every committed byte in each of those trees is the
output of running the kit's renderer over:

- one of the recipes in [`recipes/`](../../recipes/)
  (`family.yaml`, `work-os.yaml`, or `personal.yaml`),
- the primitive catalog under [`templates/`](../../templates/), and
- the hand-authored seed pages under
  [`starters/_seed/<recipe>/`](../../starters/_seed/).

There is no "starter-only" template, no "starter" code path inside
`llm_wiki_kit/`, and no hand-edited file in a committed starter
vault. If a contributor wants to change what a starter contains, the
change lands on a recipe, a primitive, or a seed page — never on
the rendered output directly. The rendered output gets *re-rendered*
by [`starters/regenerate.py`](../../starters/regenerate.py).

This invariant is enforced by a CI gate:

```bash
python starters/regenerate.py --check
```

`--check` rebuilds each starter into a tmp directory and
byte-compares against the committed tree (with documented
normalization for non-deterministic JSON keys — see
[`docs/specs/task-21-examples-tutorials/spec.md`](../specs/task-21-examples-tutorials/spec.md)
§AC6). The job fails any PR that lets the committed bytes drift away
from what the kit would produce.

## Why the invariant matters

Four downstream properties fall out of it.

1. **Drift between starter and kit is mechanically impossible.** A
   starter cannot fall behind the kit because the kit *is* the
   starter's renderer. There is no second source of truth to keep
   synchronized.

2. **A starter user who installs the kit gets `wiki upgrade` for
   free.** Once a user clones `starters/work-os/` to their own
   directory and later `pip install llm-wiki-kit`s, running `wiki
   upgrade` inside the cloned vault uses the same kit machinery an
   author-built vault uses — managed regions update in place,
   new primitives get installed, user-edited files route through
   `safe_write`'s drift detection (`.proposed` sidecars, never silent
   overwrites). The starter is *not* a separate kind of vault.

3. **The library boundary in Charter Principle 5 is preserved.** A
   starter cannot drift the kit toward application-shape because the
   starter contains no logic — it is a render result. The kit
   projects vaults; vaults do not become parts of the kit. This is
   what RFC-0006 leaned on to justify a top-level distribution
   surface on a project that explicitly does not ship an
   application.

4. **A future per-starter-repo split is mechanical.** RFC-0006
   deliberately chose same-repo (the kit's repo) as the v0
   distribution channel for starters. If user feedback later shows
   that the kit-repo noise is in the way, the future
   `llm-wiki-kit-starter-*` sibling-repo split is a publish-from-CI
   step, not a new contract — the renderer and the seeds stay on
   the kit side; the published bytes are whatever
   `regenerate.py --apply` produced.

## What `regenerate.py` does

Two modes, both load-bearing for the invariant:

- **`--check`** (CI gate). Rebuilds each starter into a temporary
  directory, normalizes the journals (sentinel-replaces non-
  deterministic fields like `timestamp`, `hash`,
  `content_hash`, `source_hash`), and byte-compares against the
  committed tree. Exits 0 on clean, 1 with a unified-diff fragment on
  divergence.
- **`--apply`** (contributor command). Same build, then atomically
  swaps each tmp tree over the committed location. POSIX `rename(2)`
  does not allow a single-call replace of a non-empty directory, so
  the swap is two same-filesystem renames (`committed → backup`,
  then `staged → committed`) with rollback on the second-rename
  failure path. A double-fault preserves the backup and surfaces a
  recovery command. The contract is documented in
  `starters/regenerate.py::apply_vault`.

The build itself uses the kit's own `cli.main(["init", ...])` plus
`safe_write` for every seed page. No bypass; no special path. If
this property ever breaks, the projection invariant is dead — and
the CI gate is the alarm.

## What lives where

Three committed trees, two different parents:

| Vault                                                   | Parent                                | Recipe     | Purpose                                                            |
|---------------------------------------------------------|---------------------------------------|------------|--------------------------------------------------------------------|
| `starters/family/`                                      | `starters/`                           | `family`   | Clone-and-use family vault. First-class distribution per RFC-0006. |
| `starters/work-os/`                                     | `starters/`                           | `work-os`  | Clone-and-use professional vault. First-class distribution.        |
| `docs/guides/how-to/_examples/conflict-pending/`        | `docs/guides/how-to/_examples/`       | `personal` | Worked example for the `wiki-conflict` how-to. Not a starter.      |

The conflict-pending vault lives outside `starters/` because it
*is* documentation infrastructure, not a usable starting point — it
ships a `.proposed` sidecar and a journal carrying a
`PageProposalEvent`, so a user who cloned it would have to resolve
the conflict before doing anything else. But it is still produced by
the same `regenerate.py` from the same kit, so the projection
invariant still applies to it.

The personal recipe ships in the kit (`recipes/personal.yaml`) and
can be invoked any time via `wiki init --recipe personal`. RFC-0006
did not promote a `starters/personal/` rendering — that would
require new seed content scoped to a personal-vault audience, which
is a separate decision deserving its own consideration.

## What this is *not*

- **Not a packaging surface.** Nothing under `starters/` ends up in
  the wheel; `pyproject.toml`'s `packages = ["llm_wiki_kit"]` keeps
  the kit's distribution narrow. The starters are repo content,
  consumed by `git clone`.
- **Not a separate versioning axis.** A starter is pinned to the
  kit's HEAD by construction; a user who wants the starter that
  matches kit `v2.3.1` clones the corresponding kit tag.
  RFC-0006 deliberately decided not to add a separate starter
  version surface.
- **Not user-editable.** A contributor who edits a file under
  `starters/family/` directly will trip the `--check` CI gate on
  the next push. The right way to change a starter is to edit the
  recipe, the primitive, or the seed page; then re-run
  `regenerate.py --apply`.

## Where to look next

- [`starters/README.md`](../../starters/README.md) — user-facing
  index of the available starters and the `cp -r` workflow.
- [`starters/regenerate.py`](../../starters/regenerate.py) — the
  renderer.
- [`docs/specs/task-21-examples-tutorials/spec.md`](../specs/task-21-examples-tutorials/spec.md)
  — the spec for the regenerator and the committed-vault gates
  (AC6, AC7).
- [`docs/rfc/0006-promote-examples-to-starters.md`](../rfc/0006-promote-examples-to-starters.md)
  — the RFC that promoted the rendered vaults from "previews" to
  first-class starter distributions, and articulated the projection
  invariant.
