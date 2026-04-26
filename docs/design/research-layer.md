# Research Layer Design

The kit's third pattern (alongside Capture and Operate) is a Research Layer for multi-source, multi-week investigations toward an actionable verdict. Both variants instantiate the same architecture; only the domain content differs.

This pattern is grounded in the **Unified Research Framework** that consolidates professional ontologies of science (the "Truth" model) and investment analysis (the "Alpha" model). The shared insight: every effective research effort has a **central claim**, a structured **ontology** (Entities → Attributes → Mental Model → Verdict), a phased **workflow** (Capture → Sieve → Synthesize → Feedback), and a **verification discipline** (Two-Source Rule + chronology + adversarial read).

## Why a research layer

Most things in the wiki are *facts* (recipes, specs, ADRs, medical visits). Research is different — it's a *process* of investigating an open question with a defined verdict shape. The kit's existing capture path handles individual sources; the operate path handles wiki → wiki composition. Neither is enough on its own:

- A one-off `ingest-website` produces a research-brief page with no enclosing project. Five articles on the same topic become five orphan pages.
- A `cross-project-synthesis` operation refreshes a domain page from already-captured wiki state. It doesn't capture *new* sources or shape a verdict.
- A multi-source decision (which AI code assistant? which neighborhood? which heat pump?) needs both — accumulated capture *and* synthesized verdict.

The Research Layer composes capture and operate around a structured project, preventing the rabbit-hole failure ("just one more source") and the single-source-mistake failure ("the one article said so").

## Ontology: the four pillars

Every research project uses the same four pillars regardless of domain:

| Pillar | Definition | Purpose |
| --- | --- | --- |
| **Entities** | the "nouns" of the research | define the scope of what's being studied |
| **Attributes** | measurable qualities of the entities | enable objective comparison and filtering |
| **Mental Model** | rules of how this domain works (cause-and-effect) | predict implications of new evidence |
| **Verdict** | the actionable selection | translate research into a specific decision |

Each pillar lives as its own page inside the research project's folder:

```
wiki/research/2026-04-25-ai-code-assistants/
├── overview.md       # Central claim, phase, verdict shape, status
├── entities.md       # Cursor, Cline, Claude Code, GitHub Copilot, …
├── attributes.md     # Speed, context-window, accuracy, cost, IDE integration
├── mental-model.md   # RAG vs long-context vs agentic; how each handles "context"
├── verdict.md        # Selected: Claude Code; backup: Cursor; verification trail
├── artifact.md       # Capabilities matrix (the verdict_shape declared upfront)
├── sources/          # Per-source pages tagged with pillar_contributions
└── feedback.md       # Post-feedback notes (only after phase = feedback)
```

The structure is **identical for work and family** research projects. Both variants land research efforts in `wiki/research/{YYYY-MM-DD}-{slug}/` at the vault root. The convention is consistent so a researcher moving between vaults sees the same shape.

## Workflow: the four phases

Each research project moves through phases tracked in the overview's `phase:` frontmatter.

### Phase 1: Capture

Goal: collect everything into the project's `sources/` folder. Don't organize yet.

Per the framework: "the 48-hour sweep" — a focused burst of accumulation, not the project's whole lifespan. After 48-72 hours of capture, move to Sieve. New sources can still be added during Sieve and Synthesize, but the bulk should be captured upfront so Sieve has enough material to organize.

Tools used:
- [[ingest-website]] for articles, blog posts, vendor docs, news
- [[ingest-document]] for PDFs, white papers, brochures
- [[research]] for API-backed research sources — the orchestrator picks the right provider based on question semantics, the active project's pillar gaps, and the providers enabled in `.claude/research-providers.yaml`. Built-in providers: Perplexity (current-state web), Semantic Scholar (academic literature), Gemini Deep Research (long-form strategic synthesis; work-variant default). Adding a new provider is a config + script-branch addition, not a new skill.

Each captured source lands at `sources/{source-slug}.md` using the `_templates/research-source.md` template, with `pillar_contributions:` frontmatter declaring which pillars it informs.

### Phase 2: Sieve

Goal: sort the source pool into the four pillars. Archive what doesn't fit.

The [[research-sieve]] operation reads `sources/*.md`, groups contributions by pillar, and writes:

- `entities.md` — the catalog, with pointers to every source that mentions each entity
- `attributes.md` — comparable specs across entities, with sources
- `mental-model.md` — the rules, with sources for each rule
- `verdict.md` — early candidates with sources (refined later in Synthesize)

Anything that doesn't fit a pillar goes to `sources/_archive/`. The discipline: discard 90% of information that doesn't directly support or refute the central claim.

### Phase 3: Synthesize

Goal: produce the artifact (Matrix, Shortlist, or Blueprint).

The [[research-synthesize]] operation reads the four pillar pages and produces `artifact.md` using the template that matches the project's declared `verdict_shape:`:

| `verdict_shape` | Artifact template | Use when |
|---|---|---|
| `matrix` | `_templates/research-matrix.md` | Comparing N alternatives across consistent attributes (vendor selection, tool eval, capability comparison) |
| `shortlist` | `_templates/research-shortlist.md` | Ranked candidates with rationale (home purchase, school choice, vacation destination, hire finalists) |
| `blueprint` | `_templates/research-blueprint.md` | Spatial / structural arrangement (kitchen layout, room redesign, architecture diagram) |

The shape is **declared upfront** at research-start time so capture and sieve know what to optimize for. Changing shape mid-project is allowed but expensive — it means re-sieving against different criteria.

### Phase 4: Feedback

Goal: test the verdict in the real world.

Per the framework: "the small-scale test" — try the tool's free tier, visit the suburb at 8 AM Monday, tape out the pantry layout. Capture the test results in `feedback.md`. If results contradict the verdict, set `verdict_status: challenged` and re-enter the loop (typically Sieve, sometimes Capture). Otherwise close the project (`status: archived`).

Feedback is the difference between a research artifact and a real decision. Skip this phase and the verdict is hypothetical.

## Verification

Two disciplines from investigative journalism, both encoded structurally in the kit.

### Two-Source Rule

Every load-bearing claim in `verdict.md` and `artifact.md` must cite **at least two corroborating sources** from `sources/`. Single-sourced claims are flagged with `> [!warning] Single-source` callouts, not silently merged.

This is mechanical, not subjective:

- The lint skill flags single-sourced verdict claims at scan time
- Each source page declares its `verification_strength: primary | secondary | hearsay`; the agent prefers primary sources for load-bearing claims
- The `verification_count` field on the project's overview tracks how many verdict claims have ≥2 corroborating sources — one of the stop signals

Most lightweight research efforts skip this rule and pay the cost of being wrong on the load-bearing claim. The kit doesn't.

### Chronology

Each source page tracks:

- When the source was published (`published_at:`)
- When the events the source describes happened (`events_described:`)
- Whether claims are still current

A 2023 benchmark of AI code assistants is not a current data point in 2026; the source page makes this explicit so Synthesize can weight or discard appropriately.

### Adversarial Read

Every source page has an `## Adversarial Read` section: what's missing, biased, or possibly misleading; what counter-source is needed. This forces the researcher to engage with each source critically rather than collect uncritically.

## Stop conditions: passive verdict-check

The framework's most useful discipline is "stop the moment the verdict is clear." The kit encodes this **passively**:

The [[research-verdict-check]] operation runs **on demand** (not interrupting captures, not auto-progressing phases) and reports:

- Current `verdict_status` (open / crystallizing / clear / challenged)
- Source count + diminishing-returns signal (are recent sources adding new pillar contributions, or just confirming?)
- `verification_count` vs. verdict-claim count (load-bearing-claim corroboration ratio)
- Recommendation: continue capture / move to sieve / move to synthesize / stop

The user runs verdict-check periodically; the operation surfaces a recommendation. **Decision authority stays with the human.** The operation does not block captures, does not autonomously advance phases, does not refuse to run more captures. The framework's "stop" rule is a discipline, not a gate.

## Composition with capture and operate

The Research Layer doesn't replace Capture or Operate — it composes them.

- **Capture remains the source-acquisition primitive.** Research sources come from the same `[[ingest-website]]` and `[[ingest-document]]` skills used elsewhere; they just land in a research project's `sources/` folder rather than free-floating in `raw/`. The [[research]] orchestrator is a content-type ingester that wraps API-backed providers — Perplexity, Semantic Scholar, Gemini Deep Research — and applies research-source schema tagging. Providers are config-driven (`.claude/research-providers.yaml`); the orchestrator picks among enabled providers based on question semantics and budget. Adding a new provider is a config + script-branch addition, not a new skill.
- **Operate remains the wiki → wiki primitive.** The four research-phase operations ([[research-start]], [[research-sieve]], [[research-synthesize]], [[research-verdict-check]]) are operations in the operate-loop sense — they read structured pages, compose, write derived pages.

The Research Layer's contribution is a *coordinated sequence* of captures and operations, structured by the 4-pillar ontology and phase progression.

## Per-variant instantiation

The architecture is identical; the domain examples differ.

### Work variant: research projects

Common research efforts in an engineering team:

- **Tool / vendor evaluation.** Verdict shape: matrix. Example: "Evaluate AI code assistants for the team."
- **Architecture pattern decision.** Verdict shape: matrix or shortlist. Example: "Pick a stream-processing engine for the order pipeline."
- **Hire / team-build research.** Verdict shape: shortlist. Example: "Shortlist five candidates for the senior platform engineer role."
- **Customer / market research.** Verdict shape: shortlist or matrix. Example: "Top three SMB customer segments for our Q3 push."

Research feeds into:
- [[domains/]] pages (when a research effort produces durable cross-project learning)
- [[playbooks/]] (when the research produces a reusable methodology)
- [[tools/]] (when the verdict is a tool selection — the research-matrix becomes the tool eval)

### Family variant: research projects

Common research efforts in a household:

- **Major purchase decisions.** Verdict shape: matrix or shortlist. Examples: "Pick a heat pump"; "Choose a minivan."
- **Home / location decisions.** Verdict shape: shortlist. Examples: "Suburb shortlist for relocation"; "Three pediatricians worth interviewing."
- **Educational decisions.** Verdict shape: shortlist or matrix. Examples: "Compare three high schools for Mia"; "Summer-camp options for Jake."
- **Medical research.** Verdict shape: matrix or shortlist. Examples: "Compare three orthodontic treatment options"; "Specialist shortlist for chronic-condition workup."
- **Home systems.** Verdict shape: blueprint. Examples: "Kitchen pantry zone layout"; "Garage tool storage flow."
- **Major vacations.** Verdict shape: shortlist. Example: "Three viable destinations for spring break."

Research feeds into:
- `wiki/home/decisions/` (when the verdict shapes a household decision record)
- `wiki/health/` (when medical research informs ongoing care)
- `wiki/food/dietary-notes` (when food research updates allergen / preference info)

## Failure modes

- **The "browsing" failure.** No central claim. Captures accumulate; sieve never happens; verdict never crystallizes. Mitigation: the `central_claim:` frontmatter field is required at research-start; without it, the operation refuses to scaffold.
- **The "rabbit hole" failure.** Capture phase never ends. Mitigation: passive verdict-check signals diminishing returns; researcher reads the signal and chooses to stop or continue.
- **The "single-source mistake" failure.** Verdict's load-bearing claim has only one source, and that source is wrong, biased, or outdated. Mitigation: Two-Source Rule enforced via `verification_count` and lint flags.
- **The "stale verdict" failure.** Verdict was correct when synthesized but the world has moved. Mitigation: archive verdicts with date; re-research when revisiting.
- **The "wrong shape" failure.** Project declared `verdict_shape: matrix` but the actual decision is structural / spatial (blueprint). Mitigation: `verdict_shape` is changeable; operation cost makes it a deliberate choice.
- **The "ingest creep" failure.** A casual web ingest gets pulled into a research project that doesn't exist. Mitigation: when a research-source ingester runs without an active project, the orchestrator asks "save as one-off research brief, or start a new research project (run [[research-start]])?"

## Worked example: AI code assistants research (work variant)

A worked example showing the full lifecycle.

**Day 1 — research-start:**
The user invokes [[research-start]]: *"Should we adopt a new AI code assistant for the team? Hypothesis: Claude Code's speed advantages outweigh GPT-4's plugin ecosystem. Verdict shape: matrix."*

The operation scaffolds `wiki/research/2026-04-25-ai-code-assistants/` from `_templates/research-project.md` with:
- `phase: capture`, `verdict_status: open`, `verdict_shape: matrix`
- `central_claim: "Claude Code's speed advantages outweigh GPT-4's plugin ecosystem for our team's workflow."`
- Empty pillar pages and an empty `sources/` folder

**Days 1-3 — Capture:**
The user feeds 12 sources via [[ingest-website]] and [[research]] (which dispatches to Perplexity for vendor benchmarks and Semantic Scholar for academic context-window papers): vendor docs (Cursor, Cline, Claude Code, Copilot, Aider, Continue), benchmark articles, two academic papers on context-window utilization, two team-internal trial reports.

Each lands at `sources/{slug}.md` with `pillar_contributions: [entities, attributes]` etc.

**Day 4 — research-sieve:**
[[research-sieve]] reads all 12 source pages and sorts contributions:
- `entities.md`: 6 tools listed with brief descriptions and per-source citations
- `attributes.md`: speed, context window, accuracy on real PRs, IDE integration, cost, agent capabilities, plugin ecosystem
- `mental-model.md`: RAG vs long-context vs agentic loops; how each handles cross-file context
- `verdict.md`: top candidates ranked, sourced

**Day 5 — research-verdict-check (passive):**
The user runs [[research-verdict-check]]. It reports: 4 of 6 attribute claims corroborated by 2+ sources; `verdict_status: crystallizing`; recommendation: capture 2 more sources for the under-corroborated attributes, then synthesize.

The user adds 2 targeted sources, then proceeds.

**Day 6 — research-synthesize:**
[[research-synthesize]] reads pillars, produces `artifact.md` from `_templates/research-matrix.md`:
- 6 tools × 7 attributes
- Verdict: Adopt Claude Code; backup Cursor
- Verification trail: each load-bearing matrix cell links to ≥2 sources; `verification_count: 7`

**Days 7-21 — Phase 4: Feedback:**
Team uses Claude Code free tier for 2 weeks. Captured trial results land at `feedback.md`. Results align with the verdict; status moves to `archived`. The artifact gets cross-linked into [[wiki/tools/claude-code]] and the relevant [[wiki/playbooks/ai-code-assistant-eval]].

**Total cycle:** ~3 weeks from start to verdict to validated feedback.

The same shape applies to family research — the artifact differs (a kitchen-pantry blueprint instead of a tool matrix), but the workflow, ontology, and verification discipline are identical.
