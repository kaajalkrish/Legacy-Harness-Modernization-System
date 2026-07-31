#!/usr/bin/env python3
"""
engine.py

Python port of the "cobol-ast-parser" and "section-mapper" skills from the
2_parser_c reverse-engineering agent. Given a single COBOL source file, it
extracts the division/section/paragraph structural skeleton (CobolAstParser)
and then enriches it with a paragraph-level control flow graph
(SectionMapper). Pure stdlib, no COBOL grammar library.

Consumed by orchestrator.py — never invoked standalone.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# COBOL fixed-format column handling
# ---------------------------------------------------------------------------

def read_source_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


# def content_lines(lines: list[str]) -> list[tuple[int, str]]:
#     """(line_no, content) pairs for non-comment lines, content = columns 8-72."""
#     out = []
#     for i, raw in enumerate(lines, start=1):
#         if len(raw) >= 7 and raw[6] in ("*", "/"):
#             continue
#         out.append((i, raw[7:72] if len(raw) > 7 else ""))
#     return out


def content_lines(lines: list[str]) -> list[tuple[int, str]]:
    """(line_no, content) pairs for non-comment lines, content = columns 8-72."""
    out = []
    for i, raw in enumerate(lines, start=1):
        if len(raw) >= 7:
            if raw[6] in ("*", "/"):
                continue
            # Treat debugging lines ('D') as active code per specifications
            if raw[6].upper() == "D":
                out.append((i, raw[7:72] if len(raw) > 7 else ""))
                continue
        out.append((i, raw[7:72] if len(raw) > 7 else ""))
    return out


def starts_area_a(text: str) -> bool:
    return bool(text) and not text[0].isspace()


def build_logical_statements(lines: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    """Join continuation lines up to a terminating period. Returns
    (start_line, end_line, joined_text) triples, skipping blank lines."""
    statements: list[tuple[int, int, str]] = []
    buf: list[str] = []
    start_line: Optional[int] = None
    for line_no, text in lines:
        stripped = text.strip()
        if not stripped:
            continue
        if start_line is None:
            start_line = line_no
        buf.append(stripped)
        joined = " ".join(buf)
        if stripped.endswith("."):
            statements.append((start_line, line_no, joined))
            buf = []
            start_line = None
    if buf and start_line is not None:
        statements.append((start_line, lines[-1][0] if lines else start_line, " ".join(buf)))
    return statements


# ---------------------------------------------------------------------------
# Reserved words — used to reject false-positive paragraph names
# ---------------------------------------------------------------------------

RESERVED_WORDS = {
    "IDENTIFICATION", "ENVIRONMENT", "DATA", "PROCEDURE", "DIVISION",
    "FILE", "WORKING-STORAGE", "LOCAL-STORAGE", "LINKAGE", "COMMUNICATION",
    "REPORT", "SECTION", "FD", "SD", "MOVE", "IF", "ELSE", "END-IF",
    "EVALUATE", "WHEN", "END-EVALUATE", "CALL", "GO", "STOP", "RUN",
    "GOBACK", "EXIT", "PROGRAM", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY",
    "DIVIDE", "READ", "WRITE", "OPEN", "CLOSE", "DISPLAY", "ACCEPT",
    "STRING", "UNSTRING", "INITIALIZE", "SET", "SEARCH", "SORT", "MERGE",
    "RELEASE", "RETURN", "DELETE", "REWRITE", "START", "CANCEL",
    "CONTINUE", "NEXT", "SENTENCE", "END-PERFORM", "END-READ",
    "END-WRITE", "END-CALL", "END-STRING", "END-UNSTRING", "PERFORM",
    "THRU", "UNTIL", "VARYING", "TIMES", "DEPENDING", "ON", "TO", "FROM",
    "INTO", "USING", "BY", "REFERENCE", "CONTENT", "VALUE", "GIVING",
    "ALTER", "PROCEED",
}

# ---------------------------------------------------------------------------
# Regex patterns (Python re equivalents of the skill's grep patterns)
# ---------------------------------------------------------------------------

DIVISION_RE = re.compile(r"\b(IDENTIFICATION|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b", re.IGNORECASE)
DATA_SECTION_RE = re.compile(
    r"\b(FILE|WORKING-STORAGE|LOCAL-STORAGE|LINKAGE|COMMUNICATION|REPORT)\s+SECTION\b", re.IGNORECASE
)
PROGRAM_ID_RE = re.compile(r"PROGRAM-ID\.\s*([A-Z0-9\-]+)", re.IGNORECASE)
AUTHOR_RE = re.compile(r"AUTHOR\.\s*(.+?)\.?\s*$", re.IGNORECASE)
DATE_WRITTEN_RE = re.compile(r"DATE-WRITTEN\.\s*(.+?)\.?\s*$", re.IGNORECASE)
DATE_COMPILED_RE = re.compile(r"DATE-COMPILED\.\s*(.+?)\.?\s*$", re.IGNORECASE)

FD_SD_RE = re.compile(r"^\s*(FD|SD)\s+([A-Z0-9\-]+)", re.IGNORECASE)
RECORDING_MODE_RE = re.compile(r"RECORDING\s+MODE\s+IS\s+([A-Z])", re.IGNORECASE)
RECORD_CONTAINS_RE = re.compile(r"RECORD\s+(?:CONTAINS|IS)\s+([^.]+?)(?:\s+CHARACTERS)?\.?\s*$", re.IGNORECASE)
BLOCK_CONTAINS_RE = re.compile(r"BLOCK\s+CONTAINS\s+(\S+)", re.IGNORECASE)

LEVEL_ENTRY_RE = re.compile(r"^(\d{1,2})\s+(FILLER|[A-Z0-9\-]+)\b(.*)$", re.IGNORECASE)
DATA_COPY_RE = re.compile(r"^\s*COPY\s+([A-Z0-9\-]+)", re.IGNORECASE)
PIC_RE = re.compile(r"PIC(?:TURE)?\s+(?:IS\s+)?(\S+)", re.IGNORECASE)
OCCURS_RE = re.compile(r"OCCURS\s+(\d+)", re.IGNORECASE)
REDEFINES_RE = re.compile(r"REDEFINES\s+([A-Z0-9\-]+)", re.IGNORECASE)
VALUE_RE = re.compile(r"VALUES?\s+(?:IS\s+)?(.+?)\.?\s*$", re.IGNORECASE)

PARAGRAPH_RE = re.compile(r"^([A-Z0-9][A-Z0-9\-]*)\.(?:\s|$)")
SECTION_HEADER_RE = re.compile(r"^([A-Z0-9][A-Z0-9\-]*)\s+SECTION\.", re.IGNORECASE)
TERMINAL_RE = re.compile(r"\b(STOP\s+RUN|GOBACK|EXIT\s+PROGRAM)\b", re.IGNORECASE)

PERFORM_INLINE_RE = re.compile(r"PERFORM\s+(UNTIL|VARYING|WITH\s+TEST)", re.IGNORECASE)
PERFORM_THRU_RE = re.compile(r"PERFORM\s+([A-Z0-9\-]+)\s+THRU\s+([A-Z0-9\-]+)", re.IGNORECASE)
PERFORM_UNTIL_RE = re.compile(r"PERFORM\s+([A-Z0-9\-]+)\s+UNTIL\s+(.+)", re.IGNORECASE)
PERFORM_VARYING_RE = re.compile(r"PERFORM\s+([A-Z0-9\-]+)\s+VARYING\s+(.+)", re.IGNORECASE)
PERFORM_TIMES_RE = re.compile(r"PERFORM\s+([A-Z0-9\-]+)\s+([0-9]+|[A-Z0-9\-]+)\s+TIMES", re.IGNORECASE)
PERFORM_SIMPLE_RE = re.compile(r"PERFORM\s+([A-Z0-9\-]+)\b", re.IGNORECASE)
END_PERFORM_RE = re.compile(r"END-PERFORM", re.IGNORECASE)

GOTO_DEPENDING_RE = re.compile(
    r"GO\s+TO\s+((?:[A-Z0-9\-]+\s+)+)DEPENDING\s+ON\s+([A-Z0-9\-]+)", re.IGNORECASE
)
GOTO_SIMPLE_RE = re.compile(r"GO\s+TO\s+([A-Z0-9\-]+)\b", re.IGNORECASE)
ALTER_RE = re.compile(r"ALTER\s+([A-Z0-9\-]+)\s+TO\s+(?:PROCEED\s+TO\s+)?([A-Z0-9\-]+)", re.IGNORECASE)
HAS_CALL_RE = re.compile(r"\bCALL\b", re.IGNORECASE)


def _issue(severity: str, type_: str, message: str, **extra: Any) -> dict:
    d = {"severity": severity, "type": type_, "message": message}
    d.update(extra)
    return d


# ---------------------------------------------------------------------------
# Data division hierarchy builder (level-number stack)
# ---------------------------------------------------------------------------

def build_hierarchy(flat: list[dict]) -> list[dict]:
    roots: list[dict] = []
    stack: list[tuple[int, dict]] = []
    for item in flat:
        if item.get("type") == "copy_stub":
            target = stack[-1][1]["children"] if stack else roots
            target.append(dict(item))
            continue
        node = dict(item)
        node["children"] = []
        level = item["level"]
        if level == 88:
            target = stack[-1][1]["children"] if stack else roots
            target.append(node)
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        target = stack[-1][1]["children"] if stack else roots
        target.append(node)
        stack.append((level, node))
    return roots


# ---------------------------------------------------------------------------
# CobolAstParser — cobol-ast-parser skill
# ---------------------------------------------------------------------------

class CobolAstParser:
    def __init__(self, program_id: str, source_file: str):
        self.program_id = program_id
        self.source_file = source_file
        self.issues: list[dict] = []

    def parse(self, path: Path) -> dict:
        try:
            raw_lines = read_source_lines(path)
        except OSError as exc:
            self.issues.append(_issue("error", "file_not_found", f"Could not read {path}: {exc}"))
            return self._empty_ast(total_lines=0)

        total_lines = len(raw_lines)
        lines = content_lines(raw_lines)

        divisions = self._find_divisions(lines, total_lines)
        ident = self._parse_identification(lines, divisions.get("IDENTIFICATION"))
        data_division = self._parse_data_division(lines, divisions.get("DATA"))
        procedure_division = self._parse_procedure_division(lines, divisions.get("PROCEDURE"))

        if "PROCEDURE" not in divisions:
            self.issues.append(_issue("warning", "division_not_found", "PROCEDURE DIVISION boundary not detected"))
        if "DATA" not in divisions:
            self.issues.append(_issue("warning", "division_not_found", "DATA DIVISION boundary not detected"))

        global_copy_stubs = []
        for sec in ["file_section", "working_storage_section", "linkage_section"]:
            # Safely navigate nested children trees if they exist
            entries = data_division.get(sec, {}).get("entries", [])
            
            # Helper to recursively scan for stubs in the nested data tree
            def find_stubs(nodes):
                for entry in nodes:
                    if entry.get("type") == "copy_stub":
                        global_copy_stubs.append({
                            "copybook": entry["copybook"],
                            "division": "DATA",
                            "section": sec.upper().replace("_SECTION", ""),
                            "line": entry["line"]
                        })
                    if "children" in entry and entry["children"]:
                        find_stubs(entry["children"])
            
            find_stubs(entries)

        # -------------------------------------------------------------------
        # MODIFIED: Return dict updated with missing schema specifications
        # -------------------------------------------------------------------
        return {
            "meta": {
                "program_id": self.program_id,
                "source_file": self.source_file,
                "total_lines": total_lines,
            },
            "parse_issues": self.issues,
            "identification_division": ident,
            "environment_division": {  # To satisfy downstream dependencies tracking layouts
                "start_line": divisions.get("ENVIRONMENT", {}).get("start_line"), 
                "end_line": divisions.get("ENVIRONMENT", {}).get("end_line"), 
                "file_control_entries": [] 
            },
            "data_division": data_division,
            "procedure_division": procedure_division,
            "copy_stubs": global_copy_stubs,  # Populated root-level array schema
        }

        # return {
        #     "meta": {
        #         "program_id": self.program_id,
        #         "source_file": self.source_file,
        #         "total_lines": total_lines,
        #     },
        #     "parse_issues": self.issues,
        #     "identification_division": ident,
        #     "data_division": data_division,
        #     "procedure_division": procedure_division,
        # }

    def _empty_ast(self, total_lines: int) -> dict:
        return {
            "meta": {"program_id": self.program_id, "source_file": self.source_file, "total_lines": total_lines},
            "parse_issues": self.issues,
            "identification_division": {"start_line": None, "end_line": None, "program_id": self.program_id},
            "data_division": {
                "start_line": None, "end_line": None,
                "file_section": {"entries": [], "start_line": None},
                "working_storage_section": {"entries": [], "start_line": None},
                "linkage_section": {"entries": [], "start_line": None},
            },
            "procedure_division": {
                "start_line": None, "end_line": None,
                "sections": [], "paragraphs": [], "terminal_statements": [],
            },
        }

    # -- Phase 1: division boundaries --------------------------------------

    def _find_divisions(self, lines: list[tuple[int, str]], total_lines: int) -> dict[str, dict]:
        found = []
        for line_no, text in lines:
            if not starts_area_a(text):
                continue
            m = DIVISION_RE.search(text)
            if m:
                found.append((m.group(1).upper(), line_no))
        divisions: dict[str, dict] = {}
        for idx, (name, start) in enumerate(found):
            end = found[idx + 1][1] - 1 if idx + 1 < len(found) else total_lines
            divisions[name] = {"start_line": start, "end_line": end}
        return divisions

    # -- Phase 2: identification division ----------------------------------

    def _parse_identification(self, lines: list[tuple[int, str]], bounds: Optional[dict]) -> dict:
        result = {
            "start_line": bounds["start_line"] if bounds else None,
            "end_line": bounds["end_line"] if bounds else None,
            "program_id": self.program_id,
        }
        if not bounds:
            return result
        for line_no, text in lines:
            if line_no < bounds["start_line"] or line_no > bounds["end_line"]:
                continue
            m = AUTHOR_RE.search(text)
            if m and m.group(1).strip():
                result["author"] = m.group(1).strip()
                continue
            m = DATE_WRITTEN_RE.search(text)
            if m and m.group(1).strip():
                result["date_written"] = m.group(1).strip()
                continue
            m = DATE_COMPILED_RE.search(text)
            if m and m.group(1).strip():
                result["date_compiled"] = m.group(1).strip()
        return result

    # -- Phase 3: data division ---------------------------------------------

    def _parse_data_division(self, lines: list[tuple[int, str]], bounds: Optional[dict]) -> dict:
        empty = {
            "start_line": bounds["start_line"] if bounds else None,
            "end_line": bounds["end_line"] if bounds else None,
            "file_section": {"entries": [], "start_line": None},
            "working_storage_section": {"entries": [], "start_line": None},
            "linkage_section": {"entries": [], "start_line": None},
        }
        if not bounds:
            return empty

        section_bounds = self._find_data_sections(lines, bounds)

        empty["file_section"] = self._parse_file_section(lines, section_bounds.get("FILE"))
        empty["working_storage_section"] = self._parse_ws_or_linkage(
            lines, section_bounds.get("WORKING-STORAGE"), "WORKING-STORAGE"
        )
        empty["linkage_section"] = self._parse_ws_or_linkage(
            lines, section_bounds.get("LINKAGE"), "LINKAGE"
        )
        return empty

    def _find_data_sections(self, lines: list[tuple[int, str]], data_bounds: dict) -> dict[str, dict]:
        found = []
        for line_no, text in lines:
            if line_no < data_bounds["start_line"] or line_no > data_bounds["end_line"]:
                continue
            if not starts_area_a(text):
                continue
            m = DATA_SECTION_RE.search(text)
            if m:
                found.append((m.group(1).upper(), line_no))
        sections: dict[str, dict] = {}
        for idx, (name, start) in enumerate(found):
            end = found[idx + 1][1] - 1 if idx + 1 < len(found) else data_bounds["end_line"]
            sections[name] = {"start_line": start, "end_line": end}
        return sections

    def _parse_file_section(self, lines: list[tuple[int, str]], bounds: Optional[dict]) -> dict:
        if not bounds:
            return {"entries": [], "start_line": None}
        matches = []
        for line_no, text in lines:
            if line_no < bounds["start_line"] or line_no > bounds["end_line"]:
                continue
            if not starts_area_a(text):
                continue
            m = FD_SD_RE.match(text.lstrip()) if starts_area_a(text) else None
            m = FD_SD_RE.search(text)
            if m:
                matches.append((line_no, m.group(1).upper(), m.group(2).upper()))

        entries = []
        for idx, (line_no, kind, name) in enumerate(matches):
            end_line = matches[idx + 1][0] - 1 if idx + 1 < len(matches) else bounds["end_line"]
            recording_mode = None
            record_contains = None
            block_contains = None
            for l2, t2 in lines:
                if l2 < line_no or l2 > end_line:
                    continue
                if recording_mode is None:
                    m = RECORDING_MODE_RE.search(t2)
                    if m:
                        recording_mode = m.group(1).upper()
                if record_contains is None:
                    m = RECORD_CONTAINS_RE.search(t2)
                    if m:
                        record_contains = m.group(1).strip()
                if block_contains is None:
                    m = BLOCK_CONTAINS_RE.search(t2)
                    if m:
                        block_contains = m.group(1).strip()
            entries.append({
                "type": kind,
                "file_name": name,
                "line": line_no,
                "end_line": end_line,
                "recording_mode": recording_mode,
                "record_contains": record_contains,
                "block_contains": block_contains,
            })
        return {"entries": entries, "start_line": bounds["start_line"]}

    def _parse_ws_or_linkage(self, lines: list[tuple[int, str]], bounds: Optional[dict], section_name: str) -> dict:
        if not bounds:
            return {"entries": [], "start_line": None}

        section_lines = [(ln, t) for ln, t in lines if bounds["start_line"] < ln <= bounds["end_line"]]
        statements = build_logical_statements(section_lines)

        flat: list[dict] = []
        last_top_level: Optional[str] = None

        for start_line, _end_line, text in statements:
            copy_m = DATA_COPY_RE.match(text)
            if copy_m:
                flat.append({
                    "type": "copy_stub",
                    "copybook": copy_m.group(1).upper(),
                    "library": None,
                    "line": start_line,
                    "section": section_name,
                    "parent_level": last_top_level,
                })
                continue

            m = LEVEL_ENTRY_RE.match(text)
            if not m:
                continue
            level = int(m.group(1))
            name = m.group(2).upper()
            rest = m.group(3) or ""

            pic_m = PIC_RE.search(rest)
            occurs_m = OCCURS_RE.search(rest)
            redefines_m = REDEFINES_RE.search(rest)
            value_m = VALUE_RE.search(rest)

            pic_value = pic_m.group(1) if pic_m else None
            if pic_value and pic_value.endswith("."):
                pic_value = pic_value[:-1]

            entry = {
                "level": level,
                "name": name,
                "line": start_line,
                "section": section_name,
                "pic": pic_value,
                "occurs": int(occurs_m.group(1)) if occurs_m else None,
                "redefines": redefines_m.group(1).upper() if redefines_m else None,
                "value": value_m.group(1).strip() if value_m else None,
            }
            flat.append(entry)
            if level in (1, 77):
                last_top_level = f"{level:02d}"

        return {"entries": build_hierarchy(flat), "start_line": bounds["start_line"]}

    # -- Phase 4: procedure division -----------------------------------------

    def _parse_procedure_division(self, lines: list[tuple[int, str]], bounds: Optional[dict]) -> dict:
        # empty = {
        #     "start_line": bounds["start_line"] if bounds else None,
        #     "end_line": bounds["end_line"] if bounds else None,
        #     "sections": [], "paragraphs": [], "terminal_statements": [],
        # }
        # if not bounds:
        #     return empty

        empty = {
            "start_line": bounds["start_line"] if bounds else None,
            "end_line": bounds["end_line"] if bounds else None,
            "using_parameters": [],  # Add this key
            "sections": [], "paragraphs": [], "terminal_statements": [],
        }
        if not bounds:
            return empty

        # 1. Extract USING parameters from the header line(s)
        using_parameters = []
        header_lines = [t for ln, t in lines if ln == bounds["start_line"] or ln == bounds["start_line"] + 1]
        combined_header = " ".join(header_lines)
        using_match = re.search(r"PROCEDURE\s+DIVISION\s+USING\s+([^.]+)", combined_header, re.IGNORECASE)
        if using_match:
            using_parameters = [p.strip().upper() for p in using_match.group(1).replace(",", " ").split() if p.strip()]
        
        empty["using_parameters"] = using_parameters

        boundaries = []  # (kind, name, start_line)
        for line_no, text in lines:
            if line_no <= bounds["start_line"] or line_no > bounds["end_line"]:
                continue
            if not starts_area_a(text):
                continue
            sec_m = SECTION_HEADER_RE.match(text.strip())
            if sec_m:
                name = sec_m.group(1).upper()
                if name not in RESERVED_WORDS:
                    boundaries.append(("section", name, line_no))
                continue
            para_m = PARAGRAPH_RE.match(text.strip())
            if para_m:
                name = para_m.group(1).upper()
                if name in RESERVED_WORDS:
                    self.issues.append(_issue(
                        "info", "ambiguous_paragraph_name",
                        f"Skipped '{name}' — matches a reserved word", line=line_no,
                    ))
                    continue
                boundaries.append(("paragraph", name, line_no))

        sections = []
        paragraphs = []
        current_section: Optional[str] = None
        first_paragraph_seen = False

        for idx, (kind, name, start_line) in enumerate(boundaries):
            end_line = boundaries[idx + 1][2] - 1 if idx + 1 < len(boundaries) else bounds["end_line"]
            if kind == "section":
                sections.append({"name": name, "start_line": start_line, "end_line": end_line})
                current_section = name
            else:
                para_lines = [(ln, t) for ln, t in lines if start_line <= ln <= end_line]
                para_text = " ".join(t for _ln, t in para_lines)
                entry = {
                    "name": name,
                    "section": current_section,
                    "start_line": start_line,
                    "end_line": end_line,
                    "has_perform": bool(PERFORM_SIMPLE_RE.search(para_text) or PERFORM_INLINE_RE.search(para_text)),
                    "has_goto": bool(GOTO_SIMPLE_RE.search(para_text)),
                    "has_call": bool(HAS_CALL_RE.search(para_text)),
                    "has_stop_run": bool(TERMINAL_RE.search(para_text)),
                    "is_entry_point": not first_paragraph_seen,
                }
                first_paragraph_seen = True
                paragraphs.append(entry)

        terminal_statements = []
        for line_no, text in lines:
            if line_no <= bounds["start_line"] or line_no > bounds["end_line"]:
                continue
            m = TERMINAL_RE.search(text)
            if m:
                terminal_statements.append({
                    "type": re.sub(r"\s+", " ", m.group(1).upper()),
                    "line": line_no,
                })

        return {
            "start_line": bounds["start_line"],
            "end_line": bounds["end_line"],
            "sections": sections,
            "paragraphs": paragraphs,
            "terminal_statements": terminal_statements,
        }


# ---------------------------------------------------------------------------
# SectionMapper — section-mapper skill
# ---------------------------------------------------------------------------

class SectionMapper:
    def __init__(self):
        self.cfg_issues: list[dict] = []

    def map(self, ast: dict, raw_lines: list[str]) -> dict:
        proc = ast.get("procedure_division", {})
        paragraphs = proc.get("paragraphs", [])
        sections = proc.get("sections", [])

        para_by_name = {p["name"]: p for p in paragraphs}
        section_by_name = {s["name"]: s for s in sections}
        para_order = [p["name"] for p in paragraphs]

        lines = content_lines(raw_lines)

        nodes = {
            p["name"]: {
                "id": p["name"], "type": "paragraph", "section": p["section"],
                "start_line": p["start_line"], "end_line": p["end_line"],
                "is_entry_point": False, "is_terminal": False, "is_dead_code": False,
                "unstructured_constructs": [],
            }
            for p in paragraphs
        }

        edges: list[dict] = []
        unstructured_constructs: list[dict] = []
        incoming_targets: set[str] = set()

        for para in paragraphs:
            para_lines = [(ln, t) for ln, t in lines if para["start_line"] <= ln <= para["end_line"]]
            self._scan_paragraph(
                para, para_lines, para_by_name, section_by_name, para_order,
                edges, unstructured_constructs, incoming_targets, nodes,
            )

        entry_points = [para_order[0]] if para_order else []
        for name in entry_points:
            if name in nodes:
                nodes[name]["is_entry_point"] = True

        terminal_para_names = set()
        for stmt in proc.get("terminal_statements", []):
            for p in paragraphs:
                if p["start_line"] <= stmt["line"] <= p["end_line"]:
                    terminal_para_names.add(p["name"])
        for name in terminal_para_names:
            if name in nodes:
                nodes[name]["is_terminal"] = True

        dead_code_candidates = []
        for p in paragraphs:
            name = p["name"]
            if name in entry_points:
                continue
            if name not in incoming_targets:
                nodes[name]["is_dead_code"] = True
                dead_code_candidates.append(name)

        return {
            "control_flow_graph": {
                "entry_points": entry_points,
                "terminal_nodes": sorted(terminal_para_names, key=lambda n: para_order.index(n) if n in para_order else 0),
                "nodes": list(nodes.values()),
                "edges": edges,
                "dead_code_candidates": dead_code_candidates,
                "unstructured_constructs": unstructured_constructs,
                "cfg_issues": self.cfg_issues,
            }
        }

    def _resolve(self, target: str, para_by_name: dict, section_by_name: dict) -> tuple[bool, str]:
        if target in para_by_name:
            return True, "paragraph"
        if target in section_by_name:
            return True, "section"
        return False, "unknown"

    def _add_edge(
        self, edges: list[dict], unstructured: list[dict], nodes: dict, incoming: set[str],
        from_name: str, to_name: Optional[str], edge_type: str, resolved: bool,
        source_line: int, is_unstructured: bool, **extra: Any,
    ) -> None:
        edge = {
            "from": from_name, "type": edge_type, "resolved": resolved,
            "source_line": source_line, "unstructured": is_unstructured, "to": to_name,
        }
        edge.update(extra)
        edges.append(edge)
        if to_name and resolved:
            incoming.add(to_name)
        if from_name in nodes and is_unstructured:
            nodes[from_name]["unstructured_constructs"].append(edge_type)
        if is_unstructured:
            unstructured.append({
                "type": edge_type, "paragraph": from_name, "target": to_name,
                "line": source_line,
                "severity": "critical" if edge_type == "ALTER" else "warning",
            })

    def _scan_paragraph(
        self, para: dict, para_lines: list[tuple[int, str]], para_by_name: dict,
        section_by_name: dict, para_order: list[str], edges: list[dict],
        unstructured: list[dict], incoming: set[str], nodes: dict,
    ) -> None:
        source = para["name"]

        statements = build_logical_statements(para_lines)

        for start_line, end_line, text in statements:
            line_no = start_line
            m = ALTER_RE.search(text)
            if m:
                altered_para, new_target = m.group(1).upper(), m.group(2).upper()
                resolved, _ = self._resolve(new_target, para_by_name, section_by_name)
                self._add_edge(
                    edges, unstructured, nodes, incoming, source, new_target, "ALTER",
                    resolved, line_no, True, altered_paragraph=altered_para,
                )
                continue

            m = GOTO_DEPENDING_RE.search(text)
            if m:
                targets = [t.upper() for t in m.group(1).split()]
                depending_var = m.group(2).upper()
                self._add_edge(
                    edges, unstructured, nodes, incoming, source, None, "GOTO_DEPENDING",
                    False, line_no, True, depending_variable=depending_var, possible_targets=targets,
                )
                continue

            m = GOTO_SIMPLE_RE.search(text)
            if m:
                target = m.group(1).upper()
                resolved, _ = self._resolve(target, para_by_name, section_by_name)
                if not resolved:
                    self.cfg_issues.append(_issue(
                        "warning", "unresolved_target", f"GO TO target '{target}' not found", paragraph=source, line=line_no,
                    ))
                self._add_edge(edges, unstructured, nodes, incoming, source, target, "GOTO", resolved, line_no, True)
                continue

            m = PERFORM_THRU_RE.search(text)
            if m:
                a_para, b_para = m.group(1).upper(), m.group(2).upper()
                resolved_a = a_para in para_by_name
                resolved_b = b_para in para_by_name
                implicit_range = None
                if resolved_a and resolved_b and a_para in para_order and b_para in para_order:
                    i, j = para_order.index(a_para), para_order.index(b_para)
                    if i <= j:
                        implicit_range = para_order[i:j + 1]
                    else:
                        self.cfg_issues.append(_issue(
                            "warning", "ambiguous_thru_range",
                            f"PERFORM {a_para} THRU {b_para} — {b_para} precedes {a_para} in source order",
                            paragraph=source, line=line_no,
                        ))
                else:
                    self.cfg_issues.append(_issue(
                        "warning", "ambiguous_thru_range",
                        f"PERFORM {a_para} THRU {b_para} — range could not be resolved",
                        paragraph=source, line=line_no,
                    ))
                self._add_edge(
                    edges, unstructured, nodes, incoming, source, a_para, "PERFORM_THRU",
                    resolved_a, line_no, True, implicit_thru_range=implicit_range,
                )
                if implicit_range:
                    incoming.update(implicit_range)
                continue

            m = PERFORM_INLINE_RE.search(text)
            if m:
                end_line = para["end_line"]
                for l2, t2 in para_lines:
                    if l2 >= line_no and END_PERFORM_RE.search(t2):
                        end_line = l2
                        break
                else:
                    self.cfg_issues.append(_issue(
                        "error", "missing_end_perform",
                        f"Inline PERFORM at line {line_no} has no matching END-PERFORM in paragraph bounds",
                        paragraph=source, line=line_no,
                    ))
                self._add_edge(
                    edges, unstructured, nodes, incoming, source, source, "PERFORM_INLINE",
                    True, line_no, False, inline=True, condition_text=text.strip(),
                    loop_start_line=line_no, loop_end_line=end_line,
                )
                continue

            m = PERFORM_UNTIL_RE.search(text)
            if m and not PERFORM_INLINE_RE.match(f"PERFORM {m.group(1)}"):
                target, condition = m.group(1).upper(), m.group(2).strip()
                resolved, _ = self._resolve(target, para_by_name, section_by_name)
                self._add_edge(
                    edges, unstructured, nodes, incoming, source, target, "PERFORM_UNTIL",
                    resolved, line_no, False, condition_text=condition,
                )
                continue

            m = PERFORM_VARYING_RE.search(text)
            if m:
                target, clause = m.group(1).upper(), m.group(2).strip()
                resolved, _ = self._resolve(target, para_by_name, section_by_name)
                self._add_edge(
                    edges, unstructured, nodes, incoming, source, target, "PERFORM_VARYING",
                    resolved, line_no, False, varying_clause=clause,
                )
                continue

            m = PERFORM_TIMES_RE.search(text)
            if m:
                target = m.group(1).upper()
                resolved, _ = self._resolve(target, para_by_name, section_by_name)
                self._add_edge(
                    edges, unstructured, nodes, incoming, source, target, "PERFORM_TIMES",
                    resolved, line_no, False, times=m.group(2),
                )
                continue

            m = PERFORM_SIMPLE_RE.search(text)
            if m:
                target = m.group(1).upper()
                resolved, kind = self._resolve(target, para_by_name, section_by_name)
                edge_type = "PERFORM_SECTION" if kind == "section" else "PERFORM_SIMPLE"
                if not resolved:
                    self.cfg_issues.append(_issue(
                        "warning", "unresolved_target", f"PERFORM target '{target}' not found",
                        paragraph=source, line=line_no,
                    ))
                self._add_edge(edges, unstructured, nodes, incoming, source, target, edge_type, resolved, line_no, False)
