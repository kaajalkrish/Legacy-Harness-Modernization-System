# COBOL Reverse Engineering Dashboard — Reference Guide

A plain-English walkthrough of the dashboard, what every section means, and how to explain it to anyone.

---

## What is this dashboard?

This is a **live dashboard** for the COBOL → BRD (Business Requirements Document) reverse engineering pipeline. You point it at a folder of old COBOL source code, run the 10-phase harness, and the dashboard shows you everything the harness discovered — programs, data structures, business rules, a full BRD, and a quality verdict — all without touching a single line of the original code.

**How to launch:**
```
python dashboard/start.py --output outputs/carddemo
```
Opens automatically at `http://localhost:8787`.

**Current demo input:** `outputs/carddemo` — the IBM CardDemo COBOL sample with 44 programs and 62 copybooks. All 10 phases ran to completion and the BRD received a **PASS** verdict.

---

## Live polling — does it update automatically?

**Yes.** The dashboard polls `/api/state` every **5 seconds**. The server reads artifact files from disk on every poll — it does not cache results.

**Practical workflow:**
- Terminal 1: `python dashboard/start.py --output outputs/carddemo` — dashboard stays open
- Terminal 2: `python run_pipeline.py` or individual phase commands — agents write artifacts to disk

As each phase finishes and writes its output file, the dashboard picks it up within 5 seconds:
- Sidebar phase circles turn green one by one
- OVERALL % ticks up (e.g. 10% → 20% → … → 100%)
- KPI tiles (programs, rules, records) update as each phase adds data
- Timeline grows a new entry per completed phase
- The "Live · updated HH:MM:SS" timestamp in the header refreshes every 5 seconds

**No browser refresh needed at any point.**

---

## Layout

```
┌─────────────────────┬──────────────────────────────────────────────────┐
│  Sidebar            │  Header: title, status badge, theme, export      │
│  (phase list)       │  Meta strip: project dir, entry point, BRD name  │
│                     │  Stats row: 6 KPI tiles                           │
│  10 numbered        │  Tab bar: 9 tabs                                  │
│  phase circles      │                                                   │
│                     │  Tab content (changes per tab)                    │
│  Collapse ‹         │                                                   │
└─────────────────────┴──────────────────────────────────────────────────┘
```

- **Sidebar** — collapsible. Click `‹` to hide, `›` to show. When collapsed, only the yellow phase-number circles are visible so you can still track progress.
- **Header** — shows overall pipeline status. Green `● live · complete` = all phases finished.
- **Meta strip** — WHERE the code lives (project dir), what the harness started from (entry point), and what document was produced (BRD name).
- **Stats row** — 6 top-level numbers at a glance (see below).

---

## Stats Row — KPI tiles

| Tile | What it counts | carddemo value |
|---|---|---|
| **OVERALL** | % of pipeline phases that finished | 100% |
| **PROGRAMS** | COBOL programs found in the source | 44 |
| **COPYBOOKS** | Copybook files (shared data definitions) | 62 |
| **RECORDS** | Data records extracted from DATA DIVISIONs | 596 |
| **RULES** | Business rules mined from branch conditions | 324 |
| **ARTIFACTS** | Output files produced by the harness | ~310 |

---

## Tabs — one by one

### 1. Pipeline
**What it shows:** The 10 phases of the harness in a grid. Click any phase card to expand its detail.

**How to explain it:** "Each box is one agent. Green dot = done. You can see what file it produced, how big it is, and how long it took. At the bottom is the BRD Judge card — it shows the 5-dimension quality score and the final PASS/REVISE verdict."

Key detail: the progress bar at the top reflects how many phases are complete.

---

### 2. Agents
**What it shows:** A table of all 10 agents — what each one does, whether it's deterministic or LLM-assisted, and what file it outputs.

**How to explain it:** "Row = one agent. The Type badge tells you if it ran pure code (Deterministic) or used an AI model (LLM + Python). Duration shows how long that agent took. The first phase has no duration because there's no previous phase to measure from."

---

### 3. Artifacts
**What it shows:** Every file produced by the harness, filterable by phase or file name.

**How to explain it:** "The harness writes hundreds of JSON, Markdown and diagram files. This tab lets you see all of them, how big they are, and which phase produced them. Filter by phase name to narrow down."

---

### 4. Call Trace
**What it shows:** Every operation a COBOL program performs — internal paragraph calls (PERFORM), program calls (CALL), and database queries (EXEC SQL) — in source-line order.

**How to explain it:** "Imagine a flight recorder for the COBOL program. Every time it jumps to another paragraph, calls another program, or hits the database, it's one row in this table. Blue = stays inside this program, green = hits the database. The 'Returns?' column tells you if control comes back after that operation."

Filter pills let you slice by operation category.

---

### 5. Synthetic Testing
**What it shows:** A quality gate derived from the 324 business rules — how many are confirmed enough to be turned into test scenarios, and how many still need SME review.

**The quality score — what it is and how it's calculated:**

The score (0–100) is a **weighted evidence coverage metric**:

```
score = (confirmed×1.0 + high×0.9 + medium×0.5 + low×0.2) / total_rules × 100
```

For carddemo:
- 185 confirmed rules × 1.0 = 185.0
- 20 high confidence × 0.9  = 18.0
- 47 medium confidence × 0.5 = 23.5
- 72 low confidence × 0.2   = 14.4
- Total weighted = 240.9 / 324 × 100 = **74 / 100**

**Is the score accurate?** Yes. The confidence level on each rule is set by the Rules agent (Phase 7) based on how clearly the COBOL source expresses the rule's business intent. "Confirmed" means both the branch condition and its business effect are unambiguous. "Low" means the condition is present in the code but the business meaning is uncertain. The score correctly reflects that 74% of this codebase's rules have strong enough evidence to write verifiable test cases — the remaining 26% need a subject-matter expert to clarify what the business effect actually is.

**How to explain it in a demo:** "Before we can test this system, we need to know how many of the rules we extracted are actually testable. 74 out of 100 means most rules are solid — but 119 rules need someone with business knowledge to confirm what they actually mean before we can write a test for them."

---

### 6. Interactive Workflow
**What it shows:** The program call graph — which COBOL programs call which other programs — rendered as a live Mermaid flowchart.

**How to explain it:** "Each box is one COBOL program. An arrow means 'Program A calls Program B'. You can click any box to see its metadata in the side panel. The diagram only shows direct program-to-program calls; copybook includes are hidden to keep it readable."

carddemo has 44 programs and 62 CALLS_PROGRAM edges.

---

### 7. Timeline
**What it shows:** A vertical timeline of when each phase finished, how long it ran, and what it produced.

**How to explain it:** "Each dot on the line is a phase completion event, stamped with the real time from when the harness ran. You can see whether the pipeline ran in minutes or hours, and which phases were the bottlenecks."

Phases 6 and 7 (Logic + Rules) are the LLM phases and take the longest.

---

### 8. Rules Explorer (previously "Conversation")
**What it shows:** Every one of the 324 business rules mined from the COBOL source, browsable and filterable.

**How to use it:**
- Filter by category pill: VALIDATION (300), CALCULATION (4), LIMIT_CHECK (4), ROUTING (16)
- Filter by confidence: confirmed / high / medium / low
- Search by rule name, ID, or description text
- Click any row → expands to show the exact COBOL condition text, pattern type, source program and paragraph, and whether SME review is flagged

**How to explain it in a demo:** "These are the business rules the system extracted automatically from the COBOL code — no manual reading required. You can filter by type, see exactly where in the code each rule comes from, and flag the ones that need a business analyst to validate."

---

### 9. State
**What it shows:** The raw JSON that backs the entire dashboard — the same object served by `GET /api/state`.

**How to explain it:** "This is everything the dashboard knows, in one JSON tree. You can copy it, export it, or hand it to another tool. It's the single source of truth for this run."

---

## Export options and header buttons

| Button | What it does |
|---|---|
| **View BRD** | Opens the full Business Requirements Document in a modal overlay — properly rendered with headings, tables, blockquotes. Has a Download .md button to save the file |
| **Export JSON** | Opens `/api/state` in a new tab — the full data model as JSON, save it as a file |
| **Export PDF** | Triggers `window.print()` — sidebar and controls are hidden for a clean print |
| **Light/Dark theme** | Toggles theme, persisted in `localStorage` |

The **"Live · updated HH:MM:SS"** timestamp under the title shows when the dashboard last polled the server. It refreshes every 5 seconds.

---

## Is carddemo good for demo?

**Yes** — it is the best available input for demos because:
- **44 programs, 62 copybooks** — substantial enough to show a real system graph
- **324 business rules** extracted and classified
- **596 data records** from the DATA DIVISION
- **BRD verdict: PASS** with 5-dimension score
- **All 10 phases complete** — every tab has live data
- **IBM CardDemo** is a publicly known, well-understood COBOL sample — no IP concerns

---

## Technical stack (for developers)

| Layer | Tech |
|---|---|
| Backend | FastAPI 0.142 · Python 3.11 · uvicorn on port 8787 |
| Frontend | React 18 · Vite 6 · TypeScript · Tailwind CSS 3 |
| Diagrams | Mermaid.js 11 (flowchart) |
| Charts | Recharts 3 |
| State viewer | react-json-view-lite |
| Launcher | `dashboard/start.py` — validates output dir, builds if needed, opens browser |

---

## Enhancements over the reference images

The reference screenshots showed an earlier 7-phase version of the pipeline. Our build adds:

| Enhancement | Why it matters |
|---|---|
| **10-phase pipeline support** | Full harness (Discovery → BRD Judge) vs. 7 phases in reference |
| **BRD Judge verdict card** | 5-dimension quality scorecard (completeness, accuracy, coverage, clarity, actionability) + PASS/REVISE badge inside the Pipeline tab — not in reference |
| **Phase type badges** | Agents tab shows "Deterministic" vs "LLM + Python" so you can see which phases used AI |
| **Multi-program Call Trace** | Reference showed a single-program trace; our build has a dropdown to pick any of the 44 CardDemo programs |
| **Workflow noise filtering** | Reference showed the raw full graph (hundreds of copybook edges); our build filters to CALLS\_PROGRAM only — 62 clean program-call edges vs 462 total |
| **Artifact search + filter** | Phase pill filter + filename search + extension colour-coding (JSON blue, Markdown green, Mermaid yellow) |
| **`start.py` one-command launcher** | `python dashboard/start.py --output outputs/carddemo` — auto-builds frontend if needed, auto-opens browser |
| **Theme persisted across sessions** | Light/dark choice saved in `localStorage` |
| **Live polling every 5 seconds** | Dashboard auto-updates as pipeline phases complete — no refresh needed |
| **View BRD button** | Renders the full BRD in-browser with proper headings, tables, blockquotes via `marked.js` — plus a Download .md button |
| **Synthetic Testing tab with real data** | Quality score (74/100 for carddemo), confidence and category breakdowns from actual rules — not a stub |
| **Rules Explorer tab** | All 324 rules filterable by category and confidence, expandable rows with condition text and source location |

## Accuracy vs. reference images

Key differences vs. the reference screenshots (all intentional):

| Feature | Reference | This build |
|---|---|---|
| Title | "Mainframe-Source COBOL Reverse Engineering" | "COBOL Reverse Engineering" |
| Logo badge | "RE" | "C→B" |
| Phases | 7 phases (smaller harness) | 10 phases |
| Synthetic Testing | Live test cycle data (separate pipeline) | Real rules coverage data from rules_artifact.json |
| Conversation | Stub | Rules browser + SME annotation panel |
| All other tabs | Matched | Matched |
