# Extending the kit: upstream PR or sideload

This guide is for contributors deciding *where a new primitive should
live*. The mechanics — file shapes, install paths, CI gates — are in
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md) at the repo root and in
[`docs/guides/how-to/add-a-primitive.md`](../how-to/add-a-primitive.md).
This document is the *why* behind the two paths.

## Two paths, one catalog

The kit's primitive catalog grows from two sources:

1. **Bundled primitives** under `templates/<kind>/<name>/` in the kit
   itself. These ship with the wheel; every kit install gets them.
   The hand-curated kit catalog is small, audited line-by-line, and
   bound by the shipped recipes (`family`, `work-os`, `personal`).

2. **Sideloaded primitives** living inside a separate Python package
   the user installs alongside the kit. The kit discovers them
   through the `wiki-primitive` entry-point group at runtime —
   `importlib.metadata.entry_points(group="wiki-primitive")` returns
   every installed package that ships primitives.

The two paths produce the same end shape: a primitive in a vault. The
difference is *where the primitive's source of truth lives* and *who
audits it*.

## Why two paths exist

`docs/CHARTER.md` Principle 4 frames the kit as a "common core plus
droppable primitives." Principle 5 names it library-not-application:
the kit retains the dispatch surface; primitives are inputs to that
surface, not surfaces themselves.

The bundled-only model honoured Principle 4 only for primitives the
kit ships. A contributor with a domain-narrow primitive
(`ingest-dnd-session-notes`, `ehr-followup`, `competitor-brief`) had
two unworkable options: open an upstream PR — which the maintainer
shouldn't merge, because no kit-shipped recipe should bind a primitive
that surprises the recipe's typical user — or fork the kit and carry
a patch across every upgrade. Both options have prohibitive cost; the
domain-narrow primitive never gets written.

Sideload adds a third option that respects both principles:

- Principle 4 is honoured fully: the catalog grows for the user, but
  *additively* — sideloaded primitives never replace or override
  bundled ones.
- Principle 5 is honoured: the kit still owns the dispatch surface.
  A sideload package ships content (manifests, snippets, SKILL.md
  fragments) plus declarative dispatch metadata; it never ships a
  Python callable the kit invokes. The kit reads templates from a
  filesystem path, runs the same Pydantic validators, applies the
  same outcome-verb gates, writes through the same `safe_write`.
  Discovery is "package name → templates path," never "package name
  → function pointer."

## What each path costs

### Upstream PR

- **For the contributor.** Write the primitive, write the seed page,
  open a PR, wait for review. CI runs the merged catalog through
  every gate (outcome verb shape, SKILL fragment, region collision,
  starter seed coverage). If the primitive's vocabulary is generic
  and its seed coverage is real, review is fast.
- **For the kit.** Every accepted upstream primitive is permanent
  surface — it ships in every install forever. The kit's hand-curated
  catalog stays small and audited because the bar is the three
  questions of the decision tree.

### Sideload

- **For the contributor.** Stand up a Python package with a
  `templates/` directory and an entry-point declaration in
  `pyproject.toml`. The package needs its own tests, its own release
  cadence, its own pinned compatibility range against the kit
  (`llm-wiki-kit>=2.1,<3`). The kit cannot help with eval coverage
  for sideloaded primitives — that's the package author's problem.
- **For the kit.** Every CLI invocation pays the entry-point
  enumeration cost (typically tens to a few hundred milliseconds on
  first call, environment-dependent — see the spec on why the kit
  doesn't pin a numeric budget). The merged catalog runs through the
  same gates that bundled primitives run through, so install-time
  validation still fires.

## When each path is right

The decision tree in
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md) is the rule. The shape
behind the rule:

- **Upstream PR** when the primitive's *vocabulary* is generic enough
  that a typical user of any shipped recipe could plausibly use it.
  "Meeting" and "recipe" and "trip" pass the test; "DnD session" and
  "competitor brief" don't.
- **Sideload** when the primitive serves an audience the kit's
  shipped recipes don't target. Domain-narrow primitives, work-
  specific operations, personal vocabularies — anything where forcing
  the kit's bundled recipes to bind it would surprise users of those
  recipes.

The grey zone — a primitive that *could* go either way — should default
to sideload first. The cost of moving a primitive from sideload to
upstream later (rename, file move, open a PR) is small; the cost of
moving it the other direction (depublish a bundled primitive, migrate
existing vaults) is large.

## What "additive-only" buys us

The kit rejects every form of override at the sideload boundary:

- Name collision (sideload provides a primitive named the same as a
  bundled one) → load-time error.
- Region override (sideload contributes to a managed region a bundled
  primitive already owns) → install-time error.
- SKILL directory shadow (sideload ships `files/skills/<name>/` that
  matches a bundled SKILL) → load-time error.
- Outcome verb duplicate (sideload declares a verb already in the
  bundled namespace) → load-time error.

Each of these is a hard refusal, not a silent shadow. That keeps the
"common core + droppable primitives" framing honest: a user reading
their vault's output knows which bytes the kit shipped and which a
sideload package contributed, and there's no path for a sideload
package to quietly redefine the kit's behaviour. Override is
fork-the-kit territory; sideload is *extension* territory.

The asymmetric `extra='ignore'` policy (sideloaded primitives accept
unknown fields; bundled ones reject) is the one place the kit
deliberately loosens. The asymmetry exists so a sideload package can
*forward-declare* a field in anticipation of a future minor kit
release without forcing a sideload-package release in the same window
the kit ships. The looseness stays visible: `wiki doctor` lists every
dropped field by package and primitive name, so a sideload package
shipping a *typo* ("outcoms" instead of "outcomes") shows up in the
diagnostic surface the moment a user runs `wiki doctor`.

## Further reading

- [`docs/specs/primitive-sideload/spec.md`](../../specs/primitive-sideload/spec.md)
  — the load-bearing contract.
- [`docs/rfc/0007-primitive-contribution-model.md`](../../rfc/0007-primitive-contribution-model.md)
  — the policy decision and its rationale.
- [`docs/CHARTER.md`](../../CHARTER.md) §Principles 4 and 5 — the
  principles the model honours.
