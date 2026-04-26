---
type: index
folder: tax
status: active
provenance: mixed
created: 2026-04-25
modified: 2026-04-25
tags: [index, tax, finances]
---

## Synopsis

Tax records — one folder per tax year, containing all forms received (W-2, 1099s, 1098s, K-1s, etc.) plus reconciliation notes and filing artifacts. Each form is captured via [[ingest-tax-document]] as it arrives during tax season.

## Folder structure

```
finances/tax/
├── 2025/
│   ├── index.md                  # Year summary; total income, key sources, filing status
│   ├── w2-{employer}.md          # W-2 per employer
│   ├── 1099-div-{broker}.md      # Dividend income per broker
│   ├── 1099-b-{broker}.md        # Brokerage gain/loss per broker
│   ├── 1099-int-{bank}.md        # Interest income
│   ├── 1099-nec-{client}.md      # Self-employment / freelance income
│   ├── k1-{partnership}.md       # K-1 partnership income
│   └── return.md                 # Filing artifact / e-file confirmation
├── 2026/
│   └── ...
```

## How this folder works

Each tax document is captured as it arrives (typically Jan-Mar each year):

1. Drop the PDF into `raw/tax/{year}/{form-type}-{issuer}.pdf`
2. Run [[ingest-tax-document]] — extracts key figures, detects SSN, creates a structured `tax-document` page
3. Reconcile against expected (year-end pay stubs, brokerage statements, freelance-income invoices)
4. After filing, set `status: filed` on each form and add the return artifact

## Common access patterns

- "Pull all 1099s for 2025" → folder browse + filter by form_type
- "Total freelance income for 2025" → sum across 1099-NEC + Schedule C
- "Did the W-2 match year-end pay?" → reconciliation notes
- "Returns history" → browse year-folder index pages

## Tax-cycle cadence

- **January-March:** capture forms as they arrive
- **March-April:** reconcile + file
- **April:** confirm filing artifacts
- **Year-round:** capture deduction-relevant receipts (charity, medical, freelance business expenses) into the year folder
- **Quarterly (if self-employed):** estimated-payment dates trigger summary check

## Related

- [[ingest-tax-document]] for structured capture
- Holdings inventory cross-references for 1099-B and 1099-DIV
- Decision log captures filing-strategy decisions
- For freelance / consulting income: `wiki/career/applications/` and project pages provide income context

## Privacy

Tax records are highly sensitive. Cloud-drive at-rest encryption baseline; never send personal context to external research providers — the personal-variant CLAUDE.variant.md privacy section spells out the rule.
