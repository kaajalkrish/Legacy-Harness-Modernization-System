# Legacy-Modernization Harness

A 10-agent pipeline that turns legacy COBOL into a validated Business Requirements
Document (BRD). This file is the harness manifest: it indexes the agents and skills
under `.claude/` and maps each to the Python module that backs it.

> **The Python is the source of truth.** These `.claude/` files describe and orchestrate
> it; they do not replace or change it. Facts → Python. Meaning → LLM.

Orchestrated end-to-end by [`run_pipeline.py`](../run_pipeline.py) with interactive
`[y/n/s]` gates. Phases 1–5 are deterministic (no LLM, no API key); Phases 6, 7, 9 and 10 are hybrid
(Python does the facts, the LLM does the meaning) and run either via the AI-host path
(Claude Code, no key) or the Python builders (with a key).

---

## Directory layout

```
.claude/
├── harness.md                 ← this manifest
├── agents/                    ← one subagent per pipeline module (execution order)
│   ├── 01-discovery.md
│   ├── 02-parser.md
│   ├── 03-topology.md
│   ├── 04-context.md
│   ├── 05-data.md
│   ├── 06-logic.md
│   ├── 07-rules.md
│   ├── 08-diagram.md
│   ├── 09-brd.md
│   └── 10-judge.md
└── skills/                    ← granular capabilities (ordered by first-use phase)
    ├── 01-cobol-ast-parser/SKILL.md
    ├── 02-section-mapper/SKILL.md
    ├── 03-control-flow-tracer/SKILL.md
    ├── 04-pseudocode-generator/SKILL.md
    ├── 05-condition-classifier/SKILL.md
    ├── 06-rule-tagger/SKILL.md
    ├── 07-gap-detector/SKILL.md
    ├── 08-section-assembler/SKILL.md
    ├── 09-groundedness-gate/SKILL.md
    └── 10-brd-scorer/SKILL.md
```

> Filenames carry the ordering prefix; each file's `name:` frontmatter stays the clean
> slug (`discovery`, `pseudocode-generator`, ...), which is how agents/skills are actually
> identified and invoked.

---

## Agents (execution order)

| # | Agent | Type | Phase | Backing module | Writes |
|---|-------|------|:-----:|----------------|--------|
| 01 | [discovery](agents/01-discovery.md) | Deterministic | 1 | `phases/p01_discovery/scanner.py` | `discovery/inventory.json` |
| 02 | [parser](agents/02-parser.md) | Deterministic | 2 | `phases/p02_parser/orchestrator.py` · `phases/p02_parser/engine.py` | `analysis/raw_structure/*` · `parser_artifact.json` |
| 03 | [topology](agents/03-topology.md) | Deterministic | 3 | `phases/p03_topology/graph_builder.py` | `topology/graph.json` |
| 04 | [context](agents/04-context.md) | Deterministic | 4 | `phases/p04_context/context_builder.py` | `context/*_context.txt` · `system_index.json` |
| 05 | [data](agents/05-data.md) | Deterministic | 5 | `phases/p05_data/data_builder.py` | `data/data_artifact.json` · `data_layouts/*` |
| 06 | [logic](agents/06-logic.md) | LLM + Python | 6 | `phases/p06_logic/logic_builder.py` + `phases/p06_logic/logic_agent.md` | `logic/program_logic/*` · `logic_artifact.json` |
| 07 | [rules](agents/07-rules.md) | LLM + Python | 7 | `phases/p07_rules/rules_builder.py` + `phases/p07_rules/rules_agent.md` | `rules/rules_artifact.json` · `classified_conditions.json` |
| 08 | [diagram](agents/08-diagram.md) | Deterministic | 8 | `phases/p08_diagram/diagram_builder.py` | `diagram/*.mmd` · `diagrams_artifact.json` |
| 09 | [brd](agents/09-brd.md) | LLM + Python | 9 | `phases/p09_brd/brd_builder.py` + `phases/p09_brd/brd_agent.md` | `final_report/brd.md` · `gaps_register.*` |
| 10 | [judge](agents/10-judge.md) | LLM + Python | 10 | `phases/p10_judge/brd_judge.py` + `phases/p10_judge/brd_judge_agent.md` | `final_report/brd_judge.md` / `.json` |

*Phase number = folder number. The diagram (Phase 8) runs just before the BRD (Phase 9) so the
BRD can embed the `*.mmd` files; both sit behind one pipeline gate.*

## Skills (ordered by first-use phase)

| # | Skill | Used by | Half |
|---|-------|---------|------|
| 01 | [cobol-ast-parser](skills/01-cobol-ast-parser/SKILL.md) | parser | deterministic (Phase 2) |
| 02 | [section-mapper](skills/02-section-mapper/SKILL.md) | parser | deterministic (Phase 2) |
| 03 | [control-flow-tracer](skills/03-control-flow-tracer/SKILL.md) | parser / logic | deterministic — superseded by section-mapper |
| 04 | [pseudocode-generator](skills/04-pseudocode-generator/SKILL.md) | logic | LLM |
| 05 | [condition-classifier](skills/05-condition-classifier/SKILL.md) | rules | deterministic |
| 06 | [rule-tagger](skills/06-rule-tagger/SKILL.md) | rules | LLM |
| 07 | [gap-detector](skills/07-gap-detector/SKILL.md) | brd | deterministic |
| 08 | [section-assembler](skills/08-section-assembler/SKILL.md) | brd | deterministic + LLM prose |
| 09 | [groundedness-gate](skills/09-groundedness-gate/SKILL.md) | judge | deterministic |
| 10 | [brd-scorer](skills/10-brd-scorer/SKILL.md) | judge | LLM |

---

## Artifact flow

```
COBOL src
  → 01 inventory.json
  → 02 parser_artifact.json (+ raw_structure/*, CFG)
  → 03 graph.json
  → 04 *_context.txt
  → 05 data_artifact.json (+ data_layouts/*)
  → 06 logic_artifact.json (+ program_logic/*)              [LLM / AI host]
  → 07 rules_brief.json → rules_ai.json → rules_artifact.json          [hybrid]
  → 08 *.mmd + diagrams_artifact.json                        [deterministic]
  → 09 brd_brief.json → brd_narratives.json → brd.md + gaps_register.* [hybrid]
  → 10 brd_judge_brief.json → brd_scores.json → brd_judge.md/.json
       →  PASS | REVISE → back to 09                                   [hybrid]
```
`*_brief.json` is written by Python (the facts the AI may use); the middle file is written by
Claude Code (AI host, no key) or produced via the API; the builder validates it (fingerprint /
brd_sha, unknown ids dropped) before applying it. Without it a neutral template is used.

Each phase self-checks: if its output exists it offers skip-vs-rerun; if an upstream
artifact is missing it stops with a clear error rather than producing garbage.

---

## How to run

```bash
python run_pipeline.py --input <path-to-cobol> --output <out>
# Phases 1–5: pure Python, instant, no key.  Phases 6, 7, 9 and 10: LLM (default answer = skip).
```

## Design invariant

Facts → Python. Meaning → LLM. Every id/program a later phase cites must exist in an
earlier artifact — enforced by the
[groundedness-gate](skills/09-groundedness-gate/SKILL.md), so nothing the pipeline asserts
can be hallucinated.
