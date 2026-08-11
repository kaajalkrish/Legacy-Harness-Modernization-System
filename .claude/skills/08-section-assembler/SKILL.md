---
name: section-assembler
description: >
  Assemble the Business Requirements Document from the artifacts — inventory tables, data
  dictionary, business-rules catalogue, process summaries, error catalogue, diagrams and
  appendices — as deterministic Python, leaving only the connecting narrative to the LLM.
  Part of the BRD agent (Phase 8).
---

# Skill: section-assembler

**Used by:** [09-brd](../../agents/09-brd.md) · **Half:** deterministic + LLM prose · **Adapted from:** Udara legacy-modernization-harness

## Input
`inventory.json`, `parser_artifact.json`, `data_artifact.json`, `logic_artifact.json`,
`rules_artifact.json`, the `*.mmd` diagrams, and the gaps register.

## Task (deterministic)
- Build each BRD chapter from the artifacts: system overview + inventory tables, the data
  dictionary, the business-rules catalogue, per-process summaries, the error catalogue,
  embedded Mermaid diagrams, and appendices.
- Emit stable ids (`BR-`, `GAP-`, `RS-`) and cite programs exactly as they appear upstream.

## LLM boundary
Only the connecting prose — executive summary, system-context narrative, per-process
narratives — is written by the model. Facts, tables and ids are assembled by code.

## Rules
- Every id and program referenced in prose must already exist in the assembled sections
  (this is what the [groundedness-gate](../09-groundedness-gate/SKILL.md) later checks).

## Output
`final_report/brd.md` + `brd_summary.md`.
