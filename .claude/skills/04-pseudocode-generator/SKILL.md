---
name: pseudocode-generator
description: >
  Translate a single COBOL paragraph into clear, standardized, plain-English pseudocode
  using a fixed translation catalogue (IF/ELSE, WHILE/FOR, SELECT CASE, CALL, SET,
  COMPUTE, READ/WRITE, CICS, SQL). Used by the Logic agent (Phase 6). Invoke when
  converting COBOL statements into analyst-readable steps.
---

# Skill: pseudocode-generator

**Used by:** [06-logic](../../agents/06-logic.md) · **Half:** LLM · **Adapted from:** Udara legacy-modernization-harness

## Input
One paragraph's statements (with line ranges from the Phase 2 AST), the program's
context sheet, and the relevant data-dictionary fields.

## Translation catalogue (apply verbatim)
- Conditionals → `IF / ELSE IF / ELSE / END IF`.
- `PERFORM UNTIL` test-before → `WHILE cond DO / END WHILE`; test-after → `DO / WHILE cond END DO`.
- `PERFORM VARYING` → `FOR index FROM x TO y STEP z / END FOR`.
- `EVALUATE` → `SELECT CASE / WHEN / ELSE / END SELECT`; `EVALUATE TRUE` → `IF / ELSE IF / ELSE`.
- Static `CALL` → `CALL prog PASSING (params)`; dynamic `CALL` → `CALL [dynamic: var] PASSING (...) !! REVIEW`.
- `MOVE` → `SET a = b` (ZEROS/SPACES → `CLEAR`; HIGH-VALUES → end-of-file sentinel; CORRESPONDING → copy matching fields).
- `COMPUTE/ADD/SUBTRACT/MULTIPLY/DIVIDE` → `COMPUTE result = expr` (ROUNDED → ROUND(); ON SIZE ERROR → overflow branch).
- `READ ... AT END` → read + end-of-file branch; keyed READ → `READ WHERE key = ...`.
- `WRITE/REWRITE/DELETE ... INVALID KEY` → op + error branch.
- `EXEC CICS ...` → `CICS <verb>` + response-code check.
- `EXEC SQL ...` → `SQL <verb>`; ALWAYS add `CHECK SQLCODE`.
- Expand 88-level names to their meaning; annotate idioms with `-- note`; 2-space indent.

## Rules
- Describe only what the code does. Never invent logic or literals — use named placeholders.
- Untranslatable verb → keep the raw line as `!! UNTRANSLATED:` and set `ambiguous=true`.

## Output
The `pseudocode` string (+ `branches`, `calls_made`, `field_references`, `annotations`)
for the paragraph, per the schema in `phases/p06_logic/logic_agent.md`.
