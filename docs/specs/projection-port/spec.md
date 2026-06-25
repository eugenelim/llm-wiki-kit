# Spec: projection-port

- **Status:** Shipped <!-- Draft | Approved | Implementing | Shipped | Archived -->
- **Owner:** eugenelim
- **Plan:** [`plan.md`](plan.md)
- **Constrained by:** RFC-0010, RFC-0009, ADR-0011, ADR-0004, ADR-0002
- **Contract:** none
- **Shape:** service

> **Spec contract:** this document defines what "done" means. The implementing
> PR must match this spec, or update it. Verification must be derivable from it.

## Objective

The kit exposes one callable, mechanical write path into a vault — the
**projection port**, the verb `wiki project`. Any skill, kit-native or foreign,
lands managed vault state by handing the port a finished Markdown artifact
(YAML frontmatter + body): the port validates the frontmatter against the
vault's faceted schema, resolves where the page lands, and writes it through the
kit's drift-protected, journaled write path. A prompt-only foreign skill with
**zero vault-internal knowledge** — no access to the private `safe_write`, no
bespoke per-command wiring — can now project a page by writing a plain file and
calling one verb.

```
wiki project <artifact.md> [--at <vault-relative-dest>] [--as <subtype>] [--by <name>]
```

The port owns only the **closed, mechanical half** of projection: schema
validation, destination resolution, the drift-protected write, and the journal
record. The **open, reasoning half** — deciding whether a page belongs in the
vault (scope), whether it contradicts an existing page, and which facts or tasks
to propagate — stays the authoring skill's job, because each needs LLM judgment
the port cannot mechanize. This is RFC-0010's split made concrete: translation
is open and LLM-determined; validation is closed and mechanical at the port.

Success: the `ingest` authoring skill's shared-flow "write" step invokes
`wiki project` instead of narrating a direct `safe_write`; a finished artifact
dropped anywhere with a schema-valid frontmatter lands at the right role folder
through the port with a clean journal baseline; and a frontmatter that violates
the schema is rejected at the boundary with a one-line reason and **no write**.

**Divergence from RFC-0010 D1 (named, and justified).** RFC-0010 D1 sketches
`wiki project <artifact.md> --as <subtype> [--at <path>]` with destination as
"subtype routing, or explicit `--at`". This spec routes by **`genre`**, not
`subtype`, and treats `--at` as the explicit override rather than the fallback —
because a `subtype`→folder table would mint kind-keyed folders, which
`role-folders-and-containers` §Never do forbids (kind is the `subtype` facet,
never a folder). Genre maps to one of the four fixed role folders; `subtype`
never changes where a page lands. The RFC is Accepted and frozen, so the
correction lives here, not in an RFC edit.

**Container-scoped pages require `--at`.** Genre-routing homes a page in a *role
folder* (`people/`, `library/`, `atlas/`). A page that belongs inside an
`efforts/<type>/<instance>/` container (a project meeting, a case decision)
carries a role-folder genre (`record`, `decision`, `update`) the table would send
to `library/`; the port cannot mechanically know container membership (that is the
`parent:` reasoning the authoring skill owns), so the **caller passes `--at` for
container pages**. The genre default is correct only for non-container role-folder
pages.

## Boundaries

The three-tier guard that keeps an implementing agent inside the lines.
*Always do* applies without asking; *Ask first* requires human sign-off
before proceeding; *Never do* is a hard rule, even under time pressure.

### Always do

- Parse all frontmatter and schema YAML with `yaml.safe_load` (never `yaml.load`):
  a `!!python/object` tag in a foreign artifact must not deserialize.
- Validate the artifact's frontmatter against the vault's
  `frontmatter.schema.yaml` (required facets present; `genre` in the fixed
  baseline enum; `status` and `provenance` in their enums; `subtype` in the
  schema's known `subtypes`) **before** any write, and reject with a `WikiError`
  one-liner on the first violation.
- Route every write through `write_helper.safe_write` so drift detection and the
  `PageWrite`/`PageProposal` journal event happen exactly as for every other kit
  write.
- Resolve a destination the artifact didn't pin with `--at` from the page's
  `genre` → role-folder table, using **only the basename** of the artifact
  (`Path(artifact).name`, stripping any directory components) as the page slug.
- Confine **both** the `--at` destination and the genre-routed
  `wiki/<role>/<slug>` candidate through the **one** shared path resolver: after
  `Path.resolve(strict=False)` the result must be `vault_root` or a descendant,
  else reject. Call the single shared helper for both branches; never reimplement
  or hand-join the confinement check.

### Ask first

- Adding a `genre` → role-folder entry for a genre the table does not yet route
  (the four role folders are fixed by RFC-0009 / `role-folders-and-containers`).
- Exposing raw `safe_write` as its own low-level verb (RFC-0010 D1 rejects this —
  it re-couples callers to journal/schema knowledge).
- Auto-accepting a `subtype` the vault schema does not yet know (a new subtype is
  RFC-0009's human-accept journal gate, not a silent port write).

### Never do

- Add a runtime dependency — frontmatter and schema parsing use the already-present
  `pyyaml`. *(structural)*
- Add a new top-level kit-source directory, or any aggregator/registry beyond the
  one new `projection.py` module. *(structural)*
- Key the destination on `subtype` (a `meetings/` or `decisions/` folder): role is
  `genre` → one of the four role folders; kind is the `subtype` facet and is never a
  folder (`role-folders-and-containers` §Never do). *(structural)*
- Bypass `safe_write` with a direct `Path.write_text` against a vault page
  (ADR-0004). *(structural)*
- Mechanize the reasoning half in the port — scope check, contradiction check,
  fact/task propagation, and the changelog line stay the authoring skill's job;
  the port does not read the vault to judge belonging or conflicts.

## Testing Strategy

- **Frontmatter parsing & schema validation** (strict `yaml.safe_load` of a
  `---`-delimited block; required-facet presence; `genre`/`status`/`provenance`
  enum membership; `subtype` known-in-schema; malformed YAML and a non-safe YAML
  tag → reject): **TDD** — pure functions over in-memory strings and a schema
  dict, a compressible invariant with many branches.
- **Destination resolution** (`genre` → role folder + artifact basename; `--at`
  override; confinement of **both** branches through the one shared resolver —
  `..`, absolute, and symlinked-parent escape rejected for `--at` *and* for a
  crafted basename; unknown-genre and missing-role-folder errors): **TDD** — pure
  path logic with enumerable branches.
- **`wiki project` end-to-end** (a schema-valid artifact writes a page under the
  resolved role folder and appends one `PageWrite`; a drift collision routes to a
  `.proposed` sidecar + `PageProposal`; a bad `genre`, unknown `subtype`, missing
  facet, or escaping `--at` exits non-zero and writes nothing): **goal-based**,
  exercised by an **integration** test against `tmp_path`, **and** the real verb
  run once by hand on a fixture vault with stdout/exit code recorded (manual QA:
  the change ships a user-invoked CLI verb).
- **`ingest` SKILL prose points at the port** (the shared-flow write step and the
  anti-pattern reference `wiki project`, not a bare `safe_write`): **goal-based** —
  a `grep` over `core/files/skills/ingest/SKILL.md`.

## Acceptance Criteria

- [x] `wiki project <artifact.md>` with schema-valid frontmatter and no `--at`
      writes the page to `wiki/<role-folder>/<basename>` where role-folder is the
      `genre` → role mapping (`profile`→`people/`, `moc`→`atlas/`, all other genres
      →`library/`) and `<basename>` is `Path(artifact).name`, and appends exactly
      one `PageWrite` event. (Container-scoped pages are out of genre-routing scope
      and use `--at`; see Objective.)
- [x] `wiki project <artifact.md> --at <dest>` writes to the explicit
      vault-relative `<dest>`, overriding genre routing.
- [x] Both the `--at` destination and the genre-routed `wiki/<role>/<basename>`
      candidate are confinement-checked by the same shared resolver: after
      `Path.resolve(strict=False)` the path is `vault_root` or a descendant, else
      the verb exits non-zero and writes nothing. A crafted basename or `--at`
      containing `..`, an absolute path, or a symlink whose resolved prefix leaves
      the vault is rejected — neither boundary is left unguarded.
- [x] `--as <subtype>` sets the `subtype` facet when the artifact omits it and
      overrides it when present; absent `--as`, the artifact's own `subtype` is
      used. On override the written frontmatter carries the new `subtype` and
      **every other frontmatter key and value is preserved** (no reordering, no
      dropped keys); the body is byte-identical to the input body.
- [x] All frontmatter and schema YAML is parsed with `yaml.safe_load`; an artifact
      carrying a non-safe YAML tag (e.g. `!!python/object`) is rejected, not
      deserialized.
- [x] A frontmatter missing any of the six required facets, or carrying a `genre`
      outside the baseline enum, a `status`/`provenance` outside its enum, or a
      `subtype` not in the schema's known `subtypes`, exits non-zero with a
      one-line reason and writes no file and appends no event.
- [x] An artifact whose frontmatter is malformed YAML, or which has no frontmatter
      block, exits non-zero with a one-line reason and writes nothing.
- [x] When the resolved destination already exists on disk and its content has
      drifted from the journal baseline, the port writes a `<dest>.proposed`
      sidecar and appends a `PageProposal` (the existing `safe_write` drift path),
      not a silent overwrite.
- [x] When the vault lacks the role folder a page routes to (e.g. no `wiki/atlas/`),
      `wiki project` without `--at` exits non-zero naming the missing folder rather
      than creating an unrecognized top-level folder — only `wiki init`/ontology
      seeds may mint a role folder (`role-folders-and-containers` §Never do).
- [x] `--by <name>` attributes the write in the journal; absent it, the write is
      attributed to a fixed projection vehicle `wiki-project` (the writer's
      identity, matching the `by` semantics every other kit writer uses — not the
      page's `subtype`).
- [x] `core/files/skills/ingest/SKILL.md`'s shared-flow write step and the
      "don't write outside the flow" anti-pattern reference `wiki project` as the
      sanctioned write path.
- [x] `ruff check llm_wiki_kit tests`, `ruff format --check llm_wiki_kit tests`,
      `mypy llm_wiki_kit tests`, and `pytest -m 'not slow'` pass.

## Assumptions

- Technical: runtime deps are `pyyaml>=6` + `pydantic>=2`; YAML frontmatter and
  schema parsing need no new dependency (source: `pyproject.toml`).
- Technical: only `write_helper.safe_write` and `journal.append_event` are callable
  Python write primitives; schema validation, scope/contradiction, fact propagation,
  and the changelog exist only as SKILL prose, so the port's validation step is
  net-new code (source: `core/files/skills/ingest/SKILL.md:122-145`;
  `write_helper.py:78`).
- Technical: the faceted schema renders to `<vault_root>/frontmatter.schema.yaml`
  with a fixed `genres` enum, a populated `subtypes` managed region, `statuses`,
  and `provenance` (source: `starters/work-os/frontmatter.schema.yaml`;
  `render.py:52`).
- Technical: the produced vault has exactly four role folders — `people/`,
  `efforts/`, `library/`, `atlas/` — and kind is the `subtype` facet, never a
  folder, so destination routing is `genre` → role folder, not `subtype` → folder
  (source: `docs/specs/role-folders-and-containers/spec.md`; `starters/work-os/wiki/`).
- Technical: `safe_write(path, content, by, journal_path) -> WriteResult` appends
  the `PageWrite`/`PageProposal` event itself (event-before-disk), so the port's
  journal step is the `safe_write` call, not a separate append (source:
  `write_helper.py:78`).
- Technical: a vault-relative path-safety resolver pattern exists as
  `cli._resolve_out_path` (rejects absolute/`..`/symlink-escape); the port's `--at`
  resolution mirrors it (source: `cli.py:2084`).
- Technical: a lenient page-frontmatter parser exists in `search.py:211` (malformed
  → `{}`); the port needs a strict variant (malformed → reject), so the parser is
  net-new (source: `llm_wiki_kit/search.py:211`).
- Process: a new CLI verb plus a new module is a structural change → full-mode
  work-loop with spec-stage adversarial and security (file I/O + untrusted
  frontmatter) review; the spec cites RFC-0010, RFC-0009, ADR-0004 (source:
  work-loop SKILL; `docs/rfc/0010-decouple-authoring-from-projection.md`).
- Product: the near-term consumers are the `ingest` authoring skill (re-pointed to
  the verb) and future prompt-only foreign packs; folding `_cmd_research` and the
  operations writer onto the port, the landing-box `adopt` skill, container-aware
  routing, and the changelog append are deferred RFC-0010 follow-ons captured at
  `docs/backlog.md#projection-port` (source: user confirmation 2026-06-24).
- Technical: a foreign artifact is read whole into memory before parsing; artifacts
  are local files the caller already chose to project (no network fetch, no
  unbounded stream), so no size bound is enforced — if a future caller projects
  large untrusted blobs this assumption is revisited (source: design judgment,
  consistent with `safe_write`'s whole-content model).
