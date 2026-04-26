---
name: ingest-website
description: "Convert an HTML web URL (article, blog post, documentation, reference material) to clean markdown using defuddle locally — or pure.md fallback for JS-heavy/bot-blocked sites. Source-type cleanup ingester — output is markdown saved to raw/, handed back to the ingest orchestrator. Use when the source is an HTML web page. For binary URLs (PDF, image, .docx) use ingest-document; for lightweight URL-only saves use ingest-bookmark."
license: MIT
compatibility: "Requires Node.js + defuddle-cli (npm install -g defuddle-cli). Optional: pure.md account for JS-heavy/bot-blocked sites."
metadata:
  variant: shared
---

# Ingest Website Skill

Specialized ingester for web URLs. The orchestrator (`ingest.md`) routes to this skill when the source is an HTML web page — articles, blog posts, documentation, reference material. Output is clean markdown saved to `raw/`, then handed back to the orchestrator's shared post-extraction flow.

For binary URLs (PDFs, images, .docx), use [[ingest-document]] — even when the user gives you a URL.

## Backends

This skill picks one of two backends based on what's available and whether the URL is sensitive. A third path — pre-cleaned input from the Obsidian Web Clipper — bypasses both backends entirely (see "Web Clipper Input" below).

### Default: defuddle (local, private)

[Defuddle](https://github.com/kepano/defuddle) is the open-source extractor behind the Obsidian Web Clipper. It runs locally — no third-party logging, no rate limits, no cost.

**Prerequisite:** `npm install -g defuddle-cli` (one time, requires Node).

**Usage:**
```bash
defuddle parse "<url>" --md > raw/web-clips/<YYYY-MM-DD>-<slug>.md
```

Use defuddle for:
- Public articles, blog posts, docs
- Sites without aggressive bot detection
- **Any URL that's internal, auth-protected, behind a paywall accessed via your cookies, or contains a session token.** Pass cookies with `--cookies` if needed.

### Fallback: pure.md (cloud, hosted)

[pure.md](https://pure.md/) is a URL-prefix REST service that handles the cases defuddle struggles with: heavy JS-rendered SPAs, sites that bot-block defuddle's headers, and anti-scraping defenses.

**Usage:**
```bash
curl "https://pure.md/<full-url>" > raw/web-clips/<YYYY-MM-DD>-<slug>.md
```

Anonymous calls work for low volume. For heavier use, set `PUREMD_API_KEY` (Starter tier: $0.003/fetch, 60 req/min, $1 free credit).

> [!warning] Privacy trade-off
> pure.md caches and logs every URL it fetches as part of how the service works. **Never route the following to pure.md:**
> - Internal company / intranet URLs
> - URLs containing auth tokens, session keys, or signed query parameters
> - Pages behind paywalls accessed via your authenticated cookies
> - Anything covered by an NDA or compliance regime
>
> When in doubt, stay on defuddle. If defuddle fails on a sensitive URL, surface the failure to the user rather than silently falling back to pure.md.

## Web Clipper Input

The [Obsidian Web Clipper](https://obsidian.md/clipper) browser extension uses the same defuddle engine as this skill. When a user clips with it, the cleanup is already done — there's no URL to fetch and no backend to pick. The orchestrator (`ingest`) handles this path directly:

- **Recommended setup:** Web Clipper writes to `raw/web-clips/<YYYY-MM-DD>-<slug>.md` with the kit's frontmatter schema. The orchestrator picks the file up like any other `raw/` source. No relocation needed. See [`docs/guides/web-clipper.md`](../../../docs/guides/web-clipper.md) for the template config.
- **Default fallback:** Web Clipper writes to `Clippings/{title}.md` (its built-in default). The orchestrator detects the file, treats it as already-cleaned web markdown, routes to content-type schema, and **relocates** to `raw/web-clips/<YYYY-MM-DD>-<slug>.md` after a successful wiki update — so all sources end up in the canonical immutable `raw/` store. On failure (user rejects, scope skip, ambiguous routing), the file stays in `Clippings/` for retry.

In both paths, this skill is **not invoked** — the cleanup step is already done. This skill runs only for the URL-on-demand case (user pastes / asks for a URL).

## Operation (URL-on-demand path)

1. Receive a URL from the orchestrator.
2. Decide backend:
   - If the URL looks internal/auth'd (intranet hostname, query string with tokens, etc.) → defuddle only. If defuddle fails, stop and report to the user.
   - Otherwise → try defuddle first.
3. If defuddle returns empty output, garbled markdown, or errors out → fall back to pure.md (after the privacy check above).
4. Save raw markdown to `raw/web-clips/<YYYY-MM-DD>-<slug>.md` with frontmatter:
   ```yaml
   ---
   source_url: <original-url>
   fetched_via: defuddle | pure.md
   fetched_at: <YYYY-MM-DD>
   provenance: extracted
   ---
   ```
5. Hand back to the orchestrator. The orchestrator runs the article-extraction flow (thesis identification, key-claim extraction, scope check against `purpose.md`, interactive review with the user, wiki updates).

## Failure modes

- **Defuddle returns empty/garbled output.** Site is likely JS-rendered. Fall back to pure.md (with privacy gate).
- **Defuddle blocked by bot detection.** Same — fall back to pure.md.
- **pure.md hits the 60 req/min rate cap.** Either wait, or set `PUREMD_API_KEY` for the Starter tier.
- **Paywalled article.** Use `defuddle parse <url> --cookies <path-to-cookies>` from your authenticated browser session, or fetch via your institutional/library proxy first. Do not pass cookies to pure.md.
- **URL is non-HTML (PDF, DOCX, image).** Wrong skill — route to [[ingest-document]] instead.
