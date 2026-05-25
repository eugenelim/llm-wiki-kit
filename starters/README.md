# starters/

Three committed, ready-to-use Obsidian vaults. Pick one, copy it to a
folder of your own, open it in Claude Code (or any agent that reads
`AGENTS.md`). You do **not** need to `pip install` anything to use a
starter vault — the kit produced these for you.

| Starter           | Best for                                                                                            |
|-------------------|-----------------------------------------------------------------------------------------------------|
| [`family/`](family/)     | A household OS — people, meals, medical, trips, vendors, receipts, taxes, action items.        |
| [`work-os/`](work-os/)   | A professional OS — stakeholders, projects, customers, domains, decisions, meetings, interviews.|

## Use a starter

```bash
# 1. Clone this repo so you have the starter on disk.
git clone https://github.com/eugenelim/llm-wiki-kit
cd llm-wiki-kit

# 2. Copy the starter to a folder of your own.
cp -r starters/work-os ~/my-work-os
cd ~/my-work-os

# 3. Optional — put your vault under version control.
git init && git add . && git commit -m "initial"

# 4. Open it. The vault is just markdown — works in any editor.
#    For the LLM-driven side, open the folder in Claude Code.

# 5. Start using it. The vault's AGENTS.md tells the agent which
#    skills are wired up. Try something like:
#       "Read .wiki.journal/journal.jsonl and summarize what's in
#        this vault."
```

That's it. No Python, no `pip install`, no kit setup.

## Want to pull in kit upgrades later?

A starter is a *projection* of the kit — the deterministic output of
running the kit's renderer over a recipe plus the seed pages under
`_seed/`. Two consequences:

- The starter has no "fork problem" with the kit. New primitives,
  new schemas, fixed bugs in templates — all of these land in the
  kit, get rendered into the starter on the next `regenerate.py
  --apply`, and CI verifies the result on every PR.
- If you want those upgrades in *your* copy, install the kit and
  run `wiki upgrade` inside your cloned starter:

  ```bash
  pip install llm-wiki-kit       # or pipx install
  cd ~/my-work-os
  wiki upgrade
  ```

  This is the same upgrade path an author-built vault uses. Any
  pages you have edited are preserved through the kit's drift
  detection — conflicts land as `.proposed` sidecars, never as
  silent overwrites. The conflict resolution workflow is documented
  in [`docs/guides/how-to/resolve-a-conflict.md`](../docs/guides/how-to/resolve-a-conflict.md).

You can keep postponing the install indefinitely; the starter is
fully usable without it.

## What's in a starter?

Each starter ships:

- `AGENTS.md` and `CORE.md` — the contract the vault and the LLM
  share. Open these first.
- `wiki/<area>/` — the typed pages your starter ships with. Real
  examples (not placeholders) so you can see what good content looks
  like for that area.
- `skills/` — vault-side skills the agent loads inside Claude Code
  (`wiki-doctor`, `wiki-conflict`, the ingest skills, the
  operations).
- `.wiki.journal/journal.jsonl` — the audit log of every state
  change. Already populated with the events that built the starter.
- `_templates/`, `frontmatter.schema.yaml`, `.gitignore` — kit
  scaffolding.

## Where the docs live

- **User-facing tutorials:** [`docs/guides/tutorials/`](../docs/guides/tutorials/)
  walk through using the kit `wiki init`-style; if you're starting
  from a cloned starter, you can usually skim them.
- **Conflict resolution:** [`docs/guides/how-to/resolve-a-conflict.md`](../docs/guides/how-to/resolve-a-conflict.md).
- **Architecture and how starters get produced:**
  [`docs/architecture/starters.md`](../docs/architecture/starters.md).
- **Roadmap, ADRs, RFCs:** see the kit-side docs under `docs/`.
  Most of these are kit-maintainer docs; starter users rarely need
  them.
