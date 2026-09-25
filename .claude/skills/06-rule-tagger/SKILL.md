---
name: rule-tagger
description: >
  The AI half of the Rules agent (Phase 7): group programs into business capabilities,
  confirm or correct each candidate's business/technical tier, and give each business rule a
  concise NAME and DESCRIPTION. Runs as Claude Code writing rules_ai.json (no key) or via the
  API; a templated fallback is used otherwise. It must not change which rules exist.
---

# Skill: rule-tagger

**Used by:** [07-rules](../../agents/07-rules.md) · **Half:** AI · **Adapted from:** Udara legacy-modernization-harness

Runs after the [condition-classifier](../05-condition-classifier/SKILL.md).

## Input
`<out>/rules/rules_brief.json` — programs (id, run mode, summary) and de-duplicated
candidates (condition text or 88-level values, first-pass tier), plus a `fingerprint`.

## Task
Write `<out>/rules/rules_ai.json` (full schema in
[rules_agent.md](../../../phases/p07_rules/rules_agent.md)):
- **capabilities** — every program in exactly one named business capability.
- **rules** — per `condition_id`: `tier` (business | technical); for business rules a short
  imperative **name** ("Reject a transaction that exceeds the credit limit") and a 1-3
  sentence **description** in business language, stating 88-level values/ranges in words.

## Rules
- Use only the brief's facts — never invent thresholds, outcomes, programs or ids.
- Copy `meta.fingerprint`; a mismatch makes the builder reject the file.
- Do not add, merge, split or drop rules — only name, group and tier them.

## Output
Re-run the builder: it validates `rules_ai.json` and merges it into `rules_artifact.json`
(`wording: ai`, capability rule sets `RS-###`).
