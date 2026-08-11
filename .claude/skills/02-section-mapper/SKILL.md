---
name: section-mapper
description: >
  Enrich a parsed COBOL AST with a paragraph-level control-flow graph — PERFORM ranges,
  GO TO edges, and the section→paragraph mapping — deterministically. This is the real,
  used realization of control-flow tracing in the harness (Phase 2); the LLM never
  re-derives it. Second half of the Parser agent.
---

# Skill: section-mapper

**Used by:** [02-parser](../../agents/02-parser.md) · **Half:** deterministic · **Adapted from:** Udara legacy-modernization-harness (2_parser) · **Implements:** `phases/p02_parser/engine.py` → `SectionMapper`

## Input
The AST from [cobol-ast-parser](../01-cobol-ast-parser/SKILL.md) plus the raw source
lines.

## Task
- Build the paragraph-level **control-flow graph**: `PERFORM` / `PERFORM THRU` ranges
  between paragraphs, `GOTO` / `GOTO_DEPENDING` edges (each flagged for review), and
  call edges (`STATIC_CALL`, `CICS_LINK`, `CICS_XCTL`).
- Map sections to their member paragraphs.
- Collect `cfg_issues` for unresolved targets.

## Rules
- Deterministic — this is the harness's control-flow tracer; downstream phases consume
  the CFG rather than re-computing it (see [control-flow-tracer](../03-control-flow-tracer/SKILL.md)).

## Output
`control_flow_graph` merged into `analysis/raw_structure/<PROGRAM>.json`.
