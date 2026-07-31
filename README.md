# Legacy-Harness-Modernization-System

**A 9-agent pipeline that turns legacy COBOL into a validated Business Requirements Document (BRD)** — a plain-English explanation of what an old mainframe system does, backed by a data dictionary, a business-rules catalogue, and diagrams — so a modernization team can understand and rebuild it *without reading COBOL*.

Deterministic where possible, LLM only where needed, and it runs **with no API key**. Proven end-to-end on two different codebases (see [Proven on two codebases](#proven-on-two-codebases)).

---

## What it does

You point it at a folder of COBOL. It reads the code, understands it, and produces:

- 📇 an **inventory** of every program, copybook, and JCL job, plus a dependency graph
- 📖 a **data dictionary** (every field decoded — PIC, REDEFINES, OCCURS, 88-levels)
- 🧠 **plain-English pseudocode** for every paragraph
- 📋 a **business-rules catalogue** (validation, calculation, limit, routing rules — each traced to a real source line)
- 📊 **diagrams** (component map, ER diagram, per-program flows)
- 📄 a complete **Business Requirements Document** (`brd.md`)
- ✅ a **judge verdict** (PASS / REVISE) that validates the BRD and scores it

---

## The core idea

The harness fuses two philosophies:

| Principle | What it gives us |
|---|---|
| **Deterministic where we can** | Facts (file lists, structure, data types, rules) are extracted by plain Python — free, instant, and identical every run. No hallucinations. |
| **LLM only where we must** | Only *meaning* (turning cryptic COBOL into readable English) uses an LLM. |
| **Groundedness gate** | Every statement must trace back to real source code. Invented facts are caught mechanically, not left to the model to notice. |
| **No API key needed** | The LLM steps run through a no-key "AI-host" path, so the whole pipeline works offline. |

> **In one line:** *Facts → Python. Meaning → LLM. And the closer a step gets to a claim someone will trust, the less we let the LLM near it.*

---

## The 9-agent pipeline

Each agent is a folder + a builder, chained together (with skip/re-run gates) in `run_pipeline.py`.

| # | Agent | What it produces | Type |
|---|---|---|---|
| 1 | **Discovery** | Catalog every file + reference → `inventory.json` | Deterministic |
| 2 | **Parser** | Structural X-ray of each program (divisions, paragraphs, flow) | Deterministic |
| 3 | **Topology** | Dependency graph → `graph.json` (a lightweight, file-based Neo4j replacement) | Deterministic |
| 4 | **Context** | A readable one-page briefing per program | Deterministic |
| 5 | **Data** | Full data dictionary (COPY expansion, PIC decode, REDEFINES/OCCURS/88-levels) | Deterministic |
| 6 | **Logic** | Plain-English pseudocode per paragraph | **Hybrid (LLM)** |
| 7 | **Rules** | Mined + classified business rules, each traced to source | **Hybrid** |
| 8 | **Diagram + BRD** | Mermaid diagrams + the assembled BRD | **Hybrid** |
| 9 | **Judge** | Groundedness + consistency validation, 5-dimension score, PASS/REVISE | **Hybrid** |

Agents 1–5 and the Diagram generator are **fully deterministic**. Only **Logic, Rules, BRD narrative, and Judge** use an LLM — and even there, the risky part (existence of facts and rules) stays deterministic; the LLM only handles wording and readability.

---

## Proven on two codebases

The harness was built and validated on **two completely different COBOL applications** — this proves it generalizes rather than being tuned to one system.

### Run 1 — Portfolio Management System *(the codebase we built on)*

We started small and deliberate: a **21-program sample** (about half of the full 42-program system), so we could iterate on each agent quickly before scaling up.

### Run 2 — AWS CardDemo *(a completely different codebase)*

Then we pointed the finished harness at the **full 44-program AWS CardDemo** — a credit-card management system (accounts, cards, transactions, bill pay, authorizations) — a codebase it had never seen. It ran end to end with **zero parse errors**.

### The two runs, side by side

| Metric | Portfolio *(built on)* | **AWS CardDemo** *(generalization test)* |
|---|---|---|
| Programs | 42 (ran a 21-program sample) | **44 (full)** |
| Copybooks | 20 | **62** |
| JCL jobs | — | **55** |
| Paragraphs parsed | — | **870** (0 parse errors) |
| Data records | 146 | **596** |
| **Data fields** | 823 | **10,223** |
| 88-level conditions | 200 | **909** |
| Pseudocode paragraphs | ~180 | **514** |
| **Business rules** | 110 | **324** (94 rule sets) |
| Diagrams | 23 | **46** |
| BRD size | ~26 pages | **~61 pages** |
| Gaps flagged for review | — | **253** (0 high-severity) |
| **Judge verdict** | ✅ PASS (4.15/5) | ✅ **PASS (3.85/5), groundedness PASS, 0 consistency issues** |

**Takeaway:** the same pipeline documented a small custom system *and* a much larger, unfamiliar one — CardDemo yielded ~3× the business rules and 12× the fields — with the groundedness gate passing in both cases. The harness generalizes.

---

## How to run it

```powershell
# from the project root
python run_pipeline.py --input <path-to-cobol> --output <path-to-outputs>
```

- Phases **1–5** are pure Python (no key, instant).
- Phases **6–9** are the LLM/hybrid steps (run via the no-key AI-host path).
- The pipeline is interactive — it asks `y/n/s` at each phase so you can run, skip, or re-run.

**Example (CardDemo):**
```powershell
python run_pipeline.py --input carddemo_input --output carddemo_outputs
```

Then open the result in VS Code (with a Mermaid preview extension to see the diagrams):
```
carddemo_outputs/final_report/brd.md          # the Business Requirements Document
carddemo_outputs/final_report/brd_judge.md    # the PASS/REVISE verdict + scores
carddemo_outputs/final_report/gaps_register.md # items flagged for SME review
```

---

## Repository layout

```
run_pipeline.py         # the orchestrator (chains all 9 agents)
discovery/              # Agent 1 — inventory scanner
analysis/               # Agent 2 — parser (engine + orchestrator)
topology/               # Agent 3 — graph builder
context_builder/        # Agent 4 — context sheets
data/                   # Agent 5 — data dictionary
logic/                  # Agent 6 — pseudocode (builder + agent prompt)
rules/                  # Agent 7 — business-rules miner
brd/                    # Agents 8 & 9 — BRD builder + judge
diagram/                # Diagram generator (Mermaid)
carddemo_input/         # AWS CardDemo source (the 44-program run)
carddemo_outputs/       # Full CardDemo results (inventory → BRD → judge)
outputs/                # Portfolio system results
comparison.md           # Agent-by-agent comparison of the reference harnesses
flow.md                 # Architecture / pipeline documentation
```

---

## Notes

- **AWS CardDemo** (`carddemo_input/`) is an AWS sample codebase, Apache-2.0 licensed.
- The harness combines ideas from two reference approaches: a deterministic, code-first migrator and an LLM-agent reverse-engineering harness (`comparison.md` documents the agent-by-agent differences).
