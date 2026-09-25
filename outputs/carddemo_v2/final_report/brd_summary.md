# AWS CardDemo — Business Requirements Summary

**Full BRD:** brd.md · **Generated:** 2026-09-25

## What this system does

AWS CardDemo runs the core of a credit-card business. It signs users on, maintains credit-card accounts, their customers and their cards, captures and posts card transactions, calculates monthly interest, takes bill payments, produces account statements and transaction reports, and makes real-time approve-or-decline decisions on card authorization requests. Regular users work from a Main menu of account, card, transaction, bill-payment and report functions; administrators also have an Admin menu for maintaining application users. Online screens handle day-to-day work, while batch jobs post each day's transactions, apply monthly interest and produce statements.

## At a glance

- Programs: 44 (25 online, 17 batch, 2 shared)
- Business rules: 44 in 8 rule sets
- Data: 334 entities, 596 records, 10223 fields
- Open gaps: 16 (0 high/critical)

## Business capabilities

- **Sign-On and Access Control** — 3 programs
- **User Administration** — 4 programs
- **Account Management** — 5 programs
- **Card Management** — 5 programs
- **Transaction Entry and Posting** — 5 programs
- **Interest and Bill Payment** — 2 programs
- **Statements and Reporting** — 4 programs
- **Card Authorization** — 8 programs
- **Transaction Type Reference Data** — 3 programs
- **Data Migration and Shared Services** — 5 programs

## Key business rules

- **BR-018** — Reject a transaction that would take the account over its credit limit
- **BR-019** — Reject a transaction dated after the account expiration date
- **BR-021** — Post a daily transaction only when it passes every validation
- **BR-020** — Treat zero or positive amounts as credits and negative amounts as debits
- **BR-039** — Decline an authorization that exceeds the available credit
- **BR-035** — Treat response code 00 as an approved authorization
- **BR-009** — Reject a Social Security Number with an invalid first part
- **BR-040** — Approve an authorization that passes all decline checks
- **BR-043** — Classify the reason for a declined authorization
- **BR-024** — Compute interest only when the interest rate is not zero

## High-severity gaps

- None.

## Next steps

1. Review the key business rules in section 4.1 with business owners, starting with the transaction posting and card authorization decisions.
2. Resolve the nine low-confidence rules recorded as GAP-003 to GAP-011, in particular the 2525.00 extract default (BR-005) and the full-balance bill payment (BR-027).
3. Locate the missing transaction-type database definitions (GAP-001, GAP-002) and complete the data model.
4. Walk through the ambiguous logic in GAP-012 to GAP-016 with subject-matter experts.
5. Build test cases from the confirmed rules for daily posting, interest, bill payment and authorization before changing those programs.
6. Review the statement generator and the other unstructured and high-complexity programs to decide how their control flow will be replaced.
7. Plan how each platform dependency (CICS, IMS, IBM MQ, DB2 and Language Environment services) will be replaced or retained.
