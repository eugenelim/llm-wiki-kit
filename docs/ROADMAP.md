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

## Post-PR-C follow-ups

PR-C of [`wiki-init-adopt`](specs/wiki-init-adopt/) explicitly
defers one recovery-path gap to a follow-on spec:

- **`wiki upgrade --force-render`** (or `wiki init --adopt
  --resume`) — re-render the installed primitive closure over
  existing adopt baselines even when no catalog version has
  bumped. Today's `wiki upgrade` short-circuits on a matching-
  version no-op (`llm_wiki_kit/upgrade.py:plan_upgrade`), so a
  crash mid-install leaves a partial vault with no productive
  automated recovery. The spec for this would lift the
  short-circuit behind a flag and pin the drift-aware re-render
  semantics ADR-0008 §6 already names. Tracked in
  [`docs/specs/wiki-init-adopt/plan.md`](specs/wiki-init-adopt/plan.md)
  PR-C step 13's "DEFERRED RATIONALE".

## Pointers

- Migration tasks: [`docs/rfc/0001-v2-architecture.md`](rfc/0001-v2-architecture.md)
- Tooling adoption: [`docs/rfc/0002-adopt-agent-ready-repo-tooling.md`](rfc/0002-adopt-agent-ready-repo-tooling.md)
- Specs in flight: [`docs/specs/`](specs/)
