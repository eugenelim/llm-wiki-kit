# RFC-0005: Narrow the charter mission to the vault author

- **Status:** Open for comment
- **Author:** maintainer
- **Created:** 2026-05-25
- **Discussion:** PR opened against `main` from
  `eugenelim/rfc-charter-audience-tension`
- **Resolves to:** A follow-up PR that edits `docs/CHARTER.md` §Mission
  and §Principles (Principle 6 clarification only — Principle 5
  unchanged). The Tier 2 audience question — how (or whether) we
  serve non-author users — is split into the sibling RFC-0006
  (promote `examples/` to `starters/`). No code change in this RFC.

## Summary

The charter says two things that have been in tension since v2 began,
and the tension has been silently re-resolved in every recent
product-shaping spec. The mission targets a non-engineer ("a working
professional or a family"). Principle 5 says the kit is a library,
not an application. A non-engineer cannot consume a library;
engineering literacy is required to even install one.

This RFC picks one of the two. It narrows the mission to the
*engineering-comfortable author* who maintains a wiki for themselves
and for the people around them, and it keeps Principle 5 unchanged.
Audiences who cannot install the kit themselves (true non-engineers,
households without a tech-comfortable member) are acknowledged as a
distinct downstream-distribution problem and routed to the sibling
**RFC-0006** ("Promote `examples/` to first-class starter
distributions"), which proposes the concrete answer: a `starters/`
directory in this repo that ships pre-rendered, ready-to-use vaults
producible from the kit but consumable without it. Explicitly *not*
by softening the library boundary.

A reader who agrees the mission should be narrowed — and that
Principle 5 should stay sharp — can skip the rest. The rest is the
argument for why this is the right cut, what existing decisions look
like under the new framing, and what changes (and what doesn't) in
documents the charter pulls on.

## Motivation

### The tension, named

The charter, today:

- **Mission** (`docs/CHARTER.md` line 14): "`llm-wiki-kit` makes it
  practical for a non-engineer — a working professional or a family
  — to keep a useful Obsidian wiki…"
- **Principle 5** (`docs/CHARTER.md` line 98): "**Library-not-
  application.** The kit is invoked by Claude as a set of primitives
  Claude can call. Claude is the application; the kit is the
  library. We don't try to be the agent, the orchestrator, or the
  model."

A non-engineer cannot consume a library. The kit's day-1 surface
makes that concrete:

- `pip install llm-wiki-kit` (or `pipx install`) — assumes Python
  3.11+ on PATH, working pip / pipx, the ability to read a stack
  trace when wheels fail.
- `wiki init my-vault --recipe personal` — assumes shell literacy.
- The vault is then full of engineering vocabulary in load-bearing
  places: `AGENTS.md` on the front door, a `.wiki.journal/` directory
  the user is told is "the kit's source of truth", `frontmatter.schema.yaml`
  in the vault root, references to `safe_write`, drift, and proposals
  in the user-facing how-tos.
- The kit's own development discipline (ADRs, RFCs, specs) is
  surfaced to the user as a feature ("eat our own dogfood",
  Principle 6) — implying the same discipline is on the menu for
  vault maintainers.

Each of these is the *right* engineering choice for the kit. None of
them survives contact with the literal mission audience ("a working
professional or a family"). A non-engineer encountering the README's
"5 steps, fresh machine to working vault" hits the first step and
stops — not because the kit is hostile, but because `pip install`
literally requires engineering literacy to recover from when it
breaks.

### Drift, not deliberation, has been resolving the tension

The strongest evidence the tension is unresolved: every recent spec
that touches the product surface has had to argue the principle into
a corner before it could ship. Three concrete cases, from the spec
tree:

- **`docs/specs/outcome-named-entry-points/spec.md` §"Tension to
  name"** (lines 48–65) explicitly names this conflict, then
  resolves it locally by reframing outcome verbs as "declarative
  metadata on the operation primitive" plus "mechanical routers." A
  clever resolution, but every future application-shaped surface
  gets to make the same move.
- **`docs/specs/wiki-bootstrap/spec.md` §"Tension to name"** (lines
  49–82) spends multiple paragraphs defending a first-run wizard
  against Principle 5 ("the kit's Python writes nothing for this
  skill", "state is one-bit-of-marker, not a multi-step state
  machine"). The defenses are good engineering; they would not be
  necessary if the mission and the principle agreed.
- **`docs/specs/wiki-init-git/spec.md`** ships a default-on `git
  init` + `git commit` at `wiki init` time. The spec assumes a user
  who has `git` on PATH and a configured `user.name` /
  `user.email`. That user is engineering-adjacent by construction;
  calling the feature out as "for non-engineers" would be a
  stretch.

The pattern is not "we deliberated and chose to soften the
principle." The pattern is "the principle is being narrowly defended
spec-by-spec, while the cumulative product surface drifts toward
engineering-adjacent users — which is who the kit was always quietly
serving." The reviewer's adversarial concern (have we been softening
the principle because individual PRs pushed against it, rather than
because we deliberated?) is the right question. The honest answer is
yes — and the right response is to stop drifting and pick.

### What changes if we do nothing

Three failure modes the kit is already paying for, and which
compound the longer the tension stays unresolved:

1. **Every product-surface spec re-litigates Principle 5.** The two
   "Tension to name" sections above are not the last; any future
   spec that adds a CLI alias, a slash command, a wizard, a doctor
   check, or any user-facing affordance will have to do the same
   dance. That cost is paid in spec length, reviewer time, and a
   slow erosion of confidence in the principle.
1. **Marketing and reality drift apart.** The README says "a non-
   engineer can `pip install` and get a working vault." This is
   approximately false — it requires a working Python 3.11, a
   working pip, network access, the ability to read a pip error.
   Honesty over capability (Principle 1) is the kit's most-cited
   value; shipping a mission claim the kit cannot stand behind is a
   violation of Principle 1 by the *charter itself*.
1. **Tier 2 audiences (true non-engineers) get nothing, and the
   existing `examples/*-mini/` artifacts stay mis-positioned.** The
   kit already renders three full vaults under `examples/` (family,
   work-os, personal) and CI verifies they match the kit's output
   byte-for-byte. They are framed as *previews* — "browse to see
   what the kit produces" — when they are functionally complete
   v1-style starter vaults. As long as the mission claims to serve
   non-engineers directly, the kit has no incentive to promote
   those artifacts to the front door (RFC-0006). The ambiguity
   blocks both directions: we can't sharpen the library for
   engineers without seeming to abandon the family, and we can't
   promote the starters without contradicting the library framing.

## Proposal

### What changes

Replace the charter mission text. Keep Principle 5 verbatim.

Proposed new §Mission (text to land in the follow-up charter-edit
PR, not in this RFC):

> `llm-wiki-kit` makes it practical for one technically-comfortable
> author — an engineer, an engineering-adjacent professional, or
> the tech-confident member of a household — to set up and maintain
> an Obsidian wiki that they and the people around them can use,
> and that an LLM can read, ingest into, and operate on. The kit
> serves the author; the downstream readers (family members,
> teammates, stakeholders) consume the resulting vault in whatever
> editor or chat client they already use, and need no relationship
> with the kit itself.
>
> The kit ships a common core plus a catalog of droppable
> primitives, composed by recipes, so each author gets a vault
> shaped to their actual life or work without having to design one
> from scratch.
>
> Audiences who cannot install the kit themselves — true non-
> engineers, households or teams without a tech-comfortable
> maintainer — are a Tier 2 audience served by *starter
> distributions*: pre-rendered vaults producible from the kit but
> consumable without it. The kit produces them; the user clones
> one. The library boundary in Principle 5 is unchanged, because
> a starter is a CI-generated artifact of the library, not a
> parallel application. See sibling RFC-0006 for the concrete
> proposal.

Principle 5 stays exactly as written.

Principle 6 ("eat our own dogfood") gains a one-sentence
clarification — *the discipline the kit follows is for kit
development; vaults do not inherit it* — to remove the ambient
implication that ADR/RFC/spec discipline is a feature on offer to
vault maintainers. (Charter §Scope already excludes ADR/RFC/spec
primitives from being shipped into vaults; the clarification just
makes the audience read of Principle 6 explicit.)

### What stays the same

- Principle 5 is unchanged. The library boundary is unchanged. The
  kit does not become an LLM wrapper, an orchestrator, or an
  Electron app at the edges.
- The three shipped recipes (`family`, `work-os`, `personal`) keep
  their names. They describe the *vault's purpose* — a vault for a
  family, a vault for a working professional, a vault for a single
  person — not the *kit user*. The kit user is the author in all
  three cases.
- `docs/CHARTER.md` §Scope (what the project does / does not do) is
  unchanged. The kit still doesn't host vaults, doesn't ship an
  LLM, doesn't include engineering-team primitives, doesn't lock
  users into Obsidian.
- All existing ADRs (0001–0008) are unchanged. RFC-0001's v2
  architecture is unchanged. No code moves.

### How recent decisions look under the new framing

A direction-setting RFC is worth what the work-loop tomorrow looks
like under it. Five concrete recent decisions:

1. **Outcome-named entry points** (`docs/specs/outcome-named-entry-points/`,
   shipped). Aligns cleanly. The spec's resolution — "declarative
   metadata + mechanical routers" — remains the right shape under
   either framing. The *tension* the spec spends a section
   defending against is gone: an engineering-adjacent author who
   types `wiki digest` instead of `wiki run weekly-digest` is just
   the user we said we were serving. The spec doesn't need to be
   edited; the awkwardness in its §"Tension to name" simply stops
   being load-bearing.

1. **`wiki init` defaulting to `git init`** (`docs/specs/wiki-init-git/`,
   shipped). Aligns. The spec assumes a user who has `git` on PATH
   and a configured `user.name` / `user.email`. Under the current
   mission, that assumption is a stretch ("a family" rarely has git
   configured globally); under the new mission, the assumption is
   exactly right. The `--no-git` opt-out becomes a courtesy for
   authors who manage versions another way, not an accommodation
   for a non-engineer audience the kit was never actually going to
   reach.

1. **`wiki-bootstrap` skill** (`docs/specs/wiki-bootstrap/`,
   drafted). Aligns, and the spec's defenses against Principle 5
   become excess freight. Under the new mission, a vault-side
   onboarding skill that walks an engineering-adjacent author
   through their first-day verbs is not in tension with the
   library boundary at all — it's a courtesy SKILL the *author*
   runs in *their* Claude session, exactly like `wiki-conflict`
   and `wiki-doctor`. The two load-bearing properties the spec
   leans on (no kit-side Python writes; one-bit-of-marker state)
   remain good engineering, but they no longer have to do
   principle-defense work.

1. **Starter distributions** (sibling RFC-0006, drafted alongside
   this one). Aligns, and this RFC names where the audience the
   primary mission no longer covers actually gets served. Under
   the current "non-engineer family" mission, the existing
   `examples/*-mini/` artifacts are mis-positioned: they ship as
   "previews" because positioning them as the front door would
   contradict the library narrative. Under the new mission, they
   are the *Tier 2 distribution* — promoted in-place to
   `starters/`, surfaced on the README, and consumable without
   `pip install`. The starter doesn't blur the library boundary
   because it is a CI-rendered artifact *of* the library
   (verified byte-for-byte by `regenerate.py --check` today),
   not a parallel application. RFC-0006 carries the concrete
   proposal.

1. **The journal, AGENTS.md, and the ADR/RFC/spec discipline
   themselves**. Aligns. Under the current mission, the kit's
   ambient engineering vocabulary is in conflict with the
   audience. Under the new mission, the vocabulary is honestly
   named: `AGENTS.md` is the contract the author and their LLM
   share, the journal is the author's audit log, the discipline
   (Principle 6) is for kit development and does not ride into the
   vault as a feature. The kit can stop apologizing for its own
   engineering shape because the audience is engineering-adjacent.

### What this RFC does *not* propose

- No new mission text for the charter is *landed* by this RFC. The
  text above is the proposed wording; the follow-up PR is what
  edits the charter file. The split (RFC sets direction; follow-up
  PR edits the canonical doc) matches the charter-revision
  protocol in `docs/CONVENTIONS.md` §"How to add an RFC".
- No code change. No spec change. No ADR is rendered obsolete or
  in need of supersession. The kit's modules, CLI surface, and
  journal schema are untouched.
- No deletion of audience-shaped recipes (`family`, `work-os`,
  `personal`). They keep their names and their primitives. The
  user *building* the family vault is the author; the *family*
  still reads the resulting vault.
- No commitment to actually ship a starter-repo distribution. The
  starter is named as the honest target for Tier 2 audiences; the
  decision to build one is its own future RFC.

### Documents that need to change in the follow-up PR

Counted out so the follow-up PR's scope is bounded ahead of time:

1. `docs/CHARTER.md` §Mission — replace the audience clause with
   the proposed text above. Three paragraphs (author, kit-shape
   carry-over, Tier 2 acknowledgment).
1. `docs/CHARTER.md` Principle 6 — append a one-sentence
   clarification that the kit's `AGENTS.md` / ADR / RFC / spec
   discipline is for *kit development*, not for vaults the kit
   produces.
1. `docs/CHARTER.md` §"When to revise" — no edit needed. The
   existing triggers ("mission has actually changed", "scope has
   shifted", "a principle has stopped resolving ties") still
   apply; the mission narrowing here is itself one of those
   triggers being honored.
1. `README.md` — the front page currently says "a non-engineer can
   `pip install llm-wiki-kit`…". Rephrase to "a single maintainer
   can `pip install llm-wiki-kit`…", and adjust the §"Talking to
   Claude" framing so the imagined reader is the author, not the
   entire family.
1. `docs/ROADMAP.md` — name the Tier 2 starter-repo distribution
   as an out-of-kit future direction (one paragraph). No
   commitment to a timeline.
1. `docs/guides/tutorials/tutorial-1-first-vault.md` and
   `tutorial-2-work-os-walkthrough.md` — a once-over to make sure
   the imagined reader is the author. The current tutorials
   probably need only light wording fixes; the cold-walk
   discipline already forces them to be concrete.

No `docs/architecture/` change. No spec change. No ADR is
superseded.

### Future RFCs and specs that become easier

- **RFC-0006 (starter distributions).** Drafted as a sibling. The
  Tier 2 audience now has an explicit home, and RFC-0006 doesn't
  have to argue both that non-engineers deserve service *and* that
  the library shouldn't serve them directly — this RFC settles the
  first half so RFC-0006 can focus on the *how*.
- **Author-shaped CLI affordances.** Future verbs, doctor checks,
  inspection commands, journal explorers can be designed for the
  author without spec-length defenses against Principle 5.
- **Engineering-team-shaped recipes.** The charter currently rules
  out ADR/RFC/sprint-planning primitives in shipped vaults
  (§Scope). That exclusion still holds under the new mission, but
  now by Principle 5 + Scope, not by audience. A future RFC that
  *did* want to ship some engineering-adjacent primitives (a
  research-log recipe, say, or a maintainer's-personal-vault
  recipe) can argue that case without tripping the audience claim.

### Future RFCs and specs that become harder

- **The "for a family" narrative.** The mission's current
  romanticism — a family keeping a useful wiki — is genuinely
  appealing, and the new framing trades some of it away. The
  family is still served (their tech-confident member maintains
  the vault for them), but the project's marketing-shaped pitch
  loses a beat.
- **A pure-GUI installer or Electron wrapper.** Under the old
  mission, that kind of project was implicitly on the roadmap (it
  would have served non-engineers directly). Under the new
  mission, it's outside the kit and probably outside this project
  entirely — a downstream-distribution project, parallel to the
  starter repo. Anyone who wanted to build it inside this repo
  would now have to argue against both Principle 5 and the new
  mission. That is a feature, not a bug, but it's worth naming.
- **Recipe naming pressure.** The recipe names (`family`,
  `work-os`, `personal`) describe the *vault's purpose*; a reader
  who hits the new mission first might briefly expect them to
  describe the *kit user*. The naming is still defensible (the
  kit user is the author in all three; the recipes shape vaults
  for those audiences), but the README and tutorials may need to
  be more explicit about this distinction. Light cost, probably a
  one-line addition in §Recipes.

## Alternatives

Four ways to resolve the tension. This RFC picks the second; the
others are recorded so the choice is explicit.

### (A) Soften Principle 5 to "library at the core, application at the edges"

Reframe Principle 5 to permit application-shaped surfaces on top of
the library — a bootstrap wizard, named outcome verbs, a starter
repo — with explicit rules for what crosses the line.

*Why rejected.* Principle 5 is doing real load-bearing work. It
blocks the kit from becoming an LLM wrapper, an orchestrator, a TUI
framework, or a recipe-selector — and it does so because the line
is sharp. "Application at the edges" is by construction a soft
line; the "explicit rules for what crosses" would either codify
exactly the set of recent PRs (which is the strongest possible
evidence the reviewer's drift-not-deliberation concern is correct)
or be vague enough to license anything. The reviewer's adversarial
question becomes structurally unanswerable: any future application-
shaped spec gets to argue "this is at the edge, like the other
things." The principle stops being a tiebreaker.

A milder variant — "soften Principle 5 but require a new ADR per
edge surface" — replaces the soft line with procedural ceremony.
That's the worst of both worlds: it doesn't sharpen the boundary,
and it adds a tax to every future product-shaping spec.

### (B) Narrow the mission to the engineering-comfortable author (this proposal)

Picked. See §Proposal.

### (C) Author/user split as a third framing

Distinguish *vault author* (engineering-adjacent) from *vault user*
(potentially non-engineer). The mission claims to serve both; the
charter spells out which one the kit's surfaces are designed for.

*Why rejected.* This is option B with a thinner skin. The mission
sentence ends up saying "the kit serves the author so the author
can serve the user", which is exactly what option B says — it just
keeps the word "non-engineer" in the mission text for sentiment.
The sentiment cost (loss of romanticism) is paid; the clarity
benefit (an explicit primary audience) is given back. Pick one role
for the mission to address; option B's role is the right one.

### (D) Do nothing — let the tension keep getting re-resolved spec-by-spec

The current status quo. Every product-shaping spec writes its own
"Tension to name" section; the kit's marketing-shaped claims and
its actual day-1 surface drift apart; the Tier 2 audience never
gets a home.

*Why rejected.* The tension is paying interest. Two specs already
have multi-paragraph defenses against Principle 5; future specs
will add more. Either the charter eventually breaks (someone lands
a charter edit "as part of an unrelated PR" because the friction
has become intolerable — exactly the kind of drift the charter's
"revise via RFC" protocol exists to prevent), or the kit keeps
growing apologetic spec sections forever. Inaction is the worst
option not because it's wrong on the merits but because it lets
the merits go unargued indefinitely.

## Drawbacks

The honest costs of accepting this RFC.

- **The "for a family" pitch loses force.** The current mission
  has genuine emotional resonance — a family keeping a useful wiki
  is a better story than an engineering-adjacent author
  maintaining one. This is a real cost. Mitigation: the new
  mission still describes the family's *vault*; only the
  *audience* shifts. The story can still be told; it just has to
  be honest about who installs the kit.
- **It reads as a retreat.** "We said non-engineers; now we say
  engineers" is open to a "they gave up" reading. Mitigation:
  Principle 1 (honesty over capability) is the kit's most-cited
  value; admitting the audience reality is *applying* the
  principle, not violating it. The reviewer should land the
  framing deliberately, not apologetically.
- **The starter-repo handwave defers real work.** Naming "Tier 2
  audiences will be served by a future starter repo" creates an
  obligation the project may or may not honor. Mitigation: the
  RFC does not commit to *building* the starter; it names it as
  the honest target if and when the project chooses to serve
  Tier 2. Naming is cheaper than building, and a named target is
  easier to resist over-promising against.
- **A future maintainer may re-litigate.** Charter revisions are
  revisable. Someone may, in a year, decide the kit should serve
  non-engineers directly and propose another RFC reversing this
  one. Mitigation: that's the protocol working as intended. The
  cost of the relitigation is paid by the future RFC's authors,
  not by today's.
- **Some Principle-5-defending spec sections become excess
  freight.** `outcome-named-entry-points/spec.md` and
  `wiki-bootstrap/spec.md` each have a §"Tension to name" that no
  longer needs to do principle-defense work. Mitigation: leave
  them as-is; spec history is a feature. Future specs simply
  won't need to write the equivalent section.

## Unresolved questions

Phrased as questions so reviewers can take a position.

- **Should the new mission text explicitly name the Tier 2 audience
  (true non-engineers) and the starter-repo path, or keep the
  charter focused on the primary audience and let the roadmap
  handle Tier 2?** This RFC's proposed text names Tier 2 in a
  third paragraph. A tighter alternative is to drop that paragraph
  and leave the Tier 2 acknowledgment in `docs/ROADMAP.md` only.
  The cost of keeping Tier 2 in the charter is verbosity; the cost
  of dropping it is that the charter loses the explicit
  acknowledgment that the project sees the audience and has chosen
  not to serve them directly yet.
- **Does Principle 6 ("eat our own dogfood") need a one-sentence
  clarification, or is the existing wording sufficient under the
  new mission?** This RFC proposes a one-sentence clarification.
  A reviewer who reads Principle 6 today and sees no ambiguity may
  prefer to leave it alone.
- **Should the README's §"Quick start" be restructured, or just
  reworded?** Restructuring (e.g. lifting the "if you don't have
  Python set up" path out of the front page) is more invasive but
  more honest. Rewording is cheaper and lower-risk. This RFC
  proposes rewording only and defers any restructuring to a future
  README pass.
- **Do the recipe names need clarification (e.g. a §Recipes
  preamble explaining "the recipe names describe the vault, not
  the kit user")?** Probably yes, but the cost is small and the
  follow-up PR can decide on a one-line addition without further
  RFC.

## Outcome

To be filled in when the RFC is accepted, rejected, or withdrawn.
Lists the follow-up PRs (charter edit, README rephrase, roadmap
note) that came out of this RFC.
