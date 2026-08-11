#!/usr/bin/env python3
"""
orchestrator.py

Python port of the "2_parser_c" reverse-engineering agent. Reads the
inventory_artifact.json produced by the Inventory Agent (new/inventory/scanner.py),
runs engine.CobolAstParser + engine.SectionMapper over every COBOL program in
dependency order, and writes:

    OUTPUT_DIR/raw_structure/{PROGRAM_ID}.json  — one AST+CFG file per program
    OUTPUT_DIR/parser_artifact.json             — combined manifest

Usage:
    python orchestrator.py --inventory <path/to/inventory.json> \
        [--repo-root <path>] [--output-dir ./output/parser] \
        [--program-filter A,B,C]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

#from engine import CobolAstParser, SectionMapper, read_source_lines
from phases.p02_parser.engine import CobolAstParser, SectionMapper, read_source_lines

AGENT_VERSION = "2_parser@1.0"

RELEVANT_CALL_EDGE_TYPES = {"STATIC_CALL", "CICS_LINK", "CICS_XCTL"}
PERFORM_EDGE_PREFIX = "PERFORM"
GOTO_EDGE_TYPES = {"GOTO", "GOTO_DEPENDING"}


# ---------------------------------------------------------------------------
# Dependency ordering
# ---------------------------------------------------------------------------

def topological_order(program_ids: list[str], edges: list[dict]) -> tuple[list[str], list[str]]:
    id_set = set(program_ids)
    depends_on: dict[str, set[str]] = {pid: set() for pid in program_ids}
    dependents: dict[str, set[str]] = {pid: set() for pid in program_ids}

    for e in edges:
        if e.get("type") not in RELEVANT_CALL_EDGE_TYPES or not e.get("resolved"):
            continue
        src, dst = e.get("from"), e.get("to")
        if src in id_set and dst in id_set and src != dst:
            depends_on[src].add(dst)
            dependents[dst].add(src)

    in_degree = {pid: len(depends_on[pid]) for pid in program_ids}
    queue = [pid for pid in program_ids if in_degree[pid] == 0]
    ordered: list[str] = []
    seen: set[str] = set()

    while queue:
        node = queue.pop(0)
        if node in seen:
            continue
        seen.add(node)
        ordered.append(node)
        for dep in sorted(dependents[node]):
            if dep in seen:
                continue
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    remainder = [pid for pid in program_ids if pid not in seen]
    return ordered, remainder


# ---------------------------------------------------------------------------
# Per-program processing
# ---------------------------------------------------------------------------

def process_program(entry: dict, repo_root: Path) -> dict:
    program_id = entry["id"]
    rel_path = entry.get("relative_path") or entry["path"]
    source_path = repo_root / rel_path

    parser = CobolAstParser(program_id, str(source_path))
    try:
        ast = parser.parse(source_path)
    except Exception as exc:  # keep the run alive — one bad file must not abort the batch
        ast = parser._empty_ast(0)
        ast["parse_issues"].append({
            "severity": "error", "type": "parse_failure",
            "message": f"Unhandled exception during AST parse: {exc}",
        })

    try:
        raw_lines = read_source_lines(source_path)
    except OSError:
        raw_lines = []

    mapper = SectionMapper()
    try:
        cfg = mapper.map(ast, raw_lines)
    except Exception as exc:
        cfg = {"control_flow_graph": {
            "entry_points": [], "terminal_nodes": [], "nodes": [], "edges": [],
            "dead_code_candidates": [], "unstructured_constructs": [],
            "cfg_issues": [{"severity": "error", "type": "cfg_failure", "message": str(exc)}],
        }}
    ast.update(cfg)
    return ast


def parse_status_of(ast: dict) -> str:
    if any(i.get("severity") == "error" for i in ast.get("parse_issues", [])):
        return "error"
    if ast.get("control_flow_graph", {}).get("cfg_issues"):
        if any(i.get("severity") == "error" for i in ast["control_flow_graph"]["cfg_issues"]):
            return "error"
    return "success"


def summarize_program(entry: dict, ast: dict, ast_file: str) -> dict:
    cfg = ast.get("control_flow_graph", {})
    unstructured = cfg.get("unstructured_constructs", [])
    return {
        "program_id": entry["id"],
        "source_file": ast["meta"]["source_file"],
        "ast_file": ast_file,
        "total_lines": ast["meta"]["total_lines"],
        "paragraph_count": len(ast["procedure_division"].get("paragraphs", [])),
        "section_count": len(ast["procedure_division"].get("sections", [])),
        "has_unstructured_flow": bool(unstructured),
        "has_alter": any(u.get("type") == "ALTER" for u in unstructured),
        "dead_code_candidates": len(cfg.get("dead_code_candidates", [])),
        "parse_status": parse_status_of(ast),
    }


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------

def build_manifest(source_artifact: str, program_summaries: list[dict], run_issues: list[dict]) -> dict:
    programs_failed = sum(1 for p in program_summaries if p["parse_status"] == "error")

    total_perform_edges = 0
    total_goto_edges = 0
    total_alter_statements = 0
    total_inline_performs = 0
    total_dead_code = 0
    programs_with_unstructured = 0

    for p in program_summaries:
        if p["has_unstructured_flow"]:
            programs_with_unstructured += 1
        total_dead_code += p["dead_code_candidates"]

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "agent_version": AGENT_VERSION,
            "source_artifact": source_artifact,
            "programs_parsed": len(program_summaries),
            "programs_failed": programs_failed,
        },
        "stats": {
            "total_paragraphs": sum(p["paragraph_count"] for p in program_summaries),
            "total_sections": sum(p["section_count"] for p in program_summaries),
            "total_perform_edges": total_perform_edges,
            "total_goto_edges": total_goto_edges,
            "total_alter_statements": total_alter_statements,
            "total_inline_performs": total_inline_performs,
            "total_dead_code_candidates": total_dead_code,
            "programs_with_unstructured_flow": programs_with_unstructured,
        },
        "programs": program_summaries,
        "issues": run_issues,
    }


def fold_edge_stats(manifest: dict, ast: dict) -> None:
    edges = ast.get("control_flow_graph", {}).get("edges", [])
    stats = manifest["stats"]
    for e in edges:
        etype = e.get("type", "")
        if etype.startswith(PERFORM_EDGE_PREFIX):
            stats["total_perform_edges"] += 1
            if etype == "PERFORM_INLINE":
                stats["total_inline_performs"] += 1
        elif etype in GOTO_EDGE_TYPES:
            stats["total_goto_edges"] += 1
        elif etype == "ALTER":
            stats["total_alter_statements"] += 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(manifest: dict, output_path: Path) -> None:
    meta, stats = manifest["meta"], manifest["stats"]
    print("=== Parser Agent Complete ===")
    print(f"Programs parsed    : {meta['programs_parsed']}")
    print(f"Paragraphs found   : {stats['total_paragraphs']}")
    print(f"PERFORM edges      : {stats['total_perform_edges']}")
    print(f"GO TO edges        : {stats['total_goto_edges']}  (flagged for review)")
    print(f"Parse errors       : {meta['programs_failed']}")
    print(f"Output             : {output_path}")
    print("=============================")


def load_inventory(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"error: could not read INVENTORY_ARTIFACT at {path}: {exc}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"error: INVENTORY_ARTIFACT at {path} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Python port of the 2_parser_c COBOL parser agent.")
    ap.add_argument("--inventory", required=True, help="Path to inventory_artifact.json from Agent 1")
    ap.add_argument("--repo-root", default=None, help="Absolute path to the COBOL repo root (default: inventory meta.repo_root)")
    ap.add_argument("--output-dir", default="./output/parser", help="Directory to write parser output")
    ap.add_argument("--program-filter", default=None, help="Comma-separated PROGRAM-IDs to limit scope")
    args = ap.parse_args()

    inventory_path = Path(args.inventory).resolve()
    inventory = load_inventory(inventory_path)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(inventory["meta"]["repo_root"])
    if not repo_root.is_dir():
        print(f"error: REPO_ROOT does not exist or is not a directory: {repo_root}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    raw_structure_dir = output_dir / "raw_structure"
    raw_structure_dir.mkdir(parents=True, exist_ok=True)

    run_issues: list[dict] = []

    programs = [e for e in inventory.get("file_registry", []) if e.get("type") == "program"]
    if args.program_filter:
        wanted = {p.strip().upper() for p in args.program_filter.split(",") if p.strip()}
        programs = [p for p in programs if p["id"].upper() in wanted]

    if not programs:
        run_issues.append({
            "severity": "error", "type": "no_programs_found",
            "message": "No COBOL programs found in inventory file_registry. Parse run aborted.",
        })
        manifest = build_manifest(str(inventory_path), [], run_issues)
        output_path = output_dir / "parser_artifact.json"
        output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print_summary(manifest, output_path)
        return

    program_ids = [p["id"] for p in programs]
    edges = inventory.get("call_graph", {}).get("edges", [])
    ordered_ids, cyclic_ids = topological_order(program_ids, edges)
    if cyclic_ids:
        run_issues.append({
            "severity": "warning", "type": "circular_call_graph",
            "message": "Circular CALL/LINK dependency detected; affected programs parsed in registry order.",
            "programs": cyclic_ids,
        })
    order = ordered_ids + cyclic_ids
    programs_by_id = {p["id"]: p for p in programs}

    manifest = build_manifest(str(inventory_path), [], run_issues)
    program_summaries: list[dict] = []

    for program_id in order:
        entry = programs_by_id[program_id]
        ast = process_program(entry, repo_root)

        ast_file = f"raw_structure/{program_id}.json"
        (raw_structure_dir / f"{program_id}.json").write_text(json.dumps(ast, indent=2), encoding="utf-8")

        fold_edge_stats(manifest, ast)
        program_summaries.append(summarize_program(entry, ast, ast_file))

    manifest["programs"] = program_summaries
    manifest["meta"]["programs_parsed"] = len(program_summaries)
    manifest["meta"]["programs_failed"] = sum(1 for p in program_summaries if p["parse_status"] == "error")
    manifest["stats"]["total_paragraphs"] = sum(p["paragraph_count"] for p in program_summaries)
    manifest["stats"]["total_sections"] = sum(p["section_count"] for p in program_summaries)
    manifest["stats"]["total_dead_code_candidates"] = sum(p["dead_code_candidates"] for p in program_summaries)
    manifest["stats"]["programs_with_unstructured_flow"] = sum(1 for p in program_summaries if p["has_unstructured_flow"])

    output_path = output_dir / "parser_artifact.json"
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print_summary(manifest, output_path)


if __name__ == "__main__":
    main()
