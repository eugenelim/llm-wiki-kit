# Outcome-catalog fixture

Synthetic operation primitives used by `tests/unit/test_install_outcomes.py`,
`tests/integration/test_wiki_init_outcomes.py`, and
`tests/integration/test_wiki_upgrade_outcomes.py` to exercise the
outcome-named-entry-points installer pipeline without relying on
specific verbs in the shipped catalog. Tests against the fixture
catalog stay valid regardless of which shipped operations declare
`outcomes:` over time — see
`docs/specs/outcome-named-entry-points/` for the spec.

Two primitives:

- `operations/fixture-digest/` — well-formed operation declaring
  `outcomes: [prep-digest]`. Its `SKILL.md` description contains the
  verb verbatim, so the installer's SKILL-fragment validator passes.
- `operations/fixture-skill-missing/` — operation declaring
  `outcomes: [track-missing]`, but the matching `SKILL.md`
  description deliberately omits the verb. Used by negative-path
  tests for `install.validate_outcome_skill_fragments`.

Verb choices use stems already in
`llm_wiki_kit.primitives.OUTCOME_VERB_STEMS` (`prep-`, `track-`) so
no PR-1 constant edit is required to load this catalog through
`discover_primitives`.
