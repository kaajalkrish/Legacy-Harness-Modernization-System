# AGENTS.md

Guidance for AI coding agents (and humans) working in this repo. Companion to
**[README.md](README.md)** (the project story) and **[.claude/harness.md](.claude/harness.md)**
(the agent + skill manifest). Follows the [AGENTS.md](https://agents.md) convention.

## Project
**Legacy-Harness Modernization System** — a 10-phase pipeline that reads legacy COBOL and
produces a validated Business Requirements Document (BRD), a data dictionary, a business-rules
catalogue, Mermaid diagrams, and a PASS/REVISE judge verdict. Facts come from deterministic
Python; only *meaning* (pseudocode, rule wording, narrative prose, scoring) uses an LLM. It runs
with no API key via an AI-host path, or with a key via the Python builders.

## Layout
| Path | What |
|---|---|
| `run_pipeline.py` | Orchestrator — chains all phases with `[y/n/s]` gates |
| `phases/pNN_*/` | The 10 agent packages, one per phase (`p01_discovery` … `p10_judge`) |
| `.claude/agents/`, `.claude/skills/`, `.claude/harness.md` | Claude Code harness definitions |
| `inputs/{sample,carddemo,sample_mini}/` | COBOL source inputs |
| `outputs/{sample,carddemo}/` | Generated artifacts per codebase |

## The 10 phases
| # | Phase | Package | Type |
|---|-------|---------|------|
| 1 | Discovery | `phases/p01_discovery` | Deterministic |
| 2 | Parser | `phases/p02_parser` | Deterministic |
| 3 | Topology | `phases/p03_topology` | Deterministic |
| 4 | Context | `phases/p04_context` | Deterministic |
| 5 | Data | `phases/p05_data` | Deterministic |
| 6 | Logic | `phases/p06_logic` | LLM + Python |
| 7 | Rules | `phases/p07_rules` | LLM + Python |
| 8 | Diagram | `phases/p08_diagram` | Deterministic |
| 9 | BRD | `phases/p09_brd` | LLM + Python |
| 10 | Judge | `phases/p10_judge` | LLM + Python |

*Folder order (p01…p10) is execution order, and the phase number equals the folder number.*

## Build / run
No third-party dependencies for phases 1–5 (pure stdlib).
```bash
python run_pipeline.py                                              # inputs/sample -> outputs/sample
python run_pipeline.py --input inputs/carddemo --output outputs/carddemo
```
Run a single phase from the repo root, e.g.:
```bash
python -m phases.p02_parser.orchestrator \
    --inventory outputs/sample/discovery/inventory.json \
    --output-dir outputs/sample/analysis
```

## Conventions
- **Deterministic first.** File lists, structure, field types, and rule *existence* come from
  Python — never the LLM. The LLM only supplies wording, narrative, and scores.
- **Groundedness gate.** Every `BR-`/`GAP-`/`RS-` id and every program the BRD cites must exist
  in the artifacts; an invented reference hard-floors the judge's accuracy score.
- **Phase folders are `pNN_name`** — valid, sortable Python identifiers (a digit-first name is
  not importable). Imports are rooted at the repo root: `phases.pNN_name.module`.
- Each LLM phase keeps its prompt spec (`*_agent.md`) beside its builder; the `.claude/agents/*.md`
  files are the Claude Code subagent definitions (thin pointers to those specs).

## Verifying a change
```bash
python -m py_compile run_pipeline.py                 # syntax
python -c "import phases.p02_parser.orchestrator, phases.p05_data.data_builder"  # imports resolve
python run_pipeline.py                               # run phases 1–5 (deterministic, no key)
python -m unittest discover -s tests -v              # smoke + regression tests (no key)
```
Phases 1–5 are free and instant to re-run. Phases 6, 7, 9 and 10 use the LLM (default answer at those gates
is skip).

## Don't
- Don't rename phase folders or move `run_pipeline.py` without updating imports **and** the docs.
- Don't move `.claude/agents` or `.claude/skills` out of `.claude/` (breaks Claude Code discovery).
- Don't write invented facts into artifacts — the judge (Phase 10) will catch them.
