# Specs

Feature specs live here, one directory per feature with a `spec.md` (the contract)
and a `plan.md` (the strategy). See `docs/CONVENTIONS.md` for the lifecycle and the
`new-spec` skill for how they're created. A spec is the validation gate for its
feature: if the implementation diverges, the spec is wrong — fix it in the same PR.

## Active (Draft / Implementing)

| Spec | Status |
|------|--------|
| [role-folders-and-containers](role-folders-and-containers/spec.md) | Approved |

RFC-0009 follow-on #2: realizes the LYT role-folder layout (people/ nodes,
efforts/<type>/ containers, library/ capture, atlas/ synthesis) on top of the
facets `faceted-frontmatter-schema` shipped. Lands before
`operations-and-search-rekey` and `capture-synthesis-gating`.

## Shipped / Implemented

| Spec | Status |
|------|--------|
| [faceted-frontmatter-schema](faceted-frontmatter-schema/spec.md) | Shipped |
| [wiki-agents](wiki-agents/spec.md) | Shipped |
| [wiki-bootstrap](wiki-bootstrap/spec.md) | Shipped |
| [workspace-primitive](workspace-primitive/spec.md) | Shipped |
| [personal-recipe-workspaces](personal-recipe-workspaces/spec.md) | Shipped |
| [primitive-sideload](primitive-sideload/spec.md) | Shipped |
| [starter-seed-coverage](starter-seed-coverage/spec.md) | Shipped |
| [journal-locking](journal-locking/spec.md) | Implemented |
| [journal-reader-cache](journal-reader-cache/spec.md) | Implemented |
| [outcome-named-entry-points](outcome-named-entry-points/spec.md) | Implemented |
| [safe-write-ordering](safe-write-ordering/spec.md) | Implemented |
| [wheel-bundled-assets](wheel-bundled-assets/spec.md) | Implemented |
| [wiki-init-adopt](wiki-init-adopt/spec.md) | Implemented |
| [wiki-init-git](wiki-init-git/spec.md) | Implemented |
| [wiki-journal-readers](wiki-journal-readers/spec.md) | Implemented |
| [wiki-research-skill](wiki-research-skill/spec.md) | Implemented |
| [wiki-run-exec](wiki-run-exec/spec.md) | Implemented |
| [wiki-schedule](wiki-schedule/spec.md) | Implemented |
| [wiki-search](wiki-search/spec.md) | Implemented |
| [wiki-upgrade](wiki-upgrade/spec.md) | Implemented |
| [wiki-upgrade-force-render](wiki-upgrade-force-render/spec.md) | Implemented |
| [task-17-wiki-run](task-17-wiki-run/spec.md) | Implemented |
| [task-18-research-perplexity](task-18-research-perplexity/spec.md) | Implemented |
| [task-19-research-gemini-semscholar](task-19-research-gemini-semscholar/spec.md) | Implemented |
| [task-20-eval-harness](task-20-eval-harness/spec.md) | Implemented |
| [task-21-examples-tutorials](task-21-examples-tutorials/spec.md) | Implemented |
