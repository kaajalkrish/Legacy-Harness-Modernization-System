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
Phases 1–5 are deterministic (no key, instant). Phases 6–9 are hybrid (LLM); the default
answer at those gates is **skip** so you never spend tokens by accident.

## Conventions / do-not-break
- **Facts → Python. Meaning → LLM.** Every `BR-`/`GAP-`/`RS-` id or program a later phase cites
  must exist in an earlier artifact — enforced by the groundedness gate (Phase 9 / judge).
- Phase folders are `pNN_name` — valid Python identifiers **on purpose** (a folder starting with
  a digit, e.g. `01_discovery`, is not importable). Imports are rooted at the repo root:
  `phases.pNN_name.module`; run modules with `python -m phases.pNN_name.module` from the root.
- Don't rename phase folders, move `run_pipeline.py`, or change the import root without also
  updating `run_pipeline.py` and the `.claude/` docs.
- The Python builders never read their `*_agent.md` prompts at runtime — those are the AI-host
  specs. Changing a prompt won't change deterministic output.
