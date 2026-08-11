---
name: brd-scorer
description: >
  Score a generated BRD on five weighted dimensions (completeness, accuracy, clarity,
  consistency, actionability), each 1-5, with written feedback. This is the LLM half of
  the Judge agent (Phase 9); a deterministic gate can still override the accuracy score.
  Neutral 3s are used when no scoring is available.
---

# Skill: brd-scorer

**Used by:** [10-judge](../../agents/10-judge.md) · **Half:** LLM · **Runs with:** [groundedness-gate](../09-groundedness-gate/SKILL.md)

## Input
`final_report/brd.md` + the upstream artifacts (for cross-checking claims).

## Task
Score each dimension 1–5 and give concise, actionable feedback:
- **Completeness** — are all programs, data, rules and processes covered?
- **Accuracy** — do statements match the artifacts? (subject to the gate override)
- **Clarity** — readable by a non-COBOL analyst?
- **Consistency** — internally coherent, no contradictions?
- **Actionability** — enough for a team to rebuild without reading COBOL?

## Rules
- Score what the BRD actually says; cite specifics in feedback.
- If the groundedness gate failed, accuracy is hard-floored regardless of your score.
- AI-host mode: emit the scores/feedback JSON and pass it via `--scores-file`; if no
  scores are available, neutral 3s are used.

## Output
Per-dimension scores + feedback → weighted by `phases/p10_judge/brd_judge.py` into the final score and
the PASS / REVISE verdict (`brd_judge.md` / `.json`).
