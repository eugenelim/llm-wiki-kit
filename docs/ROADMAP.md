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

## Deferred from v2.0

The RFC explicitly defers a single item out of v2.0; it needs its own
spec before any task picks it up.

- **`wiki init --adopt`** — adopt an existing folder as a vault rather
  than refusing on a non-empty target. Flagged as an "Unresolved
  question" in RFC-0001 and deferred at Task 10. The semantics are
  non-trivial — every pre-existing file needs to be journaled before
  any kit-owned write can land safely, baseline hashes have to be
  seeded, and the policy for files the kit wouldn't otherwise own has
  to be pinned. The inline comment in `llm_wiki_kit/cli.py:_cmd_init`
  carries the same pointer for future readers.

## Pointers

- Migration tasks: [`docs/rfc/0001-v2-architecture.md`](rfc/0001-v2-architecture.md)
- Tooling adoption: [`docs/rfc/0002-adopt-agent-ready-repo-tooling.md`](rfc/0002-adopt-agent-ready-repo-tooling.md)
- Specs in flight: [`docs/specs/`](specs/)
