# AGENTS.md

> **This is the canonical agent context file.** `CLAUDE.md` is a symlink to this file.
> Cursor, Codex, Gemini CLI, and Copilot also read it (via their own discovery rules).
>
> Keep this file under ~200 lines. If you’re tempted to add to it, ask first whether
> the content belongs in `docs/`, `core/files/skills/`, or a subdirectory `AGENTS.md`.

## What this repo is

A Python package and template catalog for `llm-wiki-kit` — a kit for building
LLM-maintained markdown wikis (Karpathy’s LLM Wiki pattern, adapted), composed
from a common core plus a catalog of droppable primitives, configured by recipes.

The kit is **not** a wiki vault — it’s the tool that builds and maintains
vaults. End users pip-install it, then run `wiki init --recipe <name>` against
a folder to get a working Obsidian-compatible vault with skills, schemas, and
operations wired up.

The detailed map of what lives where is in [`docs/architecture/overview.md`](docs/architecture/overview.md). **Read it before exploring.** It will save you 20 minutes of grep.

## Source of truth

For each kind of decision, there is exactly one place it lives:

|Question                                                         |Where it lives                                                                            |
|-----------------------------------------------------------------|------------------------------------------------------------------------------------------|
|What is this project, and what’s in/out of scope?                |`docs/CHARTER.md`                                                                         |
|Why did we choose X over Y?                                      |`docs/adr/` (Architecture Decision Records)                                               |
|What should we change, and how?                                  |`docs/rfc/` (Request For Comments)                                                        |
|What exactly does this primitive / command / skill do?           |`docs/specs/<thing>/spec.md`                                                              |
|How will we build it, step by step?                              |`docs/specs/<thing>/plan.md`                                                              |
|How is the kit’s own code organized today?                       |`docs/architecture/`                                                                      |
|Where is the kit going next?                                     |`docs/ROADMAP.md`                                                                         |
|How do users use the kit?                                        |`docs/guides/{tutorials,how-to,reference,explanation}/` (Diátaxis; some existing user docs still live flat at `docs/guides/*.md` and migrate gradually)|
|How does Claude do `<repeating task>` *inside a vault*?          |The `core/files/skills/<task>/SKILL.md` files we ship (these are vault-side, not kit-side)|
|How does Claude do `<repeating task>` *while developing the kit*?|This file plus `docs/CONVENTIONS.md`                                                      |

If you can’t find the answer in one of these places, **the answer doesn’t
exist yet** — ask, or open an RFC. Don’t guess. Lifecycle and mechanics
(living vs. frozen, ADR vs. RFC, etc.) live in `docs/CONVENTIONS.md`.

## Two scopes, one repo

A frequent source of confusion: this repo contains both **kit-development context**
(which agents read when working on the kit’s Python code, templates, and docs)
and **vault-side skills** (markdown files under `core/files/skills/` and
`templates/*/files/skills/` that get *copied into a user’s vault* and read by
*their* Claude session).

- Reading **this `AGENTS.md`**? You’re an agent working on the kit. Follow the
  workflow below. Don’t touch a user’s vault.
- Reading **`core/files/skills/wiki-conflict/SKILL.md`** in a real wiki? You’re
  helping a user resolve a conflict in their vault. That context is separate.

Never let the two leak into each other.

## Workflow

For anything beyond a one-line edit, follow the **plan → execute → verify →
review** loop. Summary:

1. **Plan before acting.** For anything spec-shaped, read the spec first.
   For architecturally significant work, use Plan Mode and the agent’s
   deepest-thinking setting. Phrase every plan task as a verifiable goal,
   not a list of steps — the task name should be the success criterion.
1. **Tasks come from the migration plan.** During v2 development, every
   piece of work corresponds to a numbered task in
   `docs/rfc/0001-v2-architecture.md`. Pick one, do it, ship it. Don’t
   start a second task in the same session.
1. **Specs are validation gates, not write-once docs.** If implementation
   diverges from the spec, update the spec in the same PR. Drift is a bug.
1. **Verification before code.** Every task in the migration plan has
   explicit acceptance criteria. Translate them into tests *before*
   writing the implementation:
- **TDD** for `models.py`, `journal.py`, `write_helper.py`,
  `managed_regions.py`, `render.py`, `primitives.py`, `recipes.py` —
  pure functions, validation, parsing. Default.
- **Integration tests** for `wiki init`, `wiki add`, `wiki doctor`,
  `wiki ingest`, `wiki run` — run against a temp dir, assert on
  resulting files and journal state.
- **Evals** (`tests/evals/`) for skill triggering, operation outcomes,
  and provenance — drive Claude Code via subprocess against a fixture
  vault. These are slower and live in their own CI workflow.
1. **Run mechanical gates** (`ruff`, `mypy`, `pytest`) before declaring done.
1. **Self-review against the task spec.** Did you produce exactly the
   outputs listed? No more, no less? Did all acceptance criteria pass?
1. **One PR per task.** Commit message format: `v2: task <N> - <one-line summary>`.
1. **Capture what you learned** before opening the PR — into the right
   `AGENTS.md`, ADR, or `docs/guides/explanation/` doc.

## Commands you’ll need

```
pip install -e .[dev]       # one-time setup (installs runtime + dev deps)
pytest                       # run unit + integration tests (skips `slow` by convention; CI runs `pytest -m 'not slow'`)
pytest -m 'not slow'         # explicit opt-out (the CI invocation)
pytest -m slow               # wheel-acceptance suite (builds + installs the wheel)
pytest tests/unit            # unit tests only (fast)
pytest tests/evals           # eval suite (slow, also runs in separate CI workflow)
ruff check llm_wiki_kit/     # lint
ruff format llm_wiki_kit/    # format
mypy llm_wiki_kit tests      # type-check (note: includes tests/, matches CI)
wiki --help                  # exercise the CLI
```

## Runtime dependencies

The kit’s runtime deps are intentionally minimal: **`pyyaml` and `pydantic>=2`**,
plus stdlib. **Do not add a runtime dependency without writing a new ADR first.**
Dev dependencies (`pytest`, `ruff`, `mypy`) are unconstrained.

The single biggest reason to keep this tight is deployment: the kit ships to
end users who are not engineers (professional teams, families).
Every dep is a thing they could fail to install.

Pending future ADRs that will likely add a runtime dep: Docling (for
PDF/DOCX/PPTX ingest, Tier 1 roadmap), and possibly `sqlite-fts5` shims if
the search primitive grows past ripgrep.

## Skills available to you (kit-side, not vault-side)

Kit-side skills live at `.claude/skills/` (this is for agents working on
the kit’s own code, NOT for end users): `work-loop` is the entry point for
any non-trivial change. Workflow skills (`new-spec`, `new-adr`, `new-rfc`,
`bug-fix`, `update-conventions`) land in PR-2 of RFC-0002. Specialist
subagents at `.claude/agents/` — `adversarial-reviewer`, `quality-engineer`,
`security-reviewer`, `implementer` — are invoked per the work-loop SKILL.

Vault-side skills, copied into a user’s vault by `wiki init`, live under
`core/files/skills/` and `templates/*/files/skills/`. Different scope,
different audience, never mix.

## Things you should not do without asking

- **Don’t run destructive commands** (`rm -rf`, `git push --force`, dropping
  database tables) without explicit confirmation in the same turn.
- **Don’t edit `docs/CHARTER.md` directly** — substantive changes go through
  an RFC. Trivial edits (typos, broken links) are fine as a normal PR.
- **Don’t add runtime dependencies** without an ADR. Dependencies are forever.
- **Don’t fabricate APIs.** If you’re not sure a function exists, grep first.
  Inventing imports that “look right” wastes everyone’s time when the build fails.
- **Don’t create new top-level directories.** The structure is intentional. If
  you think a new one is needed, propose it in an RFC.
- **Don’t reach into a user’s hypothetical vault** during development. Tests
  use `tmp_path` fixtures or `tests/fixtures/*-vault/`. The kit’s code should
  never assume a vault path other than what’s explicitly passed in.
- **Don’t bypass `write_helper.safe_write()`** for any file write that lands
  in a user’s vault. Drift detection is load-bearing. (Documented exceptions:
  `write_helper.resolve_proposal` for user-mediated merges,
  `write_helper._ensure_obsidianignore` for the additive Obsidian-index
  config — see `docs/specs/safe-write-ordering/spec.md`.)
- **Don’t merge kit-side and vault-side skill scopes.** Repo-root `.claude/`
  is for the kit’s own development; `core/files/skills/` and
  `templates/*/files/skills/` are what `wiki init` copies into a user’s
  vault.

## When this file is wrong

Flag drift in your PR — don’t silently work around it. AGENTS.md vs. reality
drift is the biggest cause of agent quality decay. Substantive changes to
this file go through RFC; small fixes are normal PRs.

-----

*See `docs/CONVENTIONS.md` for the full conventions, or
`docs/architecture/overview.md` to start exploring.*
