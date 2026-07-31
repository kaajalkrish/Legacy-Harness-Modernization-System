---
name: logic_agent
adapted_from: Udara legacy-modernization-harness — .github/skills/pseudocode-generator + control-flow-tracer
description: >
  Phase 6 of the new_legacy_harness. For each COBOL program, translate every
  paragraph into clear, standardized, plain-English pseudocode and capture the
  branches, calls, field references, complexity score and idiom annotations.
  Can be executed two ways: (A) by an AI host (Claude Code / Copilot) with NO API
  key, or (B) by the standalone Python program logic/logic_builder.py WITH an API
  key. Both use the same prompt + output schema defined below.
---

# Logic Agent

## Role
You are the fourth analysis step. Your job is to explain what each COBOL program
*does*, step by step, in plain English a business analyst can read. You do NOT
re-derive the control-flow structure — that was already computed deterministically
in Phase 2 (the AST + control_flow_graph). You focus on the interpretive part:
translating statements into pseudocode and surfacing meaning.

## Inputs (this project's paths — changed from Udara)
| Input | Where | From |
|---|---|---|
| Program structure (paragraphs + line ranges + CFG) | `outputs/analysis/raw_structure/<PROGRAM>.json` | Phase 2 |
| Context sheet (what it is + dependencies) | `outputs/context/<PROGRAM>_context.txt` | Phase 4 |
| Data dictionary (field meanings) | `outputs/data/data_artifact.json` | Phase 5 |
| Raw COBOL source | path in the AST `meta.source_file` | the repo |

## What changed vs Udara (deliberately)
1. **Control-flow tracing is NOT redone here.** Udara's `control-flow-tracer`
   re-derived execution order / loops / dead code with the LLM. Our Phase 2 already
   produces that deterministically, so we skip it — cheaper, no re-hallucination.
2. **Our folder layout** (`outputs/...`) replaces Udara's `output/...`.
3. **Line ranges come from Phase 2**, attached deterministically — never asked of the LLM.
4. **One structured JSON call per program** (the schema below), instead of two skills.

## Execution steps (per program)
1. Gather clues (deterministic): context sheet + relevant data fields + paragraphs.
2. Package clues + raw COBOL into one message (deterministic).
3. Explain (LLM / AI host): produce the JSON in the schema below.
4. Save (deterministic): `outputs/logic/program_logic/<PROGRAM>_logic.json`,
   then aggregate all into `outputs/logic/logic_artifact.json`.

## Pseudocode style + translation catalogue (from Udara, kept)
- Conditionals: `IF / ELSE IF / ELSE / END IF`
- `PERFORM UNTIL` (test before) -> `WHILE cond DO / END WHILE`; test after -> `DO / WHILE cond END DO`
- `PERFORM VARYING` -> `FOR index FROM x TO y STEP z / END FOR`
- `EVALUATE` -> `SELECT CASE / WHEN / ELSE / END SELECT`; `EVALUATE TRUE` -> `IF / ELSE IF / ELSE`
- Static `CALL` -> `CALL prog PASSING (params)`; dynamic `CALL` -> `CALL [dynamic: var] PASSING (params)  !! REVIEW`
- `MOVE` -> `SET a = b` (ZEROS/SPACES -> `CLEAR`; HIGH-VALUES -> end-of-file sentinel; CORRESPONDING -> copy matching fields)
- `COMPUTE/ADD/SUBTRACT/MULTIPLY/DIVIDE` -> `COMPUTE result = expr` (ROUNDED -> ROUND(); ON SIZE ERROR -> overflow branch)
- `READ ... AT END` -> `READ next record; IF end of file THEN ... ELSE ...`; keyed READ -> `READ WHERE key = ...`
- `WRITE/REWRITE/DELETE ... INVALID KEY` -> WRITE/UPDATE/DELETE record + key/write-error branch
- `EXEC CICS` -> `CICS <verb>` (READ/WRITE/SEND MAP/RECEIVE MAP/LINK/XCTL/RETURN/HANDLE/GETMAIN/ABEND) + response-code check
- `EXEC SQL` -> `SQL SELECT/INSERT/UPDATE/DELETE/FETCH ...`; ALWAYS add `CHECK SQLCODE` branch
- `STRING`/`UNSTRING`/`INSPECT`/`OPEN`/`CLOSE`/`STOP RUN`/`GOBACK` per Udara catalogue
- Expand `88`-level names to meaning; explain idioms with `-- annotation`; 2-space indent.

## Grounding rules
- Describe only what the code does. Never invent logic or literals; use named placeholders.
- Ambiguous or undeterminable (dynamic CALL) -> `ambiguous=true`, note it, mark the line.
- Untranslatable verb -> keep the raw line as `!! UNTRANSLATED:` and set `ambiguous=true`.

## Complexity score (1-10, from Udara)
+1 per IF, +1 per EVALUATE, +2 per nested IF, +1 per loop, +2 per GO TO, +3 per ALTER,
+1 per CALL, +1 per I/O op. (1-3 simple, 4-6 moderate, 7-9 complex, 10+ critical.)

## Output schema (per program) — matches logic/logic_builder.py OUTPUT_SCHEMA
```json
{
  "meta": { "program_id", "source_file", "model", "agent_version" },
  "summary": "3-8 sentence business narrative",
  "paragraphs": [
    {
      "name", "line_range": [start, end],
      "pseudocode": "multi-line plain-English pseudocode",
      "branches": ["each IF/EVALUATE/GO TO/PERFORM decision"],
      "calls_made": ["paragraphs/programs performed or called"],
      "field_references": ["data fields read/written"],
      "complexity_score": 0,
      "ambiguous": false,
      "annotations": [{ "line": 0, "note": "idiom / SME-review note" }],
      "notes": ""
    }
  ]
}
```

## Aggregate output — `outputs/logic/logic_artifact.json`
`meta` (programs_explained, model) + `stats` (paragraphs, ambiguous, critical) +
`programs` (per-program summary rows) + `issues`.
