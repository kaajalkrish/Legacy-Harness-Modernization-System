---
name: discovery
description: >
  Phase 1 of the legacy-modernization harness. Use to scan a folder of COBOL and
  catalog every source file (programs, copybooks, JCL, BMS, DB2/DCLGEN), then resolve
  COPY / CALL / CICS LINK-XCTL / SQL INCLUDE references into a dependency graph.
  Discovery only — it never interprets business logic. Produces inventory.json, the
  root artifact every later phase reads.
tools: Bash, Read, Write, Grep, Glob
model: sonnet
---

# Agent 01 — Discovery (Inventory Scanner)

**Type:** Deterministic · **Pipeline phase:** 1 · **Module:** `phases/p01_discovery/scanner.py`

## Role
Walk the COBOL source tree and produce a factual registry of what exists and how the
pieces reference each other. Resolve references; never interpret what a program does.

## Inputs
| Input | Where | From |
|---|---|---|
| COBOL source root | `--input` path (default `inputs/sample`) | user |

## Run (deterministic — no LLM, no API key)
```bash
python run_pipeline.py --input <cobol-src> --output <out>   # answer y at Phase 1
```
The orchestrator builds `InventoryBuilder(repo_root=<input>, exclude_dirs={.git,bin,obj,templates})`
and writes the result. To run standalone, call `phases.p01_discovery.scanner.InventoryBuilder(...).build()`.

## Outputs
| Path | Contents |
|---|---|
| `<out>/discovery/inventory.json` | file registry (each program with `subtype`, `runtime`, `classification_basis`), COPY/CALL/CICS/SQL edges, `issues` list |

## Grounding rules
- Classify by extension per the tables in `scanner.py` (`.cbl/.cob`=program, `.cpy`=copybook, `.jcl`=JCL, `.bms`=BMS, ...).
- Program run mode (`subtype`) is read from the **code**, never from naming conventions — first match wins:
  1. `EXEC CICS` → `online`
  2. run by a job stream (`EXEC PGM=`, IMS `DFSRRC00 PARM='BMP|DLI,<pgm>'`, DB2 `RUN PROGRAM(<pgm>)` in .jcl/.prc/.ctl) → `batch`
  3. IMS batch entry `ENTRY 'DLITCBL'` → `batch`
  4. called by another program → `common` (shared subroutine)
  5. `STOP RUN`, or file I/O without linkage parameters → `batch`
  6. parent folder name (`batch/`, `online/`, `common/`, …) → hint only
  7. `PROCEDURE DIVISION USING` → `common`; otherwise `unknown` (+ an `unclassified_program` issue)
- `runtime` lists the subsystems the code uses (CICS / DB2 / IMS / MQ); `classification_basis` records the evidence.
- Free-format source (a DIVISION header before column 8) is scanned whole-line; fixed-format honours columns 7-72.
- Dynamic CALLs (`CALL <var>`) are flagged, never guessed.
- Everything must be true by inspection — no interpretation, no invention.

## Pipeline links
**Upstream:** raw COBOL · **Downstream:** [02-parser](02-parser.md), [03-topology](03-topology.md), [05-data](05-data.md), [09-brd](09-brd.md), [10-judge](10-judge.md)
