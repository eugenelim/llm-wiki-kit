# Setup Guide

End-to-end walkthrough for getting an LLM Wiki Kit vault running. Pick a variant, copy it into a synced location, install the agent skills, and open in Obsidian.

## Prerequisites

- **Obsidian** (free) — https://obsidian.md
- **Claude Code** or **Claude Cowork** with file-system access — https://claude.com/code
- **Node + npm** if you'll use the `defuddle` web ingester (recommended)
- **Python 3.10+** for the bundled scripts (`wiki-search.py`, `tag-lint.py`, `convergence-debt.py`, `ingest_document.py`, `research.py`)
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
pip install bm25s[core] PyStemmer pyyaml      # for wiki-search
pip install docling                           # for ingest-document (default path)
pip install pymupdf4llm                       # optional --fast path for ingest-document
```

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

## Beyond the basics

- [`sync-options.md`](sync-options.md) — shared drive vs. Git tradeoffs, when to switch.
- [`file-formats.md`](file-formats.md) — companion-page rules, `.docx`/`.xlsx`/`.pptx` support.
- [`customizing.md`](customizing.md) — building a custom variant beyond `work` and `family`.
