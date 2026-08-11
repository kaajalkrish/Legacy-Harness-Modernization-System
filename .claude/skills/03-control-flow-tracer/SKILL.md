---
name: control-flow-tracer
description: >
  Derive a program's control-flow graph — paragraph execution order, PERFORM ranges,
  loops, GO TO edges and reachability. In Udara this was an LLM step; in THIS harness it
  is superseded by the deterministic section-mapper (Phase 2) and is never re-derived by
  the LLM. Use this skill's rules when reading or reasoning about the CFG.
---

# Skill: control-flow-tracer

**Used by:** [02-parser](../../agents/02-parser.md), [06-logic](../../agents/06-logic.md) · **Half:** deterministic (superseded by [section-mapper](../02-section-mapper/SKILL.md)) · **Adapted from:** Udara legacy-modernization-harness

In Udara this was an **LLM** skill (the Logic phase re-derived execution order, loops and
dead code). **This harness deliberately drops that** — the deterministic
[section-mapper](../02-section-mapper/SKILL.md) already produces the CFG in Phase 2, so it
is never re-traced (cheaper, no re-hallucination). Kept here for provenance and to define
how the CFG is consumed.

## What the CFG contains
- Paragraph nodes with source line ranges.
- `PERFORM` edges (including `PERFORM THRU` ranges) between paragraphs.
- `GOTO` / `GOTO_DEPENDING` edges — every one flagged for review.
- Call edges: `STATIC_CALL`, `CICS_LINK`, `CICS_XCTL`.

## How to use it downstream (Logic, Phase 6)
- Read the CFG; do **not** re-derive execution order, loops or dead code with the LLM.
- Attach line ranges from the CFG — never ask the model to estimate them.
- Treat flagged `GO TO` / dynamic edges as SME-review items.

## Output
Consumed from `analysis/raw_structure/<PROGRAM>.json` → `control_flow_graph`.
