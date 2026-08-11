#!/usr/bin/env python3
"""
diagram_builder.py  —  Diagram agent (deterministic, no LLM).

Python port of the "6_diagram" agent. Generates Mermaid diagrams from the
artifacts we already have:

  * component_overview.mmd  — program call/link graph (from topology/graph.json)
  * erd.mmd                 — entity-relationship diagram (from data_artifact data_model)
  * flow_<PROGRAM>.mmd      — per-program call/flow graph (from the Phase 6 logic files)

All structural — no LLM. Mermaid renders on GitHub, in VS Code (Mermaid preview),
at mermaid.live, and inside the BRD.

Inputs
  --graph   outputs/topology/graph.json
  --data    outputs/data/data_artifact.json
  --logic   outputs/logic/logic_artifact.json  (also reads program_logic/*.json)
  --output-dir  outputs/diagram
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def sid(name: str) -> str:
    """Mermaid-safe node id."""
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name))


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Component overview — program call/link graph
# ---------------------------------------------------------------------------

def component_overview(graph: dict) -> str:
    nodes = graph.get("nodes", [])
    lines = ["flowchart LR"]
    progs = [n for n in nodes if str(n.get("type")).upper() == "PROGRAM"]
    for n in progs:
        lines.append(f'  {sid(n["id"])}["{n["id"]}"]')
    seen = set()
    for e in graph.get("edges", []):
        if e.get("type") == "CALLS_PROGRAM":
            a, b = e.get("source"), e.get("target")
            if not a or not b:
                continue
            k = (a, b)
            if k in seen:
                continue
            seen.add(k)
            lines.append(f"  {sid(a)} --> {sid(b)}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# ERD — key data entities and their estimated relationships
# ---------------------------------------------------------------------------

def erd(data: dict, max_entities: int = 16) -> str:
    dm = data.get("data_model", {})
    ents = dm.get("entities", [])
    rels = dm.get("relationships", [])

    in_rel = set()
    for r in rels:
        in_rel.add(r.get("from"))
        in_rel.add(r.get("to"))
    top = sorted(ents, key=lambda e: -e.get("field_count", 0))[:max_entities]
    keep_names = {e["name"] for e in top} | in_rel
    keep = [e for e in ents if e["name"] in keep_names][:max_entities + 8]
    kept_names = {e["name"] for e in keep}

    lines = ["erDiagram"]
    for e in keep:
        lines.append(f'  {sid(e["name"])} {{')
        lines.append(f'    int field_count "{e.get("field_count", 0)}"')
        used = ", ".join(e.get("used_by", [])[:3]) or "-"
        lines.append(f'    string used_by "{used}"')
        lines.append("  }")
    seen = set()
    for r in rels:
        a, b = r.get("from"), r.get("to")
        if a in kept_names and b in kept_names and a != b:
            k = tuple(sorted((sid(a), sid(b))))
            if k in seen:
                continue
            seen.add(k)
            via = (r.get("via", "related") or "related").replace('"', "'")[:28]
            lines.append(f'  {sid(a)} ||--o{{ {sid(b)} : "{via}"')
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Per-program flow — call graph from the logic paragraphs
# ---------------------------------------------------------------------------

def program_flow(pl: dict) -> str:
    paras = pl.get("paragraphs", [])
    lines = ["flowchart TD"]
    own = {p["name"] for p in paras}
    for p in paras:
        lines.append(f'  {sid(p["name"])}["{p["name"]}"]')
    seen = set()
    for p in paras:
        for c in p.get("calls_made", []):
            k = (p["name"], c)
            if k in seen:
                continue
            seen.add(k)
            style = "-->" if c in own else "-.->"  # dashed to external/other programs
            lines.append(f"  {sid(p['name'])} {style} {sid(c)}")
    if len(lines) == 1:
        lines.append(f'  {sid(pl.get("meta", {}).get("program_id", "PROGRAM"))}["(no internal calls)"]')
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build(graph_p: Path, data_p: Path, logic_p: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    diagrams = out / "diagrams"
    diagrams.mkdir(exist_ok=True)

    graph = load(graph_p)
    data = load(data_p)
    logic = load(logic_p)

    index = {"meta": {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
             "diagrams": []}

    (out / "component_overview.mmd").write_text(component_overview(graph), encoding="utf-8")
    index["diagrams"].append({"id": "COMP-OVERVIEW", "file": "component_overview.mmd",
                              "type": "component", "title": "System component overview"})

    (out / "erd.mmd").write_text(erd(data), encoding="utf-8")
    index["diagrams"].append({"id": "ERD-MAIN", "file": "erd.mmd", "type": "erd",
                              "title": "Data model — key entities and relationships"})

    logic_dir = logic_p.parent
    for prog in logic.get("programs", []):
        pid = prog["program_id"]
        lf = logic_dir / prog.get("logic_file", f"program_logic/{pid}_logic.json")
        if not lf.exists():
            continue
        pl = load(lf)
        (diagrams / f"flow_{pid}.mmd").write_text(program_flow(pl), encoding="utf-8")
        index["diagrams"].append({"id": f"FLOW-{pid}", "file": f"diagrams/flow_{pid}.mmd",
                                  "type": "flow", "title": f"{pid} process/call flow", "program_id": pid})

    (out / "diagrams_artifact.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def main() -> None:
    ap = argparse.ArgumentParser(description="Diagram agent — deterministic Mermaid generation.")
    ap.add_argument("--graph", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--logic", required=True)
    ap.add_argument("--output-dir", default="./outputs/diagram")
    args = ap.parse_args()

    idx = build(Path(args.graph), Path(args.data), Path(args.logic), Path(args.output_dir))
    types: dict[str, int] = {}
    for dgm in idx["diagrams"]:
        types[dgm["type"]] = types.get(dgm["type"], 0) + 1
    print("=== Diagram Agent Complete ===")
    print(f"Diagrams generated : {len(idx['diagrams'])}")
    for t, n in sorted(types.items()):
        print(f"   {t:<10}: {n}")
    print(f"Output             : {Path(args.output_dir)}")
    print("==============================")


if __name__ == "__main__":
    main()
