# Conventions

> How we work on this repo. The companion to `AGENTS.md` — that file tells
> agents *what* to do; this file explains the lifecycle and mechanics behind
> the docs they reference.
>
> Substantive changes to this file go through an RFC. Trivial fixes (typos,
> broken links, clarifications) land as normal PRs.

## The doc hierarchy

| Doc kind | Lives in | Status | Changes via |
|---|---|---|---|
| Charter | `docs/CHARTER.md` | Frozen | RFC |
| ADR | `docs/adr/NNNN-*.md` | Frozen once accepted | New ADR that supersedes |
| RFC | `docs/rfc/NNNN-*.md` | Living until accepted, then frozen | Edit while open; supersede when closed |
| Spec | `docs/specs/<thing>/spec.md` | Living | Edit in the same PR as the code |
| Plan | `docs/specs/<thing>/plan.md` | Living until done | Edit while implementing |
| Architecture | `docs/architecture/` | Living | Edit when layout or modules change |
| Concept / how-to / reference / tutorial | `docs/{concepts,how-to,reference,tutorials}/` | Living | Normal PR |
| Roadmap | `docs/ROADMAP.md` | Living | Normal PR; substantive shifts via RFC |

The two-axis distinction is **frozen vs. living** and **decision vs. plan**.
ADRs and the charter are frozen — once accepted, they record what we
believed at a point in time, and they get superseded rather than edited.
Specs, plans, and architecture are living — they describe current truth
and must be kept in sync with the code.

## ADR vs. RFC vs. spec — when to use which

- **ADR** — we decided something load-bearing and want the decision to
  survive personnel turnover. Past tense. "We chose X because Y." Frozen
  once accepted; superseded by a new ADR when wrong.
- **RFC** — we're proposing a change and want feedback before committing.
  Future tense. "We should do X because Y." Lives in `rfc/` open for
  comment; on acceptance, produces ADRs and specs and is itself archived.
- **Spec** — the contract for one piece of the kit. Present tense. "This
  thing takes X, returns Y, holds invariant Z." Updated alongside the
  code; spec/code drift is a bug.

If you're not sure: **ADR for one-off decisions, RFC for changes that
need review, spec for ongoing definition.** When in doubt, ask in the PR.

## Numbering

- ADRs: `0001-`, `0002-`, … globally monotonic. Don't reuse numbers,
  even for withdrawn ADRs (mark them `Status: Withdrawn` and skip the
  number).
- RFCs: same scheme, separate sequence.
- Specs: no numbering — directory name `docs/specs/<thing>/` is the
  identifier.

## File naming

- ADRs: `NNNN-<kebab-case-title>.md`
- RFCs: same
- Specs: each in its own directory under `docs/specs/`, with `spec.md`
  and (optionally) `plan.md` inside.

## What counts as "load-bearing" (ADR-worthy)?

A decision is load-bearing if:

- It would be expensive to reverse (cost of switching > cost of the
  current path × 2).
- Future code will reference it as a constraint ("we can't add X because
  ADR-NNNN says…").
- Reasonable people would disagree, and we need a tiebreak the next time
  the question comes up.

Examples of load-bearing decisions in this repo: rendering engine
(`ADR-0001`), state-truth model (`ADR-0002`), shared-file write model
(`ADR-0003`), drift-detection model (`ADR-0004`), schema model
(`ADR-0005`).

Examples of NOT load-bearing: which test framework to use (pytest is
the default; switching is local), which CLI library (Click vs. argparse,
local), formatting choices (ruff config).

## How to add an ADR

1. Copy `docs/_templates/adr.md` to `docs/adr/NNNN-<title>.md` with the
   next free number.
1. Fill in context, decision, consequences, alternatives.
1. Mark `Status: Proposed`.
1. Open a PR that adds the ADR alongside the change it justifies.
1. On merge, change `Status:` to `Accepted` and don't touch it again.

## How to add an RFC

1. Copy `docs/_templates/rfc.md` to `docs/rfc/NNNN-<title>.md`.
1. Mark `Status: Open for comment`.
1. Open a PR. The PR is the discussion thread.
1. When ready to decide: either land the PR with `Status: Accepted` and
   the ADRs/specs/code it produces, or close with `Status: Rejected` or
   `Withdrawn` and a one-paragraph rationale.

## How to add a spec + plan

1. Create `docs/specs/<thing>/`.
1. Copy `docs/_templates/spec.md` to `spec.md`, fill it out.
1. Copy `docs/_templates/plan.md` to `plan.md`, fill it out — but only
   if the work needs more than one PR. For a single-PR change, the plan
   is overhead.
1. Reference the spec from the code (a module-level docstring is fine).
1. Keep them in sync as the code evolves.

## Commit messages

During v2 development: `v2: task <N> - <one-line summary>` where N is
the task number from `docs/rfc/0001-v2-architecture.md`.

After v2: conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`,
`test:`, `chore:`) with the affected module in parens when useful:
`fix(journal): handle empty file as zero events`.

## PR scope

- **One task per PR.** Migration tasks each get one PR. Don't bundle.
- **Spec and code together.** If you're changing behavior, the spec and
  any affected docs change in the same PR.
- **ADRs are their own PR or rolled into the PR that motivated them.**
  Whichever produces clearer history.

## Tests as the bar for "done"

A task is done when the acceptance criteria pass — not when the code
compiles or "looks right." For migration tasks, acceptance criteria
come from the migration RFC. For everything else, from the spec.

The mechanical gates (`pytest`, `ruff`, `mypy`) catch the cheap problems
before review. They're necessary, not sufficient.

## When this file is wrong

Same rule as AGENTS.md: flag drift, don't work around it. The
conventions exist to make the work boring and predictable. If they're
producing friction without value, fix them — via RFC for substantive
shifts, normal PR for cleanups.
