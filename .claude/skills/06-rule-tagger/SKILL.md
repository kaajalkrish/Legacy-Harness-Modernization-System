---
name: rule-tagger
description: >
  Give each classified business rule (and rule set) a concise human-readable NAME and
  DESCRIPTION. This is the LLM half of the Rules agent (Phase 7); a templated fallback is
  used when no API key is set. Naming only — it must not change which rules exist.
---

# Skill: rule-tagger

**Used by:** [07-rules](../../agents/07-rules.md) · **Half:** LLM (cosmetic) · **Adapted from:** Udara legacy-modernization-harness

Runs after the [condition-classifier](../05-condition-classifier/SKILL.md).

## Input
`classified_conditions.json` — de-duplicated, categorized conditions grouped into rule
sets.

## Task
For each rule / rule set write:
- a short **name** (e.g. "Credit limit must not be exceeded"),
- a one- or two-sentence **description** in business language.

## Rules
- Describe only the classified condition — do not add, merge, split or drop rules.
- Keep each rule traceable to its `BR-`/`RS-` id and source program/line.
- No key set → use the deterministic templated name/description fallback.

## Output
The `name` + `description` fields merged into `rules_artifact.json`.
