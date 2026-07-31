---
name: rules_agent
adapted_from: Udara legacy-modernization-harness — .github/skills/condition-classifier + rule-tagger
description: >
  Phase 7 of the new_legacy_harness. Turns the branching conditions extracted by the
  Logic agent (Phase 6) and the 88-level conditions from the Data agent (Phase 5) into a
  named, deduplicated business-rules catalogue. HYBRID: condition extraction, classification,
  deduplication and grouping are deterministic Python; the business-readable rule NAME and
  DESCRIPTION are written by the LLM. Two run modes, same output shape:
    A) rules/rules_builder.py  (deterministic classify + LLM descriptions when a key is set; a
       templated fallback otherwise).
    B) AI-host — this file executed by Claude Code / Copilot (no API key), writing the polished
       names/descriptions itself.
---

# Rules Agent

## Role
Extract, classify and document every business rule embedded in the codebase — turn raw
branching logic into a named catalogue a business analyst can validate without knowing COBOL.
Never invent a rule: every rule traces back to a specific program/paragraph/line.

## Inputs (this project's paths)
| Input | Where | From |
|---|---|---|
| Branches per paragraph | outputs/logic/program_logic/<PROGRAM>_logic.json  (`branches`) | Phase 6 |
| 88-level conditions + field types | outputs/data/data_artifact.json | Phase 5 |

## What is deterministic vs LLM
- Deterministic (Python, rules_builder.py): collect conditions; classify each into a category
  (VALIDATION / CALCULATION / ROUTING / LIMIT_CHECK / ERROR_HANDLING / COMPLIANCE), a structural
  pattern, and a 1-5 signal strength; drop noise (signal 1 → error-handling catalogue); promote
  signal ≥ 2; deduplicate across programs; group into rule sets; assign confidence.
- LLM (the paid step): for each promoted condition write the business-readable NAME (imperative,
  e.g. "Enforce transaction amount does not exceed credit limit") and a 2-3 sentence DESCRIPTION,
  grounded only in the condition + its source. Same order; do not invent thresholds or outcomes.

## Classification signals (from Udara, kept)
- VALIDATION: field suffix -TYPE/-CODE/-STATUS/-FLAG/-IND; 88-level conditions (signal 5);
  paragraph VALIDATE/CHECK/VERIFY/EDIT.
- ROUTING: EVALUATE on a function/type/command field; GO TO … DEPENDING (signal 4).
- LIMIT_CHECK: >, <, >=, <= against LIMIT/MAX/MIN/BALANCE/AMOUNT/THRESHOLD/RETRY/FREQUENCY (signal 4-5).
- CALCULATION: COMPUTE/ADD/…; paragraph CALC/TOTAL/RATE/INTEREST/FEE.
- ERROR_HANDLING (noise, signal 1): file status, SQLCODE, CICS RESP, AT END, INVALID KEY.
- COMPLIANCE: AUDIT/SECURITY/AUTH; amounts ≥ regulatory thresholds (flag for SME).

## Naming (from Udara, kept)
NAME = VERB(by category) + business field name (strip WS-/LS-/… prefixes, expand abbreviations
ACCT→Account, TRANS→Transaction, LMT→Limit, …) + qualifier from the structural pattern.

## Output schema — outputs/rules/
- classified_conditions.json — every condition with category / pattern / signal (intermediate).
- rules_artifact.json — meta + stats (by_category, by_confidence) + rule_sets + business_rules
  (rule_id, name, category, confidence, requires_sme_review, description, condition, sources,
  primary_source, implemented_in_programs, is_duplicated) + error_handling_catalogue + rules_by_program.

## Constraints (from Udara)
- Every rule traces to ≥ 1 source line. If purpose is unclear, confidence "low" + requires_sme_review.
- 88-level names are near-certain rule indicators. Do not merge rules on different fields without flagging.
