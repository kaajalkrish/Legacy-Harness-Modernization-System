---
name: section-assembler
description: >
  Assemble the Business Requirements Document from the artifacts — cover, table of contents,
  at-a-glance facts, capabilities, business-rules catalogue, data model, process descriptions,
  architecture/inventory, technical conditions, gaps, risk indicators and appendices — as
  deterministic Python, leaving only the connecting narrative to the AI step (Claude Code
  writing brd_narratives.json, or the API). Part of the BRD agent (Phase 8).
---

# Skill: section-assembler

**Used by:** [09-brd](../../agents/09-brd.md) · **Half:** deterministic + AI prose · **Adapted from:** Udara legacy-modernization-harness

## Input
`inventory.json`, `parser_artifact.json`, `data_artifact.json`, `logic_artifact.json`,
`rules_artifact.json` (with capabilities), the `*.mmd` diagrams, and the gaps register.

## Task (deterministic)
- Build every chapter's facts from the artifacts (structure in
  [brd_agent.md](../../../phases/p09_brd/brd_agent.md)): at-a-glance table, capability and
  program tables, the key-rules table and full catalogue, data model, process descriptions with
  flow diagrams, inventory, platform dependencies, technical conditions, gaps, structural risk
  indicators (GO TO, ALTER, complexity, dead code) and appendices.
- Emit stable ids (`BR-`, `TR-`, `RS-`, `GAP-`) and cite programs exactly as upstream.
- Write `brd_brief.json` — the only facts the AI step may use.

## AI boundary
The AI writes only prose sections into `brd_narratives.json`: executive summary, business
purpose, users & actors, scope, system context, per-capability narratives, key-rule selection,
modernization considerations, next steps. Without it, a neutral fact-based template is used.

## Rules
- A narrative section citing an id that does not exist is dropped; a stale fingerprint rejects
  the file. The [groundedness-gate](../09-groundedness-gate/SKILL.md) re-checks the whole BRD.
- The fallback template contains no domain wording — only counts, run modes, subsystems and
  program summaries.

## Output
`final_report/brd.md` + `brd_summary.md` + `brd_brief.json`.
