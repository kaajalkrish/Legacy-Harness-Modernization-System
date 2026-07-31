#!/usr/bin/env python3
"""
data_builder.py  —  Phase 5: Data phase (deterministic, no LLM).

Python port of the "3_data" reverse-engineering agent. It turns the cryptic
COBOL DATA DIVISION into a clean, flat data dictionary plus an ERD-ready data
model. It is 100% rule-based:

  * COPY stubs are expanded into real copybook fields
  * PIC clauses are decoded into type / size / decimals
  * REDEFINES, OCCURS tables and 88-level conditions are surfaced
  * a cross-program usage map is built from the inventory's copybook_map

Inputs
  --inventory   outputs/discovery/inventory.json   (Phase 1: copybook registry + map + repo_root)
  --ast-dir     outputs/analysis                    (Phase 2: raw_structure/<PROGRAM>.json)
  --output-dir  outputs/data                        (where to write)

Outputs
  outputs/data/data_layouts/<COPYBOOK>.json     one file per copybook (expanded)
  outputs/data/data_layouts/<PROGRAM>_WS.json   one file per program (inline + expanded)
  outputs/data/data_artifact.json               unified dictionary + data model

Usage
    python -m data.data_builder --inventory <inv.json> --ast-dir <outputs/analysis> \
        --output-dir <outputs/data>
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Reuse the exact COBOL fixed-column + level-entry parsing from the Phase 2 engine
# so copybooks are read with the same rules programs are.
from analysis.engine import (
    read_source_lines,
    content_lines,
    build_logical_statements,
    build_hierarchy,
    LEVEL_ENTRY_RE,
    DATA_COPY_RE,
    PIC_RE,
    OCCURS_RE,
    REDEFINES_RE,
    VALUE_RE,
)

AGENT_VERSION = "3_data_python@1.0"

# USAGE clause (storage format). Not captured by the Phase 2 engine, so we read it
# ourselves when parsing copybooks.
USAGE_RE = re.compile(
    r"\bUSAGE\s+(?:IS\s+)?(COMP-[0-9]|COMP|BINARY|PACKED-DECIMAL|DISPLAY)\b"
    r"|\b(COMP-[0-9]|BINARY|PACKED-DECIMAL)\b",
    re.IGNORECASE,
)

# Field-name suffixes we treat as "key-ish" when guessing entity relationships.
KEY_SUFFIXES = ("-ID", "-KEY", "-NO", "-NUM", "-CODE")


# ---------------------------------------------------------------------------
# PIC decoding  —  the "what does PIC 9(7)V99 mean" lookup, all fixed rules
# ---------------------------------------------------------------------------

def _expand(symbols: str) -> str:
    """Expand COBOL count notation: '9(5)' -> '99999', 'X(3)' -> 'XXX'."""
    return re.sub(r"([A-Z0-9])\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), symbols)


def decode_pic(pic: str) -> dict:
    """Decode a PIC string into a plain type/size description."""
    p = pic.upper()
    signed = p.startswith("S")
    core = p[1:] if signed else p

    if "V" in core:
        int_part, dec_part = core.split("V", 1)
    else:
        int_part, dec_part = core, ""

    exp_int = _expand(int_part)
    exp_dec = _expand(dec_part)
    exp_all = _expand(core)

    if "X" in exp_all:
        return {"type": "text", "length": len(exp_all.replace("V", ""))}
    if "A" in exp_all and "9" not in exp_all:
        return {"type": "alphabetic", "length": exp_all.count("A")}
    if "9" in exp_all:
        return {
            "type": "number",
            "digits": exp_int.count("9"),
            "decimals": exp_dec.count("9"),
            "signed": signed,
        }
    return {"type": "other", "raw": pic}


# ---------------------------------------------------------------------------
# Copybook parsing  —  read a .cpy file into a level-number hierarchy
# ---------------------------------------------------------------------------

def parse_layout_from_lines(raw_lines: list[str]) -> list[dict]:
    """Parse raw COBOL data-definition lines into a nested field hierarchy."""
    lines = content_lines(raw_lines)
    statements = build_logical_statements(lines)

    flat: list[dict] = []
    for start_line, _end_line, text in statements:
        copy_m = DATA_COPY_RE.match(text)
        if copy_m:
            flat.append({"type": "copy_stub", "copybook": copy_m.group(1).upper(), "line": start_line})
            continue

        m = LEVEL_ENTRY_RE.match(text)
        if not m:
            continue

        level = int(m.group(1))
        name = m.group(2).upper()
        rest = m.group(3) or ""

        pic_m = PIC_RE.search(rest)
        occ_m = OCCURS_RE.search(rest)
        red_m = REDEFINES_RE.search(rest)
        val_m = VALUE_RE.search(rest)
        use_m = USAGE_RE.search(rest)

        pic_value = pic_m.group(1) if pic_m else None
        if pic_value and pic_value.endswith("."):
            pic_value = pic_value[:-1]

        usage = None
        if use_m:
            usage = (use_m.group(1) or use_m.group(2) or "").upper() or None

        flat.append({
            "level": level,
            "name": name,
            "line": start_line,
            "pic": pic_value,
            "occurs": int(occ_m.group(1)) if occ_m else None,
            "redefines": red_m.group(1).upper() if red_m else None,
            "value": val_m.group(1).strip() if val_m else None,
            "usage": usage,
        })

    return build_hierarchy(flat)


# ---------------------------------------------------------------------------
# COPY-stub expansion  —  splice a copybook's fields in wherever it is COPYed
# ---------------------------------------------------------------------------

def expand_stubs(nodes: list[dict], layouts: dict[str, list[dict]],
                 issues: list[dict], visited: Optional[set] = None) -> list[dict]:
    """Return a copy of `nodes` with every copy_stub replaced by the copybook's fields."""
    visited = visited or set()
    result: list[dict] = []
    for node in nodes:
        if node.get("type") == "copy_stub":
            cb = node.get("copybook")
            if cb in visited:
                issues.append({"severity": "warning", "type": "circular_copy",
                               "message": f"Circular COPY of {cb} — not expanded again"})
                continue
            layout = layouts.get(cb)
            if layout is None:
                issues.append({"severity": "warning", "type": "unresolved_copy_stub",
                               "message": f"COPY {cb} not found in copybook registry"})
                result.append(node)  # keep the unresolved stub visible
                continue
            expanded = expand_stubs(layout, layouts, issues, visited | {cb})
            result.extend(copy.deepcopy(expanded))
        else:
            n = dict(node)
            if n.get("children"):
                n["children"] = expand_stubs(n["children"], layouts, issues, visited)
            result.append(n)
    return result


# ---------------------------------------------------------------------------
# Flatten a hierarchy into dictionary rows (88-levels fold into their parent)
# ---------------------------------------------------------------------------

def flatten(nodes: list[dict], record: str, source: str, used_by: list[str],
            out_fields: list[dict], stats: dict) -> None:
    for node in nodes:
        if node.get("type") == "copy_stub":
            continue

        children = node.get("children") or []
        conditions: dict[str, Any] = {}
        real_children: list[dict] = []
        for child in children:
            if child.get("level") == 88:
                conditions[child.get("name")] = child.get("value")
            else:
                real_children.append(child)

        field: dict[str, Any] = {
            "name": node.get("name"),
            "level": node.get("level"),
            "record": record,
            "source": source,
            "used_by": used_by,
            "line": node.get("line"),
        }

        pic = node.get("pic")
        if pic:
            field.update(decode_pic(pic))
            field["pic"] = pic
        else:
            field["type"] = "group"
            field["subfields"] = len(real_children)

        if node.get("occurs"):
            field["occurs"] = node["occurs"]
            stats["occurs_tables"] += 1
        if node.get("redefines"):
            field["redefines"] = node["redefines"]
            stats["redefines"] += 1
        if node.get("usage"):
            field["usage"] = node["usage"]
            if node["usage"].startswith("COMP-3") or node["usage"] == "PACKED-DECIMAL":
                field["packed"] = True
        if conditions:
            field["conditions"] = conditions
            stats["level_88_conditions"] += len(conditions)

        out_fields.append(field)
        stats["fields"] += 1

        if real_children:
            flatten(real_children, record, source, used_by, out_fields, stats)


def top_level_records(nodes: list[dict]) -> list[dict]:
    """The record roots of a layout (01/77 groups, or any top-level node)."""
    return [n for n in nodes if n.get("type") != "copy_stub"]


# ---------------------------------------------------------------------------
# Loading Phase 1 / Phase 2 artifacts
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def program_data_sections(ast: dict) -> list[dict]:
    """All inline data entries from a program AST's WS / LINKAGE / FILE sections."""
    dd = ast.get("data_division", {}) or {}
    entries: list[dict] = []
    for sec in ("working_storage_section", "linkage_section", "file_section"):
        entries.extend((dd.get(sec, {}) or {}).get("entries", []) or [])
    return entries


# ---------------------------------------------------------------------------
# Data model (entities + estimated relationships)
# ---------------------------------------------------------------------------

def is_keyish(name: str) -> bool:
    return bool(name) and name != "FILLER" and any(name.endswith(s) for s in KEY_SUFFIXES)


def build_relationships(entities: list[dict]) -> list[dict]:
    """Estimate entity relationships by shared key-ish field names."""
    name_to_entities: dict[str, list[str]] = {}
    for ent in entities:
        for fname in ent["field_names"]:
            if is_keyish(fname):
                name_to_entities.setdefault(fname, [])
                if ent["name"] not in name_to_entities[fname]:
                    name_to_entities[fname].append(ent["name"])

    relationships: list[dict] = []
    for fname, ents in name_to_entities.items():
        if len(ents) < 2:
            continue
        anchor = ents[0]
        for other in ents[1:]:
            relationships.append({
                "from": anchor,
                "to": other,
                "via": f"shared field {fname}",
                "estimated": True,
            })
    return relationships


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build(inventory_path: Path, ast_dir: Path, output_dir: Path) -> dict:
    inventory = load_json(inventory_path)
    repo_root = Path(inventory.get("meta", {}).get("repo_root", "."))
    copybook_registry = inventory.get("copybook_registry", [])
    copybook_map = inventory.get("copybook_map", {})

    layouts_dir = output_dir / "data_layouts"
    layouts_dir.mkdir(parents=True, exist_ok=True)

    issues: list[dict] = []
    stats = {
        "copybooks_parsed": 0,
        "inline_ws_sections": 0,
        "records": 0,
        "fields": 0,
        "redefines": 0,
        "occurs_tables": 0,
        "level_88_conditions": 0,
        "shared_structures": 0,
        "unresolved_copy_stubs": 0,
    }

    # 1. Parse every copybook into a field hierarchy (canonical source of shared data)
    copybook_layouts: dict[str, list[dict]] = {}
    for entry in copybook_registry:
        if entry.get("type") != "copybook":
            continue  # skip db2/DCLGEN for now
        cb_id = entry["id"]
        cb_path = repo_root / (entry.get("relative_path") or entry.get("path"))
        try:
            raw = read_source_lines(cb_path)
        except OSError as exc:
            issues.append({"severity": "error", "type": "copybook_read_error",
                           "message": f"Could not read copybook {cb_id}: {exc}"})
            continue
        copybook_layouts[cb_id] = parse_layout_from_lines(raw)
        stats["copybooks_parsed"] += 1

    fields: list[dict] = []
    records: list[dict] = []
    entities: list[dict] = []
    seen_entity_names: set[str] = set()

    def register_entity(name: str, node: dict, source: str, used_by: list[str]) -> None:
        if name in seen_entity_names:
            return
        seen_entity_names.add(name)
        field_names: list[str] = []

        def collect_names(n: dict) -> None:
            for c in n.get("children", []) or []:
                if c.get("level") == 88 or c.get("type") == "copy_stub":
                    continue
                field_names.append(c.get("name"))
                collect_names(c)

        collect_names(node)
        entities.append({
            "name": name,
            "source": source,
            "used_by": used_by,
            "field_names": [n for n in field_names if n],
        })

    # 2. Copybook fields (canonical, dedup, used_by from copybook_map)
    for cb_id, layout in copybook_layouts.items():
        used_by = copybook_map.get(cb_id, [])
        if len(used_by) >= 2:
            stats["shared_structures"] += 1

        # Expanded copybook (nested COPYs spliced in) for the per-copybook layout file
        expanded = expand_stubs(layout, copybook_layouts, issues)
        (layouts_dir / f"{cb_id}.json").write_text(
            json.dumps({"copybook": cb_id, "used_by": used_by, "records": expanded}, indent=2),
            encoding="utf-8",
        )

        # Dictionary rows come from the copybook's OWN entries (no nested expansion —
        # each field is counted once at its canonical copybook).
        for root in top_level_records(layout):
            rec_name = root.get("name", cb_id)
            records.append({"name": rec_name, "source": cb_id, "kind": "copybook", "used_by": used_by})
            register_entity(rec_name, root, cb_id, used_by)
            flatten([root], rec_name, cb_id, used_by, fields, stats)

    # 3. Program inline fields (defined directly in a program, not via COPY)
    raw_structure = ast_dir / "raw_structure"
    ast_files = sorted(raw_structure.glob("*.json")) if raw_structure.exists() else []
    for ast_path in ast_files:
        try:
            ast = load_json(ast_path)
        except (OSError, json.JSONDecodeError) as exc:
            issues.append({"severity": "warning", "type": "ast_read_error",
                           "message": f"Could not read AST {ast_path.name}: {exc}"})
            continue

        program_id = ast.get("meta", {}).get("program_id", ast_path.stem).upper()
        inline_entries = program_data_sections(ast)
        if not inline_entries:
            continue
        stats["inline_ws_sections"] += 1

        # Per-program layout file: fully expanded (copybook fields spliced in) — a
        # complete data picture for that program.
        expanded_program = expand_stubs(inline_entries, copybook_layouts, issues)
        (layouts_dir / f"{program_id}_WS.json").write_text(
            json.dumps({"program": program_id, "records": expanded_program}, indent=2),
            encoding="utf-8",
        )

        # Dictionary rows: only fields the program itself declares (skip copy_stub subtrees;
        # those already counted at the copybook).
        program_own = [n for n in inline_entries if n.get("type") != "copy_stub"]
        for root in program_own:
            rec_name = root.get("name", program_id)
            records.append({"name": rec_name, "source": program_id, "kind": "program", "used_by": [program_id]})
            register_entity(rec_name, root, program_id, [program_id])
            flatten([root], rec_name, program_id, [program_id], fields, stats)

    stats["records"] = len(records)
    stats["unresolved_copy_stubs"] = sum(1 for i in issues if i["type"] == "unresolved_copy_stub")

    relationships = build_relationships(entities)

    artifact = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_version": AGENT_VERSION,
            "source_inventory": str(inventory_path),
            "source_ast_dir": str(ast_dir),
        },
        "stats": stats,
        "fields": fields,
        "records": records,
        "data_model": {
            "entities": [
                {"name": e["name"], "source": e["source"], "used_by": e["used_by"],
                 "field_count": len(e["field_names"])}
                for e in entities
            ],
            "relationships": relationships,
        },
        "issues": issues,
    }
    return artifact


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(artifact: dict, output_path: Path) -> None:
    s = artifact["stats"]
    print("=== Data Agent Complete ===")
    print(f"Copybooks parsed      : {s['copybooks_parsed']}")
    print(f"Inline WS sections    : {s['inline_ws_sections']}")
    print(f"Total records (01-lvl): {s['records']}")
    print(f"Total fields          : {s['fields']}")
    print(f"REDEFINES resolved    : {s['redefines']}")
    print(f"OCCURS tables found   : {s['occurs_tables']}")
    print(f"88-level conditions   : {s['level_88_conditions']}")
    print(f"Shared structures     : {s['shared_structures']}")
    print(f"Unresolved COPY stubs : {s['unresolved_copy_stubs']}")
    print(f"Output                : {output_path}")
    print("===========================")


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 5 — deterministic COBOL data dictionary builder.")
    ap.add_argument("--inventory", required=True, help="Path to inventory.json from Phase 1")
    ap.add_argument("--ast-dir", required=True, help="Phase 2 output dir (contains raw_structure/)")
    ap.add_argument("--output-dir", default="./outputs/data", help="Directory to write data output")
    args = ap.parse_args()

    inventory_path = Path(args.inventory).resolve()
    if not inventory_path.exists():
        print(f"error: inventory not found: {inventory_path}", file=sys.stderr)
        sys.exit(1)

    ast_dir = Path(args.ast_dir).resolve()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    artifact = build(inventory_path, ast_dir, output_dir)

    output_path = output_dir / "data_artifact.json"
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    print_summary(artifact, output_path)


if __name__ == "__main__":
    main()
