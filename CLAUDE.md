# CLAUDE.md

Project memory for Claude Code. See **[AGENTS.md](AGENTS.md)** for the full agent/contributor
guide and **[.claude/harness.md](.claude/harness.md)** for the pipeline manifest.

## What this is
A 10-phase pipeline that turns legacy COBOL into a validated **Business Requirements Document
(BRD)** — plus a data dictionary, business-rules catalogue, diagrams, and a PASS/REVISE judge
verdict. Deterministic where possible, LLM only for meaning, runs with **no API key**.

## Structure
- `run_pipeline.py` — orchestrator (interactive `[y/n/s]` gates).
- `phases/p01_discovery` … `p10_judge/` — the 10 agent packages (one per phase). Each holds
  its Python builder and, for LLM phases, the co-located `*_agent.md` prompt spec.
- `.claude/agents/`, `.claude/skills/`, `.claude/harness.md` — Claude Code harness definitions.
  **Keep these in `.claude/` — do not move them, or Claude Code can't discover them.**
- `inputs/{sample,carddemo,sample_mini}` · `outputs/{sample,carddemo}`.

## Run
```bash
python run_pipeline.py                                              # defaults: inputs/sample -> outputs/sample
python run_pipeline.py --input inputs/carddemo --output outputs/carddemo
```
Phases 1–5 are deterministic (no key, instant). Phases 6, 7, 9 and 10 are hybrid (LLM); the default
answer at those gates is **skip** so you never spend tokens by accident. Phase 8 (diagrams) is
deterministic. Phase number = folder number (`p08_diagram` is Phase 8, `p10_judge` Phase 10).

## AI step without an API key (Claude Code as the LLM)
Each hybrid builder writes a **brief** of the facts it may use; Claude Code writes the AI file
next to it following the phase's `*_agent.md`; re-running the builder validates and applies it.
| Phase | Brief (written by Python) | AI file (written by Claude Code) |
|---|---|---|
| 6 Logic | — (reads AST + context sheets) | `logic/program_logic/*.json` + `logic_artifact.json` |
| 7 Rules | `rules/rules_brief.json` | `rules/rules_ai.json` — capabilities, rule names, tiers |
| 9 BRD | `final_report/brd_brief.json` | `final_report/brd_narratives.json` — narrative sections |
| 10 Judge | `final_report/brd_judge_brief.json` | `final_report/brd_scores.json` — 5 dimension scores |
Validation: a stale `fingerprint` / `brd_sha` rejects the file; unknown programs or ids are dropped.
Order matters: finish Phase 7's AI file before writing the BRD narratives (rule ids must be final).
Without a key or AI file, builders fall back to neutral templates (the judge cannot PASS unscored).

## Tests
```bash
python -m unittest discover -s tests -v      # no key, no network; writes only to temp dirs
```

## Conventions / do-not-break
- **Facts → Python. Meaning → LLM.** Every `BR-`/`TR-`/`RS-`/`GAP-` id or program a later phase
  cites must exist in an earlier artifact, and BRD prose may only use terms and counts the
  analysis supports — enforced by the judge (Phase 10).
- Builders must stay codebase-neutral: no domain wording in templates, no naming-convention
  rules (e.g. program prefixes) — classify from the code itself.
- Phase folders are `pNN_name` — valid Python identifiers **on purpose** (a folder starting with
  a digit, e.g. `01_discovery`, is not importable). Imports are rooted at the repo root:
  `phases.pNN_name.module`; run modules with `python -m phases.pNN_name.module` from the root.
- Don't rename phase folders, move `run_pipeline.py`, or change the import root without also
  updating `run_pipeline.py` and the `.claude/` docs.
- The Python builders never read their `*_agent.md` prompts at runtime — those are the AI-host
  specs. Changing a prompt won't change deterministic output.
