# Portfolio Management System — Business Requirements Summary

**Full BRD:** brd.md · **Generated:** 2026-07-18

## What this system does

The Portfolio Management System is a mixed batch/online system. Online inquiry transactions run under CICS (screen handlers such as the portfolio and history inquiries), while batch jobs perform bulk maintenance, reporting and data loads. Shared services provide DB2 connection management, commit control, error logging and audit trail writing. Data is held in indexed VSAM files (portfolio master, position, transaction history) and DB2 tables.

## Scale

- Programs: 21 (5 batch, 4 online)
- Business rules: 110 in 44 rule sets
- Data: 146 records, 823 fields
- Gaps: 26 (3 high/critical)

## Key rule sets

- **End validation rules** — 10 rules
- **Transaction routing rules** — 9 rules
- **Portfolio validation rules** — 8 rules
- **Error validation rules** — 6 rules
- **Cursor validation rules** — 5 rules

## Critical / high gaps

- **GAP-001 (high)** — Circular COPY chain detected: CKPRST COPY CKPRST which COPYs CKPRST
- **GAP-002 (high)** — POSUPDT.cbl is empty — no program logic.
- **GAP-003 (high)** — CURSMGR.cbl truncated — fetch/close paragraphs missing though INQHIST depends on them.

## Next steps

1. Resolve 3 high/critical gaps with SME review (Chapter 9).
2. Validate the 4 low-confidence rules.
3. Confirm the estimated data relationships with a data architect.
4. Generate diagrams (Diagram agent) and embed them into the BRD.

