---
name: brd_judge_agent
adapted_from: Chaminda cobol_java_migrator — src/cobol_modernizer/agent/brd_judge.py
description: >
  Phase 10 of the harness — BRD Validation (the Judge). Validates the generated BRD for
  completeness, accuracy, clarity, consistency and actionability. HYBRID: the groundedness gate,
  consistency checks and narrative-grounding checks are deterministic Python; the five 1-5
  dimension scores + written feedback are the AI step's job. Two ways to run the AI step:
    A) AI-host — Claude Code reads brd_judge_brief.json + brd.md and writes brd_scores.json.
    B) API — brd_judge.py calls the model itself when ANTHROPIC_API_KEY is set.
  Without either, neutral 3s are used (which cannot PASS).
---

# BRD Judge (Validation)

## Role
Grade the BRD and gate it before sign-off. Never let ungrounded content pass: every reference,
business term and count in the BRD must trace to the analysis of *this* codebase.

## Inputs
brd.md (Phase 9) + inventory (P1) + data (P5) + logic (P6) + rules (P7) + gaps_register.json.

## Deterministic checks (Python — authoritative)
- **Groundedness:** every `BR-`, `TR-`, `RS-`, `GAP-` id the BRD cites must exist. Any invented
  reference hard-floors accuracy to 2.
- **Narrative grounding** (executive summary, business context, capability intros, modernization):
  - *Terms* — each business term must appear somewhere in the evidence: program summaries,
    pseudocode, rule text, capability names or data field/record names (general English and BRD
    vocabulary excepted). 3+ unsupported terms is high severity (e.g. "portfolio" in a card
    system) and caps accuracy at 2.
  - *Numbers* — every "N programs / rules / gaps / capabilities / fields …" must equal a count the
    artifacts support (totals or meaningful subsets). An unsupported count caps accuracy at 2.
- **Consistency:** chapters 1-9 present; headline numbers match; every business rule and gap is
  referenced; the generated diagrams are embedded. A high-severity issue caps consistency at 2.

## AI step — the contract
The judge always writes **`<out>/final_report/brd_judge_brief.json`**: `meta.brd_sha` (identifies
the exact brd.md), the deterministic findings, and the weights.

### AI-host procedure (Claude Code, no key)
1. Run the judge once (writes the brief), read `brd_judge_brief.json` and `brd.md`.
2. Write **`<out>/final_report/brd_scores.json`**:
```json
{
  "meta": {"brd_sha": "<copy from the brief>", "mode": "ai-host"},
  "dimensions": {
    "completeness":  {"score": 4, "rationale": "..."},
    "accuracy":      {"score": 4, "rationale": "..."},
    "clarity":       {"score": 4, "rationale": "..."},
    "consistency":   {"score": 5, "rationale": "..."},
    "actionability": {"score": 4, "rationale": "..."}
  },
  "feedback": [{"dimension": "clarity", "severity": "low",
                "suggestion": "...", "target_section": "4.2"}]
}
```
3. Re-run the judge — it applies the scores (auto-detected; or `--scores-file`). Scores written for
   a different version of brd.md (`brd_sha` mismatch) are ignored.

### Scoring rubric (be strict — the readers are senior leaders)
| Score | Meaning |
|---|---|
| 5 | Leader-ready: nothing to fix for this dimension. |
| 4 | Minor issues that do not mislead. |
| 3 | Noticeable issues; usable with care. |
| 2 | Misleading or materially incomplete. |
| 1 | Unusable. |
- **Completeness** — capabilities, key rules, data, processes, gaps and next steps all present.
- **Accuracy** — prose matches the artifacts; any deterministic finding above caps it at 2.
- **Clarity** — a business leader can read chapters 1-4 without COBOL knowledge; rule names are
  business statements, not raw conditions.
- **Consistency** — no contradictions between chapters, counts and tables.
- **Actionability** — a modernization team knows what to confirm, what to build and what is risky.
Score only what the BRD shows; cite the section in every feedback item.

## Dimensions & weights
completeness 0.25 · accuracy 0.30 · clarity 0.15 · consistency 0.15 · actionability 0.15.
Weighted score → rating: high (≥ 4.2 and every dim ≥ 3) · medium (≥ 3.0 and every dim ≥ 2) · low.

## Verdict
PASS when the rating is high/medium and there is no high-severity issue and no groundedness
failure; otherwise REVISE (hand back to Phase 9).

## Output — `<out>/final_report/`
`brd_judge.json` (verdict, rating, weighted score, scoring mode, per-dimension scores,
groundedness_failures, consistency_issues, feedback) + `brd_judge.md` (readable report) +
`brd_judge_brief.json`.
