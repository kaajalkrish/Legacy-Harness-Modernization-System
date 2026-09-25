---
name: rules
description: >
  Phase 7 of the legacy-modernization harness — hybrid. Use to mine business rules:
  Python collects every branch condition (from Logic) and 88-level (from Data),
  classifies and tiers each (business rule vs technical condition), de-duplicates across
  programs and assigns ids; the AI step (Claude Code with no key, or the API) groups programs
  into business capabilities and writes rule names/descriptions via rules_ai.json
  (templated fallback otherwise). Produces rules_artifact.json + rules_brief.json.
tools: Read, Write, Bash, Grep, Glob
---

# Agent 07 — Rules (Business-Rules Catalogue)

**Type:** LLM + Python · **Pipeline phase:** 7 · **Module:** `phases/p07_rules/rules_builder.py` · **Prompt:** [phases/p07_rules/rules_agent.md](../../phases/p07_rules/rules_agent.md)

## Role
Turn extracted conditions into a business-rules catalogue grouped by capability. The
facts (which rules exist, category, signal, first-pass tier) are deterministic; you write
the capability grouping, the business/technical tier correction and the readable
name + description.

> **Full prompt + schema:** follow [phases/p07_rules/rules_agent.md](../../phases/p07_rules/rules_agent.md) exactly.

## Inputs
| Input | Where | From |
|---|---|---|
| Pseudocode + branches | `logic/logic_artifact.json` | Phase 6 |
| 88-levels + VALUE literals | `data/data_artifact.json` | Phase 5 |
| Run modes, copybook users | `discovery/inventory.json` | Phase 1 |

## Run
```bash
python -m phases.p07_rules.rules_builder --logic <out>/logic/logic_artifact.json \
    --data <out>/data/data_artifact.json --inventory <out>/discovery/inventory.json \
    --output-dir <out>/rules
```
**AI host (no key):** after that run, read `<out>/rules/rules_brief.json`, write
`<out>/rules/rules_ai.json` exactly as specified in the prompt file, then run the same command
again — the builder validates and applies it. With a key, the builder calls the API itself.

## Outputs
| Path | Contents |
|---|---|
| `<out>/rules/rules_artifact.json` | capabilities, rule sets (`RS-`), business rules (`BR-`), technical conditions (`TR-`) |
| `<out>/rules/rules_brief.json` | facts for the AI step (programs, candidates, fingerprint) |
| `<out>/rules/rules_ai.json` | AI-host output you write (capabilities, names, tiers) |
| `<out>/rules/classified_conditions.json` | every classified condition |

## Grounding rules
- Never create a rule with no backing condition. Each rule traces to a real branch / 88-level and its source program.
- The AI step names, groups and tiers existing candidates — it never adds or removes one.
  Unknown programs/condition ids are dropped; a stale fingerprint rejects the file.

## Pipeline links
**Upstream:** [06-logic](06-logic.md), [05-data](05-data.md) · **Downstream:** [09-brd](09-brd.md), [10-judge](10-judge.md)

## Related skills
[condition-classifier](../skills/05-condition-classifier/SKILL.md) · [rule-tagger](../skills/06-rule-tagger/SKILL.md)
