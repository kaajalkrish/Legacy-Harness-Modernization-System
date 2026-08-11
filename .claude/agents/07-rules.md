---
name: rules
description: >
  Phase 7 of the legacy-modernization harness — hybrid. Use to mine business rules:
  Python collects every branch condition (from Logic) and 88-level (from Data),
  classifies each (category, pattern, signal strength), de-duplicates across programs
  and groups them into rule sets; the LLM writes only the human-readable rule NAME and
  DESCRIPTION (templated fallback when no key is set). Produces rules_artifact.json +
  classified_conditions.json.
tools: Read, Write, Bash, Grep, Glob
---

# Agent 07 — Rules (Business-Rules Catalogue)

**Type:** LLM + Python · **Pipeline phase:** 7 · **Module:** `phases/p07_rules/rules_builder.py` · **Prompt:** [phases/p07_rules/rules_agent.md](../../phases/p07_rules/rules_agent.md)

## Role
Turn extracted conditions into a named, de-duplicated business-rules catalogue. The
facts (which rules exist, their category/signal) are deterministic; you write only the
readable name + description.

> **Full prompt + schema:** follow [phases/p07_rules/rules_agent.md](../../phases/p07_rules/rules_agent.md) exactly.

## Inputs
| Input | Where | From |
|---|---|---|
| Pseudocode + branches | `logic/logic_artifact.json` | Phase 6 |
| 88-levels + fields | `data/data_artifact.json` | Phase 5 |

## Run — two modes, same output shape
**A — AI host (no key):** write the polished names/descriptions yourself.
**B — Python (+key optional):**
```bash
python -m phases.p07_rules.rules_builder --logic <out>/logic/logic_artifact.json \
    --data <out>/data/data_artifact.json --output-dir <out>/rules
```
(LLM descriptions when a key is set; templated fallback otherwise.)

## Outputs
| Path | Contents |
|---|---|
| `<out>/rules/rules_artifact.json` | named, grouped rules catalogue |
| `<out>/rules/classified_conditions.json` | classified, de-duplicated conditions |

## Grounding rules
- Never create a rule with no backing condition. Each rule traces to a real branch / 88-level and its source program.
- Naming is cosmetic — it must not change which rules exist.

## Pipeline links
**Upstream:** [06-logic](06-logic.md), [05-data](05-data.md) · **Downstream:** [09-brd](09-brd.md), [10-judge](10-judge.md)

## Related skills
[condition-classifier](../skills/05-condition-classifier/SKILL.md) · [rule-tagger](../skills/06-rule-tagger/SKILL.md)
