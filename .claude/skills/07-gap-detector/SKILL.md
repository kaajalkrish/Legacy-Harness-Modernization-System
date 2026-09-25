---
name: gap-detector
description: >
  Detect and register gaps — things a modernization team must resolve with an SME:
  ambiguous logic, dynamic CALLs, unresolved copybooks/programs, missing data meanings,
  untranslated verbs. Deterministic. Part of the BRD agent (Phase 9); produces the gaps
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
- **One gap per missing item.** Every unresolved COPY / CALL / SQL INCLUDE target becomes a
  single gap listing all programs that reference it (inventory and data-phase reports merge).
- **Platform components are not gaps.** IBM runtime pieces — CICS (`DFH*`), MQ (`CMQ*`,
  `MQOPEN`…), IMS (`CBLTDLI`, `AIBTDLI`…), DB2 (`SQLCA`, `DSNTIAR`…), Language Environment
  (`CEE*`, `IGZ*`), COBOL runtime (`ILBO*`) — go to an **external dependencies** list
  (component, subsystem, used-by programs). They are expected to be absent from the repo.
- Assembler modules in the repo (`.asm`, `.mlc`) resolve CALLs (registered by Discovery).
- Dynamic CALLs are one gap per program + variable; informational run messages are skipped.

## Output
`final_report/gaps_register.md` + `gaps_register.json` (`gaps` + `external_dependencies`),
embedded into the BRD (Chapter 9, with 9.1 External system dependencies) and later
checked by the [groundedness-gate](../09-groundedness-gate/SKILL.md).
