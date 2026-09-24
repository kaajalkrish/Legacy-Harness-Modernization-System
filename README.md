# Legacy-Harness-Modernization-System

**A 9-agent AI pipeline that turns legacy COBOL into a validated Business Requirements Document (BRD).**

It produces a plain-English explanation of what a mainframe system does, backed by a data dictionary, a business-rules catalogue, and architecture diagrams, so a modernization team can rebuild the system *without reading COBOL*.

### How it works

The nine agents work across four phases:

1. **Parse:** Deterministic parsers extract program structure, data fields, and call relationships directly from the source code. Facts come from code, not from the LLM.
2. **Understand:** AI agents interpret those facts into business logic, rules, and data meaning.
3. **Document:** The pipeline assembles the BRD, data dictionary, business-rules catalogue, and Mermaid architecture diagrams.
4. **Validate:** Every output is checked against the original source, and each business rule is traced back to the code it came from.


Deterministic where possible, LLM only where needed, and it runs **with no API key**. Proven end-to-end on two different codebases: a 21-program Portfolio system and the full 44-program **AWS CardDemo**.

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. End-to-End Workflow](#2-end-to-end-workflow)
- [3. Control-Flow and Run States](#3-control-flow-and-run-states)
- [4. Artifact Dependency Graph](#4-artifact-dependency-graph)
- [5. Design Principles](#5-design-principles)
- [6. Agent Catalog (per-agent flow)](#6-agent-catalog-per-agent-flow)
  - [Agent 1 — Discovery](#agent-1--discovery)
  - [Agent 2 — Parser](#agent-2--parser)
  - [Agent 3 — Topology](#agent-3--topology)
  - [Agent 4 — Context](#agent-4--context)
  - [Agent 5 — Data](#agent-5--data)
  - [Agent 6 — Logic](#agent-6--logic)
  - [Agent 7 — Rules](#agent-7--rules)
  - [Agent 8 — Diagram + BRD](#agent-8--diagram--brd)
  - [Agent 9 — Judge](#agent-9--judge)
- [7. Responsibility Matrix](#7-responsibility-matrix)
- [8. Proven on Two Codebases](#8-proven-on-two-codebases)
- [9. How to Run](#9-how-to-run)
- [10. Repository Layout](#10-repository-layout)
- [11. Notes and Credits](#11-notes-and-credits)

---

## 1. Overview

You point the harness at a folder of COBOL. It reads the code, understands it, and produces:

- 📇 an **inventory** of every program, copybook, and JCL job + a dependency graph
- 📖 a **data dictionary** (every field decoded — PIC, REDEFINES, OCCURS, 88-levels)
- 🧠 **plain-English pseudocode** for every paragraph
- 📋 a **business-rules catalogue** (validation / calculation / limit / routing rules, each traced to a real source line)
- 📊 **diagrams** (component map, ER diagram, per-program flows)
- 📄 a complete **Business Requirements Document** (`brd.md`)
- ✅ a **judge verdict** (PASS / REVISE) that validates and scores the BRD

The whole thing runs from a single orchestrator, `run_pipeline.py`, which chains nine agents in order.

---

## 2. End-to-End Workflow

The pipeline is a linear spine: raw COBOL enters at the top, and each agent enriches the picture until a validated BRD comes out the bottom.

```mermaid
flowchart TD
    SRC["📁 Raw COBOL codebase<br/>(programs, copybooks, JCL)"]

    A1["1 · Discovery<br/><i>catalog files + references</i>"]
    A2["2 · Parser<br/><i>structural X-ray per program</i>"]
    A3["3 · Topology<br/><i>dependency graph</i>"]
    A4["4 · Context<br/><i>readable briefing per program</i>"]
    A5["5 · Data<br/><i>data dictionary</i>"]
    A6["6 · Logic<br/><i>plain-English pseudocode</i>"]
    A7["7 · Rules<br/><i>business-rules catalogue</i>"]
    A8["8 · Diagram + BRD<br/><i>diagrams + assemble document</i>"]
    A9["9 · Judge<br/><i>validate + score</i>"]

    OUT["📄 brd.md + 📊 diagrams<br/>✅ PASS / REVISE verdict"]

    SRC --> A1 --> A2 --> A3 --> A4 --> A5 --> A6 --> A7 --> A8 --> A9 --> OUT

    classDef det fill:#e8f1ff,stroke:#3b7dd8,color:#0b3d91;
    classDef llm fill:#fff3e0,stroke:#e08a17,color:#7a4a00;
    classDef io  fill:#eef7ee,stroke:#3a9d5d,color:#14532d;
    class A1,A2,A3,A4,A5 det;
    class A6,A7,A8,A9 llm;
    class SRC,OUT io;
```

> 🔵 **Blue = deterministic** (pure Python, no LLM). 🟠 **Amber = hybrid** (Python + an LLM step for the *meaning*).

---

## 3. Control-Flow and Run States

`run_pipeline.py` is **interactive and resumable**. Before each phase it asks `[y/n/s]` — run it, stop, or skip to the next phase (reusing existing output). Deterministic phases are cheap to re-run; the LLM phases default to **skip** so you never spend tokens by accident.

```mermaid
stateDiagram-v2
    [*] --> Discovery
    Discovery --> Parser: proceed (y)
    Parser --> Topology: proceed (y)
    Topology --> Context: proceed (y)
    Context --> Data: proceed (y)
    Data --> Logic: proceed (y)

    Logic --> Rules: proceed (y)
    Rules --> DiagramBRD: proceed (y)
    DiagramBRD --> Judge: proceed (y)
    Judge --> [*]: PASS

    Judge --> DiagramBRD: REVISE (regenerate)

    Discovery --> [*]: stop (n)
    Data --> [*]: stop before LLM (n, default)

    note right of Data
        Phases 1-5 are deterministic:
        free, instant, safe to re-run.
    end note
    note right of Logic
        Phases 6-9 use the LLM
        (no-key AI-host path).
        Default answer is "skip".
    end note
```

Each phase also self-checks: if its output already exists it offers **skip vs re-run**, and if an upstream artifact is missing it stops with a clear error instead of producing garbage.

---

## 4. Artifact Dependency Graph

Every agent writes a JSON/Markdown artifact that later agents read. This is *how* the groundedness discipline works — nothing is invented; each stage consumes the verified output of the last.

```mermaid
flowchart LR
    subgraph Deterministic
        INV["inventory.json"]
        AST["parser_artifact.json<br/>+ raw_structure/*"]
        GRAPH["graph.json"]
        CTX["*_context.txt"]
        DATA["data_artifact.json<br/>+ data_layouts/*"]
    end
    subgraph Hybrid
        LOGIC["logic_artifact.json<br/>+ program_logic/*"]
        RULES["rules_artifact.json"]
        DIAG["*.mmd diagrams"]
        BRD["brd.md + gaps_register"]
        JUDGE["brd_judge.md / .json"]
    end

    INV --> AST --> GRAPH --> CTX
    AST --> DATA
    INV --> DATA
    CTX --> LOGIC
    DATA --> LOGIC
    AST --> LOGIC
    LOGIC --> RULES
    DATA --> RULES
    GRAPH --> DIAG
    DATA --> DIAG
    LOGIC --> DIAG
    INV --> BRD
    DATA --> BRD
    RULES --> BRD
    LOGIC --> BRD
    DIAG --> BRD
    BRD --> JUDGE
    RULES --> JUDGE
    DATA --> JUDGE

    classDef det fill:#e8f1ff,stroke:#3b7dd8,color:#0b3d91;
    classDef llm fill:#fff3e0,stroke:#e08a17,color:#7a4a00;
    class INV,AST,GRAPH,CTX,DATA det;
    class LOGIC,RULES,DIAG,BRD,JUDGE llm;
```

---

## 5. Design Principles

| Principle | What it means |
|---|---|
| **Deterministic where we can** | Facts (file lists, structure, field types, rule *existence*) come from plain Python — free, instant, identical every run, and impossible to hallucinate. |
| **LLM only where we must** | Only *meaning* (turning cryptic COBOL into readable English) uses an LLM. |
| **Groundedness gate** | Every `BR-`/`GAP-`/`RS-` id and program the BRD cites must exist in the artifacts. An invented reference hard-floors the accuracy score — caught by code, not by the model. |
| **No API key needed** | LLM steps run through a no-key "AI-host" path, so the whole pipeline works offline. |

> **In one line:** *Facts → Python. Meaning → LLM. And the closer a step gets to a claim someone will trust, the less we let the LLM near it.*

---

## 6. Agent Catalog (per-agent flow)

Each agent below shows its **inputs → process → outputs** and a one-line "why."

### Agent 1 — Discovery
Scans the repo and catalogs every source file, then resolves `COPY`/`CALL`/`CICS`/`SQL` references into a dependency graph. *Discovery only — it does not interpret logic.*

```mermaid
flowchart LR
    S["Raw COBOL folder"] --> D["Discovery scanner<br/>(regex + fixed-column rules)"]
    D --> O["inventory.json<br/>(file registry, call graph, issues)"]
    classDef d fill:#e8f1ff,stroke:#3b7dd8;
    class D d;
```

### Agent 2 — Parser
Opens each program and extracts its structural skeleton — divisions, sections, paragraphs, WORKING-STORAGE, and the PERFORM/GO TO control flow. Flags every `GO TO` for review.

```mermaid
flowchart LR
    I["inventory.json + raw COBOL"] --> P["Parser<br/>(engine + orchestrator)"]
    P --> O["raw_structure/PROGRAM.json<br/>+ parser_artifact.json"]
    classDef d fill:#e8f1ff,stroke:#3b7dd8;
    class P d;
```

### Agent 3 — Topology
Merges the inventory edges + parsed structure into one system graph of nodes (programs, copybooks, DB2) and relationships. A **local, file-based replacement for Neo4j**.

```mermaid
flowchart LR
    I["inventory.json + parser AST"] --> T["Topology / graph builder"]
    T --> O["graph.json<br/>(nodes + edges)"]
    classDef d fill:#e8f1ff,stroke:#3b7dd8;
    class T d;
```

### Agent 4 — Context
Pre-digests each program's raw AST into a compact, **human-readable briefing sheet** — data structures, entry points, paragraph shape — so the later Logic step (and you) get the essentials, not raw JSON.

```mermaid
flowchart LR
    I["graph.json + parser AST"] --> C["Context builder"]
    C --> O["PROGRAM_context.txt<br/>+ system_index.json"]
    classDef d fill:#e8f1ff,stroke:#3b7dd8;
    class C d;
```

### Agent 5 — Data
Turns the cryptic DATA DIVISION into a clean data dictionary: expands `COPY` stubs, decodes `PIC` clauses, resolves `REDEFINES`/`OCCURS`, and surfaces `88-level` condition names (the seeds of business rules).

```mermaid
flowchart LR
    I["inventory.json + parser AST + copybooks"] --> DA["Data builder<br/>(100% rule-based)"]
    DA --> O["data_artifact.json<br/>+ data_layouts/*"]
    classDef d fill:#e8f1ff,stroke:#3b7dd8;
    class DA d;
```

### Agent 6 — Logic
**First hybrid agent.** Python gathers the clues (context + data + AST + source) into one bounded message; a single LLM step turns each paragraph into plain-English pseudocode (flagging `ambiguous` logic and branches); Python writes the files.

```mermaid
flowchart LR
    I["context + data + AST + source"] --> PREP["Python: gather + bound the prompt"]
    PREP --> LLM["LLM: paragraph → pseudocode"]
    LLM --> WRITE["Python: write files"]
    WRITE --> O["program_logic/PROGRAM_logic.json<br/>+ logic_artifact.json"]
    classDef l fill:#fff3e0,stroke:#e08a17;
    class LLM l;
```

### Agent 7 — Rules
Python collects every branch + `88-level`, classifies each (category, pattern, signal strength), de-duplicates across programs, and groups them into rule sets. The LLM only writes the human-readable **name + description** (with a templated fallback).

```mermaid
flowchart LR
    I["logic_artifact + data_artifact"] --> FIND["Python: find + classify + dedupe"]
    FIND --> NAME["LLM (optional): name + describe"]
    NAME --> O["rules_artifact.json<br/>+ classified_conditions.json"]
    classDef l fill:#fff3e0,stroke:#e08a17;
    class NAME l;
```

### Agent 8 — Diagram + BRD
The **Diagram** part is deterministic — it redraws the graph/data/logic into Mermaid (component overview, ERD, per-program flows). The **BRD** part assembles every chapter from the artifacts (facts, tables, rules catalogue, gaps) with Python; the LLM writes only the connecting narrative.

```mermaid
flowchart LR
    subgraph DiagramAgent["Diagram - deterministic"]
        G["graph + data + logic"] --> MMD["*.mmd diagrams"]
    end
    subgraph BRDAgent["BRD - hybrid"]
        ART["all artifacts + diagrams"] --> ASM["Python: assemble chapters + gaps"]
        ASM --> NAR["LLM: exec summary + narratives"]
        NAR --> DOC["brd.md + brd_summary.md<br/>+ gaps_register"]
    end
    MMD --> ART
    classDef d fill:#e8f1ff,stroke:#3b7dd8;
    classDef l fill:#fff3e0,stroke:#e08a17;
    class MMD,ASM d;
    class NAR l;
```

### Agent 9 — Judge
The quality gate. **Validation** (deterministic): the groundedness gate + consistency checks. **Judge** (LLM): scores 5 weighted dimensions. Then Python applies the gate, computes the weighted score, and rules **PASS / REVISE**.

```mermaid
flowchart LR
    I["brd.md + artifacts + gaps"] --> V["Validation (Python)<br/>groundedness gate + consistency"]
    V --> J["Judge (LLM)<br/>score 5 dimensions + feedback"]
    J --> G["Python: apply gate → weight → rate"]
    G --> O["brd_judge.md / .json<br/>PASS / REVISE"]
    classDef d fill:#e8f1ff,stroke:#3b7dd8;
    classDef l fill:#fff3e0,stroke:#e08a17;
    class V,G d;
    class J l;
```

---

## 7. Responsibility Matrix

| # | Agent | Responsibility | Reads | Writes | Type |
|---|---|---|---|---|---|
| 1 | **Discovery** | Catalog files + resolve references | Raw COBOL | `inventory.json` | Deterministic |
| 2 | **Parser** | Extract structural skeleton per program | inventory + source | `raw_structure/*`, `parser_artifact.json` | Deterministic |
| 3 | **Topology** | Build the system dependency graph | inventory + AST | `graph.json` | Deterministic |
| 4 | **Context** | Pre-digest each program into a briefing | graph + AST | `*_context.txt`, `system_index.json` | Deterministic |
| 5 | **Data** | Decode the full data dictionary | inventory + AST + copybooks | `data_artifact.json`, `data_layouts/*` | Deterministic |
| 6 | **Logic** | Translate paragraphs → pseudocode | context + data + AST + source | `program_logic/*`, `logic_artifact.json` | LLM + Python |
| 7 | **Rules** | Mine + classify business rules | logic + data | `rules_artifact.json`, `classified_conditions.json` | LLM + Python |
| 8 | **Diagram + BRD** | Draw diagrams + assemble the BRD | all artifacts | `*.mmd`, `brd.md`, `gaps_register` | LLM + Python |
| 9 | **Judge** | Validate groundedness + score the BRD | brd + artifacts | `brd_judge.md`, `brd_judge.json` | LLM + Python |

**Type:** *Deterministic* = pure Python (no LLM). *LLM + Python* = a hybrid agent — Python does the factual work (finding, classifying, assembling) and the LLM handles only the "soft" part (meaning, wording, narrative, or scoring), so the facts can never be hallucinated.

---

## 8. Proven on Two Codebases

The harness was **built on one system and validated on a completely different one** — proof it generalizes rather than being tuned to a single codebase.

- **Run 1 — Portfolio Management System** *(the codebase we built on)*: we started small on a **21-program sample** (about half of the 42-program system) so we could iterate on each agent quickly.
- **Run 2 — AWS CardDemo** *(a codebase it had never seen)*: we then ran the finished harness on the **full 44-program** credit-card system (accounts, cards, transactions, bill pay, authorizations). It ran end to end with **zero parse errors**.

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
| Gaps flagged | — | **253** (0 high-severity) |
| **Judge verdict** | ✅ PASS (4.15/5) | ✅ **PASS (3.85/5)**, groundedness PASS, 0 consistency issues |

**Takeaway:** the same pipeline documented a small custom system *and* a much larger unfamiliar one — CardDemo yielded ~3× the rules and 12× the fields — with the groundedness gate passing both times.

---

## 9. How to Run

```powershell
# from the project root
python run_pipeline.py --input <path-to-cobol> --output <path-to-outputs>
```

- Phases **1–5** are pure Python (no key, instant).
- Phases **6–9** are the LLM/hybrid steps (run via the no-key AI-host path).
- The run is interactive — answer `[y/n/s]` at each phase to run, stop, or skip.

**Example (CardDemo):**
```powershell
python run_pipeline.py --input inputs/carddemo --output outputs/carddemo
```

With no `--input` / `--output`, the pipeline defaults to `inputs/sample` → `outputs/sample`.

Then open the results (use a Mermaid preview extension in VS Code to see the diagrams):

```
outputs/carddemo/final_report/brd.md            # the Business Requirements Document
outputs/carddemo/final_report/brd_judge.md      # the PASS/REVISE verdict + scores
outputs/carddemo/final_report/gaps_register.md  # items flagged for SME review
```

---

## 10. Repository Layout

```
run_pipeline.py           # orchestrator — chains all agents with y/n/s gates
CLAUDE.md                 # project memory for Claude Code
AGENTS.md                 # agent/contributor guide (open AGENTS.md standard)
phases/                   # all pipeline agents, one folder per phase
  p01_discovery/          #   Agent 1 — inventory scanner
  p02_parser/             #   Agent 2 — parser (engine + orchestrator)
  p03_topology/           #   Agent 3 — graph builder
  p04_context/            #   Agent 4 — context sheets
  p05_data/               #   Agent 5 — data dictionary
  p06_logic/              #   Agent 6 — pseudocode (builder + agent prompt)
  p07_rules/              #   Agent 7 — business-rules miner
  p08_diagram/            #   Agent 8a — Mermaid diagram generator
  p09_brd/                #   Agent 8 — BRD builder (+ agent prompt)
  p10_judge/              #   Agent 9 — BRD validation / judge (+ agent prompt)
.claude/                  # Claude Code harness
  agents/                 #   10 subagent definitions (01-discovery … 10-judge)
  skills/                 #   10 granular skill definitions
  harness.md              #   pipeline manifest
inputs/
  carddemo/               # AWS CardDemo source (the 44-program run)
  sample/                 # Portfolio system source (default run)
  sample_mini/            # smaller Portfolio sample
outputs/
  carddemo/               # full CardDemo results (inventory → BRD → judge)
  sample/                 # Portfolio system results
comparison.md             # agent-by-agent comparison of the reference harnesses
flow.md                   # architecture / pipeline documentation
```

---

## 11. Notes and Credits

- **AWS CardDemo** (`inputs/carddemo/`) is an AWS sample codebase, Apache-2.0 licensed.
- The harness combines ideas from two reference approaches — a deterministic, code-first migrator and an LLM-agent reverse-engineering harness. `comparison.md` documents the agent-by-agent differences.
- Diagrams in this README and in the BRD are **Mermaid**, which renders natively on GitHub and in VS Code's Markdown preview.
