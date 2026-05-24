# Roadmap

> **Living document.** Update by normal PR; substantive shifts (a new
> tier, a re-prioritized capability, scope removal) go through an RFC
> in [`docs/rfc/`](rfc/) before they land here.

The kit's near-term direction. For decisions already made, see
[`docs/adr/`](adr/). For proposed changes, see
[`docs/rfc/`](rfc/). For the kit's mission and out-of-scope guarantees,
see [`CHARTER.md`](CHARTER.md). For shipped work, see
[`../CHANGELOG.md`](../CHANGELOG.md).

## Status

`v2.0.0` is tagged. All 22 migration tasks from
[`docs/rfc/0001-v2-architecture.md`](rfc/0001-v2-architecture.md) plus
the Phase F contract-completion sweep have shipped.

## Shipped post-v2.0

The RFC explicitly deferred one item out of v2.0; it has now shipped.

- **`wiki init --adopt`** — adopts an existing folder as a vault by
  journaling kit-owned files as ``PageAdoptedEvent`` /
  ``ManagedRegionAdoptedEvent`` baselines before the install
  pipeline runs. Policy pinned in
  [`docs/adr/0008-init-adopt-ownership-policy.md`](adr/0008-init-adopt-ownership-policy.md);
  contract and plan in
  [`docs/specs/wiki-init-adopt/`](specs/wiki-init-adopt/). Shipped
  across three sequential PRs per the plan (event types + replay,
  adopt-aware `safe_write` predicate, `_cmd_init --adopt` end-to-end).

- **Agent identity primitives ([RFC-0004](rfc/0004-agent-identity-primitives.md)).**
  `agent` is the fourth primitive kind alongside `ontology`,
  `content-type`, `operation`, and `infrastructure`. Recipes declare
  which agent runs which operation; `wiki schedule install` freezes
  the resolved agent on the journaled event and passes
  `--agent <name>` to `claude` at exec time per
  [ADR-0010](adr/0010-agent-passthrough-via-claude-agent-flag.md).
  Contract in [`docs/specs/wiki-agents/`](specs/wiki-agents/); shipped
  across eight sequential PRs ending in PR-7 (default agent catalog +
  recipe bindings + vault-side `wiki-conflict` / `wiki-agent` SKILLs).

- **`wiki upgrade --force-render`** — re-renders the installed
  primitive closure unconditionally to recover from a partial
  install (a crash mid-`wiki init` after one or more
  ``PrimitiveInstallEvent`` rows land but before the corresponding
  ``PageWriteEvent`` rows). Lifts ``plan_upgrade``'s
  matching-version short-circuit behind an explicit ``--force-render``
  flag; the adopt-aware ``safe_write`` predicate (ADR-0008 §Decision
  sub-choice 3) routes drift to ``.proposed`` sidecars exactly as a
  catalog-bump ``wiki upgrade`` does. Closes the PR-C deferral named
  in `wiki-init-adopt`'s plan step 13. Contract in
  [`docs/specs/wiki-upgrade-force-render/`](specs/wiki-upgrade-force-render/).

## In flight

_(nothing in flight right now)_

## Cleanup after PRs ship

- **Delete `adopt._required_regions` alias** one release after
  `wiki upgrade --force-render` ships. The lift to public
  `compute_required_regions` carries a one-cycle alias for any
  external caller (none in-tree today; precaution against
  in-flight branches). See `llm_wiki_kit/adopt.py` and
  [`docs/specs/wiki-upgrade-force-render/plan.md`](specs/wiki-upgrade-force-render/plan.md)
  §Risks.

## Pointers

- Migration tasks: [`docs/rfc/0001-v2-architecture.md`](rfc/0001-v2-architecture.md)
- Tooling adoption: [`docs/rfc/0002-adopt-agent-ready-repo-tooling.md`](rfc/0002-adopt-agent-ready-repo-tooling.md)
- Specs in flight: [`docs/specs/`](specs/)
