---
name: brd
description: >
  Phase 9 of the legacy-modernization harness — hybrid, and the document producer. Runs
  after the deterministic diagram agent (Phase 8) has drawn the Mermaid diagrams. The
  BRD builder assembles every chapter (facts, tables, rules catalogue, gaps, appendices)
  from the artifacts with Python, and the LLM writes only the connecting narrative (exec
  summary, system-context and per-process prose). Produces brd.md, brd_summary.md and the
  gaps register.
tools: Read, Write, Bash, Grep, Glob
---

# Agent 09 — BRD (Synthesis / Document Producer)

**Type:** LLM + Python · **Pipeline phase:** 9 · **Module:** `phases/p09_brd/brd_builder.py` · **Prompt:** [phases/p09_brd/brd_agent.md](../../phases/p09_brd/brd_agent.md)

## Role
Assemble the final Business Requirements Document. Deterministic Python does the factual
assembly and gap-detection; you (the LLM) write only the connecting prose.

> **Full prompt + schema:** follow [phases/p09_brd/brd_agent.md](../../phases/p09_brd/brd_agent.md) exactly.

## Inputs
All prior artifacts: `discovery/inventory.json`, `analysis/parser_artifact.json`,
`data/data_artifact.json`, `logic/logic_artifact.json`, `rules/rules_artifact.json`,
plus the diagrams from [08-diagram](08-diagram.md).

## Run
**Step 1 — Diagrams:** run [08-diagram](08-diagram.md) (Phase 8) first, so the `*.mmd`
files exist for the BRD to embed.
**Step 2 — BRD (hybrid):**
```bash
python -m phases.p09_brd.brd_builder --inventory <out>/discovery/inventory.json \
    --parser <out>/analysis/parser_artifact.json --data <out>/data/data_artifact.json \
    --logic <out>/logic/logic_artifact.json --rules <out>/rules/rules_artifact.json \
    --diagrams <out>/diagram --output-dir <out>/final_report \
    --system-name "<System Name>"
```
**AI host (no key):** after that run, read `<out>/final_report/brd_brief.json`, write
`<out>/final_report/brd_narratives.json` exactly as specified in
[phases/p09_brd/brd_agent.md](../../phases/p09_brd/brd_agent.md), then run the same command again —
the builder validates and applies it. Finish Phase 7 (incl. its `rules_ai.json`) first so rule ids
are final. With a key, the builder calls the API itself; with neither, a neutral template is used.

## Outputs
| Path | Contents |
|---|---|
| `<out>/final_report/brd.md` | the Business Requirements Document |
| `<out>/final_report/brd_summary.md` | one-page summary |
| `<out>/final_report/gaps_register.md` + `.json` | SME-review items + external platform dependencies |
| `<out>/final_report/brd_brief.json` | facts for the AI step (with fingerprint) |
| `<out>/final_report/brd_narratives.json` | AI-host prose you write |
| (diagrams) | produced by [08-diagram](08-diagram.md) |

## Grounding rules
- Every `BR-`/`TR-`/`RS-`/`GAP-` id and program cited must exist in the artifacts; a narrative
  section citing an unknown id is dropped, and a stale fingerprint rejects the file.
- The narrative connects facts — it never introduces new ones.

## Pipeline links
**Upstream:** [08-diagram](08-diagram.md) + all artifacts · **Downstream:** [10-judge](10-judge.md)

## Related skills
[gap-detector](../skills/07-gap-detector/SKILL.md) · [section-assembler](../skills/08-section-assembler/SKILL.md)
