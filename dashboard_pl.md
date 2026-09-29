# Dashboard — Technical Specification

## Purpose

A local web dashboard for the 10-phase COBOL → BRD reverse engineering harness. Reads artifacts produced by the pipeline and presents them as a structured analytics interface. Serves one output directory at a time; supports any harness run by changing the `outputDir` query parameter.

---

## Architecture

```
repo root/
├── dashboard/
│   ├── server.py          FastAPI backend (port 8787)
│   ├── start.py           One-command launcher
│   ├── requirements.txt   Python dependencies
│   └── frontend/
│       ├── src/           React + TypeScript source
│       ├── dist/          Built assets (served by FastAPI)
│       └── package.json
├── dashboard_pl.md        This file
└── db_work.md             User guide
```

**Backend** — FastAPI reads artifact files from the output directory on every request. No caching; always reflects current disk state. Enables live updates as the pipeline runs.

**Frontend** — React 18 SPA built with Vite 6. Polls `/api/state` every 5 seconds and updates all views in place.

---

## Stack

| Component | Technology | Version |
|---|---|---|
| Backend server | FastAPI + uvicorn | 0.142 / 0.54 |
| Frontend framework | React + TypeScript | 18 / 5.6 |
| Build tool | Vite | 6 |
| CSS | Tailwind CSS | 3 |
| Diagrams | Mermaid.js | 11 |
| Markdown parser | marked.js | 15 |
| Charts | Recharts | 3 |
| Python environment | venv at repo root | `.venv/` |
| Node modules | npm | `dashboard/frontend/node_modules/` |

---

## Running the Dashboard

```bash
# From repo root — launches server + opens browser
python dashboard/start.py --output outputs/carddemo

# Or manually:
source .venv/Scripts/activate          # Windows: .venv\Scripts\activate
uvicorn dashboard.server:app --port 8787 --reload

# Dev mode (hot-reload frontend):
cd dashboard/frontend && npm run dev
```

---

## Backend API

All endpoints accept `outputDir` as a required query parameter pointing to the harness output folder.

| Endpoint | Purpose |
|---|---|
| `GET /api/state` | Assembles and returns the full dashboard data model |
| `GET /api/artifacts` | Directory listing of all produced artifact files |
| `GET /api/call-trace` | CFG-derived call trace; optional `program` filter |
| `GET /api/brd` | BRD markdown content and file metadata |
| `GET /api/rules` | All business rules with stats and rule sets |
| `GET /api/topology` | Raw topology graph (nodes + edges) |

Static files — production build is served from `dashboard/frontend/dist/` mounted at `/`.

---

## Frontend Structure

```
src/
├── App.tsx                  Root: layout, tab routing, header, sidebar
├── useAppState.ts           Polling hook — fetches /api/state every 5s
├── types.ts                 TypeScript interfaces for all data shapes
├── index.css                Design tokens, utility classes, dark/light theme
├── components/
│   ├── Sidebar.tsx          Collapsible phase list
│   ├── StatsRow.tsx         6-tile KPI bar
│   ├── BRDModal.tsx         BRD viewer — marked.js + Mermaid rendering + TOC
│   └── tabs/
│       ├── PipelineTab.tsx        Phase cards + BRD Judge verdict
│       ├── AgentsTab.tsx          Agent table
│       ├── ArtifactsTab.tsx       Filterable artifact catalogue
│       ├── CallTraceTab.tsx       CFG call trace with filters
│       ├── SyntheticTestingTab.tsx Quality score from rules confidence
│       ├── WorkflowTab.tsx        Mermaid program call graph
│       ├── TimelineTab.tsx        Phase completion timeline
│       ├── RulesTab.tsx           Filterable business rules browser
│       └── StateTab.tsx           Raw JSON viewer
```

---

## Design System

Defined in `src/index.css` as CSS custom properties on `:root`.

### Colour tokens (dark theme default)

| Token | Value | Used for |
|---|---|---|
| `--color-bg` | `#111111` | Page background |
| `--color-surface` | `#1a1a1a` | Cards, panels |
| `--color-surface-2` | `#222222` | Nested surfaces, inputs |
| `--color-border` | `#2a2a2a` | All borders |
| `--color-text` | `#f0f0f0` | Primary text |
| `--color-text-muted` | `#888888` | Labels, metadata |
| `--color-accent` | `#e8b800` | Yellow accent, active states |
| `--color-green` | `#22c55e` | Done status, confirmed |
| `--color-blue` | `#3b82f6` | Control flow, info |
| `--color-red` | `#ef4444` | Errors |
| `--color-orange` | `#f97316` | Warnings, no-return |

Light theme overrides apply via `[data-theme="light"]` on `<html>`. Theme preference is persisted in `localStorage`.

### Utility classes

`.card` `.badge` `.badge-done` `.badge-pending` `.badge-llm` `.badge-det` `.badge-pass` `.badge-revise` `.pill` `.pill.active` `.kpi-tile` `.tab-bar` `.tab-btn` `.sidebar` `.sidebar.collapsed` `.progress-bar` `.progress-bar-fill` `.data-table` `.phase-circle`

---

## Data Model (`/api/state` response shape)

```typescript
{
  meta: {
    project: string          // harness project name
    entry_point: string      // source root scanned
    output_dir: string       // output folder path
    brd_name: string         // filename of produced BRD
    status: "complete" | "in-progress"
    updated: string          // ISO timestamp of last poll
  }
  stats: {
    programs: number         // from inventory.stats.programs
    copybooks: number        // from inventory.stats.copybooks
    records: number          // from data_artifact
    rules: number            // from rules_artifact
    diagrams: number         // from diagrams_artifact
    artifacts: number        // count of .json/.md/.mmd files
  }
  overall_pct: number        // done_phases / 10 * 100
  phases: PhaseDef[]         // 10 entries, one per phase
  timeline: TimelineEntry[]  // generated_at deltas per phase
  verdict: {
    verdict: "PASS" | "REVISE" | "—"
    rating: string
    weighted_score: number
    dimensions: Record<string, { score: number; rationale: string }>
    feedback: Array<{ dimension; severity; suggestion }>
    groundedness_failures: string[]
  }
  topology: {
    nodes: TopoNode[]        // CALLS_PROGRAM nodes only
    edges: TopoEdge[]        // from/to/type normalised
    all_nodes_count: number  // full graph size for info
    all_edges_count: number
  }
  rules_by_category: Record<string, number>
  rules_by_confidence: Record<string, number>
}
```

---

## Phase — Artifact Mapping

| Phase | ID | Artifact path | Type |
|---|---|---|---|
| 1 Discovery | `discovery` | `discovery/inventory.json` | Deterministic |
| 2 Parser | `parser` | `analysis/parser_artifact.json` | Deterministic |
| 3 Topology | `topology` | `topology/graph.json` | Deterministic |
| 4 Context | `context` | `context/system_index.json` | Deterministic |
| 5 Data | `data` | `data/data_artifact.json` | Deterministic |
| 6 Logic | `logic` | `logic/logic_artifact.json` | LLM + Python |
| 7 Rules | `rules` | `rules/rules_artifact.json` | LLM + Python |
| 8 Diagram | `diagram` | `diagram/diagrams_artifact.json` | Deterministic |
| 9 BRD | `brd` | `final_report/brd.md` | LLM + Python |
| 10 Judge | `judge` | `final_report/brd_judge.json` | LLM + Python |

Phase status is derived by checking whether the artifact file exists. Duration is the delta between consecutive `meta.generated_at` timestamps.

---

## Synthetic Testing — Quality Score

The quality score (0–100) is computed in `SyntheticTestingTab.tsx` from the rules confidence distribution already present in `/api/state`:

```
score = (confirmed×1.0 + high×0.9 + medium×0.5 + low×0.2) / total_rules × 100
```

This is a **weighted evidence coverage metric** — it measures what fraction of the extracted rules have strong enough evidence in the COBOL source to be directly expressed as verifiable test conditions. A score of 70+ indicates the majority of rules are test-ready. Rules at medium/low confidence require SME clarification before testing.

---

## Build Commands

```bash
# Install Python dependencies
pip install -r dashboard/requirements.txt

# Install frontend dependencies
cd dashboard/frontend && npm install

# Build production frontend
cd dashboard/frontend && npm run build

# Run harness tests
python -m unittest discover -s tests -v
```

---

## v1.1 Feature Summary

| Feature | Status |
|---|---|
| 9 tabs — all with live data | ✓ |
| Live polling (5s) | ✓ |
| View BRD — marked.js + Mermaid + TOC | ✓ |
| Synthetic Testing quality score | ✓ |
| Rules Explorer (filterable) | ✓ |
| Collapsible sidebar with expand button | ✓ |
| Dark / light theme (persisted) | ✓ |
| Export JSON / Export PDF / Download BRD | ✓ |
| Plug-and-play for any harness output dir | ✓ |
| One-command launcher (`start.py`) | ✓ |
