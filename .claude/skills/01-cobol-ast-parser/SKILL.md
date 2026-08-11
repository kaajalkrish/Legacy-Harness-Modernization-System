---
name: cobol-ast-parser
description: >
  Extract the structural skeleton of a single COBOL program — divisions, sections,
  paragraphs (with line ranges) and the WORKING-STORAGE data entries — using
  fixed-column rules and pure stdlib regex, no COBOL grammar library. Deterministic;
  the first half of the Parser agent (Phase 2).
---

# Skill: cobol-ast-parser

**Used by:** [02-parser](../../agents/02-parser.md) · **Half:** deterministic · **Adapted from:** Udara legacy-modernization-harness (2_parser) · **Implements:** `phases/p02_parser/engine.py` → `CobolAstParser`

## Input
One COBOL source file (path from `discovery/inventory.json`), read with the harness's
fixed-column reader (`read_source_lines`).

## Task
- Identify the four divisions and their sections/paragraphs.
- Record each paragraph with its **source line range**.
- Parse the DATA DIVISION / WORKING-STORAGE level entries (level number, name, PIC,
  REDEFINES, OCCURS, 88-levels) and `COPY` stubs.
- Collect `issues` for anything unparseable — never silently drop it.

## Rules
- Pure stdlib, no grammar library; structure only, no interpretation of meaning.
- Line ranges come from the source, never estimated.

## Output
The AST dict (`procedure_division.paragraphs/sections`, `data_division` entries) that
`section-mapper` then enriches, written to `analysis/raw_structure/<PROGRAM>.json`.
Pairs with [section-mapper](../02-section-mapper/SKILL.md).
