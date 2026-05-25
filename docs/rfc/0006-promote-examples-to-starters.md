# RFC-0006: Promote `examples/` to first-class starter distributions

- **Status:** Accepted
- **Author:** maintainer
- **Created:** 2026-05-25
- **Discussion:** PR opened against `main` from
  `eugenelim/rfc-starter-distributions`
- **Resolves to:** A follow-up implementation PR that (1) moves
  `examples/family-mini/`, `examples/work-os-mini/`, and
  `examples/personal-mini/` to `starters/family/`, `starters/work-os/`,
  `starters/personal/`; (2) updates `regenerate.py`, its CI gate, and
  the seed-page layout to the new paths; (3) restructures the
  `README.md` front page to lead with the clone-and-go starter path;
  (4) updates `docs/architecture/overview.md`, the two tutorials, and
  the conflict how-to to reference the new paths. No kit-code change.
- **Sibling RFC:** RFC-0005 (narrow charter mission to the vault
  author). RFC-0005 settles *who the kit serves as the primary
  audience*; this RFC settles *how we serve the audience the kit
  doesn't primarily serve*. They are independently mergeable but
  read better together.

## Summary

The kit already produces three full, byte-verified, runnable
Obsidian vaults under `examples/family-mini/`,
`examples/work-os-mini/`, and `examples/personal-mini/`. CI guarantees
they match the kit's own output — `examples/regenerate.py --check`
rebuilds each vault from the recipe + seed pages and byte-compares
against the committed tree. They are positioned in
`examples/README.md` as previews: *"browse to see what
`llm-wiki-kit` produces"*.

This RFC promotes them to first-class **starter distributions**
under a new top-level `starters/` directory, restructures the
README so the front page leads with *"pick a starter, clone it,
open it in Claude Code"*, and demotes the `pip install` path to a
secondary *"if you want to customize or upgrade"* section. The
library boundary in Principle 5 is unchanged: a starter is a
**projection** of the library — the same bytes a recipe + primitive
catalog produces, rebuildable at any time from the kit itself.

This is positioning work, not new code. The artifacts exist. The
machinery to keep them current (and to rebuild them) exists. The
change is naming, README order, and one explicit invariant — a
starter is a projection of the kit, not a fork of it — so that
two distinct usage paths (clone-and-use; later `pip install` and
upgrade in place) compose cleanly.

## Motivation

### The usability cliff `pip install` introduces

v1 of `llm-wiki-kit` shipped three forks of a vault under
`vault-templates/{family,work,personal}/`. A user `git clone`d the
repo and had a working vault on their machine within sixty seconds.
RFC-0001 replaced that with a Python package + recipe catalog,
which fixed real drift, sync, and upgrade problems — but it
introduced a new floor: `pip install llm-wiki-kit` (and the
implicit preconditions: Python 3.11+ on PATH, working `pip` or
`pipx`, the ability to read a wheel-build stack trace, a working
`git` for the default-on `git init`). For the engineering-
comfortable author RFC-0005 names as the primary audience, this
floor is fine. For everyone else, it is the cliff that ends most
attempts.

Concretely: the `README.md`'s five-step quick start is *"Install
→ Init → Version it → Open it → Talk to Claude."* Step 1 is the
filter. A user whose `pip install` fails because they're on Python
3.10 (the macOS default until very recently) gets a stack trace and
no recovery path.

### The artifacts to fix the cliff already exist

The kit already maintains three full rendered vaults in the repo:

```
examples/
├── family-mini/         # full family vault, ~50 files, real seed pages
├── work-os-mini/        # full work-os vault, ~62 files, real seed pages
├── personal-mini/       # smaller personal vault
├── conflict-pending/    # a worked example of a `.proposed` sidecar
├── _seed/               # hand-authored seed pages
├── regenerate.py        # rebuild + CI-gate
└── README.md            # positions all of these as "previews"
```

Each `*-mini/` directory contains exactly what `wiki init --recipe
<name>` would produce against the current `main`, plus a small
set of hand-authored seed pages from `_seed/<recipe>/` that make
the rendered vault non-empty (acme-corp QBR meetings, atlas-
migration decisions, household trip plans, family meals). The
`--check` mode of `regenerate.py` runs in CI and fails if the
committed bytes diverge from a fresh rebuild. Drift between
starter and kit is, by construction, mechanically impossible.

What's missing is positioning. The README directs new users to
`pip install`; the rendered vaults are mentioned only deep in
sections about "what you'll see in week 1" and the architecture
deep-dive. A first-time visitor who would be perfectly happy
cloning a starter and using it never sees the option.

### The "mini" framing actively discourages use

Calling the vaults `family-mini`, `work-os-mini`, `personal-mini`
implies they are stripped-down previews. They are not. They are
the same vault you get from `wiki init`, plus seed content. A
user who reads "mini" reasonably concludes *"I should install the
full thing"* — and gets routed back to the cliff.

The suffix is also asymmetric and intentional: it was named in
`docs/specs/task-21-examples-tutorials/spec.md` to keep the
example vaults visibly distinct from "the real thing you'd build
with the kit." That distinction made sense when the audience for
the artifacts was *"reader sanity-checking the kit's output before
installing"* — i.e. the engineering-adjacent author. Under
RFC-0005's narrowed mission, the engineering-adjacent author is
the kit's primary audience and doesn't need a preview; the
starter-clone user is the Tier 2 audience and needs the artifact
to be presented as the primary path, not a preview.

### What changes if we do nothing

- The audience the kit is *not* primarily serving (per RFC-0005)
  continues to get nothing — the kit's primary doc surface is
  built around `pip install`, with the existing artifacts hidden
  under "examples."
- Every new contributor who reads the README front page and the
  `examples/` directory back-to-back gets the same confused
  signal: *"there are three rendered vaults right here, but the
  front door wants me to install Python and rebuild them. Why?"*
  This is a real signal — recent contributor onboarding has
  named it.
- The "library jumped the shark on usability" framing (raised on
  this RFC's discussion thread) compounds; the kit's design is
  fine, but its product surface is not.

## Proposal

### The load-bearing property: a starter is a *projection* of the kit

The proposal rests on one invariant that makes everything else
defensible. A starter under `starters/<recipe>/` is the
deterministic output of running the kit's renderer over the
named recipe plus the named seed pages. It is **not** a fork of
the kit, **not** a hand-authored snapshot, and **not** a parallel
vault definition. Concretely:

- `starters/regenerate.py --apply` rebuilds every committed
  starter byte-for-byte from `recipes/*.yaml` + `starters/_seed/`
  + the primitive catalog under `templates/`. Running it on a
  clean checkout produces the same bytes already on disk.
- `starters/regenerate.py --check` performs the same rebuild
  into a tmp directory and byte-compares against the committed
  tree. CI runs this on every PR. Divergence fails the build.
- The starter never contains a file the kit could not produce
  from the renderer plus the named seeds. There is no "starter-
  only" template, primitive, or AGENTS.md variant.

That invariant gives us two-way regenerability:

- **Kit author → starter.** A maintainer who changes a recipe, a
  primitive, or a seed page re-runs `regenerate.py --apply` and
  commits the result. CI confirms it on every subsequent PR. The
  starter cannot fall behind the kit because the kit produces it.
- **Starter → kit-managed vault.** A user who clones a starter,
  edits a few pages, and later wants to pull in newer kit
  primitives runs `pip install llm-wiki-kit` once, then `wiki
  upgrade` *inside their cloned vault*. `wiki upgrade` is the
  same path the kit already supports: it re-renders managed
  regions, installs new primitives the recipe now ships, and
  routes any user-edited file through `safe_write`'s drift
  detection — exactly the same protocol an author-built vault
  gets. The user's edits land as `.proposed` sidecars where they
  conflict; clean regions update in place. The starter is not a
  different kind of vault from the kit's perspective.

This composes: a starter user can postpone installing the kit
indefinitely, then install it the first time they want an upgrade,
without converting or migrating anything. Same vault, same
journal, same `safe_write`.

The invariant also disposes of the "library boundary" worry
upfront. A starter cannot drift the kit toward application-shape
because the starter contains no logic — it is a *render result*.
The kit produces it; the kit upgrades it; the kit verifies it.
Principle 5 holds because the projection is one-way (the kit
projects vaults; vaults do not become parts of the kit).

### What changes

Concrete file moves, contained in a single implementation PR:

```
examples/family-mini/       →  starters/family/
examples/work-os-mini/      →  starters/work-os/
examples/personal-mini/     →  starters/personal/
examples/conflict-pending/  →  (moves — see below)
examples/_seed/             →  starters/_seed/
examples/regenerate.py      →  starters/regenerate.py
examples/README.md          →  starters/README.md  (rewritten)
```

`examples/` ceases to exist as a top-level directory.
`examples/conflict-pending/` is documentation infrastructure (a
worked example for `docs/guides/how-to/resolve-a-conflict.md`),
not a starter. It moves to
`docs/guides/how-to/_examples/conflict-pending/` in the same PR,
so the only thing left in the repo claiming to be "a vault for a
reader" is a starter.

`starters/README.md` is rewritten to be a *user-facing* index of
the three starter vaults, in the shape:

> Pick the starter that matches your situation, copy it to a
> directory of your own, open it in Claude Code. You don't need
> to install anything to use a vault. When you eventually want
> to pull in kit upgrades, install the kit and run `wiki
> upgrade` inside your copy — your edits are preserved through
> the kit's drift-detection.

The kit-author-facing content currently in `examples/README.md`
(*"how regenerate.py works,"* *"why conflict-pending uses
personal,"* *"CI gates"*) moves to
`docs/architecture/starters.md` — a new architecture page
describing the starter machinery from the kit's side, including
the projection invariant above.

### README restructure

The top-of-`README.md` reorders from:

```
# LLM Wiki Kit
A Python package and template catalog for building LLM-maintained
markdown wikis...

## Quick start
1. Install. `pip install llm-wiki-kit`
2. Init a vault. `wiki init my-vault --recipe personal`
...
```

to:

```
# LLM Wiki Kit
A kit for building LLM-maintained markdown wikis. Two ways to use it:

- **Just use a vault.** Clone a starter, open it in Claude Code.
  No Python required.
- **Build, customize, or maintain a vault.** `pip install
  llm-wiki-kit`, then `wiki init` (new vault) or `wiki upgrade`
  (existing — including a cloned starter).

## Use a starter (no install required)
1. Pick one: `starters/personal/` (smallest), `starters/family/`,
   `starters/work-os/`.
2. Copy it: `cp -r starters/work-os ~/my-vault`
3. Open `~/my-vault/` in Claude Code or any markdown editor.
4. Talk to Claude — the vault's `AGENTS.md` tells the agent what
   skills are wired up.

## Build or maintain a vault (`pip install`)
[the current quick-start, demoted to a second section, with one
new bullet pointing out that `wiki upgrade` works inside a cloned
starter just as it works against a `wiki init`-built vault]
```

This is the *order* RFC-0006 prescribes; the precise wording lands
in the implementation PR and is editable in review.

### CI and tooling

- `starters/regenerate.py` keeps the same `--check` / `--apply`
  contract. Path constants change from `examples/` to `starters/`.
- `tests/integration/test_examples_regenerable.py` is renamed and
  its path constants update. The byte-compare CI gate is
  preserved; this is the load-bearing property that keeps starter
  content honest *and* the property that lets us call the starter
  a projection rather than a fork.
- `docs/specs/task-21-examples-tutorials/spec.md` is updated to
  reference the new paths. The spec's *constraints* (asymmetric
  naming for the conflict example, regenerator contract, journal
  normalization rules) carry over.

### Updates to user-facing docs

- `docs/guides/tutorials/tutorial-1-first-vault.md` — references
  to `examples/` updated. The tutorial still builds a vault from
  scratch (testing the `wiki init` path); it does not depend on a
  starter being present.
- `docs/guides/tutorials/tutorial-2-work-os-walkthrough.md` —
  references updated. The tutorial's "your vault should look like
  this" comparison points at `starters/work-os/` instead of
  `examples/work-os-mini/`.
- `docs/guides/how-to/resolve-a-conflict.md` — references to
  `examples/conflict-pending/` updated to the new
  `docs/guides/how-to/_examples/conflict-pending/` path.
- `docs/architecture/overview.md` — adds a paragraph naming the
  starter machinery, the projection invariant, and a link to the
  new `docs/architecture/starters.md`.

### A new top-level directory at the repo root

`starters/` is a new top-level directory. AGENTS.md says new
top-level directories go through RFC. This RFC is that RFC.
Justification (the §"Check before acting" list's standard:
*"the structure is intentional"*):

1. The directory has a single, narrow purpose (ship pre-rendered
   vaults consumable without the kit).
2. Its contents are mechanically generated, not hand-edited —
   the projection invariant above is what justifies elevating it
   to the repo root rather than burying it under `docs/` or
   `examples/`.
3. It is the load-bearing path the README front page points at.
4. It is *not* a subdirectory of `docs/`, `examples/`, or
   `tests/` because it is none of those things — it is a
   *distribution surface*, the same kind of thing
   `llm_wiki_kit/` is for the library half of the project.

### What stays the same

- Every line of code under `llm_wiki_kit/` is unchanged.
- The CLI surface, the journal schema, the recipe catalog, every
  primitive, every ADR, RFC-0001's v2 architecture, and the
  drift-detection / `safe_write` model are all unchanged.
- Principle 5 is unchanged. A starter is a CI-rendered
  projection of the library; it does not add an application
  layer to the kit.
- The `regenerate.py --check` CI gate is preserved (just
  renamed). This is what mechanically forbids drift between
  starter and kit.
- The seed pages (`_seed/<recipe>/`) keep their content; only
  the parent directory moves.
- `examples/conflict-pending/` keeps its role as the
  `wiki-conflict` worked example; it just moves under
  `docs/guides/how-to/_examples/` to make the distinction sharp.

### What this RFC does *not* propose

- **No separate-repo distribution.** A future RFC may split
  `starters/` into its own repository
  (`llm-wiki-kit-starters` or per-recipe repos) once we have
  evidence the kit-repo noise is blocking users. Today, same-
  repo is the v0: zero new infrastructure, the regenerator
  keeps working, drift is impossible by construction. The
  projection invariant means the future split (kit produces;
  release pipeline publishes to sibling repos) does not invent
  new machinery — it just adds a publish step.
- **No GitHub-release tarballs.** Same argument. Cloning the
  kit repo is enough to get a starter; tarballs are an
  optimization to consider once we know users want them.
- **No new seed content for the existing starters.** The
  current seeds (~50–62 files per starter) are enough for a
  first-day user. Growing them is a separate, ongoing concern.
  A starter that ships an empty ontology folder is fine; the
  user fills it.
- **No removal of "mini" as a separate decision.** The rename
  `examples/family-mini/` → `starters/family/` drops the suffix
  as a side effect, but the suffix's *original* motivation (a
  preview-vs-real-vault distinction) is what the RFC argues
  against — so the suffix going away is part of the proposal,
  not a separate decision.
- **No code change to make the kit "starter-aware".** The kit
  doesn't know `starters/` exists. The starter is produced by
  the regenerator and consumed by the user; the kit itself
  stays unaware.
- **No change to the recipes.** `recipes/family.yaml`,
  `work-os.yaml`, `personal.yaml` are unchanged. The starter is
  the output of *running* a recipe, not a redefinition of one.

### Implementation outline

For the follow-up PR that lands after this RFC is accepted, in
the order the implementer should expect to execute:

1. **Move directories.** `git mv examples/family-mini starters/family`,
   `examples/work-os-mini starters/work-os`,
   `examples/personal-mini starters/personal`,
   `examples/_seed starters/_seed`,
   `examples/regenerate.py starters/regenerate.py`.
1. **Move the conflict example.** `git mv examples/conflict-pending
   docs/guides/how-to/_examples/conflict-pending`.
1. **Delete `examples/README.md`.** Replace it with
   `starters/README.md` (user-facing) and
   `docs/architecture/starters.md` (architecture-facing,
   includes the projection invariant).
1. **Update path constants in `starters/regenerate.py`.**
   `EXAMPLES_DIR` → `STARTERS_DIR`; `SEED_ROOT`; the recipe-
   target mapping (`family-mini` → `family`, etc.). Run
   `--check` against the moved tree; commit the result.
1. **Update the integration test.** Rename
   `tests/integration/test_examples_regenerable.py` and its path
   constants. Run the test; it should pass against the moved
   tree.
1. **Update README.md front page.** Reorder per the §"README
   restructure" sketch above. Wording is editable in review.
1. **Update tutorials and how-tos.** Grep for
   `examples/family-mini`, `examples/work-os-mini`,
   `examples/personal-mini`, `examples/conflict-pending`, and
   `examples/` more generally; replace per the new paths.
1. **Update `docs/specs/task-21-examples-tutorials/spec.md`.**
   Path references and the README cross-link. The spec stays
   Implemented; no behavioral change.
1. **Update `docs/architecture/overview.md`.** Add the paragraph
   that names the starter machinery, the projection invariant,
   and the link to `docs/architecture/starters.md`.
1. **Run `pytest -m 'not slow'`, `ruff check llm_wiki_kit tests`,
   `mypy llm_wiki_kit tests`, and `python starters/regenerate.py
   --check`.** Land in one PR.

The implementer should not split this across multiple PRs. The
moves, the README restructure, and the test/spec updates are all
the same change; a partial landing leaves the repo with broken
references.

## Alternatives

Four alternatives considered.

### (A) Same-repo `starters/` directory (this proposal)

Picked. See §Proposal.

### (B) Separate-repo distribution per starter

Three sibling repos: `llm-wiki-kit-starter-family`,
`llm-wiki-kit-starter-work-os`, `llm-wiki-kit-starter-personal`.
Each is git-cloneable in isolation; the user doesn't pull the
kit's tests, tooling, or specs.

*Why deferred.* Cleaner user surface, but requires a release
pipeline that publishes the rendered output from the kit to the
sibling repos on every kit release. That's three new repos,
three new GitHub Actions, a sync-or-drift problem we don't yet
have, and a contract surface for what "a starter release" means
that we don't yet need to commit to. The projection invariant
makes the future split cheap (the publish step is mechanical) —
which is *why* we can safely defer it: starting same-repo
doesn't paint us into a corner. Defer until we have evidence
(e.g. user feedback that the kit-repo noise is in the way) that
justifies the infrastructure cost.

### (C) GitHub-release tarballs

The kit publishes `family.tar.gz`, `work-os.tar.gz`,
`personal.tar.gz` as release assets on every tagged release. The
user downloads and extracts.

*Why deferred.* Even more friction than cloning the kit repo
(you have to know what a release tarball is, find the right one,
learn to `tar -xzf`). It's also harder to keep current — a user
who downloaded last quarter's tarball has no obvious upgrade
path short of downloading again. Cloning gives the user `git
pull` as a free upgrade mechanism, and `pip install
llm-wiki-kit && wiki upgrade` as the second-stage upgrade once
they want kit machinery. Tarballs are a possible *optimization
on top of* same-repo distribution, not an alternative to it.

### (D) Status quo

Leave `examples/` as-is. Tighten its README to be a bit more
welcoming. Don't reposition.

*Why rejected.* This is the path RFC-0005 explicitly names as
inaction: the artifacts already exist and are mis-positioned;
the audience the kit's primary mission no longer serves (per
RFC-0005) goes on receiving no front-door answer. The "preview"
framing actively misroutes users to the install path. Doing
nothing pays interest in confused contributor onboarding and a
front page that doesn't match the user RFC-0005 commits the kit
to serve.

## Drawbacks

The honest costs.

- **A clone of the kit repo pulls down the kit's tests, tooling,
  specs, and ADRs alongside the starter.** A starter user
  doesn't need any of that. The noise is real. Mitigation:
  same-repo is the v0; if users say the noise is blocking them,
  alternative (B) (per-starter repos) is the natural escalation
  path. The projection invariant means we can move to (B) later
  without inventing new sync machinery — the publish step is a
  CI job, not a new contract.

- **A new top-level directory at the repo root.** `starters/`
  is one more thing for an unfamiliar visitor to scan.
  Mitigation: the README front page now leads with it, so a
  visitor who lands at the repo root sees the starter path
  first, not as a directory to decode. AGENTS.md's "no new
  top-level directory without RFC" rule is honored by this RFC.

- **Spec/test path updates touch a lot of files.** Roughly
  15–25 files reference `examples/family-mini`,
  `examples/work-os-mini`, or `examples/conflict-pending`
  today. A grep-and-replace pass catches most; a few are in
  docstrings and require care. The implementation PR will have
  a large diff that is almost all mechanical. Mitigation: list
  the touched-file count in the PR description; the reviewer
  reads the *non-mechanical* edits (README,
  starters/README.md, the new `docs/architecture/starters.md`)
  and skims the rest.

- **`docs/specs/task-21-examples-tutorials/spec.md`'s
  "asymmetric conflict-pending naming" rationale changes.**
  That spec's §Constraints reasoning was *"`conflict-pending`
  is a worked example, not a starter; the asymmetric name (no
  `personal-mini`) is intentional."* Under this RFC, the
  "asymmetry" disappears because the conflict example moves
  out of the starter directory entirely. The spec needs a
  one-paragraph update naming the new home. Light cost, no
  spec freeze breaks.

- **`docs/architecture/overview.md` grows by one paragraph and
  a link to a new page.** Architecture docs are living; this
  is cheap, but it does mean RFC-0006 implicitly adds one
  document to the architecture set.

- **Starter users still need Claude Code (or another AGENTS.md-
  reading agent) to actually run operations.** A clone-and-go
  starter is more accessible than `pip install`, but it is not
  *zero* engineering. The user still needs to know what an LLM
  is, install a Claude client, point it at the vault.
  Mitigation: honest about this in the starter README; the
  cliff we've removed is the Python-and-pip-and-wheel-failure
  cliff, which is the load-bearing one. The user-needs-an-LLM
  cliff is shared with every product in this space.

- **The "minimal seed content" assumption may not hold long-
  term.** A user opening `starters/family/` and seeing only
  two example meals and one trip plan may decide the starter
  is empty and abandon it. Mitigation: out of scope here —
  growing seed content is a separate, ongoing concern handled
  in normal PRs against `starters/_seed/`. RFC-0006 commits to
  the *positioning* and the *projection invariant*, not to any
  specific seed-richness floor.

- **The projection invariant constrains future starter
  changes.** Once we say a starter is *only* a projection of
  the kit + seeds, we can't ship a starter-only file (a custom
  AGENTS.md preamble, a tweaked CORE.md) without either making
  the kit's renderer aware of it or breaking the invariant.
  Mitigation: this constraint is the point. If a starter needs
  a custom file, the right answer is to make the kit render it
  — either by extending a recipe, adding a primitive, or
  growing a seed page. That's the discipline that keeps
  starter and kit from diverging.

## Unresolved questions

- **Should `starters/conflict-pending/` exist as a fourth
  starter, or should the conflict example move under
  `docs/guides/how-to/_examples/` as this RFC proposes?** This
  RFC argues for the latter (conflict-pending is documentation,
  not a usable starting point; a user cloning it would inherit
  a `.proposed` sidecar they have to resolve before doing
  anything useful). A reviewer who thinks *"a worked example
  of conflict resolution is exactly what a Tier 2 user would
  want to see"* may push back.

- **Should `starters/README.md` link out to the kit-author
  docs (the current README's pip-install path), or just
  describe the starter usage and let the reader find the kit's
  docs on their own?** A one-line link at the bottom is
  probably right (specifically pointing at the
  *"`wiki upgrade` inside your cloned starter"* path, since
  that's the most common second-stage need). The
  implementation PR decides the exact wording.

- **Should the new architecture page be
  `docs/architecture/starters.md` (RFC-0006's proposal) or
  fold into the existing `docs/architecture/overview.md`?**
  Folding in is cheaper but makes the overview longer; a
  dedicated page is cleaner but adds a doc. Light decision,
  can defer to the implementation PR's reviewer.

- **Should this RFC commit to a starter-version invariant
  beyond "the starter is whatever the kit's HEAD produces"?**
  A user wanting "the starter that matches kit v2.3.1" already
  gets it by cloning the corresponding kit tag — `git checkout
  v2.3.1 && cp -r starters/work-os ~/my-vault`. Adding a
  separate starter version axis (e.g.
  `starters/work-os/VERSION`) introduces a sync problem we
  don't yet need. Worth naming so a reviewer can disagree.

- **Is `starters/` the right name?** Alternatives: `vaults/`,
  `templates/` (collides with the kit's primitive templates),
  `quickstart/`, `presets/`. `starters/` is the user-meaningful
  word in this RFC's framing ("pick a starter") and matches the
  vocabulary RFC-0005 uses. If a reviewer has a better name,
  the rename costs one mechanical pass.

## Outcome

**Accepted 2026-05-25.** Accepted alongside sibling RFC-0005
(narrow charter mission to the vault author); the two were
reviewed and landed together.

Follow-up implementation work (one PR, per §"Implementation
outline"):

- Move `examples/{family,work-os,personal}-mini/` →
  `starters/{family,work-os,personal}/`.
- Move `examples/conflict-pending/` →
  `docs/guides/how-to/_examples/conflict-pending/`.
- Move `_seed/` and `regenerate.py` under `starters/`; update path
  constants; rerun `--check` and the renamed integration test.
- Restructure `README.md` front page to lead with the clone-and-go
  starter path; demote `pip install` to a secondary section.
- Add `docs/architecture/starters.md` (kit-side machinery,
  including the projection invariant).
- Update `docs/specs/task-21-examples-tutorials/spec.md` and the
  tutorial / how-to references.
- Charter §Mission edit per RFC-0005 also lands in the same wave.
