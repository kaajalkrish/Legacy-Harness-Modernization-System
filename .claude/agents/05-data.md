---
name: data
description: >
  Phase 5 of the legacy-modernization harness. Use to turn the cryptic DATA DIVISION
  into a clean data dictionary — expand COPY stubs into real fields, decode PIC clauses
  into type/size/decimals, resolve REDEFINES and OCCURS tables, and surface 88-level
  condition names (the seeds of business rules). 100% rule-based, no LLM. Produces
  data_artifact.json plus per-copybook / per-program layouts.
tools: Bash, Read, Write, Grep, Glob
model: sonnet
---

# Agent 05 — Data (Data Dictionary)

**Type:** Deterministic · **Pipeline phase:** 5 · **Module:** `phases/p05_data/data_builder.py`

## Role
Produce the full, flat data dictionary and an ERD-ready data model. Entirely
deterministic — decoding, not interpreting.

## Inputs
| Input | Where | From |
|---|---|---|
| Copybook registry + map + repo_root | `discovery/inventory.json` | Phase 1 |
| Parsed ASTs | `analysis/raw_structure/<PROGRAM>.json` | Phase 2 |
| Copybooks | repo | source |

## Run (deterministic)
```bash
python -m phases.p05_data.data_builder --inventory <out>/discovery/inventory.json \
    --ast-dir <out>/analysis --output-dir <out>/data
```

## Outputs
| Path | Contents |
|---|---|
| `<out>/data/data_layouts/<COPYBOOK>.json` | one file per copybook (expanded) |
| `<out>/data/data_layouts/<PROGRAM>_WS.json` | one file per program (inline + expanded) |
| `<out>/data/data_artifact.json` | unified dictionary + data model |

## Grounding rules
- COPY stubs are expanded into real fields; PIC → type/size/decimals by rule.
- REDEFINES, OCCURS and 88-levels are surfaced, not guessed.

## Pipeline links
**Upstream:** [01-discovery](01-discovery.md), [02-parser](02-parser.md) · **Downstream:** [06-logic](06-logic.md), [07-rules](07-rules.md), [08-diagram](08-diagram.md), [09-brd](09-brd.md), [10-judge](10-judge.md)
