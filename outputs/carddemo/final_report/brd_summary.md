# AWS CardDemo — Business Requirements Summary

**Full BRD:** brd.md · **Generated:** 2026-07-28

## What this system does

The AWS CardDemo is a mixed batch/online system. Online inquiry transactions run under CICS (screen handlers such as the portfolio and history inquiries), while batch jobs perform bulk maintenance, reporting and data loads. Shared services provide DB2 connection management, commit control, error logging and audit trail writing. Data is held in indexed VSAM files (portfolio master, position, transaction history) and DB2 tables.

## Scale

- Programs: 44 (13 batch, 27 online)
- Business rules: 324 in 94 rule sets
- Data: 596 records, 10223 fields
- Gaps: 253 (0 high/critical)

## Key rule sets

- **Edit validation rules** — 72 rules
- **End validation rules** — 16 rules
- **Transaction routing rules** — 16 rules
- **Error validation rules** — 14 rules
- **Cdemo validation rules** — 13 rules

## Critical / high gaps

- None flagged at critical/high severity.

## Next steps

1. Resolve 0 high/critical gaps with SME review (Chapter 9).
2. Validate the 72 low-confidence rules.
3. Confirm the estimated data relationships with a data architect.
4. Generate diagrams (Diagram agent) and embed them into the BRD.

