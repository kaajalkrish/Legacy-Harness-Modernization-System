"""
Dashboard backend — FastAPI server on port 8787.
Reads harness output artifacts and serves a unified /api/state JSON.
Run: uvicorn dashboard.server:app --port 8787 --reload  (from repo root)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="COBOL RE Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _size_kb(path: Path) -> float:
    return round(path.stat().st_size / 1024, 1) if path.exists() else 0.0


def _iso(ts: str | None) -> str | None:
    return ts


def _duration_sec(t1: str | None, t2: str | None) -> int | None:
    if not t1 or not t2:
        return None
    try:
        def parse(s: str):
            s = s.replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        return int((parse(t2) - parse(t1)).total_seconds())
    except Exception:
        return None


def _fmt_duration(secs: int | None) -> str:
    if secs is None:
        return "—"
    m, s = divmod(abs(secs), 60)
    return f"{m} min {s} sec"


# ---------------------------------------------------------------------------
# Phase definitions (static metadata about our 10 phases)
# ---------------------------------------------------------------------------

PHASE_META = [
    {"id": "discovery",  "num": 1,  "name": "Discovery",       "type": "Deterministic", "agent": "discovery",  "module": "phases/p01_discovery/scanner.py"},
    {"id": "parser",     "num": 2,  "name": "Parser",           "type": "Deterministic", "agent": "parser",     "module": "phases/p02_parser/orchestrator.py"},
    {"id": "topology",   "num": 3,  "name": "Topology",         "type": "Deterministic", "agent": "topology",   "module": "phases/p03_topology/graph_builder.py"},
    {"id": "context",    "num": 4,  "name": "Context",          "type": "Deterministic", "agent": "context",    "module": "phases/p04_context/context_builder.py"},
    {"id": "data",       "num": 5,  "name": "Data",             "type": "Deterministic", "agent": "data",       "module": "phases/p05_data/data_builder.py"},
    {"id": "logic",      "num": 6,  "name": "Logic",            "type": "LLM + Python",  "agent": "logic",      "module": "phases/p06_logic/logic_builder.py"},
    {"id": "rules",      "num": 7,  "name": "Rules",            "type": "LLM + Python",  "agent": "rules",      "module": "phases/p07_rules/rules_builder.py"},
    {"id": "diagram",    "num": 8,  "name": "Diagram",          "type": "Deterministic", "agent": "diagram",    "module": "phases/p08_diagram/diagram_builder.py"},
    {"id": "brd",        "num": 9,  "name": "Synthesis (BRD)",  "type": "LLM + Python",  "agent": "brd",        "module": "phases/p09_brd/brd_builder.py"},
    {"id": "judge",      "num": 10, "name": "BRD Judge",        "type": "LLM + Python",  "agent": "judge",      "module": "phases/p10_judge/brd_judge.py"},
]

PHASE_ARTIFACTS = {
    "discovery": "discovery/inventory.json",
    "parser":    "analysis/parser_artifact.json",
    "topology":  "topology/graph.json",
    "context":   "context/system_index.json",
    "data":      "data/data_artifact.json",
    "logic":     "logic/logic_artifact.json",
    "rules":     "rules/rules_artifact.json",
    "diagram":   "diagram/diagrams_artifact.json",
    "brd":       "final_report/brd.md",
    "judge":     "final_report/brd_judge.json",
}


# ---------------------------------------------------------------------------
# State assembler
# ---------------------------------------------------------------------------

def assemble_state(out_dir: Path) -> dict:
    inv   = _read(out_dir / "discovery/inventory.json") or {}
    par   = _read(out_dir / "analysis/parser_artifact.json") or {}
    topo  = _read(out_dir / "topology/graph.json") or {}
    data  = _read(out_dir / "data/data_artifact.json") or {}
    logic = _read(out_dir / "logic/logic_artifact.json") or {}
    rules = _read(out_dir / "rules/rules_artifact.json") or {}
    diag  = _read(out_dir / "diagram/diagrams_artifact.json") or {}
    judge = _read(out_dir / "final_report/brd_judge.json") or {}

    # --- meta ---
    inv_meta  = inv.get("meta", {})
    brd_path  = out_dir / "final_report/brd.md"
    brd_name  = brd_path.name if brd_path.exists() else "—"

    meta = {
        "project":      inv_meta.get("project_name", "Mainframe-Source COBOL Reverse Engineering"),
        "domain":       inv_meta.get("domain", ""),
        "entry_point":  inv_meta.get("entry_point", str(out_dir)),
        "project_dir":  inv_meta.get("source_root", ""),
        "output_dir":   str(out_dir),
        "brd_name":     brd_name,
        "status":       "complete" if (out_dir / "final_report/brd_judge.json").exists() else "in-progress",
        "updated":      datetime.now(timezone.utc).isoformat(),
    }

    # --- stats ---
    programs_list  = inv.get("programs", [])
    copybooks_list = inv.get("copybooks", [])
    data_stats     = data.get("stats", {})
    logic_stats    = logic.get("stats", {})
    rules_stats    = rules.get("stats", {})
    diag_meta      = diag.get("meta", {})

    records_count  = (data_stats.get("total_records") or
                      data_stats.get("records") or
                      len(data.get("records", [])) or
                      sum(len(v) if isinstance(v, list) else 0
                          for v in data.get("data_layouts", {}).values()))

    rules_count = (rules_stats.get("total") or
                   len(rules.get("business_rules", [])) or
                   sum(v for v in rules_stats.get("by_category", {}).values() if isinstance(v, int)))

    # Count produced artifact files
    artifact_count = sum(1 for _ in out_dir.rglob("*") if _.is_file() and _.suffix in {".json", ".md", ".mmd", ".txt"})

    stats = {
        "programs":   len(programs_list),
        "copybooks":  len(copybooks_list),
        "records":    records_count,
        "rules":      rules_count,
        "diagrams":   diag_meta.get("total_diagrams", len(diag.get("diagrams", []))),
        "artifacts":  artifact_count,
    }

    # --- phases ---
    # Collect generated_at timestamps for timeline
    ts_map: dict[str, str | None] = {}
    for phase in PHASE_META:
        art_path = out_dir / PHASE_ARTIFACTS[phase["id"]]
        art_data = _read(art_path) if art_path.suffix == ".json" else None
        ts = None
        if isinstance(art_data, dict):
            ts = (art_data.get("meta", {}) or {}).get("generated_at")
        ts_map[phase["id"]] = ts

    phases = []
    prev_ts = None
    for phase in PHASE_META:
        art_rel  = PHASE_ARTIFACTS[phase["id"]]
        art_path = out_dir / art_rel
        exists   = art_path.exists()
        art_data = _read(art_path) if (exists and art_path.suffix == ".json") else None
        cur_ts   = ts_map.get(phase["id"])
        dur_secs = _duration_sec(prev_ts, cur_ts) if prev_ts else None

        phases.append({
            **phase,
            "status":       "done" if exists else "pending",
            "artifact":     art_rel,
            "artifact_kb":  _size_kb(art_path),
            "generated_at": cur_ts,
            "duration_sec": dur_secs,
            "duration_fmt": _fmt_duration(dur_secs),
        })
        if cur_ts:
            prev_ts = cur_ts

    done_count = sum(1 for p in phases if p["status"] == "done")
    overall_pct = round(done_count / len(phases) * 100)

    # --- timeline ---
    timeline = [
        {
            "phase_id":     p["id"],
            "phase_name":   p["name"],
            "phase_num":    p["num"],
            "status":       p["status"],
            "generated_at": p["generated_at"],
            "duration_sec": p["duration_sec"],
            "duration_fmt": p["duration_fmt"],
            "artifact":     p["artifact"],
            "artifact_kb":  p["artifact_kb"],
        }
        for p in phases if p["status"] == "done"
    ]

    # --- judge verdict ---
    verdict = {
        "verdict":        judge.get("verdict", "—"),
        "rating":         judge.get("rating", "—"),
        "weighted_score": judge.get("weighted_score"),
        "dimensions":     judge.get("dimensions", {}),
        "feedback":       judge.get("feedback", []),
        "groundedness_failures": judge.get("groundedness_failures", []),
    }

    # --- topology for workflow tab ---
    topology = {
        "nodes": topo.get("nodes", []),
        "edges": topo.get("edges", []),
    }

    return {
        "meta":        meta,
        "stats":       stats,
        "overall_pct": overall_pct,
        "phases":      phases,
        "timeline":    timeline,
        "verdict":     verdict,
        "topology":    topology,
        "rules_by_category": rules_stats.get("by_category", {}),
        "rules_by_confidence": rules_stats.get("by_confidence", {}),
    }


# ---------------------------------------------------------------------------
# Artifacts listing
# ---------------------------------------------------------------------------

def list_artifacts(out_dir: Path) -> list[dict]:
    phase_map = {PHASE_ARTIFACTS[p["id"]]: p["name"] for p in PHASE_META}
    result = []
    for f in sorted(out_dir.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix not in {".json", ".md", ".mmd", ".txt"}:
            continue
        rel = f.relative_to(out_dir).as_posix()
        phase_name = next((v for k, v in phase_map.items() if rel == k), _guess_phase(rel))
        result.append({
            "name":       f.name,
            "path":       rel,
            "phase":      phase_name,
            "size_kb":    _size_kb(f),
            "ext":        f.suffix,
        })
    return result


def _guess_phase(rel: str) -> str:
    if rel.startswith("discovery"): return "Discovery"
    if rel.startswith("analysis"):  return "Parser"
    if rel.startswith("topology"):  return "Topology"
    if rel.startswith("context"):   return "Context"
    if rel.startswith("data"):      return "Data"
    if rel.startswith("logic"):     return "Logic"
    if rel.startswith("rules"):     return "Rules"
    if rel.startswith("diagram"):   return "Diagram"
    if rel.startswith("final_report"): return "BRD / Judge"
    return "—"


# ---------------------------------------------------------------------------
# Call trace assembler
# ---------------------------------------------------------------------------

def build_call_trace(out_dir: Path, program_id: str | None) -> dict:
    raw_dir = out_dir / "analysis" / "raw_structure"
    if not raw_dir.exists():
        return {"programs": [], "entries": []}

    files = sorted(raw_dir.glob("*.json"))
    if program_id:
        files = [f for f in files if f.stem.upper() == program_id.upper()]

    all_entries = []
    programs_found = []

    for f in files:
        prog = _read(f)
        if not prog:
            continue
        prog_id = f.stem
        programs_found.append(prog_id)
        cfg = prog.get("control_flow_graph", {})
        edges = cfg.get("edges", [])

        for edge in edges:
            kind_raw = edge.get("type", "")
            kind, category = _classify_edge(kind_raw)
            all_entries.append({
                "program":      prog_id,
                "source_line":  edge.get("source_line", 0),
                "from_para":    edge.get("from", ""),
                "to_target":    edge.get("to", ""),
                "kind":         kind,
                "category":     category,
                "operation":    kind_raw,
                "returns":      edge.get("type", "").startswith("PERFORM") or edge.get("type") == "CALL",
                "resolved":     edge.get("resolved", True),
                "unstructured": edge.get("unstructured", False),
            })

    all_entries.sort(key=lambda x: (x["program"], x["source_line"]))
    for i, e in enumerate(all_entries, 1):
        e["step"] = i

    counts = {
        "total":        len(all_entries),
        "control_flow": sum(1 for e in all_entries if e["category"] == "control_flow"),
        "program_call": sum(1 for e in all_entries if e["category"] == "program_call"),
        "database":     sum(1 for e in all_entries if e["category"] == "database"),
        "returns_here": sum(1 for e in all_entries if e["returns"]),
        "no_return":    sum(1 for e in all_entries if not e["returns"]),
    }

    return {"programs": programs_found, "counts": counts, "entries": all_entries}


def _classify_edge(kind: str) -> tuple[str, str]:
    k = kind.upper()
    if "CALL" in k and "CICS" not in k:
        return "Program call", "program_call"
    if "SQL" in k or "EXEC" in k:
        return "Database", "database"
    if "PERFORM" in k:
        return "Control flow", "control_flow"
    if "GO" in k or "GOTO" in k:
        return "Control flow (no return)", "control_flow"
    if "CICS" in k:
        return "CICS call", "program_call"
    return kind, "control_flow"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/state")
def get_state(outputDir: str = Query(..., description="Path to harness output folder")):
    out = Path(outputDir)
    if not out.exists():
        raise HTTPException(404, f"Output directory not found: {outputDir}")
    return JSONResponse(assemble_state(out))


@app.get("/api/artifacts")
def get_artifacts(outputDir: str = Query(...)):
    out = Path(outputDir)
    if not out.exists():
        raise HTTPException(404, f"Output directory not found: {outputDir}")
    return JSONResponse(list_artifacts(out))


@app.get("/api/call-trace")
def get_call_trace(outputDir: str = Query(...), program: str = Query(None)):
    out = Path(outputDir)
    if not out.exists():
        raise HTTPException(404, f"Output directory not found: {outputDir}")
    return JSONResponse(build_call_trace(out, program))


@app.get("/api/topology")
def get_topology(outputDir: str = Query(...)):
    out = Path(outputDir)
    topo = _read(out / "topology/graph.json") or {}
    return JSONResponse({"nodes": topo.get("nodes", []), "edges": topo.get("edges", [])})


# Mount built frontend (production mode)
_dist = Path(__file__).parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

    from fastapi.responses import FileResponse

    @app.get("/")
    def serve_index():
        return FileResponse(str(_dist / "index.html"))

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file = _dist / full_path
        if file.exists() and file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_dist / "index.html"))
