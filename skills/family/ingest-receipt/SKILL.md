---
name: ingest-receipt
description: "Capture a receipt (photo, PDF, statement entry, or emailed receipt) and route it to the appropriate domain (finances, home, food, vehicle, health) based on what was purchased. Use when a receipt photo or PDF is dropped, a credit-card line is pasted, an email receipt is forwarded, or the user says \"save this receipt\" / \"track this expense\"."
license: MIT
metadata:
  variant: family
---

# Ingest Receipt Skill (Family Variant)

Specialized content-type ingester for receipts — photos, PDFs, statement entries, emailed receipts. Composes a source-type ingester for cleanup, then applies receipt schema. Output lands in the appropriate domain (finances, home, food, vehicle, health) based on what was purchased.

## When to Use

The orchestrator routes here when:
- A receipt photo is dropped (snapshot from phone camera)
- A PDF or email receipt is forwarded
- A statement entry is pasted (credit card line item)
- The user says "save this receipt" / "track this expense"

## Composition (two-axis routing)

| Source | Source-type cleanup | Result |
|---|---|---|
| Receipt photo | [[ingest-document]] (Docling with OCR) | OCR'd text |
| Receipt PDF / email PDF | [[ingest-document]] (Docling) | clean markdown |
| Pasted statement entry | none — handle directly | raw text |
| Email forward (forwarded receipt) | [[ingest-website]] if URL inside, or paste handling | content |

## Inputs

After source-type cleanup:
- The cleaned-up receipt content
- `wiki/home/vendors.md` — to identify recurring vendors
- `wiki/home/maintenance/schedule.md` — if the receipt is for a maintenance event
- `wiki/home/vehicles/` — if for vehicle service
- `wiki/home/appliances.md` — if for appliance purchase / repair

## Algorithm

1. **Extract core fields.** Vendor / merchant, total amount, date, payment method, individual items if itemized.
2. **Categorize.** Domain inference based on vendor + items:
   - Groceries → `wiki/finances/expenses/groceries.md` or just logged in `food/`
   - Restaurant → `finances/expenses/dining.md`
   - Vehicle service → `home/vehicles/{vehicle}-service-history.md`
   - Home maintenance / repair → `home/maintenance/history.md` + vendor update
   - Appliance / electronics → `home/appliances.md` (warranty tracking)
   - Medical → `health/{person}-medical.md` (cost breakdown)
   - Travel → `travel/upcoming/{trip}.md` or `travel/past/{trip}.md`
3. **Detect new vendor.** If the merchant isn't in `home/vendors.md`, surface for addition.
4. **Detect warranty / return window.** If the receipt is for a purchase, note the return window and any warranty period.
5. **Surface tax-relevant items.** Charitable donations, business expenses (if user tracks), medical expenses for FSA.

## Output

The output destination depends on category. Common patterns:

**For vehicle service:**
Append to `wiki/home/vehicles/{vehicle}-service-history.md`:
```markdown
## 2026-04-15 — Oil change + tire rotation

**Vendor:** Quick Lube Express ([[home/vendors#quick-lube-express]])
**Cost:** $89.50
**Mileage at service:** 47,820

Items:
- Synthetic oil change
- Tire rotation
- 27-point inspection (no issues)

Next service due: 50,000 mi or 6 months
```

**For appliance purchase:**
Update `wiki/home/appliances.md` with warranty details + companion page for receipt.

**For grocery / restaurant:**
Lighter — log in a per-month `wiki/finances/expenses/{YYYY-MM}.md` page.

**Always:** save the raw receipt to `raw/{YYYY-MM-DD}-{vendor-slug}.md` (or as a PDF/image companion). Create companion page if the original is a binary worth keeping for warranty / tax purposes.

## Side-effects

1. **Update `wiki/home/vendors.md`** if a new vendor appeared.
2. **Surface warranty / return windows** in the appropriate domain page.
3. **Append to `log/changelog.md`**: "Receipt ingested: {vendor}, ${amount}, {category}."
4. **For vehicle service:** trigger next-service calculation; surface in [[follow-up-tracker]].

## Interactive Review

```
Receipt ingested: Quick Lube Express, 2026-04-15, $89.50

Detected category: vehicle service (Honda CR-V based on context)

Items:
  - Synthetic oil change
  - Tire rotation
  - 27-point inspection (no issues)

Mileage: 47,820 (matches recent vehicle entry)

Vendor: Quick Lube Express
  Status: NEW vendor — add to home/vendors.md?

Next service: ~50,000 mi or 2026-10-15 (whichever first)
  → Will surface in follow-up-tracker

Apply: append to vehicle service history? Add vendor? Set follow-up?
```

## Failure Modes

- **OCR garbled.** Surface the extracted text; ask the user to confirm vendor / amount / date before saving.
- **Category ambiguous.** Hardware store could be home repair OR a kid's project; ask the user.
- **Receipt without itemization.** Single-line total; capture but flag that items aren't tracked. For tax / warranty purposes, surface to the user that the binary should be retained.
- **Multi-domain receipt** (e.g., a Costco run with groceries + vehicle supplies + home goods). Either decompose or save as multi-category with notes.

## Cadence

- **On demand:** Run when receipts arrive (typically right after a transaction or at end of day).
- **No scheduling:** Reactive.
- **Habit:** Establish a weekly "receipt sweep" if backlog tends to grow.
