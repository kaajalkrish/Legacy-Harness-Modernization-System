# Dashboard Plan: Mainframe-Source COBOL Reverse Engineering

> Source: 10 reference photos in `ref_pics/` captured from a running dashboard at `127.0.0.1:8787`.
> Goal: Mimic this dashboard exactly and wire it to the artifacts our 10-phase harness produces.

---

## 1. What the reference dashboard is

A local web app (Python HTTP server on port 8787) that reads the harness output artifacts and renders them as a live, interactive dashboard. The URL carries query params: `?outputDir=<path>&brdName=<file.md>`. Dark theme by default with a "Light theme" toggle.

---

## 2. Overall layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  LEFT SIDEBAR (collapsible, ~280px)      │  MAIN CONTENT AREA (flex-grow)    │
│  ┌─────────────────────────────────────┐ │  ┌──────────────────────────────┐ │
│  │ [RE] Harness Pipeline               │ │  │  HEADER (title + meta strip) │ │
│  │       Reverse Engineering           │ │  │  STATS ROW (6 KPI tiles)     │ │
│  ├─────────────────────────────────────┤ │  │  TAB BAR (9 tabs)            │ │
│  │ PIPELINE · N PHASES                 │ │  │  TAB CONTENT PANEL           │ │
│  │ ① Inventory      ● done            │ │  └──────────────────────────────┘ │
│  │ ② Parser         ● done            │ │                                    │
│  │ ③ Data           ● done            │ │                                    │
│  │ ④ Logic          ● done            │ │                                    │
│  │ ⑤ Rules          ● done            │ │                                    │
│  │ ⑥ Diagram        ● done            │ │                                    │
│  │ ⑦ Synthesis(BRD) ● done            │ │                                    │
│  └─────────────────────────────────────┘ │                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Header strip (always visible above tabs)

| Section | Content |
|---|---|
| Title | "Mainframe-Source COBOL Reverse Engineering" (large, bold) |
| Status badge | `● live · complete` (green pill) |
| Buttons top-right | "Light theme" toggle · "Export JSON" · "Export PDF" (yellow) |
| Meta row | PROJECT DIRECTORY · ENTRY POINT · OUTPUT DIRECTORY · BRD NAME (truncated paths) |

---

## 4. Stats row (6 KPI tiles, always visible below header)

| Tile | Label | Sub-label | Source artifact |
|---|---|---|---|
| OVERALL | `100%` | `N/N phases done` | count done phases |
| PROGRAMS | `1` | `reachable` | `inventory.json` → programs |
| COPYBOOKS | `195` | `expanded` | `inventory.json` → copybooks |
| RECORDS | `1337` | `in dictionary` | `data_artifact.json` → records count |
| RULES | `2334` | `catalogued` | `rules_artifact.json` → rules count |
| ARTIFACTS | `469` | `produced` | count of all output files |

---

## 5. Tab bar — 9 tabs (active tab has yellow underline)

```
Pipeline | Agents | Artifacts | Call Trace | Synthetic Testing | Interactive Workflow | Timeline | Conversation | State
```

---

## 6. Tab contents (one section per tab)

### Tab 1 — Pipeline

- **"Pipeline overview"** heading with sub-label "Overall progress"
- Full-width horizontal progress bar (blue fill = % phases complete)
- Row of phase cards below: PHASE 1 Inventory ● done, PHASE 2 Parser ● done, … through PHASE 7 (or 10 for our harness)
- Expandable phase detail sections further down (one accordion card per phase showing what it ran, what it produced, any errors)

### Tab 2 — Agents

- List of agents with name, type (Deterministic / LLM + Python), status, timing
- Each row expandable to show backing module path and what it writes

### Tab 3 — Artifacts

- File browser of everything under `outputs/<run>/`
- Shows artifact name, size, phase that produced it, timestamp

### Tab 4 — Call Trace

- **Title**: "Call trace"
- **Subtitle**: "A source-ordered record of every operation `<PROGRAM>` performs: internal routines it runs, programs and CICS transactions it calls, and database requests it issues."
- **How to read it** info box:
  - PERFORM, CALL, CICS LINK, and SQL return here after the step finishes.
  - GO TO and CICS XCTL move control away and do not come back to this point.
- **Stats line**: `341 operations · 274 return here · 67 do not return`
- **Filter pills**: `All 341` (yellow/active) · `Control flow 282` (blue dot) · `Program call 13` (blue dot) · `Database 46` (green dot)
- **Table columns**: STEP · SOURCE LINE ⓘ · IN PARAGRAPH ⓘ · KIND (badge: "Program call" / "Control flow") · OPERATION · TARGET · WHAT HAPPENS NEXT ⓘ
- Source: `logic_artifact.json` → call sequence per program

### Tab 5 — Synthetic Testing

- **Testing cycles collapsible list**: Cycle 1 (failed · score 29/100 · 7 blocking), Cycle 2 (same)
- **"Synthetic testing" section** ("Quality gate" sub-label):
  - Stats: QUALITY SCORE · BLOCKING FINDINGS · REQUIREMENTS · SCENARIOS · PASSED · WITH GAPS
  - **Coverage** table (horizontal bars):
    - Each row: category name · blue bar (achieved %) · green bar (minimum %) · "X% achieved · min Y% · ✓ meets target / ✗ below target"
    - Categories: happy path · negative path · boundary · exception · state transition · integration
  - **Score calculation** panel:
    - STARTING SCORE 100 → FINAL SCORE 29 → BLOCKING 7
    - DEDUCTIONS chips (FIND-ST-001 severity CRITICAL N=8: -11, FIND-ST-002 …, etc.)
    - Blocking penalty: -52 · Coverage penalty: -19
- **Scenarios (N) section**:
  - Filter pills: `All N` · `Gaps N` (amber triangle) · `Passed N` (green checkmark)
  - Card grid (3 columns): each card has [GAP/PASS badge] [SCN-XXX-NNN] · category tag · description paragraph · rule references (BR-xxx) · gap count badge
  - Clicking a card opens full Given/When/Then + expected result + determinism checks

> **Note**: This tab requires a Synthetic Testing phase that does NOT exist in our harness yet. This is the only tab that needs a new phase built (see Section 8).

### Tab 6 — Interactive Workflow

- Visual flow diagram of the pipeline with click-through navigation
- Not fully visible in ref pics — assume a canvas with nodes for each phase connected by arrows, clickable to drill into that phase's detail

### Tab 7 — Timeline

- **Title**: "Timeline"
- **Subtitle**: "Pipeline events as agents progress through the N phases."
- Vertical list, each entry:
  - Green dot · ISO timestamp
  - Bold: `<Phase name> completed successfully in N min N sec. Started <ts>; completed <ts>. Produced <artifact> (N KB).`
- Example timings from ref pics:
  - Inventory: 2 min 47 sec → inventory_artifact.json (241 KB)
  - Parser: 8 min 2 sec → parser_artifact.json (37 KB)
  - Data: 11 min 57 sec → data_artifact.json (7.2 MB)
  - Logic: 15 min 29 sec → logic_artifact.json (251 KB)
  - Rules: 5 min 57 sec → rules_artifact.json (6.4 MB)
  - Diagram: 11 min 57 sec → diagrams_artifact.json (14 KB)
  - Synthesis (BRD): 19 min 50 sec → brd.md (625 KB)
- Source: a `timeline.json` written by the pipeline as phases complete

### Tab 8 — Conversation

- **Title**: "Conversation & feedback"
- **Subtitle**: "Every prompt directed at an agent for this run, in time order — plus a Feedback thread showing each directed correction and how the system rectified it."
- **Stats**: `N queries · N agents · N feedback` · `All N` filter pill · `N items · N applied · N routed`
- Each feedback item:
  - SME label + classification badge (`Class B · deliberate deviation`) + `CYCLE N`
  - SME comment text (bold key terms)
  - `FEEDBACK IMPLEMENTATION · FEEDBACK-NNN` + `APPLIED` (green badge) or `ROUTED`
  - Action description: "Classified as a _______. Re-ran the analyzer … Change applied to the BRD."
- Source: a `feedback.json` or `conversation.json` written when feedback is submitted via the dashboard

### Tab 9 — State

- **Title**: "Raw state"
- **Subtitle**: "Snapshot of the in-memory DATA model backing this dashboard."
- Formatted JSON display (syntax-highlighted, dark code block) of the full data model:
  ```json
  {
    "meta": {
      "project": "Mainframe-Source COBOL Reverse Engineering",
      "domain": "Cards / Payments – Mainframe Modernization",
      "entry_point": "...",
      "brd_name": "SCA016B_brd.md",
      "updated": "2026-09-29T16:46:19.348Z",
      "project_dir": "...",
      "output_dir": "output",
      "status": "complete"
    },
    "stats": { "programs": 1, "copybooks": 195, "records": 1337, "rules": 2334, "diagrams": 0, "artifacts": 1 },
    "phases": [ { "id": "inventory", "num": 1, "name": "Inventory", "agent": "...", "status": "pending" }, ... ]
  }
  ```

---

## 7. Visual design system

| Token | Value |
|---|---|
| Background (dark) | `#111111` / `#181818` |
| Surface / card bg | `#1e1e1e` / `#222` |
| Border | `#333` |
| Text primary | `#ffffff` |
| Text muted | `#888` / `#aaa` |
| Accent yellow (active tab, phase numbers, Export PDF button) | `#f0c040` / `#e8b800` |
| Green (done status, meets-target, passed) | `#4caf50` / `#22c55e` |
| Orange/red (failed, below-target, blocking) | `#ef4444` / `#f97316` |
| Blue (control flow, progress bar fill, links) | `#3b82f6` / `#60a5fa` |
| Amber triangle (gap badge) | `#f59e0b` |
| Sidebar width | ~280px (collapsible via `<` chevron) |
| Tab font | Sans-serif, ~14px, regular; active = yellow underline 2px |
| Phase number circles | 28px diameter, yellow fill, dark number |
| KPI tile number | ~36px bold |
| KPI tile label | 11px uppercase, letter-spaced |

---

## 7b. Complete output artifact paths (from flow.md)

```
outputs/<run>/
├── discovery/inventory.json                    ← programs, copybooks list
├── analysis/raw_structure/<PROGRAM>.json       ← per-program AST
├── analysis/parser_artifact.json               ← structured summary
├── topology/graph.json                         ← dependency graph (for Interactive Workflow)
├── context/<PROGRAM>_context.txt
├── context/system_index.json
├── data/data_artifact.json                     ← records count for stats tile
├── data/data_layouts/                          ← per-copybook/program layouts
├── logic/program_logic/<PROGRAM>_logic.json    ← call sequence source for Call Trace
├── logic/logic_artifact.json
├── rules/classified_conditions.json
├── rules/rules_artifact.json                   ← rules count for stats tile
├── diagram/component_overview.mmd
├── diagram/erd.mmd
├── diagram/diagrams/flow_<PROGRAM>.mmd
├── diagram/diagrams_artifact.json
└── final_report/
    ├── brd.md
    ├── brd_summary.md
    ├── gaps_register.json
    ├── gaps_register.md
    ├── brd_judge.json                          ← PASS/REVISE verdict + 5-dim scores
    └── brd_judge.md
```

---

## 8. What our harness already produces (for each tab)

| Tab | Data available now | Gap |
|---|---|---|
| Pipeline | phase status from existence of each `*_artifact.json` | Need `timeline.json` (start/end timestamps per phase) |
| Agents | `.claude/agents/*.md` + phase folders | None — all here |
| Artifacts | `outputs/<run>/` filesystem | None |
| Call Trace | `logic_artifact.json` has PERFORM/CALL/GO TO per paragraph | Need to flatten into ordered call sequence |
| Synthetic Testing | Nothing | **New phase needed** (Phase 11?) |
| Interactive Workflow | `topology/graph.json` has dependency graph | Need visual renderer |
| Timeline | Nothing | Need timestamps logged during pipeline run |
| Conversation | Nothing | Need feedback-loop mechanism (out of scope initially) |
| State | All artifacts | Trivially assembled from existing JSON files |

---

## 9. Implementation plan (no coding yet — this is the plan only)

### Phase A — Server scaffold
- Single Python file `dashboard/server.py` — an `http.server` or FastAPI server on port 8787
- Accepts `?outputDir=<path>&brdName=<file>` query string
- Serves one HTML file (the SPA) + a `/api/state` JSON endpoint that assembles the data model from output artifacts

### Phase B — Data model (`/api/state`)
Build a `DashboardState` assembler that reads:
```
inventory.json          → meta, stats.programs, stats.copybooks
data_artifact.json      → stats.records
rules_artifact.json     → stats.rules
diagrams_artifact.json  → stats.diagrams
logic_artifact.json     → call trace rows
parser_artifact.json    → program list
final_report/brd.md     → BRD name, existence
final_report/brd_judge.json → judge verdict (PASS/REVISE), score
```
And emits the single JSON the front-end renders.

### Phase C — Timeline logging
Add a `timeline.json` writer to `run_pipeline.py`: record `{phase, started_at, completed_at, artifact, size_bytes}` for every phase that runs. The dashboard Timeline tab reads this file.

### Phase D — Front-end (single HTML file, no build step)
Build `dashboard/index.html` with:
- Vanilla JS or Alpine.js (no framework build step; keeps it simple)
- CSS variables for the color tokens above
- Left sidebar (collapsible), header strip, stats row, tab bar, tab panels
- Tabs 1–4 and 7, 9 wired to `/api/state` data — **implement these first**
- Tab 5 (Synthetic Testing) — stub "not yet available" panel until Phase E
- Tab 6 (Interactive Workflow) — render `graph.json` as a simple node-edge SVG or use Mermaid.js
- Tab 8 (Conversation) — stub "no feedback recorded" panel

### Phase E — Call Trace (Tab 4)
Post-process `logic_artifact.json` to extract a flat ordered list of operations (PERFORM, CALL, GO TO, SQL) with source line, paragraph, kind, target, and return/no-return flag. Write to `call_trace.json` as part of Phase 6's output.

### Phase F — Synthetic Testing (Tab 5) — optional new phase
If in scope, add Phase 11 `p11_syntest`:
- Read `rules_artifact.json` + `brd.md` (requirements)
- Generate Given/When/Then scenarios per rule (LLM step)
- Evaluate coverage against categories (happy path, negative, boundary, exception, state transition, integration)
- Write `syntest/syntest_artifact.json` with quality score, blocking findings, scenarios
- Dashboard Tab 5 reads this file

### Phase G — Polish
- Export PDF: `window.print()` with a `@media print` stylesheet
- Export JSON: download `state.json`
- Light/dark theme toggle: CSS `data-theme` attribute swap
- Collapsible sidebar: CSS transition on width

---

## 10. Feasibility assessment for this harness

**Yes, this is fully feasible.** Here is the breakdown:

| Feature | Feasibility | Notes |
|---|---|---|
| Pipeline tab | **Easy** | Phases 1–10 status from artifact existence |
| Agents tab | **Easy** | Static from `.claude/agents/*.md` |
| Artifacts tab | **Easy** | Directory walk of `outputs/<run>/` |
| Stats row (programs, copybooks, records, rules) | **Easy** | All in existing artifacts |
| Call Trace tab | **Medium** | Needs a flat-sequence extractor from `logic_artifact.json` |
| Timeline tab | **Easy** | Add ~15 lines of timestamp logging to `run_pipeline.py` |
| State tab | **Easy** | JSON dump of assembled data model |
| Interactive Workflow | **Medium** | Render `graph.json` — can use Mermaid.js already used by harness |
| Synthetic Testing | **Hard** | New phase; real test generation needs LLM + evaluation engine |
| Conversation/Feedback | **Hard** | Needs a feedback-loop UI + mechanism to re-run phases with corrections |

**Recommended scope for v1**: Implement tabs 1 (Pipeline), 2 (Agents), 3 (Artifacts), 7 (Timeline), 9 (State) first — these are all data already available. Then add Call Trace (4) and Interactive Workflow (6). Stub Synthetic Testing (5) and Conversation (8) with "coming soon" panels.

Our harness has **10 phases** vs the reference's **7** (the reference merges Data/Logic/Rules into fewer steps). The sidebar and pipeline cards just need to show 10 rows instead of 7. Everything else maps 1:1.

**Biggest new work item**: the `timeline.json` logging (15 min of work) and the server + HTML file (1–2 days for a clean implementation matching the visual design above).

---

## 11. Environment setup (do this before any code)

### Do we need a venv?
**Yes — two separate environments:**

| Environment | Tool | What goes in it |
|---|---|---|
| Python venv | `python -m venv .venv` | `fastapi`, `uvicorn[standard]` — the backend server only |
| Node modules | `npm install` (inside `dashboard/frontend/`) | React, Vite, Tailwind, shadcn/ui, Recharts, Mermaid.js |

They are completely independent. The Python venv never touches Node and vice versa.

**Python deps (requirements — backend only, tiny):**
```
fastapi
uvicorn[standard]
```
No pandas, no numpy, no heavy ML — just a file-reader that returns JSON.

**Node deps (frontend):**
```
react, react-dom
vite, @vitejs/plugin-react
tailwindcss, postcss, autoprefixer
recharts
mermaid
@shadcn/ui (via CLI)
typescript (optional but recommended)
```

---

## 12. Build plan and progress tracker

Estimated total: **~5 working days**. Check off each item as it is completed.

---

### PHASE 0 — Environment setup (~2 hours)
- [ ] Create `dashboard/` folder at repo root
- [ ] Create `dashboard/frontend/` for the React app
- [ ] Create Python venv: `python -m venv .venv` (at repo root)
- [ ] Install Python deps: `pip install fastapi "uvicorn[standard]"`
- [ ] Freeze: `pip freeze > dashboard/requirements.txt`
- [ ] Scaffold React app: `npm create vite@latest frontend -- --template react-ts` inside `dashboard/`
- [ ] Install Tailwind: `npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p`
- [ ] Install Recharts: `npm install recharts`
- [ ] Install Mermaid: `npm install mermaid`
- [ ] Install shadcn/ui: `npx shadcn-ui@latest init`
- [ ] Add `dashboard/frontend/` to `.gitignore` for `node_modules/` and `dist/`
- [ ] Verify: `npm run dev` shows Vite welcome page

---

### PHASE 1 — Backend: FastAPI server + state assembler (~1 day)

**File: `dashboard/server.py`**

- [ ] Bare FastAPI app with `uvicorn` entry point on port 8787
- [ ] Accept `?outputDir=<path>` query param
- [ ] `GET /api/state` endpoint — assembles and returns the full dashboard data model
- [ ] State assembler reads and merges:
  - [ ] `discovery/inventory.json` → meta, programs count, copybooks count
  - [ ] `analysis/parser_artifact.json` → parser stats
  - [ ] `data/data_artifact.json` → records count, field count
  - [ ] `logic/logic_artifact.json` → logic stats
  - [ ] `analysis/raw_structure/*.json` → control_flow_graph edges (Call Trace source)
  - [ ] `rules/rules_artifact.json` → rules count, rules by category
  - [ ] `diagram/diagrams_artifact.json` → diagrams count
  - [ ] `topology/graph.json` → nodes + edges for Interactive Workflow
  - [ ] `final_report/brd.md` → BRD name, existence, size
  - [ ] `final_report/brd_judge.json` → verdict (PASS/REVISE), weighted score, dimensions
- [ ] Phase status: derive from artifact existence (present = done, missing = pending)
- [ ] Timeline: derive from `meta.generated_at` in each artifact (durations calculated between phases)
- [ ] `GET /api/call-trace?program=<id>` endpoint — returns flat ordered CFG edge list for one program
- [ ] Mount `dashboard/frontend/dist/` as StaticFiles for production serving
- [ ] CORS enabled for `localhost:5173` (Vite dev server)
- [ ] Test: `curl http://localhost:8787/api/state?outputDir=outputs/carddemo` returns valid JSON

---

### PHASE 2 — Frontend scaffold + global layout (~1 day)

**Design tokens (match the reference exactly):**
- [ ] Define CSS variables in `index.css`: bg, surface, border, text-primary, text-muted, accent-yellow, green, red-orange, blue, amber
- [ ] Dark theme by default; `[data-theme="light"]` overrides
- [ ] Global font: system sans-serif stack, 14px base

**Layout shell (`App.tsx`):**
- [ ] Left sidebar (fixed, 280px, collapsible via `<` chevron)
  - [ ] `RE` logo badge + "Harness Pipeline / Reverse Engineering" heading
  - [ ] "PIPELINE · N PHASES" label
  - [ ] Phase list: numbered circle (yellow) + name + `● done/pending/running` badge + progress bar
- [ ] Main content area (flex-grow)
  - [ ] Header strip: title + status badge + theme toggle + Export JSON + Export PDF buttons
  - [ ] Meta strip: PROJECT DIRECTORY · ENTRY POINT · OUTPUT DIRECTORY · BRD NAME (4 columns)
  - [ ] Stats row: 6 KPI tiles (OVERALL · PROGRAMS · COPYBOOKS · RECORDS · RULES · ARTIFACTS)
  - [ ] Tab bar: 9 tabs, active = yellow 2px underline
  - [ ] Tab content panel (router)
- [ ] `useEffect` hook that fetches `/api/state?outputDir=<param>` on mount and stores in context
- [ ] outputDir read from `window.location.search` query param

---

### PHASE 3 — Tab 1: Pipeline (~3 hours)

**File: `src/tabs/PipelineTab.tsx`**

- [ ] "Pipeline overview" heading + "Overall progress" sub-label
- [ ] Full-width progress bar (% = phases done / total)
- [ ] Row of phase summary cards: PHASE N · Name · ● done/pending
- [ ] Expandable accordion per phase: agent name, backing module, artifact produced, size, `generated_at` timestamp
- [ ] Clicking a phase card scrolls to its accordion

---

### PHASE 4 — Tab 2: Agents (~2 hours)

**File: `src/tabs/AgentsTab.tsx`**

- [ ] Table: Agent # · Name · Type (Deterministic / LLM+Python) · Phase · Backing module · Output artifact · Status badge
- [ ] Data hardcoded from `.claude/agents/*.md` specs (10 rows, static)
- [ ] Expandable row: shows full description from agent spec

---

### PHASE 5 — Tab 3: Artifacts (~2 hours)

**File: `src/tabs/ArtifactsTab.tsx`**

- [ ] `GET /api/artifacts` endpoint in server (directory walk, returns name/path/size/phase/mtime)
- [ ] Filterable table: file name · producing phase · size · last modified
- [ ] Filter by phase (dropdown)
- [ ] Click row → download the file

---

### PHASE 6 — Tab 4: Call Trace (~1 day)

**File: `src/tabs/CallTraceTab.tsx`**

- [ ] Program selector dropdown (if multiple programs)
- [ ] Description + "How to read it" info box
- [ ] Stats line: N operations · N return here · N do not return
- [ ] Filter pills: All N (yellow) · Control flow N (blue) · Program call N (blue) · Database N (green)
- [ ] Table columns: STEP · SOURCE LINE ⓘ · IN PARAGRAPH · KIND (badge) · OPERATION · TARGET · WHAT HAPPENS NEXT
- [ ] Data: flatten `control_flow_graph.edges` from all `raw_structure/*.json` sorted by `source_line`
- [ ] KIND mapping: `PERFORM_SIMPLE/PERFORM_THRU` → "Control flow" (blue), `CALL` → "Program call" (blue), `EXEC SQL` → "Database" (green), `GO TO` → "Control flow no-return" (orange)
- [ ] WHAT HAPPENS NEXT: "Returns here" if `type` is PERFORM, "Moves control away" if GO TO

---

### PHASE 7 — Tab 6: Interactive Workflow (~half day)

**File: `src/tabs/WorkflowTab.tsx`**

- [ ] Convert `topology/graph.json` nodes+edges to Mermaid `flowchart LR` syntax on the fly
- [ ] Render using `mermaid.render()` into a `<div>`
- [ ] Click a node → highlight it and show a side panel with that program's stats (paragraphs, rules, copybooks)
- [ ] Zoom in/out controls

---

### PHASE 8 — Tab 7: Timeline (~2 hours)

**File: `src/tabs/TimelineTab.tsx`**

- [ ] "Timeline" heading + "Pipeline events as agents progress through the N phases" sub-label
- [ ] Vertical list, each row:
  - Green dot · ISO timestamp (from `meta.generated_at`)
  - Bold: `<Phase name> completed successfully in N min N sec`
  - Sub-text: Started `<ts>` · completed `<ts>` · Produced `<artifact>` (`N KB`)
- [ ] Duration calculated as: `generated_at[phase N]` minus `generated_at[phase N-1]`
- [ ] Timeline data assembled server-side in `/api/state`

---

### PHASE 9 — Tab 9: State (~1 hour)

**File: `src/tabs/StateTab.tsx`**

- [ ] "Raw state" heading + subtitle
- [ ] Syntax-highlighted JSON viewer (use `react-json-view` or a simple `<pre>` with highlight.js)
- [ ] "Copy JSON" button

---

### PHASE 10 — Stubs: Synthetic Testing (Tab 5) + Conversation (Tab 8) (~30 min)

- [ ] `SyntheticTestingTab.tsx`: "coming soon" panel with description of what this will show when Phase 11 is built
- [ ] `ConversationTab.tsx`: "coming soon" panel explaining feedback loop not yet implemented

---

### PHASE 11 — Polish + one-command launcher (~half day)

- [ ] Light/dark theme toggle: button swaps `data-theme` on `<html>`, persisted in `localStorage`
- [ ] Export JSON button: `window.open('/api/state?outputDir=...')` triggers download
- [ ] Export PDF button: `window.print()` with `@media print` stylesheet hiding sidebar + tab bar
- [ ] Collapsible sidebar: CSS `width` transition, chevron rotates 180°
- [ ] Responsive: at <900px sidebar collapses automatically, tab bar scrolls horizontally
- [ ] `dashboard/start.py`: checks if `frontend/dist/` exists, runs `npm run build` if not, then starts uvicorn + opens browser
- [ ] `dashboard/README.md`: "Run `python dashboard/start.py --output outputs/carddemo`"
- [ ] End-to-end smoke test: launch, verify all 7 live tabs render without errors

---

### DONE CRITERIA

The dashboard is considered v1-complete when:
- [ ] `python dashboard/start.py --output outputs/carddemo` opens the browser in one command
- [ ] All 7 live tabs (Pipeline, Agents, Artifacts, Call Trace, Interactive Workflow, Timeline, State) show real data from `outputs/carddemo`
- [ ] Stats row shows correct numbers: programs, copybooks, records, rules, artifacts
- [ ] Phase list in sidebar shows all 10 phases as `● done`
- [ ] Light/dark theme toggle works
- [ ] Export JSON downloads the state file
- [ ] Synthetic Testing and Conversation show "coming soon" panels
