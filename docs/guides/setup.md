# Setup Guide

End-to-end walkthrough for getting an LLM Wiki Kit vault running. Pick a variant, copy it into a synced location, install the agent skills, and open in Obsidian.

## Prerequisites

- **Obsidian** (free) — https://obsidian.md
- **Claude Code** or **Claude Cowork** with file-system access — https://claude.com/code
- **Node + npm** if you'll use the `defuddle` web ingester (recommended)
- **Python 3.10+** for the bundled scripts (`wiki-search.py`, `tag-lint.py`, `convergence-debt.py`, `ingest_document.py`, `research.py`)
- **ripgrep** (`rg`) on PATH — used as the default backend by `wiki-search`. Pre-installed on most dev machines; install via `brew install ripgrep`, `apt install ripgrep`, or `winget install BurntSushi.ripgrep.MSVC` if missing.
- A cloud drive client (OneDrive / Google Drive / Dropbox) **or** a Git host — see [`sync-options.md`](sync-options.md)

## 1. Clone and copy a vault template

```bash
git clone https://github.com/eugenelim/llm-wiki-kit.git
cd llm-wiki-kit

# Pick a variant and copy to your synced location.
cp -r vault-templates/work ~/OneDrive/my-team-wiki
# or
cp -r vault-templates/family ~/GoogleDrive/my-family-wiki
```

The vault-template ships with a `.gitkeep` placeholder in `.claude/skills/` — you'll populate it next.

## 2. Install Obsidian Skills (kepano/obsidian-skills)

These teach Claude correct Obsidian-flavored Markdown, Bases, JSON Canvas, the Obsidian CLI, and the defuddle web clipper.

```bash
cd ~/OneDrive/my-team-wiki   # or wherever you put the vault

git clone https://github.com/kepano/obsidian-skills.git /tmp/obsidian-skills
cp -r /tmp/obsidian-skills/.claude/* .claude/
rm -rf /tmp/obsidian-skills
```

Or use the plugin marketplace from inside Claude:
```
/plugin marketplace add kepano/obsidian-skills
/plugin install obsidian@obsidian-skills
```

If you also use the [Obsidian Web Clipper](https://obsidian.md/clipper) browser extension, configure its template per [`web-clipper.md`](web-clipper.md) so clips land directly in `raw/web-clips/`. The kit's `ingest` orchestrator works with the default `Clippings/` location too, but the recommended template skips the relocation step.

## 3. Copy the kit's skills

Skills follow the [Agent Skills spec](https://agentskills.io/specification): each skill is a directory containing `SKILL.md` (with frontmatter), `scripts/` (when applicable), and `evals/evals.json` (activation prompts). Scripts live alongside their owning skill — no separate `.claude/scripts/` directory.

From inside the cloned `llm-wiki-kit` repo:

```bash
# Shared skills (used by every variant)
cp -r skills/shared/* ~/OneDrive/my-team-wiki/.claude/skills/

# Variant-specific skills
cp -r skills/work/* ~/OneDrive/my-team-wiki/.claude/skills/
# or
cp -r skills/family/* ~/GoogleDrive/my-family-wiki/.claude/skills/
# or
cp -r skills/personal/* ~/Dropbox/my-wiki/.claude/skills/
```

The bundled Python scripts (`tag-lint.py`, `convergence-debt.py`, `wiki-search.py`, `ingest_document.py`, `research.py`) ship inside their owning skills' `scripts/` folder — they get copied along with the skill.

Optional Python dependencies (install only the ones you need):

```bash
pip install pyyaml                            # for wiki-lint (tag-lint, convergence-debt)
                                              # (also used by wiki-search for nicer YAML parsing
                                              #  — wiki-search has a built-in fallback if PyYAML is missing)
pip install docling                           # for ingest-document (default path)
pip install pymupdf4llm                       # optional --fast path for ingest-document
```

`wiki-search` itself has **no pip dependencies** — its default backend uses
ripgrep (already on most dev machines), and its FTS5 backend uses Python's
standard-library `sqlite3`. The skill auto-upgrades to FTS5 the first time the
vault crosses ~1000 pages or 50 MB; you do not need to run any setup command.

> [!note] Docling's first run downloads ML models (~hundreds of MB). After that, everything runs locally with no network calls.

## 4. Customize your vault identity

Edit `_variant/CLAUDE.variant.md` to fill in your team's or family's identity, tone, and any variant-specific tagging conventions. The root `CLAUDE.md` works as-is.

Edit `purpose.md` next — replace the placeholder scope statement with your vault's actual scope. Claude reads `purpose.md` before every ingest, so any source falling outside that scope gets skipped rather than polluting the wiki.

## 5. Open in Obsidian

Open the vault folder in Obsidian. `wiki/index.md` is your starting point. From there, navigate to active projects (work) or family domains (family).

## 6. Test the loop

Drop a real document into `raw/`, ask Claude to ingest it, and verify the resulting wiki page lands in the right place with the right frontmatter. The full ingest workflow:

1. You drop a file or paste a URL.
2. The orchestrator (`skills/shared/ingest/SKILL.md`) detects type and routes.
3. The specialized ingester ([[ingest-website]], [[ingest-document]], etc.) produces clean markdown in `raw/`.
4. The orchestrator runs scope check → contradiction check → wiki update → changelog.
5. You review and either accept the changes or redirect.

If the loop works end-to-end on a representative source, you're set.

## Upgrading an existing vault

When the kit ships an updated skill (new backend, schema bump, bug fix), an
existing vault picks it up by re-copying the skill from a fresh clone of the
source repo into the vault's `.claude/skills/` directory. The fastest path is
to ask Claude Code to do it for you — the prompt below tells it exactly what to
do and which files to expect.

### Pull the latest source

```bash
# Re-clone (or `git pull` if you already have it cloned somewhere)
git clone https://github.com/eugenelim/llm-wiki-kit.git /tmp/llm-wiki-kit
# Or, if you already have it:
git -C /path/to/llm-wiki-kit pull --ff-only
```

### Ask Claude Code to bring the changes over

From inside your **vault** directory, start Claude Code and paste this prompt
(adjust the source path if you cloned somewhere other than `/tmp/llm-wiki-kit`):

```
The latest llm-wiki-kit source is at /tmp/llm-wiki-kit. Bring the changes
over into this vault:

1. For each skill directory under /tmp/llm-wiki-kit/skills/shared/, compare it
   against .claude/skills/<same-name>/ in this vault. If the source version
   differs, replace the vault copy entirely (rm -rf the old, then cp -r the
   new). Do NOT touch any skill that is not in /tmp/llm-wiki-kit/skills/shared/.

2. Do the same for /tmp/llm-wiki-kit/skills/<my-variant>/ (work, family, or
   personal — whichever this vault uses; check _variant/CLAUDE.variant.md
   to confirm).

3. If shared/CLAUDE.md or shared/CLAUDE.variant.<my-variant>.md changed,
   propagate to this vault's CLAUDE.md and _variant/CLAUDE.variant.md
   respectively. Show me a unified diff before overwriting.

4. If .gitignore in the source has new entries that mine doesn't, append the
   new entries to my .gitignore. Don't remove any of my existing entries.

5. After copying, run any health check the skills provide. For wiki-search
   specifically: run `python .claude/skills/wiki-search/scripts/wiki-search.py
   backend wiki/` and report the output — it will rebuild the FTS5 index
   automatically if the schema changed.

6. List exactly what changed (skill names, file counts, anything in CLAUDE.md
   or .gitignore) so I can review. Don't commit anything; I'll review and
   commit myself.

Don't add new content to wiki/, raw/, or any other vault content folder.
This is a tooling refresh only.
```

Claude reads the source skills, diffs them against your vault copies, replaces
what's stale, and reports back. Review the diff and the health-check output,
then commit yourself if you're using Git.

### What the wiki-search upgrade specifically does

If you're upgrading from the original `bm25s`-based `wiki-search` to the
two-tier ripgrep + SQLite FTS5 implementation, after the skill refresh:

- The old `pip install bm25s[core] PyStemmer` line is no longer needed.
- The runtime artifact moves from `wiki/.wiki-search-index/` (legacy) to
  `wiki/.wiki-search/`. The kit's `.gitignore` ignores both, so you can delete
  the legacy directory at your convenience: `rm -rf wiki/.wiki-search-index/`.
- The first `wiki-search backend wiki/` call materializes the new
  `wiki/.wiki-search/state.json` and decides the backend. If your vault is
  already large enough, FTS5 auto-bootstraps on the next search call.

If you ever accidentally committed `wiki/.wiki-search-index/` (e.g., before the
gitignore entry was added), the upgrade is a good moment to `git rm -rf
wiki/.wiki-search-index/` so it stops appearing in diffs.

## Beyond the basics

- [`sync-options.md`](sync-options.md) — shared drive vs. Git tradeoffs, when to switch.
- [`file-formats.md`](file-formats.md) — companion-page rules, `.docx`/`.xlsx`/`.pptx` support.
- [`customizing.md`](customizing.md) — building a custom variant beyond `work` and `family`.
