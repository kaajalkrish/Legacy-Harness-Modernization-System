---
name: judge
description: >
  Phase 10 of the legacy-modernization harness — the quality gate. Use to validate and
  score the BRD. Deterministic Python runs the groundedness gate (every cited
  BR-/GAP-/RS- id and program must exist in the artifacts) plus consistency checks; the
  LLM scores 5 weighted dimensions and writes feedback; Python then applies the gate,
  computes the weighted score and rules PASS / REVISE. On REVISE, hand back to Phase 9 to
  regenerate. Produces brd_judge.md and brd_judge.json.
tools: Read, Write, Bash, Grep, Glob
---

# Agent 10 — Judge (BRD Validation)

**Type:** LLM + Python · **Pipeline phase:** 10 · **Module:** `phases/p10_judge/brd_judge.py` · **Prompt:** [phases/p10_judge/brd_judge_agent.md](../../phases/p10_judge/brd_judge_agent.md)

## Role
Decide whether the BRD is trustworthy. The gate and consistency checks are
deterministic and authoritative; your job (LLM) is only the five 1–5 dimension scores +
written feedback. A failed groundedness gate hard-floors accuracy no matter what you score.

> **Full prompt + schema:** follow [phases/p10_judge/brd_judge_agent.md](../../phases/p10_judge/brd_judge_agent.md) exactly.

## Inputs
`final_report/brd.md`, `discovery/inventory.json`, `data/data_artifact.json`,
`logic/logic_artifact.json`, `rules/rules_artifact.json`,
`final_report/gaps_register.json`, `diagram/diagrams_artifact.json`.

## Run
```bash
python -m phases.p10_judge.brd_judge --brd <out>/final_report/brd.md \
    --inventory <out>/discovery/inventory.json --data <out>/data/data_artifact.json \
    --logic <out>/logic/logic_artifact.json --rules <out>/rules/rules_artifact.json \
    --gaps <out>/final_report/gaps_register.json \
    --diagrams-index <out>/diagram/diagrams_artifact.json \
    --output-dir <out>/final_report
```
**AI host (no key):** after that run, read `<out>/final_report/brd_judge_brief.json` and `brd.md`,
write `<out>/final_report/brd_scores.json` (copy `meta.brd_sha`) per the rubric in the prompt file,
then run the same command again. Scores for a different version of brd.md are ignored; with no
scores, neutral 3s are used and the BRD cannot PASS.

## Outputs
| Path | Contents |
|---|---|
| `<out>/final_report/brd_judge.md` + `.json` | PASS / REVISE + 5-dimension scores |

## Grounding rules
- The groundedness gate is code, not opinion: any invented reference fails it.
- Do not let generous prose scoring override a failed gate.

## Pipeline links
**Upstream:** [09-brd](09-brd.md) + all artifacts · **Feedback loop:** `REVISE` → back to [09-brd](09-brd.md), then re-judge.

## Related skills
[groundedness-gate](../skills/09-groundedness-gate/SKILL.md) · [brd-scorer](../skills/10-brd-scorer/SKILL.md)
