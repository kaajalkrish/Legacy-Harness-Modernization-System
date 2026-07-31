---
name: brd_agent
adapted_from: Udara legacy-modernization-harness — .github/skills/gap-detector + section-assembler
description: >
  Phase 8 (final) of the new_legacy_harness. Assembles all prior artifacts into a single
  Business Requirements Document (brd.md) plus an executive summary and a gaps register.
  HYBRID: gap-detection and document assembly (tables, the business-rules catalogue, process
  summaries, error catalogue, appendices) are deterministic Python; the synthesis PROSE
  (executive summary, system-context narrative, per-process narratives) is written by the LLM.
  Two run modes: A) brd/brd_builder.py (LLM prose when a key is set; templated fallback),
  B) AI-host — this file run by Claude Code (no key), writing the narrative prose itself.
---

# BRD Agent (Synthesis)

## Role
Write the final Business Requirements Document a business analyst can read without knowing COBOL.
Never invent content — every statement traces to an artifact; label confidence and gaps.

## Inputs
inventory.json (P1) · parser_artifact.json (P2) · data_artifact.json (P5) · logic_artifact.json (P6)
· rules_artifact.json (P7).  Diagrams (Diagram agent) are referenced as placeholders until built.

## Deterministic vs LLM
- Deterministic (Python): gap register (aggregate unresolved refs, empty/truncated/skeleton programs,
  low-confidence rules, SME flags); all tables (inventory, copybooks, data entities, error catalogue);
  the business-rules catalogue (descriptions already written in Phase 7); per-program process summaries;
  appendices.
- LLM (paid step): executive summary; system-context narrative; per-process narratives that weave
  logic + rules into plain-English prose.

## Chapters (brd.md)
1 Executive summary · 2 System overview · 3 System inventory · 4 Data model · 5 Business rules
catalogue · 6 Process descriptions · 7 Component architecture · 8 Error handling · 9 Gaps & assumptions
· Appendices (A full data dictionary, B pseudocode reference, C diagram index).

## Output — outputs/final_report/
gaps_register.json + gaps_register.md · brd.md · brd_summary.md.

## Style (from Udara)
Plain English, present tense, active voice, no COBOL jargon (explain on first use). Business-readable
field names with the COBOL name in parentheses. Always show rule IDs and confidence marks (✓ / ⚠).
Every diagram has a figure number + caption. Prefer tables over bullet lists for structured data.
