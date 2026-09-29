# COBOL Reverse Engineering Dashboard — User Guide

## Overview

The COBOL Reverse Engineering Dashboard is a web-based analytics interface for the 10-phase COBOL → BRD (Business Requirements Document) pipeline. It presents every artifact the harness produces — programs, data structures, business rules, diagrams, and the final BRD — in a single navigable view without requiring users to open any files manually.

The dashboard runs entirely locally. No cloud services, no API keys, and no data leaves the machine.

---

## Quick Start

```bash
python dashboard/start.py --output outputs/carddemo
```

The launcher validates the output directory, builds the frontend if needed, starts the server on port 8787, and opens the browser automatically. The dashboard is ready at:

```
http://localhost:8787?outputDir=outputs/carddemo
```

To point the dashboard at a different harness run, change the `outputDir` parameter:

```
http://localhost:8787?outputDir=outputs/my_other_run
```

The dashboard is **plug-and-play**: it reads whatever output folder you specify and populates all tabs from the artifacts in that folder.

---

## Layout

```
┌─────────────────────┬────────────────────────────────────────────────────┐
│  Sidebar            │  Header: title · status · theme · export buttons   │
│                     │  Meta strip: project dir · entry point · BRD name  │
│  Phase list         │  Stats row: 6 KPI tiles                             │
│  (numbered circles) │  Tab bar: 9 tabs                                    │
│                     ├────────────────────────────────────────────────────┤
│  ‹ collapse         │  Tab content                                        │
└─────────────────────┴────────────────────────────────────────────────────┘
```

**Sidebar** — lists all 10 pipeline phases with a status indicator (green = done, grey = pending) and a per-phase progress bar. Click `‹` to collapse to icon-only view; click `›` to expand.

**Header** — shows the pipeline name, a live status badge, and the last poll timestamp. Updates every 5 seconds automatically.

**Meta strip** — project directory, harness entry point, output directory, and BRD filename for the current run.

**Stats row** — six KPI tiles summarising the run at a glance.

---

## Stats Row

| Tile | What it measures |
|---|---|
| **OVERALL** | Percentage of the 10 phases that have completed |
| **PROGRAMS** | COBOL programs found in the source repository |
| **COPYBOOKS** | Shared copybook files (expanded data definitions) |
| **RECORDS** | Data records extracted from DATA DIVISION sections |
| **RULES** | Business rules mined from branch conditions and 88-levels |
| **ARTIFACTS** | Total output files produced by the harness (.json, .md, .mmd) |

---

## Live Updates

The dashboard polls the server every **5 seconds**. If the pipeline is running in a separate terminal, the dashboard reflects each completed phase within 5 seconds of the artifact being written to disk — no manual refresh required.

As phases complete:
- Sidebar phase circles turn green
- OVERALL percentage increments
- KPI tiles update (rules, records, programs)
- The Timeline tab gains a new entry
- The "updated HH:MM:SS" timestamp in the header refreshes

**Two-terminal workflow:**
- Terminal 1: `python dashboard/start.py --output outputs/<run>` — keep open
- Terminal 2: `python run_pipeline.py` — watch the dashboard update live

---

## Tabs

### 1 · Pipeline

A full-width progress bar followed by a 5-column grid of phase cards (2 rows of 5 for the 10-phase harness). Click any card to expand its detail panel, which shows:

- Agent name and backing Python module
- Output artifact path and file size
- Phase type badge: **Deterministic** or **LLM + Python**
- Duration (time elapsed between this phase and the previous one)
- Completion timestamp

At the bottom of the tab, the **BRD Judge Verdict** card shows:
- PASS or REVISE verdict
- Weighted quality score (out of 5.0)
- Five individual dimension scores: completeness, accuracy, coverage, clarity, actionability

---

### 2 · Agents

A table of all 10 pipeline agents with one row per agent:

| Column | Content |
|---|---|
| # | Phase number |
| Agent | Name and one-line description |
| Type | Deterministic or LLM + Python |
| Backing module | Python file that implements the agent |
| Output artifact | File the agent produces |
| Status | done / pending |
| Size | Artifact file size in KB |
| Duration | Time the agent took to run |

---

### 3 · Artifacts

A searchable, filterable catalogue of every file the harness produced. Use the phase pill buttons to narrow by producing phase, or type in the search box to filter by filename.

Each row shows: filename · producing phase · file type (colour-coded) · size in KB · full path.

---

### 4 · Call Trace

A source-ordered record of every operation each COBOL program performs: internal routine calls (PERFORM), external program calls (CALL), and database queries (EXEC SQL). Data is derived from the control-flow graph written by the Parser agent (Phase 2).

**How to read it:**
- **PERFORM / CALL / SQL** — control returns to this point after the operation
- **GO TO** — control moves away permanently

**Filter pills** — narrow to All, Control flow, Program call, or Database operations.

**Columns:** STEP · PROGRAM · SOURCE LINE · IN PARAGRAPH · KIND · OPERATION · TARGET · RETURNS?

Use the program selector dropdown to view the trace for a specific program or all programs combined.

---

### 5 · Synthetic Testing

A quality gate that measures how many of the extracted business rules have sufficient evidence to be turned into automated test scenarios.

**Quality score (0–100):**

```
score = (confirmed×1.0 + high×0.9 + medium×0.5 + low×0.2) / total_rules × 100
```

The score reflects evidence strength across all rules:
- **Confirmed** — both the condition and its business effect are unambiguous in the source
- **High** — strong pattern match, business meaning likely correct
- **Medium** — condition documented, business meaning uncertain
- **Low** — weak pattern match, needs SME clarification

The tab also shows category and confidence breakdowns as horizontal bar charts, and a callout listing how many rules require subject-matter-expert review before they can be tested.

---

### 6 · Interactive Workflow

The **program call graph** rendered as a live Mermaid flowchart. Each node is a COBOL program; each arrow is a direct CALL relationship. Copybook includes and file references are excluded to keep the diagram readable.

Click any node to open a side panel showing that program's metadata (type, source path, entry points).

The diagram renders using the same theme as the current dark/light mode setting.

---

### 7 · Timeline

A vertical event timeline showing when each pipeline phase completed, derived from the `generated_at` timestamps embedded in each artifact.

Each entry shows:
- Completion timestamp
- Phase name and duration
- Artifact produced and its file size

The timeline gives a clear picture of which phases ran quickly (deterministic phases: seconds) and which took longer (LLM phases: minutes).

---

### 8 · Rules Explorer

A full browser for all business rules extracted by the harness. Filter by:
- **Category**: VALIDATION, CALCULATION, LIMIT_CHECK, ROUTING
- **Confidence**: confirmed, high, medium, low
- **Text search**: rule ID, name, or description

Click any row to expand it and see:
- The exact COBOL condition text that defines the rule
- The condition pattern type
- The source program and paragraph where it appears
- Whether the rule requires SME review
- Whether it is duplicated across multiple programs

---

### 9 · State

The raw JSON object that backs the entire dashboard — the same response returned by `GET /api/state`. Use this to inspect the full data model, verify numbers, or export structured data for downstream tools.

A **Copy JSON** button copies the full state to the clipboard.

---

## Header Buttons

| Button | Action |
|---|---|
| **View BRD** | Opens the Business Requirements Document in a full-screen modal with proper formatting, rendered Mermaid diagrams, a chapter navigation panel, and a Download .md button |
| **Export JSON** | Opens the raw state JSON in a new browser tab for saving |
| **Export PDF** | Triggers the browser print dialog with sidebar and controls hidden for a clean output |
| **Light / Dark theme** | Toggles the colour theme; preference is saved in browser storage |

---

## BRD Viewer

The BRD viewer renders the full auto-generated Business Requirements Document inside the browser:

- **Chapter navigation** — a left panel lists all headings; clicking one scrolls to that section. The active chapter highlights as you scroll.
- **Formatted content** — headings, tables, blockquotes, code blocks, and bullet lists are all styled consistently.
- **Mermaid diagrams** — all embedded diagrams (system component flowchart, ER diagram, per-program control-flow diagrams) are rendered as interactive SVGs. Rendering status is shown in the modal header.
- **Download** — the Download .md button saves the raw Markdown file to disk.

---

## Technical Reference

### Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.142 · Python · uvicorn on port 8787 |
| Frontend | React 18 · Vite 6 · TypeScript · Tailwind CSS 3 |
| Diagrams | Mermaid.js 11 (Workflow tab + BRD viewer) |
| Markdown | marked.js (BRD viewer) |
| Charts | Recharts 3 |
| Launcher | `dashboard/start.py` |

### API Endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/state?outputDir=` | Full dashboard data model (phases, stats, topology, timeline, verdict) |
| `GET /api/artifacts?outputDir=` | List of all artifact files with size and phase |
| `GET /api/call-trace?outputDir=&program=` | Control-flow trace for one or all programs |
| `GET /api/brd?outputDir=` | BRD markdown content and metadata |
| `GET /api/rules?outputDir=` | All business rules with stats |
| `GET /api/topology?outputDir=` | Raw topology graph (nodes and edges) |

### Output directory structure (required)

The dashboard expects output from the 10-phase harness. The following paths are read:

```
<outputDir>/
  discovery/inventory.json          Phase 1
  analysis/parser_artifact.json     Phase 2
  topology/graph.json               Phase 3
  context/system_index.json         Phase 4
  data/data_artifact.json           Phase 5
  logic/logic_artifact.json         Phase 6
  rules/rules_artifact.json         Phase 7
  diagram/diagrams_artifact.json    Phase 8
  final_report/brd.md               Phase 9
  final_report/brd_judge.json       Phase 10
```

If a phase has not yet run, its tab either shows a pending state or omits that section gracefully.
