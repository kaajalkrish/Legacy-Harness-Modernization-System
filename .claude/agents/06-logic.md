---
name: logic
description: >
  Phase 6 of the legacy-modernization harness — the first hybrid (LLM) phase. Use to
  translate each COBOL paragraph into clear, plain-English pseudocode and capture its
  branches, calls, field references, complexity score and idiom annotations. Python
  gathers and bounds the clues; the LLM writes the pseudocode; Python writes the files.
  Runs via the AI-host path (Claude Code, NO API key) or phases/p06_logic/logic_builder.py (with a
  key). Produces per-program logic + logic_artifact.json.
tools: Read, Write, Bash, Grep, Glob
---

# Agent 06 — Logic (Plain-English Pseudocode)

**Type:** LLM + Python · **Pipeline phase:** 6 · **Module:** `phases/p06_logic/logic_builder.py` · **Prompt:** [phases/p06_logic/logic_agent.md](../../phases/p06_logic/logic_agent.md)

## Role
Explain what each program *does*, step by step, in language a business analyst can
read. Do **not** re-derive control flow — Phase 2 already produced the AST + CFG
deterministically. You do the interpretive part only.

> **Full prompt, translation catalogue, complexity scoring and JSON schema:**
> follow [phases/p06_logic/logic_agent.md](../../phases/p06_logic/logic_agent.md) exactly. It must match
> `phases/p06_logic/logic_builder.py`'s `OUTPUT_SCHEMA` — do not restate or drift from it.

## Inputs
| Input | Where | From |
|---|---|---|
| Program structure + CFG | `analysis/raw_structure/<PROGRAM>.json` | Phase 2 |
| Context sheet | `context/<PROGRAM>_context.txt` | Phase 4 |
| Data dictionary | `data/data_artifact.json` | Phase 5 |
| Raw COBOL source | AST `meta.source_file` | repo |

## Run — two modes, same output shape
**A — AI host (no key):** read the clues and emit the schema JSON directly.
**B — Python + key:**
```bash
python -m phases.p06_logic.logic_builder --inventory <out>/discovery/inventory.json \
    --ast-dir <out>/analysis --context-dir <out>/context \
    --data <out>/data/data_artifact.json --output-dir <out>/logic
```

## Outputs
| Path | Contents |
|---|---|
| `<out>/logic/program_logic/<PROGRAM>_logic.json` | per-program pseudocode |
| `<out>/logic/logic_artifact.json` | aggregate |

## Grounding rules
- Describe only what the code does; never invent logic or literals (use named placeholders).
- Dynamic CALL / untranslatable verb → `ambiguous=true`, note it, mark the line.

## Pipeline links
**Upstream:** [02-parser](02-parser.md), [04-context](04-context.md), [05-data](05-data.md) · **Downstream:** [07-rules](07-rules.md), [08-diagram](08-diagram.md), [09-brd](09-brd.md)

## Related skills
[pseudocode-generator](../skills/04-pseudocode-generator/SKILL.md) · [control-flow-tracer](../skills/03-control-flow-tracer/SKILL.md)
