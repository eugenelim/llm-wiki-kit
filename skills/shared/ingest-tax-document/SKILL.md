---
name: ingest-tax-document
description: "Capture a tax form (W-2, 1099-DIV/INT/B/MISC/NEC, 1098, K-1, 5498, 1095-*, brokerage year-end statement, tax-prep summary) into wiki/finances/tax/{year}/. Use when a tax-form PDF is dropped (typically January-March; some K-1s and amended forms arrive later) or the user says \"save this tax form\" / \"ingest this 1099\" / \"track this W-2\". Composes ingest-document for cleanup."
license: MIT
metadata:
  variant: shared
---

# Ingest Tax Document Skill

Specialized content-type ingester for tax forms — W-2, 1099-* (DIV, INT, B, MISC, NEC), 1098, K-1, 5498, 1095-*, brokerage year-end statements, tax-prep summaries. Composes [[ingest-document]] for cleanup, then applies tax-document schema. Output lands in `wiki/finances/tax/{year}/`.

## When to Use

The orchestrator routes here when:
- A tax-form PDF is dropped (typically January-March; some K-1s and amended forms arrive later)
- The user says "save this tax form" / "ingest this 1099" / "track this W-2"
- The source matches a tax-form pattern (issuer is a known broker / employer / bank; form number prominently displayed)

Applies to family and personal variants — both have `wiki/finances/tax/` folders.

## Composition

| Source | Cleanup | Result |
|---|---|---|
| Tax-form PDF (W-2, 1099, 1098, K-1, etc.) | [[ingest-document]] (Docling) | clean markdown |
| Tax-software PDF export (TurboTax, H&R Block) | [[ingest-document]] | clean markdown |
| Brokerage year-end statement | [[ingest-document]] | clean markdown |
| Pasted form contents | none — handle directly | raw text |

## Inputs

After cleanup:
- The cleaned-up tax form content
- The tax year (auto-detected from form, or asked of user if ambiguous)
- The recipient (which family member, for joint or family filers; ask if not obvious)

Reads:
- Existing `wiki/finances/tax/{year}/` to detect duplicates
- `wiki/finances/holdings/` for 1099-B / 1099-DIV cross-references
- The tax-document template at `_templates/tax-document.md`

## Algorithm

1. **Identify form type.** Common types: W-2, W-2c (corrected), 1099-INT, 1099-DIV, 1099-B, 1099-MISC, 1099-NEC, 1099-R (retirement), 1098 (mortgage), 1098-E (student loan), 1098-T (tuition), K-1 (partnership/S-corp), 5498 (IRA contributions), 1095-A/B/C (health coverage).
2. **Identify tax year.** Usually printed prominently on the form; sometimes inferred from the issuer's reporting period.
3. **Identify recipient + issuer.** Recipient name + (last 4 of) account number. Issuer name (employer / brokerage / bank / partnership).
4. **Extract key figures** per form type:
   - **W-2:** wages (Box 1), federal withholding (Box 2), social-security wages (Box 3), state withholding (Box 17)
   - **1099-DIV:** ordinary dividends (Box 1a), qualified dividends (Box 1b), cap-gains distributions (Box 2a)
   - **1099-B:** proceeds, cost basis, gain/loss (long-term vs short-term)
   - **1099-INT:** interest income (Box 1)
   - **1099-NEC:** non-employee compensation (Box 1) — typical for freelance
   - **1098:** mortgage interest, points, property taxes
   - **K-1:** partner/shareholder income items per Schedule, with codes
5. **Detect SSN / sensitive data.** Many forms include SSN in plain text. **CRITICAL: never propagate SSN to the wiki page.** Note "SSN redacted (kept on PDF only)" in the page; alert the user if the cleanup pipeline accidentally captured it.
6. **Detect duplicates.** If a same-issuer same-form already exists for the year, surface and ask whether it's a corrected form (W-2c) or a duplicate.
7. **Cross-reference holdings** for 1099-B (sales) and 1099-DIV (dividends).

## Output

Write `wiki/finances/tax/{year}/{form-type}-{issuer-slug}.md` using `_templates/tax-document.md`:

```yaml
---
title: "{Form Type} — {Issuer} ({Year})"
type: tax-document
status: received
tax_year: {year}
form_type: "{form-type}"
issuer: "{issuer-name}"
recipient: "{family-member}"   # family variant only; omit for personal
amount: "{key-amount}"
received_date: {today}
---
```

Body: synopsis + extracted key figures + reconciliation notes section + cross-references.

Save the original PDF at `raw/tax/{year}/{form-type}-{issuer-slug}.pdf` and create a companion-page reference (per CLAUDE.md asset management).

## Side-effects

1. **Update `wiki/finances/tax/{year}/index.md`** with the new form listed.
2. **Update related holdings** if 1099-B or 1099-DIV — append to the holding's "Performance Notes" with the year's distribution / sale.
3. **Surface reconciliation gaps** if amounts don't match user-expected values. The user reconciles; the skill doesn't auto-fix.
4. **SSN protection.** Redact in body before saving; flag in the page's SSN section.
5. **Append to `log/changelog.md`**: "Tax document ingested: [[finances/tax/{year}/{slug}]]."

## Interactive Review

```
Tax document ingested: 1099-DIV — Vanguard (2025)
Recipient: Sarah
Issuer: Vanguard

Key figures:
  Ordinary dividends (1a): $1,847.32
  Qualified dividends (1b): $1,623.10
  Cap-gains distributions (2a): $284.50

Cross-references:
  - Linked to [[finances/holdings/vti-vanguard]] (Vanguard Total Stock Market)
  - Linked to [[finances/holdings/vxus-vanguard]] (Vanguard Total International)

SSN check: ✓ no SSN in body (PDF has it; not propagated to wiki)

Reconciliation: matches Sarah's Q4 dividend statement. No discrepancy flagged.

Save to wiki/finances/tax/2025/1099-div-vanguard.md?
```

## Failure Modes

- **OCR garbled** (low-quality scan). Surface extracted text; require user confirmation of key figures before saving.
- **Multiple forms in one PDF** (e.g., consolidated 1099 with sub-forms 1099-DIV / 1099-INT / 1099-B). Surface as separate pages.
- **Form type not recognized.** Ask user (uncommon types: 1099-G unemployment; 1099-S real estate; W-2G gambling).
- **SSN detected in extracted text.** Strip from body; flag for user; recommend redacting on the source PDF too.
- **Issuer ambiguous** (e.g., "Charles Schwab Bank" vs "Schwab Brokerage"). Ask user; cross-reference holdings.
- **Year not on the form** (rare; some K-1s ship without prominent year markers). Ask user.

## Privacy

Tax documents contain highly sensitive data: SSN, full income, account numbers. Apply the variant CLAUDE.variant.md privacy rules:
- Never route tax-document content to external research providers
- Abstract queries only ("what's the long-term cap-gains rate for high-income filers" is fine; "what should I do about my K-1 income from XYZ partnership" is NOT)
- Vault encryption (cloud drive at-rest) is the baseline; if using Git, keep private

## Cadence

- **Tax season (Jan-Apr):** Run as forms arrive — typically 8-15 forms per filer, more if multi-employer / multi-broker.
- **Year-round for K-1s and amended forms.**
- **Pairs with future `tax-year-summary` operation** (deferred) that aggregates a year's forms into a filing-prep summary.
