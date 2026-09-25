---
name: rules_agent
adapted_from: Udara legacy-modernization-harness — .github/skills/condition-classifier + rule-tagger
description: >
  Phase 7 of the harness. Turns the branching conditions extracted by the Logic agent
  (Phase 6) and the 88-level conditions from the Data agent (Phase 5) into a deduplicated
  business-rules catalogue grouped by business capability. HYBRID: extraction,
  classification, business/technical tiering, deduplication and ids are deterministic Python;
  the AI step groups programs into capabilities and writes business-readable rule names and
  descriptions. Two ways to run the AI step, same contract:
    A) AI-host — Claude Code (no API key) reads rules_brief.json and writes rules_ai.json.
    B) API — rules_builder.py calls the model itself when ANTHROPIC_API_KEY is set.
  Without either, an honest templated fallback is used.
---

# Rules Agent

## Role
Turn raw branching logic into a catalogue a business owner can validate without knowing
COBOL: **business rules** (decisions and domain constraints) grouped by **business
capability**, with programming mechanics set aside as **technical conditions**. Never invent a
rule — every rule traces to a real branch or 88-level in a real program.

## Inputs
| Input | Where | From |
|---|---|---|
| Branches per paragraph | `<out>/logic/program_logic/<PROGRAM>_logic.json` (`branches`) | Phase 6 |
| 88-level conditions + VALUE literals | `<out>/data/data_artifact.json` | Phase 5 |
| Run modes, copybook users | `<out>/discovery/inventory.json` (optional) | Phase 1 |

## Deterministic (Python — decides which rules exist)
1. Collect every branch and 88-level; classify category (VALIDATION / CALCULATION / ROUTING /
   LIMIT_CHECK / ERROR_HANDLING / COMPLIANCE), structural pattern and signal 1-5.
   Signal 1 (file status, SQLCODE, RESP, AT END …) → error-handling catalogue (`EH-`).
2. **Tier** each signal ≥ 2 condition, using COBOL/CICS idioms that hold for any codebase:
   - technical — loop/EOF control (`PERFORM UNTIL`, `READNEXT`, EOF/BOF), screen & session
     handling (`EIBCALEN`, `EIBAID`, PF keys, `SEND MAP`), file/DB/MQ status, record
     persistence (`REWRITE`, insert), program state & run parameters (checkpoint, debug,
     function dispatch), and 88-level flags (`…-ISVALID/NOT-OK/BLANK`, `…-EOF`, message
     tables, `…-FUNCTION`);
   - business — everything else, plus any `IF` carrying a decision word (approve, decline,
     fraud, expired, admin …) and any 88-level with real domain values (value lists, ranges).
3. Deduplicate across programs (same condition text; same 88 field + values).
4. Number: business rules `BR-###`, technical conditions `TR-###`, rule sets `RS-###`.
   Rule sets = capabilities (AI step) or, as the fallback, one set per program.

## AI step — the contract (AI-host or API)
The builder always writes **`<out>/rules/rules_brief.json`**:
- `meta.fingerprint` — identifies this exact codebase + candidate set.
- `programs[]` — `program_id`, `run_mode`, `runtime`, `summary` (from Phase 6).
- `candidates[]` — `condition_id`, `programs`, `paragraph`, `category`, `first_pass_tier`,
  `text`, and for 88-levels `field` + `values` (the actual VALUE literals).

### AI-host procedure (Claude Code, no key)
1. Run the builder once (produces the brief), then read `rules_brief.json`.
2. Write **`<out>/rules/rules_ai.json`**:
```json
{
  "meta": {"fingerprint": "<copy from the brief>", "mode": "ai-host"},
  "capabilities": [
    {"name": "Card Authorization",
     "description": "Real-time approve/decline of card purchases and review of pending authorizations.",
     "programs": ["COPAUA0C", "COPAUS0C", "COPAUS1C", "COPAUS2C", "CBPAUP0C"]}
  ],
  "rules": {
    "COND-COPAUA0C-MAKE-AUTH-DECISION-1": {
      "tier": "business",
      "name": "Decline authorization when the card is inactive",
      "description": "An authorization request is declined if the card is not active."},
    "COND-COACTUPC-0000-MAIN-1": {"tier": "technical"}
  }
}
```
3. Re-run the builder — it validates and applies the file (auto-detected in the rules folder,
   or pass `--ai-input`).

### What to write
- **capabilities** — group *every* program into a named business capability (3-10 for a
  typical system). Names are business functions ("Transaction Posting", "User Administration"),
  not technologies. A program belongs to one capability. Descriptions: 1-2 sentences.
- **rules** — for each candidate:
  - `tier`: `business` if a business owner would recognise it as a decision or constraint;
    `technical` if it is program mechanics. Correct the first-pass tier where it is wrong.
  - for business rules: `name` — imperative, business language ("Reject a transaction that
    exceeds the account credit limit"); `description` — 1-3 sentences stating the condition
    and outcome as shown. For 88-levels, state the allowed values/range in plain words
    ("FICO score must be between 300 and 850").
  - Technical candidates need only `tier`.
  - Optional `capability` (a name from your capabilities list) places a business rule
    explicitly — use it for rules on shared fields used across capabilities. Otherwise the rule
    goes to the capability holding most of its programs.

### Grounding rules (enforced by the builder)
- Use only facts in the brief: condition text, VALUE literals, program summaries. Never invent
  thresholds, outcomes, reason codes, programs or condition ids.
- Unknown programs or condition ids are dropped with a warning; a program listed in two
  capabilities keeps the first. A wrong `fingerprint` rejects the whole file (stale or from
  another codebase) — regenerate it from the current brief.
- The AI step never creates or deletes rules; it only names, groups and tiers existing ones.

## Output — `<out>/rules/`
- `classified_conditions.json` — every condition with category / pattern / signal.
- `rules_brief.json` — the AI-step input (above).
- `rules_artifact.json` — `meta` (totals, `description_mode`, `capability_source`,
  `ai_worded_rules`, `ai_warnings`) · `stats` (by_category, by_confidence, technical_by_reason) ·
  `capabilities` · `rule_sets` · `business_rules` (rule_id, rule_set, name, description,
  wording ai|templated, category, confidence, requires_sme_review, condition{text, pattern,
  field, values}, implemented_in_programs, primary_source, sources) · `technical_rules`
  (rule_id TR-###, reason, name, condition, sources) · `error_handling_catalogue` ·
  `rules_by_program`.

## Constraints
- Every rule traces to ≥ 1 source. Low-signal rules carry `requires_sme_review`.
- Templated fallback names come from the condition itself — plain, but never attached to an
  unrelated field.
