# COBOL Modernization Pipeline Architecture

## Overview

This document describes the end-to-end pipeline used to analyze a COBOL application, extract business knowledge, generate technical artifacts, and finally produce a Business Requirements Document (BRD).

The pipeline consists of ten sequential processing modules.

---

# 1. End-to-End Pipeline

```mermaid
flowchart LR

A[Raw COBOL Codebase]
--> B[1. Discovery]

B --> C[2. Analysis Parser]

C --> D[3. Topology Builder]

D --> E[4. Context Builder]

E --> F[5. Data Agent]

F --> G[6. Logic Agent]

G --> H[7. Rules Agent]

H --> I[8. Diagram Agent]

I --> J[9. BRD Generator]

J --> K[10. BRD Validator]
```

This diagram only illustrates the execution sequence.

---

# 2. Repository Layout

**Source code** lives under `phases/` — one Python package per phase (`p01_discovery` …
`p10_judge`), driven by `run_pipeline.py`. The Claude Code harness (agent + skill
definitions + manifest) lives under `.claude/`. Inputs and outputs are split per codebase:
`inputs/{sample,carddemo}` and `outputs/{sample,carddemo}`.

```text
phases/
├── p01_discovery/    scanner.py
├── p02_parser/       engine.py, orchestrator.py
├── p03_topology/     graph_builder.py
├── p04_context/      context_builder.py
├── p05_data/         data_builder.py
├── p06_logic/        logic_builder.py   + logic_agent.md
├── p07_rules/        rules_builder.py   + rules_agent.md
├── p08_diagram/      diagram_builder.py
├── p09_brd/          brd_builder.py     + brd_agent.md
└── p10_judge/        brd_judge.py       + brd_judge_agent.md
```

**Output artifact layout** (per output folder, e.g. `outputs/sample/`):

```text
outputs/

├── discovery/
│   └── inventory.json
│
├── analysis/
│   ├── raw_structure/
│   │   └── PROGRAM.json
│   └── parser_artifact.json
│
├── topology/
│   └── graph.json
│
├── context/
│   ├── PROGRAM_context.txt
│   └── system_index.json
│
├── data/
│   ├── data_artifact.json
│   └── data_layouts/
│
├── logic/
│   ├── logic_artifact.json
│   └── program_logic/
│
├── rules/
│   ├── classified_conditions.json
│   └── rules_artifact.json
│
├── diagram/
│   ├── component_overview.mmd
│   ├── erd.mmd
│   └── diagrams/
│       └── flow_PROGRAM.mmd
│
└── final_report/
    ├── brd.md
    ├── brd_summary.md
    ├── gaps_register.json
    ├── gaps_register.md
    ├── brd_judge.json                   # Phase 10 — BRD Judge (built)
    └── brd_judge.md
```

The pipeline is run via `run_pipeline.py`, a CLI orchestrator that executes each phase in order (with interactive prompts and skip/re-run support). Logic, Rules, BRD Generation and the BRD Judge are hybrid (deterministic + LLM) phases; Discovery, Parser, Topology, Context, Data and Diagram are fully deterministic.

---

# 3. Discovery Module

## Inputs

- Raw COBOL source

## Outputs

- inventory.json

```mermaid
flowchart LR

A[Raw COBOL]

A --> B[Discovery Scanner]

B --> C[inventory.json]
```

---

# 4. Analysis Parser

## Inputs

- Raw COBOL
- inventory.json

## Outputs

- PROGRAM.json
- parser_artifact.json

```mermaid
flowchart LR

A[Raw COBOL]
B[inventory.json]

A --> C[Analysis Parser]
B --> C

C --> D[PROGRAM.json]

C --> E[parser_artifact.json]
```

---

# 5. Topology Builder

```mermaid
flowchart LR

A[inventory.json]

B[PROGRAM.json]

A --> C[Topology Builder]

B --> C

C --> D[graph.json]
```

---

# 6. Context Builder

```mermaid
flowchart LR

A[graph.json]

B[PROGRAM.json]

A --> C[Context Builder]

B --> C

C --> D[PROGRAM_context.txt]

C --> E[system_index.json]
```

---

# 7. Data Agent

```mermaid
flowchart LR

A[Raw COBOL]

B[inventory.json]

C[PROGRAM.json]

A --> D[Data Agent]

B --> D

C --> D

D --> E[data_artifact.json]

D --> F[data_layouts/*.json]
```

---

# 8. Logic Agent

```mermaid
flowchart LR

A[Raw COBOL]

B[Context]

C[Parser Output]

D[Data Artifact]

A --> E

B --> E

C --> E

D --> E

E[Logic Agent]

E --> F[PROGRAM_logic.json]

E --> G[logic_artifact.json]
```

---

# 9. Rules Agent

```mermaid
flowchart LR

A[Logic Outputs]

B[Data Outputs]

A --> C[Rules Agent]

B --> C

C --> D[classified_conditions.json]

C --> E[rules_artifact.json]
```

---

# 10. Diagram Agent

```mermaid
flowchart LR

A[Topology]

B[Data]

C[Logic]

A --> D[Diagram Agent]

B --> D

C --> D

D --> E[Component Diagram]

D --> F[ER Diagram]

D --> G[Program Flow]

D --> H[Diagram Manifest]
```

---

# 11. BRD Generation

All previously generated knowledge artifacts are consolidated into the Business Requirements Document.

```mermaid
flowchart TB

A[Inventory]

B[Parser]

C[Data Dictionary]

D[Logic]

E[Rules]

F[Diagrams]

A --> G

B --> G

C --> G

D --> G

E --> G

F --> G

G[BRD Generator]

G --> H[BRD.md]

G --> I[BRD Summary]

G --> J[Gaps Register]
```

---

# 12. BRD Validation — the Judge

> **Status: Built.** Implemented as `phases/p10_judge/brd_judge.py` and wired into `run_pipeline.py` as Phase 10.
> **HYBRID** — two labelled parts: a deterministic **Validation** (groundedness gate + consistency checks)
> and an LLM **Judge** (5-dimension scoring + feedback).

```mermaid
flowchart TB

A[brd.md]
B[Rules]
C[Data]
D[Inventory]
E[Gaps]

A --> V
B --> V
C --> V
D --> V
E --> V

V["Validation — groundedness gate + consistency"]
V --> J["Judge — score 5 dimensions + feedback"]
J --> W["Apply Gate & Rate — PASS / REVISE"]

W --> G["brd_judge.md"]
W --> H["brd_judge.json"]
```

## Inputs

- brd.md (from BRD Generation)
- rules_artifact.json, data_artifact.json, logic_artifact.json, inventory.json
- gaps_register.json

## Outputs

- brd_judge.json — verdict, per-dimension scores, groundedness result, consistency issues, feedback
- brd_judge.md — human-readable report

## What each part does

- **Validation (deterministic Python):** builds the set of known references, then runs the *groundedness
  gate* — every `BR-`/`GAP-`/`RS-` id the BRD cites must exist in the artifacts; any invented one
  hard-floors the accuracy score to 2 — plus consistency checks (all chapters present, headline numbers
  match, every rule/gap covered, diagrams embedded).
- **Judge (LLM):** scores five dimensions 1–5 with rationale — completeness (0.25), accuracy (0.30),
  clarity (0.15), consistency (0.15), actionability (0.15) — and writes feedback items.
- The gate is then applied, the weighted score computed, and a **PASS / REVISE** verdict decided.

---

# 13. Complete Artifact Dependency

```mermaid
flowchart LR

Discovery --> Parser

Parser --> Topology

Parser --> Context

Parser --> Data

Topology --> Context

Context --> Logic

Data --> Logic

Logic --> Rules

Topology --> Diagram

Logic --> Diagram

Data --> Diagram

Discovery --> BRD

Parser --> BRD

Data --> BRD

Logic --> BRD

Rules --> BRD

Diagram --> BRD

BRD --> Validation
```

---

# 14. Processing Summary

| Module | Purpose | Primary Output |
|---------|----------|----------------|
| Discovery | Inventory COBOL assets | inventory.json |
| Parser | Parse COBOL structure | PROGRAM.json |
| Topology | Build dependency graph | graph.json |
| Context | Build semantic context | context.txt |
| Data Agent | Extract data model | data_artifact.json |
| Logic Agent | Extract business logic | logic_artifact.json |
| Rules Agent | Identify business rules | rules_artifact.json |
| Diagram Agent | Generate visual artifacts | Mermaid diagrams |
| BRD Generator | Produce BRD | brd.md |
| BRD Judge | Validate (groundedness + consistency) & score the BRD | brd_judge.md / brd_judge.json |


---

# Appendix A (Complete Architecture)

```mermaid 
graph TD
    %% Professional Color Palette Definitions
    classDef storage fill:#ffffff,stroke:#6c757d,stroke-width:2px,color:#333333;
    classDef processing fill:#f4f6f9,stroke:#5a6268,stroke-width:2px,color:#333333;
    classDef hybrid fill:#e8f4fd,stroke:#17a2b8,stroke-width:2px,color:#0b5ed7;
    classDef artifact fill:#eef9f0,stroke:#28a745,stroke-width:2px,color:#155724;

    %% 1. Ingestion Layer (Top)
    subgraph Ingestion_Layer [Legacy Input Source]
        A[Raw COBOL Codebase Folder <br> Programs, Copybooks, JCL, etc.]
    end

    %% 2. Execution Pipeline (Strict Linear Center Spine)
    subgraph Engine_Layer [Pipeline Processing Core]
        B(Module 1: Discovery & Dependency Scanner)
        B --- C(Module 2: Analysis Parser)
        C --- D(Module 3: Topology Graph Builder)
        D --- E(Module 4: Context Builder)
        E --- F(Module 5: Data Agent)
        F --- G(Module 6: Logic Agent)
        G --- H(Module 7: Rules Agent)
        H --- I(Module 8: Diagram Agent)
        I --- J(Module 9: BRD Generation)
        J --- K(Module 10: BRD Validation)
    end

    %% 3. Output Repository (Separated by Agent Container Blocks)
    subgraph Output_Layer [Target Artifact Storage]
        subgraph M1_Outputs [Module 1 Outputs]
            Out1[discovery/inventory.json]
        end

        subgraph M2_Outputs [Module 2 Outputs]
            Out2[analysis/raw_structure/PROGRAM.json]
            Out3[analysis/parser_artifact.json]
        end

        subgraph M3_Outputs [Module 3 Outputs]
            Out4[topology/graph.json]
        end

        subgraph M4_Outputs [Module 4 Outputs]
            Out5[context/PROGRAM_context.txt]
            Out6[context/system_index.json]
        end

        subgraph M5_Outputs [Module 5 Outputs]
            Out7[data/data_artifact.json]
            Out8[data/data_layouts/PROGRAM_or_COPYBOOK.json]
        end

        subgraph M6_Outputs [Module 6 Outputs]
            Out9[logic/program_logic/PROGRAM_logic.json]
            Out10[logic/logic_artifact.json]
        end

        subgraph M7_Outputs [Module 7 Outputs]
            Out11[rules/classified_conditions.json]
            Out12[rules/rules_artifact.json]
        end

        subgraph M8_Outputs [Module 8 Outputs]
            Out13[diagram/component_overview.mmd]
            Out14[diagram/erd.mmd]
            Out15[diagram/diagrams/flow_PROGRAM.mmd]
            Out16[diagrams_artifact.json]
        end

        subgraph M9_Outputs [Module 9 Outputs]
            Out17[final_report/brd.md]
            Out18[final_report/brd_summary.md]
            Out19[final_report/gaps_register.json]
        end

        subgraph M10_Outputs [Module 10 Outputs]
            Out20[final_report/brd_judge.md]
            Out21[final_report/brd_judge.json]
        end
    end

    %% Module 1 Data Paths
    A --> B
    B --> Out1
    
    %% Module 2 Data Paths
    A --> C
    Out1 -.-> C
    C --> Out2
    C --> Out3

    %% Module 3 Data Paths
    Out1 -.-> D
    Out2 -.-> D
    D --> Out4

    %% Module 4 Data Paths
    Out4 -.-> E
    Out2 -.-> E
    E --> Out5
    E --> Out6

    %% Module 5 Data Paths (Independent Ingestions)
    Out1 -.-> F
    Out2 -.-> F
    A --> F
    F --> Out7
    F --> Out8

    %% Module 6 Data Paths (Logic Agent Connections)
    Out5 -.-> G
    Out7 -.-> G
    Out2 -.-> G
    A --> G
    G --> Out9
    G --> Out10

    %% Module 7 Data Paths (Rules Agent Connections)
    Out10 -.-> H
    Out9 -.-> H
    Out7 -.-> H
    H --> Out11
    H --> Out12

    %% Module 8 Data Paths (Diagram Agent Connections)
    Out4 -.-> I
    Out7 -.-> I
    Out9 -.-> I
    I --> Out13
    I --> Out14
    I --> Out15
    I --> Out16

    %% Module 9 Data Paths (BRD Generation Accumulation)
    Out1 -.->|Inventory| J
    Out3 -.->|Parser Artifact| J
    Out7 -.->|Data Dictionary| J
    Out10 -.->|Logic Manifest| J
    Out12 -.->|Rules Catalogue| J
    Out13 -.->|Mermaid Visuals| J
    Out14 -.->|Mermaid Visuals| J
    Out15 -.->|Mermaid Visuals| J
    J --> Out17
    J --> Out18
    J --> Out19

    %% Module 10 Data Paths (Validation Cross-Check)
    Out17 -.->|Target BRD Text| K
    Out18 -.->|Target Summary Text| K
    Out12 -.->|Rule Truths| K
    Out7 -.->|Data Truths| K
    Out1 -.->|Inventory Scope| K
    K --> Out20
    K --> Out21

    %% Apply System Styling Classes
    class A storage;
    class B,C,D,E,F,I processing;
    class G,H,J,K hybrid;
    class Out1,Out2,Out3,Out4,Out5,Out6,Out7,Out8,Out9,Out10,Out11,Out12,Out13,Out14,Out15,Out16,Out17,Out18,Out19,Out20,Out21 artifact;


```

