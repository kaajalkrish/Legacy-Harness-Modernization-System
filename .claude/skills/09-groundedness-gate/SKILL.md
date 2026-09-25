---
name: groundedness-gate
description: >
  The harness's anti-hallucination check: verify every BR-/TR-/RS-/GAP- id the BRD cites
  exists in the upstream artifacts, that business terms and counts in the prose are supported
  by the analysis, plus cross-artifact consistency checks. Deterministic and authoritative —
  an invented reference or ungrounded narrative caps the accuracy score. Core of the Judge
  agent (Phase 10).
---

# Skill: groundedness-gate

**Used by:** [10-judge](../../agents/10-judge.md) · **Half:** deterministic (authoritative) · **Adapted from:** Chaminda cobol_java_migrator judge

This is code, not opinion.

## Input
`final_report/brd.md`, `gaps_register.json`, and the upstream `inventory.json`,
`data_artifact.json`, `logic_artifact.json`, `rules_artifact.json`, diagrams index.

## Checks
1. **Groundedness:** every `BR-`/`TR-`/`RS-`/`GAP-` id cited in the BRD must resolve to a
   real entry in the artifacts.
2. **Narrative terms:** business terms in the prose (executive summary, business context,
   capability intros, modernization) must appear in the evidence — program summaries,
   pseudocode, rule text, capability names, data field/record names. 3+ unsupported terms
   (e.g. "portfolio" in a card system) is high severity and caps accuracy at 2.
3. **Narrative numbers:** every "N programs / rules / gaps / capabilities …" in the prose
   must equal a count the artifacts support; otherwise accuracy is capped at 2.
4. **Consistency:** chapters present, headline counts match, every rule and gap referenced,
   diagrams embedded.

## Verdict contribution
- Any unresolved reference → **hard-floor the accuracy dimension**, regardless of the
  LLM's prose score. This is what makes the harness trustworthy.

## Output
The gate result + consistency-issue list, fed into the PASS / REVISE decision in
`phases/p10_judge/brd_judge.py`. Pairs with the [brd-scorer](../10-brd-scorer/SKILL.md).
