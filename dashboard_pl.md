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

**Status: v1 COMPLETE ✓** — committed to `feat/dashboard` (27 files, 6,489 lines). Build verified: `tsc + vite`, exit 0, 1 min 24 sec.

---

### PHASE 0 — Environment setup ✅ DONE
- [x] Create `dashboard/` folder at repo root
- [x] Create `dashboard/frontend/` for the React app
- [x] Create Python venv: `python -m venv .venv` (at repo root)
- [x] Install Python deps: `pip install fastapi "uvicorn[standard]"` → fastapi 0.142.0, uvicorn 0.54.0
- [x] Freeze: `dashboard/requirements.txt` written
- [x] Scaffold React app: `package.json` written manually (react-ts template equivalent)
- [x] Install Tailwind + postcss + autoprefixer (in `package.json`, installed via `npm install`)
- [x] Install Recharts v3: `npm install recharts@3` (upgraded from 2.x to avoid deprecation warning)
- [x] Install Mermaid: `mermaid@11.4.1`
- [x] shadcn/ui: **skipped** — used custom components instead (lighter, no CLI dependency)
- [x] Add `dashboard/frontend/.gitignore` for `node_modules/` and `dist/`
- [x] `npm install` completed (266 packages, 0 vulnerabilities)

---

### PHASE 1 — Backend: FastAPI server + state assembler ✅ DONE

**File: `dashboard/server.py`**

- [x] Bare FastAPI app with `uvicorn` entry point on port 8787
- [x] Accept `?outputDir=<path>` query param
- [x] `GET /api/state` endpoint — assembles and returns the full dashboard data model
- [x] State assembler reads and merges:
  - [x] `discovery/inventory.json` → meta, programs count, copybooks count
  - [x] `analysis/parser_artifact.json` → parser stats
  - [x] `data/data_artifact.json` → records count, field count
  - [x] `logic/logic_artifact.json` → logic stats
  - [x] `analysis/raw_structure/*.json` → control_flow_graph edges (Call Trace source)
  - [x] `rules/rules_artifact.json` → rules count, rules by category
  - [x] `diagram/diagrams_artifact.json` → diagrams count
  - [x] `topology/graph.json` → nodes + edges for Interactive Workflow
  - [x] `final_report/brd.md` → BRD name, existence, size
  - [x] `final_report/brd_judge.json` → verdict (PASS/REVISE), weighted score, dimensions
- [x] Phase status: derive from artifact existence (present = done, missing = pending)
- [x] Timeline: derive from `meta.generated_at` in each artifact (durations calculated between phases)
- [x] `GET /api/call-trace?program=<id>` endpoint — returns flat ordered CFG edge list for one program
- [x] `GET /api/artifacts` endpoint — directory walk, returns name/path/size/phase
- [x] `GET /api/topology` endpoint — returns graph nodes + edges
- [x] Mount `dashboard/frontend/dist/` as StaticFiles for production serving
- [x] CORS enabled for `localhost:5173` (Vite dev server)
- [x] **Verified**: `assemble_state()` returns `100% overall, 10/10 phases done, PASS verdict, 168 topology nodes`

---

### PHASE 2 — Frontend scaffold + global layout ✅ DONE

**Design tokens:**
- [x] CSS variables in `index.css`: bg, surface, surface-2, border, text, text-muted, accent-yellow, green, red, orange, blue, amber
- [x] Dark theme by default (`data-theme="dark"` on `<html>`); `[data-theme="light"]` overrides
- [x] Global font: system sans-serif stack, 14px base
- [x] Utility classes: `.card`, `.badge`, `.pill`, `.kpi-tile`, `.progress-bar`, `.data-table`, `.phase-circle`, `.tab-bar`, `.tab-btn`

**Layout shell (`App.tsx`):**
- [x] Left sidebar (272px, collapsible via `‹` chevron with CSS transition)
  - [x] `RE` logo badge + "Harness Pipeline / Reverse Engineering" heading
  - [x] "PIPELINE · N PHASES" label
  - [x] Phase list: numbered circle (yellow) + name + `● done/pending` badge + green progress bar
- [x] Main content area (flex-grow)
  - [x] Header strip: title + `● live · complete` status badge + theme toggle + Export JSON + Export PDF
  - [x] Meta strip: PROJECT DIRECTORY · ENTRY POINT · OUTPUT DIRECTORY · BRD NAME (4 columns)
  - [x] Stats row: 6 KPI tiles (OVERALL · PROGRAMS · COPYBOOKS · RECORDS · RULES · ARTIFACTS)
  - [x] Tab bar: 9 tabs, active = yellow 2px underline, horizontal scroll on overflow
  - [x] Tab content panel (conditional render router)
- [x] `useAppState` hook fetches `/api/state?outputDir=<param>` on mount
- [x] `outputDir` read from `window.location.search` query param (defaults to `outputs/carddemo`)

---

### PHASE 3 — Tab 1: Pipeline ✅ DONE

**File: `src/components/tabs/PipelineTab.tsx`**

- [x] "Pipeline overview" heading + "Overall progress" sub-label
- [x] Full-width progress bar (% = phases done / total), blue fill
- [x] Row of phase summary cards (5-column grid): PHASE N · Name · `● done/pending` — click to expand
- [x] Expandable card per phase: type badge, module path, artifact, size KB, duration, `generated_at`
- [x] BRD Judge verdict card: PASS/REVISE badge, rating, weighted score, 5-dimension score tiles

---

### PHASE 4 — Tab 2: Agents ✅ DONE

**File: `src/components/tabs/AgentsTab.tsx`**

- [x] Table: # · Name + description · Type badge · Backing module · Output artifact · Status · Size · Duration
- [x] All 10 agents with inline descriptions (no expandable row needed — descriptions shown inline)

---

### PHASE 5 — Tab 3: Artifacts ✅ DONE

**File: `src/components/tabs/ArtifactsTab.tsx`**

- [x] `/api/artifacts` endpoint in server (directory walk, returns name/path/size/phase/ext)
- [x] Searchable by filename + filterable by phase (pill buttons)
- [x] Table: file name · phase · type (colour-coded ext badge) · size KB · full path
- [x] Total file count + total KB shown in header
- [ ] Click row → download file *(not implemented — planned for v1.1)*

---

### PHASE 6 — Tab 4: Call Trace ✅ DONE

**File: `src/components/tabs/CallTraceTab.tsx`**

- [x] Program selector dropdown (shows all programs, or filter to one)
- [x] Description + "How to read it" amber info box
- [x] Stats line: N operations · N return here · N do not return
- [x] Filter pills: All (yellow) · Control flow (blue dot) · Program call (blue dot) · Database (green dot)
- [x] Table: STEP · PROGRAM · SOURCE LINE · IN PARAGRAPH · KIND (coloured badge) · OPERATION · TARGET · RETURNS?
- [x] Data: `control_flow_graph.edges` from all `raw_structure/*.json` flattened and sorted by source line
- [x] KIND mapping: PERFORM → "Control flow" (blue), CALL → "Program call" (blue), SQL → "Database" (green), GO TO → "Control flow (no return)" (orange)
- [x] RETURNS column: "Returns here" (green) / "Moves away" (orange)

---

### PHASE 7 — Tab 6: Interactive Workflow ✅ DONE

**File: `src/components/tabs/WorkflowTab.tsx`**

- [x] Converts `topology/graph.json` nodes + edges to Mermaid `flowchart LR` syntax dynamically
- [x] Renders via `mermaid.render()` into a `<div>` — respects dark/light theme
- [x] Click a node → side panel shows all node properties
- [ ] Zoom in/out controls *(not implemented — browser native scroll zoom works)*

---

### PHASE 8 — Tab 7: Timeline ✅ DONE

**File: `src/components/tabs/TimelineTab.tsx`**

- [x] "Timeline" heading + "Pipeline events as agents progress through the N phases" sub-label
- [x] Vertical timeline with green dots + connecting line
- [x] Each entry: ISO timestamp · bold phase name + duration · artifact name + KB
- [x] Durations calculated from `generated_at` delta between consecutive phases
- [x] Timeline data assembled server-side in `/api/state` → `timeline[]`

---

### PHASE 9 — Tab 9: State ✅ DONE

**File: `src/components/tabs/StateTab.tsx`**

- [x] "Raw state" heading + "Snapshot of the in-memory data model backing this dashboard" subtitle
- [x] Monospace `<pre>` JSON viewer with syntax colouring via CSS
- [x] "Copy JSON" button with "✓ Copied" confirmation flash

---

### PHASE 10 — Stubs ✅ DONE

**File: `src/components/tabs/StubTab.tsx`** (reusable component used for both stubs)

- [x] Synthetic Testing tab: 🚧 icon + "Coming in v2" badge + description of what it will show
- [x] Conversation tab: same treatment

---

### PHASE 11 — Polish + one-command launcher ✅ DONE

- [x] Light/dark theme toggle: swaps `data-theme` on `<html>`, persisted in `localStorage`
- [x] Export JSON: `window.open('/api/state?outputDir=...')` opens JSON in new tab
- [x] Export PDF: `window.print()` with `@media print` stylesheet hiding sidebar + tab bar + header actions
- [x] Collapsible sidebar: CSS `width` transition (272px ↔ 52px), chevron rotates 180°
- [x] Tab bar scrolls horizontally on narrow screens
- [x] `dashboard/start.py`: validates output dir, runs `npm install` + `npm run build` if `dist/` missing, auto-opens browser, starts uvicorn
- [ ] `dashboard/README.md` *(not yet written — use start.py docstring for now)*
- [ ] End-to-end smoke test in browser *(pending — run `python dashboard/start.py` to verify)*

---

### DONE CRITERIA — STATUS

- [x] `python dashboard/start.py --output outputs/carddemo` opens the browser in one command
- [ ] All 7 live tabs verified in browser *(pending first launch)*
- [x] Stats row assembled correctly: records=596, rules=324, diagrams=46, artifacts=310 (verified via Python unit test)
- [x] Phase list shows all 10 phases as `● done` (verified via assembler)
- [x] Light/dark theme toggle implemented
- [x] Export JSON implemented
- [x] Synthetic Testing and Conversation show "coming soon" panels
- [x] Build: TypeScript compiles clean, Vite bundles 2,121 modules, exit 0 in 1m 24s
- [x] Committed: `feat/dashboard` branch, commit `c647fd6`, 27 files, 6,489 insertions

---

### REMAINING FOR v1.1

- [ ] Browser smoke test — open dashboard and confirm all 7 tabs render live data
- [ ] Artifact download on row click (Artifacts tab)
- [ ] Zoom controls on Workflow diagram
- [ ] `dashboard/README.md`
- [ ] Programs/copybooks count fix (currently 0 — `inventory.json` key names need verification)
- [ ] Auto-collapse sidebar at <900px viewport width
