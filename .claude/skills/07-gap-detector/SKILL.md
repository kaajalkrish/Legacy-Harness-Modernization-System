---
name: gap-detector
description: >
  Detect and register gaps — things a modernization team must resolve with an SME:
  ambiguous logic, dynamic CALLs, unresolved copybooks/programs, missing data meanings,
  untranslated verbs. Deterministic. Part of the BRD agent (Phase 8); produces the gaps
  register.
---

# Skill: gap-detector

**Used by:** [09-brd](../../agents/09-brd.md) · **Half:** deterministic · **Adapted from:** Udara legacy-modernization-harness

## Input
All upstream artifacts: inventory `issues`, parser flags (GO TO / dynamic), logic
`ambiguous` paragraphs + `!! UNTRANSLATED` lines, unresolved references, and
undocumented data fields.

## Task
- Collect every flagged uncertainty into a single register.
- Give each a stable `GAP-` id, a category, a severity, and a pointer to its source
  (program / line / artifact).

## Rules
- A gap must trace to a real flag in an artifact — never invent a concern.
- Severity is assigned by rule; high-severity gaps are surfaced prominently.

## Output
`final_report/gaps_register.md` + `gaps_register.json`, embedded into the BRD and later
checked by the [groundedness-gate](../09-groundedness-gate/SKILL.md).
