---
name: groundedness-gate
description: >
  The harness's anti-hallucination check: verify every BR-/GAP-/RS- id and every program
  the BRD cites actually exists in the upstream artifacts, plus cross-artifact consistency
  checks. Deterministic and authoritative — an invented reference hard-floors the accuracy
  score. Core of the Judge agent (Phase 9).
---

# Skill: groundedness-gate

**Used by:** [10-judge](../../agents/10-judge.md) · **Half:** deterministic (authoritative) · **Adapted from:** Chaminda cobol_java_migrator judge

This is code, not opinion.

## Input
`final_report/brd.md`, `gaps_register.json`, and the upstream `inventory.json`,
`data_artifact.json`, `logic_artifact.json`, `rules_artifact.json`, diagrams index.

## Checks
1. **Groundedness:** every `BR-`/`GAP-`/`RS-` id and every program name cited in the BRD
   must resolve to a real entry in the artifacts.
2. **Consistency:** counts and references in the prose agree with the artifacts (rules
   count, program count, gap ids, etc.).

## Verdict contribution
- Any unresolved reference → **hard-floor the accuracy dimension**, regardless of the
  LLM's prose score. This is what makes the harness trustworthy.

## Output
The gate result + consistency-issue list, fed into the PASS / REVISE decision in
`phases/p10_judge/brd_judge.py`. Pairs with the [brd-scorer](../10-brd-scorer/SKILL.md).
