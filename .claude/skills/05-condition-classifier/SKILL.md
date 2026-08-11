---
name: condition-classifier
description: >
  Classify each extracted branch condition and 88-level into a business-rule category
  (validation / calculation / limit / routing / state) with a pattern and a signal
  strength, then de-duplicate identical conditions across programs. Used by the Rules
  agent (Phase 7). Deterministic — no invention.
---

# Skill: condition-classifier

**Used by:** [07-rules](../../agents/07-rules.md) · **Half:** deterministic · **Adapted from:** Udara legacy-modernization-harness

This is the **deterministic** half of Phase 7 and runs before the
[rule-tagger](../06-rule-tagger/SKILL.md).

## Input
- Branch conditions from `logic/logic_artifact.json` (Phase 6).
- 88-level condition names from `data/data_artifact.json` (Phase 5).

## Classify each condition
- **Category:** validation · calculation · limit/threshold · routing/dispatch · state/status.
- **Pattern:** the shape of the test (equality, range, flag/88, table lookup, ...).
- **Signal strength:** how confidently it is a business rule vs. incidental control flow.

## De-duplicate
- Fold conditions that are the same test across programs into one entry; record every
  source program + line so nothing is lost.

## Output
`classified_conditions.json` — one entry per distinct condition with `category`,
`pattern`, `signal`, and its source references.

## Rule
Classification and de-duplication are factual and deterministic. This step decides
*which rules exist*; it must never depend on the LLM.
