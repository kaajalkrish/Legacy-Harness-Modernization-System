---
name: brd_judge_agent
adapted_from: Chaminda cobol_java_migrator — src/cobol_modernizer/agent/brd_judge.py
description: >
  Phase 9 of the new_legacy_harness — BRD Validation (the Judge). Validates the generated BRD for
  completeness, accuracy, clarity, consistency and actionability, with a deterministic groundedness
  gate that hard-floors accuracy when the BRD cites anything that does not exist in the artifacts.
  HYBRID: the groundedness gate and consistency checks are deterministic Python; the five 1-5
  dimension scores + written feedback are the LLM's job. Two run modes: A) brd/brd_judge.py (LLM
  scoring when a key is set; --scores-file for the AI-host path; neutral 3s otherwise),
  B) AI-host — Claude Code writes the scores/feedback JSON and passes it via --scores-file.
---

# BRD Judge (Validation)

## Role
Grade the BRD and gate it before sign-off. Never let ungrounded content pass: every reference the
BRD makes must trace to a real artifact.

## Inputs
brd.md (Agent 8) + inventory (A1) + data (A5) + logic (A6) + rules (A7) + gaps_register.json.

## Dimensions & weights (from Chaminda)
completeness 0.25 · accuracy 0.30 · clarity 0.15 · consistency 0.15 · actionability 0.15.
Weighted score -> rating: high (>=4.2 and every dim >=3) · medium (>=3.2 and every dim >=2) · low.

## Deterministic gate + checks (Python)
- Groundedness: every BR-###, GAP-###, RS-### the BRD cites must exist in the artifacts. Any
  invented reference is a groundedness failure and hard-floors the accuracy score to 2.
- Consistency: all 9 chapters present; the headline numbers (programs / rules / gaps) match the
  artifacts; every rule and gap is referenced; the generated diagrams are embedded. A high-severity
  consistency issue caps the consistency score at 2.

## LLM step
Score the 5 dimensions 1-5 with a rationale and write feedback items
{dimension, severity, suggestion, target_section} — the input for the next stage (BRD Improvement).

## Verdict
PASS when rating is high/medium and there is no high-severity issue and no groundedness failure;
otherwise REVISE.

## Output — outputs/final_report/
brd_validation.json (verdict, rating, weighted score, per-dimension scores, groundedness_failures,
consistency_issues, feedback) + brd_validation.md (human-readable report).
