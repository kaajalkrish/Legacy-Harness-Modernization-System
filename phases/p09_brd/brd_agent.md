---
name: brd_agent
adapted_from: Udara legacy-modernization-harness — .github/skills/gap-detector + section-assembler
description: >
  Phase 9 of the harness. Assembles every prior artifact into a Business Requirements Document
  (brd.md), a one-page summary (brd_summary.md) and the gaps register. HYBRID: every fact, table,
  count and id is assembled by Python; the AI step writes only the connecting narrative. Two ways
  to run the AI step, same contract:
    A) AI-host — Claude Code (no API key) reads brd_brief.json and writes brd_narratives.json.
    B) API — brd_builder.py calls the model itself when ANTHROPIC_API_KEY is set.
  Without either, a neutral fact-based template is used (no domain wording of its own).
---

# BRD Agent (Synthesis)

## Role
Produce a BRD that a CTO, a business owner and a modernization lead can each read: what the
system does for the business, which rules it enforces, what data it holds, what is uncertain,
and what it will take to modernize it. Never invent content — every statement traces to an
artifact; confidence and gaps are labelled.

## Inputs
`inventory.json` (P1) · `parser_artifact.json` (P2) · `data_artifact.json` (P5) ·
`logic_artifact.json` (P6) · `rules_artifact.json` (P7, incl. capabilities) · diagrams (P8).

## Document structure (brd.md)
| # | Chapter | Written by |
|---|---|---|
| — | Cover, document control, table of contents | Python |
| 1 | Executive Summary · 1.1 At a glance · 1.2 Scope of analysis | **AI** prose + Python facts |
| 2 | Business Context and Scope · 2.1 purpose · 2.2 users & actors · 2.3 scope · 2.4 system context | **AI** |
| 3 | Business Capabilities — one section per capability: narrative + program table + rule ids | **AI** narrative + Python tables |
| 4 | Business Rules · 4.1 Key business rules · 4.2 full catalogue by rule set | **AI** selects key rules; Python catalogue |
| 5 | Data Model and Definitions | Python |
| 6 | Process Descriptions (by capability, with flow diagrams) | Phase 6 summaries |
| 7 | System Architecture and Inventory · programs · copybooks · platform dependencies · hotspots | Python |
| 8 | Error Handling and Technical Conditions | Python |
| 9 | Gaps and Assumptions Register | Python |
| 10 | Modernization Considerations and Next Steps · 10.1 risk indicators · 10.2 next steps | **AI** prose + Python risk table |
| App. | A data dictionary · B pseudocode · C diagram index · D technical conditions | Python |

## AI step — the contract
The builder always writes **`<out>/final_report/brd_brief.json`**: `meta.fingerprint`, `facts`
(counts, run-mode mix, subsystems, risk indicators), `capabilities`, `programs` (run mode,
runtime, complexity, rule ids, summary), `business_rules`, `gaps`, `external_dependencies`.

### AI-host procedure (Claude Code, no key)
1. Run Phase 7 to completion first (with its own `rules_ai.json`) — rule ids must be final.
2. Run the BRD builder once (produces the brief), then read `brd_brief.json`.
3. Write **`<out>/final_report/brd_narratives.json`**:
```json
{
  "meta": {"fingerprint": "<copy from the brief>", "mode": "ai-host"},
  "executive_summary": "3-4 short paragraphs (markdown).",
  "business_purpose": "1-2 paragraphs.",
  "users_and_actors": "Short markdown list or table of who uses the system and how.",
  "scope": "What the analysed code covers and what it does not.",
  "system_context": "1-2 paragraphs on how online, batch, data stores and integrations fit together.",
  "capabilities": {"<capability name exactly as in the brief>": "1 paragraph per capability."},
  "key_rules": [{"rule_id": "BR-012", "why": "One line on the business impact."}],
  "modernization": "2-4 paragraphs: risks, dependencies and approach considerations.",
  "next_steps": ["Concrete, ordered actions."]
}
```
4. Re-run the builder — it validates and applies the file (auto-detected, or `--narratives`).

### Writing guidance
- Audience: senior business and technology leaders who know the business. Lead with business
  meaning; plain English, present tense, active voice; no COBOL jargon (say "screen", "nightly
  job", "record", not "BMS map", "JCL step", "01-level").
- **Executive summary:** what the system is for, who uses it, its main capabilities, the most
  important findings (key rules, notable risks from `facts`), the open questions, and a one-line
  recommendation. Do not restate the at-a-glance table — Python adds it right after.
- **Users and actors:** only roles evidenced by program summaries or rules (e.g. an admin menu
  proves an administrator role).
- **Capabilities:** what the capability does for the business, how online and batch parts
  interact, and which rules matter most (cite `BR-###`).
- **Key rules:** 10-15 rules a business owner would want to confirm first — decisions
  (approve/decline/reject), limits, calculations, eligibility. `why` = business impact.
- **Modernization:** ground every point in `facts` (GO TO / ALTER / high-complexity programs,
  platform dependencies, gaps). No vendor or product recommendations, no effort estimates.

### Grounding rules (enforced by the builder)
- Use only facts in the brief. Never invent numbers, programs, rule/gap ids, thresholds, users or
  business terms the summaries and rules do not support.
- A wrong `fingerprint` rejects the whole file (stale, or from another codebase).
- A section that cites a `BR-/TR-/RS-/GAP-` id that does not exist is dropped (the neutral
  template is used for it); unknown capabilities and non-business key rules are dropped.
- Counts that appear in prose must match `facts` — the judge (Phase 10) cross-checks them.

## Outputs — `<out>/final_report/`
`brd.md` · `brd_summary.md` (one page: purpose, at a glance, capabilities, key rules, high gaps,
next steps) · `gaps_register.json` / `.md` (`gaps` + `external_dependencies`) · `brd_brief.json`.
