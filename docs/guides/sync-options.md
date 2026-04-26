# Sync Options

Where the vault lives and how members keep it in sync.

## TL;DR

- **Solo or small group, no governance needs** → shared cloud drive (OneDrive / Google Drive / Dropbox). Zero setup, intuitive for non-technical members.
- **Larger team, review gates needed, audit trail** → Git repository.
- **Both** → maintain Git as the source of truth, sync a read-only copy to a shared drive for browsing.

## Recommended: Shared Drive (OneDrive / Google Drive / Dropbox)

For households and teams that include non-technical members, a shared cloud drive is the recommended default. It requires zero setup beyond installing Obsidian and pointing it at the synced folder, and every member already understands how cloud drive sync works.

**How it works:**
- Install the cloud drive desktop client on each member's machine — this creates a local folder mirroring the cloud.
- Create the Obsidian vault inside the synced folder.
- Each member opens the same vault path in Obsidian.
- Edits propagate automatically via the cloud drive's sync engine.
- Claude Code and Claude Cowork access the vault through the local file path — they read and write directly to the synced folder.

**Practical considerations:**

- **Conflict resolution.** Cloud drives handle most sync conflicts automatically. Simultaneous edits to the same `.md` file can produce conflict copies. Mitigate by structuring work so different people edit different pages, and by having Claude (the primary wiki writer) operate through a single machine or scheduled window.
- **Google Drive caveat.** Documents Claude creates or edits must be in native Office formats (`.docx`/`.xlsx`/`.pptx`), not Google Docs/Sheets/Slides. Claude can't write directly to native Google formats. Files saved as `.docx` sync via Google Drive for Desktop and team members can open them in Google Docs (auto-converts for viewing). For markdown wiki content this is moot — `.md` files sync perfectly on all drives.
- **OneDrive / Dropbox.** Slightly better desktop sync behavior for non-Google file formats and avoid the Google Docs auto-conversion friction.

See [`file-formats.md`](file-formats.md) for the full file-format compatibility matrix.

## Alternative: Git Repository

For larger teams or when governance over wiki changes matters, a Git-backed vault provides stronger guarantees.

**Advantages over shared drive at scale:**
- Full version history with author attribution on every change
- Branch-per-project or branch-per-feature workflows for parallel wiki development
- Pull request review on AI-generated wiki updates (quality gates)
- Deterministic line-level merge conflict resolution
- CI hooks can run lint passes, validate frontmatter, check for broken wikilinks
- Better audit trail for compliance-sensitive environments

**How it works:**
- Host the vault as a Git repository (GitHub, GitLab, Bitbucket, or self-hosted).
- Technical members use Git directly or the Obsidian Git plugin (auto-commit/pull on a schedule).
- Non-technical members can use a Git GUI (GitHub Desktop, GitKraken) or a dedicated sync layer.
- Claude Code operates directly on the local clone.

## When to switch from shared drive to Git

- Team grows beyond ~8-10 people editing the wiki
- Multiple AI agents are writing to the vault concurrently
- You need PR-based review gates on wiki changes
- Regulatory or compliance requirements demand a full audit trail
- Cross-team collaboration where different groups own different project areas

## Hybrid approach

Some teams use a shared drive for day-to-day access (everyone can read and browse in Obsidian) while maintaining a Git repository as the authoritative source. A scheduled job syncs Git → shared drive. Non-technical members get easy read access; Git governance is preserved for writes.

## Project isolation (confidentiality)

For teams working across multiple projects with confidentiality boundaries, use **separate vaults per project**. This ensures Claude cannot cross-pollinate knowledge between engagements. Each vault gets its own `CLAUDE.md` schema and its own Cowork Project context. Separate Obsidian vaults with separate Cowork Projects enforce data isolation at the filesystem level — Claude cannot cross-reference content it cannot see.

For the family variant, project isolation is rarely needed — one household vault works. Consider a separate vault only if you're maintaining knowledge for someone outside the immediate household (e.g., an aging parent's records that another family member should not access).
