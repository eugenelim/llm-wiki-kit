---
name: research-synthesize
description: "Phase-3 research operation. Read pillar pages in an active project and produce artifact.md using the template that matches the project's declared verdict_shape (matrix / shortlist / blueprint). Enforces the Two-Source Rule on load-bearing claims. Use after research-sieve has populated the four pillars, when research-verdict-check reports the verdict has crystallized, or on request: \"synthesize the research\" / \"produce the artifact\"."
license: MIT
metadata:
  variant: shared
---

# Research Synthesize Skill

Phase-3 operation. Reads the project's pillar pages and produces `artifact.md` using the template that matches the project's declared `verdict_shape:`. Enforces the Two-Source Rule on load-bearing claims.

## When to Use

- After [[research-sieve]] has populated the four pillar pages
- When the user invokes "synthesize the research" or "produce the artifact"
- After [[research-verdict-check]] reports the verdict has crystallized

## Inputs

User provides:

- Project slug or path. If absent, defaults to the most-recently-modified research project.

Reads:

- `wiki/research/{slug}/overview.md` — verdict_shape, central claim, current phase
- `wiki/research/{slug}/entities.md`, `attributes.md`, `mental-model.md`, `verdict.md` — the four pillars
- `wiki/research/{slug}/sources/*.md` — for verification trail and chronology
- The corresponding artifact template:
  - `_templates/research-matrix.md` if `verdict_shape: matrix`
  - `_templates/research-shortlist.md` if `verdict_shape: shortlist`
  - `_templates/research-blueprint.md` if `verdict_shape: blueprint`

## Algorithm

1. **Validate phase.** If `phase != synthesize`, surface a warning. The expected progression is capture → sieve → synthesize.

2. **Validate verdict_shape.** Must be set on the overview. If absent or invalid, refuse and ask the user to declare.

3. **Compose artifact body** based on shape:

   - **Matrix** — entities × attributes. Each row is an entity from `entities.md`; each column is an attribute from `attributes.md`. Cells cite the source(s) that established the value. Verdict at the top references the strongest cells.
   - **Shortlist** — ranked candidates from `verdict.md`. For each, draw anchors from `mental-model.md` and supporting attributes from `attributes.md`. Verdict cites top pick + backup with load-bearing claims.
   - **Blueprint** — zones from `entities.md` (where each entity is a zone), placement principles from `mental-model.md`, flow map composed from attributes that describe activity flow. Verdict states the layout and key principle.

4. **Apply Two-Source Rule.** For each load-bearing claim in the artifact:
   - Count corroborating sources (sources whose `pillar_contributions:` includes the relevant pillar AND whose body asserts the claim)
   - If count ≥ 2: include the claim with `[[sources/{a}]], [[sources/{b}]]` citations
   - If count == 1: include the claim with `> [!warning] Single-source` callout AND list the missing-corroboration on the project's verdict page
   - If count == 0: don't include the claim; flag for user attention

5. **Apply chronology weighting.** When two sources contradict and one is older than 12 months while the other is current, prefer the current — but cite both with chronology note.

6. **Compute `verification_count`.** Number of artifact claims with ≥2 corroborating sources.

7. **Write `artifact.md`** at `wiki/research/{slug}/artifact.md` using the verdict_shape's template, with sections populated.

8. **Update `overview.md`:**
   - `phase: feedback`
   - `verification_count: {N}`
   - `verdict_status: clear` if verification ratio > 80%; otherwise `crystallizing`
   - Phase log: `{today}: research-synthesize (artifact: {shape}; verification_count: {N}; status: {status})`

## Output

The `artifact.md` page, plus updated overview frontmatter.

A summary to the user:

```
Synthesis complete for {project}:

Artifact: research-{shape} → wiki/research/{slug}/artifact.md
Verdict: {summary}
Verification: {N} of {M} claims corroborated by ≥2 sources ({pct}%)
Single-sourced claims: {K} (flagged with > [!warning] callouts)
Phase: feedback (next: small-scale test in the real world)
```

## Side-effects

1. **Append to `log/changelog.md`**: "Research synthesized: [[research/{slug}/artifact]]."
2. **Cross-link from related wiki pages.** If the verdict's top pick already has a wiki page elsewhere (e.g., `wiki/tools/claude-code` for a tool eval), append a backlink to the artifact.

## Interactive Review

Before writing the artifact, present:

```
Synthesis preview for {project} (verdict_shape: matrix):

Verdict (proposed): Claude Code (backup: Cursor)

Artifact will include:
  - 6 entities × 7 attributes
  - Verification trail: 5 of 7 attributes have ≥2 corroborating sources
  - Single-source claims (flagged): "agentic capabilities" and "plugin ecosystem"
  - Contradictions resolved (chronology): "Cursor context window" — accepting
    1M (2026 source) over 200K (2025 source)

Open questions to carry into Feedback phase:
  - Real-world performance at team scale (untested)
  - Long-term cost trajectory

Save artifact?
```

The user confirms, adjusts the verdict, or sends specific claims back to the verdict pillar for re-review.

## Failure Modes

- **Verdict pillar empty.** No verdict to synthesize from. Refuse and surface: "Verdict pillar has no candidates. Continue capture / sieve before synthesizing."
- **All claims single-sourced.** Verification is weak. Either accept the artifact with flagged warnings (user choice) or recommend more capture targeting under-corroborated claims.
- **verdict_shape mismatch with pillar content.** E.g., `matrix` declared but `entities.md` has only 2 entities (matrix needs 3+). Surface: "Matrix shape works best with 3+ entities. Switch to `shortlist`?" — let user decide.
- **Existing artifact already written.** If `artifact.md` exists from a prior synthesize run, ask whether to overwrite or version.

## Cadence

- **Once per research project:** Synthesize is the second-to-last phase. Re-synthesize only if Feedback challenges the verdict and Sieve produces meaningfully different pillar content.
- **No automation:** Synthesize is deliberate; the artifact represents a decision.
