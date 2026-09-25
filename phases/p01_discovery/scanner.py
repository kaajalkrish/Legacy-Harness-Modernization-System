#!/usr/bin/env python3
"""
inventory_agent.py

Scans a COBOL repository and writes inventory_artifact.json.

Usage:
    python inventory_agent.py --repo-root <path> [--output-dir <path>] [--exclude-dirs .git,bin,obj]
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Classification tables
# ---------------------------------------------------------------------------

PROGRAM_EXTENSIONS = {".cbl", ".cob"}
COPYBOOK_EXTENSIONS = {".cpy"}
JCL_EXTENSIONS = {".jcl"}
BMS_EXTENSIONS = {".bms"}
CTL_EXTENSIONS = {".ctl"}
LST_EXTENSIONS = {".lst"}
DB2_EXTENSIONS = {".sql", ".dclgen"}
ASM_EXTENSIONS = {".asm", ".mlc"}

DEFAULT_EXCLUDE_DIRS = {".git", "bin", "obj"}

UTILITY_PROGRAMS = {"SORT", "IDCAMS", "IEBGENER", "IEFBR14", "DFSRRC00"}

DYNAMIC_CALL_STOPWORDS = {"USING", "BY", "REFERENCE", "CONTENT", "VALUE", "LENGTH"}

# ---------------------------------------------------------------------------
# Regex patterns (mirrors the grep patterns documented in the skill files)
# ---------------------------------------------------------------------------

PROGRAM_ID_RE = re.compile(r"PROGRAM-ID\.\s+([A-Z0-9\-]+)", re.IGNORECASE)

# (?<![\w-]) rather than \b: a data name such as REQUEST-MSG-COPY must not read as COPY.
COPY_QUALIFIED_RE = re.compile(
    r"(?<![\w-])COPY\s+['\"]?([A-Z0-9\-]+)\s+(?:IN|OF)\s+[A-Z0-9\-]+", re.IGNORECASE
)
COPY_RE = re.compile(r"(?<![\w-])COPY\s+['\"]?([A-Z0-9\-]+)", re.IGNORECASE)

CALL_LITERAL_RE = re.compile(r"(?<![\w-])CALL\s+['\"]([A-Z0-9\-]+)['\"]", re.IGNORECASE)
STRING_LITERAL_RE = re.compile(r"'[^']*'?|\"[^\"]*\"?")
CALL_VAR_RE = re.compile(r"(?<![\w-])CALL\s+([A-Za-z][A-Za-z0-9\-]{2,})\b")

CICS_LINK_RE = re.compile(
    r"EXEC\s+CICS\s+LINK\s+PROGRAM\s*\(\s*['\"]?([A-Z0-9\-]+)", re.IGNORECASE
)
CICS_XCTL_RE = re.compile(
    r"EXEC\s+CICS\s+XCTL\s+PROGRAM\s*\(\s*['\"]?([A-Z0-9\-]+)", re.IGNORECASE
)
CICS_RETURN_RE = re.compile(
    r"EXEC\s+CICS\s+RETURN\s+TRANSID\s*\(\s*['\"]?([A-Z0-9\-]+)", re.IGNORECASE
)
SQL_INCLUDE_RE = re.compile(r"EXEC\s+SQL\s+INCLUDE\s+([A-Z0-9\-]+)", re.IGNORECASE)

JCL_JOB_RE = re.compile(r"^//([A-Z0-9#@$]{1,8})\s+JOB\s", re.IGNORECASE)
JCL_EXEC_RE = re.compile(
    r"^//([A-Z0-9#@$]{1,8})\s+EXEC\s+PGM=([A-Z0-9\-]+)", re.IGNORECASE
)

# Run-mode signals — read from the code itself, so classification works on any
# codebase regardless of folder layout or program naming convention.
CICS_RE = re.compile(r"\bEXEC\s+CICS\b", re.IGNORECASE)
SQL_RE = re.compile(r"\bEXEC\s+SQL\b", re.IGNORECASE)
IMS_RE = re.compile(r"\bCBLTDLI\b|\bAIBTDLI\b|\bEXEC\s+DLI\b|\bDLITCBL\b", re.IGNORECASE)
IMS_ENTRY_RE = re.compile(r"\bENTRY\s+['\"]DLITCBL['\"]", re.IGNORECASE)
MQ_RE = re.compile(r"\bCALL\s+['\"]MQ[A-Z0-9]+['\"]", re.IGNORECASE)
STOP_RUN_RE = re.compile(r"\bSTOP\s+RUN\b", re.IGNORECASE)
PROC_USING_RE = re.compile(r"\bPROCEDURE\s+DIVISION\s+USING\b", re.IGNORECASE)
FILE_SELECT_RE = re.compile(r"\bSELECT\s+(?:OPTIONAL\s+)?[A-Z0-9\-]+\s+ASSIGN\b", re.IGNORECASE)

# Ways a job stream runs a program: plain EXEC PGM=, IMS region controller PARM
# (DFSRRC00 'BMP|DLI|DBB,<program>,...'), and DB2 TSO batch RUN PROGRAM(<program>).
JOB_TEXT_EXTENSIONS = {".jcl", ".job", ".prc", ".proc", ".ctl"}
JOB_PGM_RE = re.compile(r"\bEXEC\s+PGM=([A-Z0-9#@$\-]+)", re.IGNORECASE)
JOB_IMS_PARM_RE = re.compile(r"PARM=\(?['\"]?(?:BMP|DLI|DBB),([A-Z0-9#@$\-]+)", re.IGNORECASE)
JOB_TSO_RUN_RE = re.compile(r"\bRUN\s+PROGRAM\s*\(\s*([A-Z0-9#@$\-]+)", re.IGNORECASE)

# Folder names are only a last-resort hint, used when the code gives no signal.
FOLDER_HINTS = {"batch": "batch", "online": "online", "cics": "online",
                "common": "common", "shared": "common", "subroutines": "common",
                "utility": "utility", "utilities": "utility", "test": "test"}

SCAN_EXTENSIONS = (
    PROGRAM_EXTENSIONS
    | COPYBOOK_EXTENSIONS
    | JCL_EXTENSIONS
    | BMS_EXTENSIONS
    | CTL_EXTENSIONS
    | LST_EXTENSIONS
    | DB2_EXTENSIONS
    | ASM_EXTENSIONS
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def classify_file(file_path: Path):
    ext = file_path.suffix.lower()

    # 1. Classify COBOL Programs (.cbl, .cob)
    if ext in {".cbl", ".cob", ".ccp"}:
        # Run mode (batch / online / common) is decided later from the code
        # itself — see InventoryBuilder.classify_programs.
        return "program", "unknown"

    # 2. Classify Copybooks (.cpy, .cop)
    elif ext in {".cpy", ".cop"}:
        return "copybook", "copybook"

    # 3. Classify Db2 Includes (.sql, .dclgen)
    elif ext in {".sql", ".dclgen"}:
        return "db2", "db2"

    # 4. Classify JCL Jobs (.jcl, .job)
    elif ext in {".jcl", ".job"}:
        return "jcl", "jcl"

    # 5. Classify BMS Maps (.bms, .map)
    elif ext in {".bms", ".map"}:
        return "bms", "bms"

    # 6. Assembler modules — not parsed, but real CALL targets
    elif ext in ASM_EXTENSIONS:
        return "assembler", "assembler"

    # 6. Fallback for any other extensions
    else:
        return "unknown", "unknown"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def folder_hint(rel_path: str) -> Optional[str]:
    """Run-mode hint from a parent folder name (e.g. programs/batch), or None."""
    for part in reversed(Path(rel_path).parts[:-1]):
        hint = FOLDER_HINTS.get(part.lower())
        if hint:
            return hint
    return None


# A DIVISION header that starts before column 8 can only be free-format source.
FREE_FORMAT_RE = re.compile(
    r"^ {0,6}(?:IDENTIFICATION|ID|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION",
    re.IGNORECASE | re.MULTILINE)


def cobol_scannable_lines(raw_text: str):
    """Yield (line_no, text) pairs honouring COBOL fixed-column rules.

    Columns 1-6 (sequence numbers) and 73-80 (identification) are ignored.
    Column 7 is the indicator: '*' or '/' means the whole line is a comment
    and is skipped. Columns 8-72 are the scannable program text.

    Free-format source (detected by a DIVISION header before column 8) is
    scanned whole-line; a leading '*' or '*>' marks a comment.
    """
    if FREE_FORMAT_RE.search(raw_text):
        for i, raw in enumerate(raw_text.splitlines(), start=1):
            if raw.lstrip().startswith("*"):
                continue
            yield i, raw
        return
    for i, raw in enumerate(raw_text.splitlines(), start=1):
        if len(raw) >= 7 and raw[6] in ("*", "/"):
            continue
        yield i, raw[7:72]


def normalise_target(name: str) -> str:
    return name.strip().upper()


def is_utility_program(name: str) -> bool:
    return name.upper() in UTILITY_PROGRAMS


def variable_declared(raw_text: str, var_name: str) -> bool:
    """Best-effort check that a CALL argument is a WORKING-STORAGE data name.

    This does not isolate the WORKING-STORAGE SECTION boundaries; it looks
    for a level-number declaration of the name anywhere in the file, which
    is a reasonable approximation for the "confirmed" flag on dynamic calls.
    """
    pattern = re.compile(rf"^\s*\d{{2}}\s+{re.escape(var_name)}\b", re.IGNORECASE | re.MULTILINE)
    return bool(pattern.search(raw_text))


# ---------------------------------------------------------------------------
# Inventory builder
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str
    type: str
    message: str
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        d = {"severity": self.severity, "type": self.type}
        d.update(self.extra)
        d["message"] = self.message
        return d


class InventoryBuilder:
    def __init__(self, repo_root: Path, exclude_dirs: set):
        self.repo_root = repo_root
        self.exclude_dirs = exclude_dirs

        self.file_registry = []
        self.copybook_registry = []
        self.jcl_registry = []
        self.other_counts = {"bms_map": 0, "control_card": 0, "listing": 0, "unknown": 0}

        self.program_lookup = {}   # id -> file_registry entry
        self.copybook_lookup = {}  # id -> copybook_registry entry
        self.module_registry = []  # non-COBOL modules (assembler) that programs CALL
        self.module_lookup = {}
        self.program_signals = {}  # id -> run-mode signals read from the code
        self.job_runs = {}         # program id -> job/proc file that runs it

        self.nodes = []
        self.edges = []
        self.issues = []

        self.total_files_scanned = 0

    # -- issue helper --------------------------------------------------

    def add_issue(self, severity, type_, message, **extra):
        self.issues.append(Issue(severity, type_, message, extra).to_dict())

    # -- step 1: walk -----------------------------------------------------

    def is_excluded(self, path: Path) -> bool:
        return any(part in self.exclude_dirs for part in path.parts)

    def walk(self):
        for path in sorted(self.repo_root.rglob("*")):
            if not path.is_file():
                continue
            if self.is_excluded(path.relative_to(self.repo_root)):
                continue
            ext = path.suffix.lower()
            if ext not in SCAN_EXTENSIONS:
                continue
            self.total_files_scanned += 1
            self.process_file(path)

    def process_file(self, path: Path):
        rel_path = path.relative_to(self.repo_root).as_posix()
        file_type, subtype = classify_file(path)

        if file_type == "unknown":
            self.add_issue("info", "unclassified_extension", f"File extension not recognised: {rel_path}",
                            path=rel_path)
            self.other_counts["unknown"] += 1
            return

        if file_type == "program":
            self.process_program(path, rel_path, subtype)
        elif file_type == "copybook":
            self.process_copybook(path, rel_path, "copybook")
        elif file_type == "db2":
            self.process_copybook(path, rel_path, "db2")
        elif file_type == "jcl":
            self.process_jcl(path, rel_path)
        elif file_type == "assembler":
            entry = {"id": path.stem.upper(), "path": rel_path, "type": "assembler"}
            self.module_registry.append(entry)
            self.module_lookup.setdefault(entry["id"], entry)
        elif file_type in ("bms_map", "control_card", "listing"):
            self.other_counts[file_type] += 1

    def process_program(self, path: Path, rel_path: str, subtype: str):
        try:
            raw_text = read_text(path)
        except OSError as e:
            self.add_issue("error", "file_read_error", f"Could not read {rel_path}: {e}", path=rel_path)
            return

        match = None
        for line_no, text in cobol_scannable_lines(raw_text):
            m = PROGRAM_ID_RE.search(text)
            if m:
                match = m.group(1)
                break

        if match:
            program_id = match.strip().rstrip(".").upper()
        else:
            program_id = path.stem.upper()
            self.add_issue("warning", "missing_program_id", "PROGRAM-ID not found — using filename as fallback ID",
                            source_file=rel_path, fallback_id=program_id)

        entry = {
            "id": program_id,
            "program_id": program_id,
            "path": rel_path,
            "relative_path": rel_path,
            "type": "program",
            "subtype": subtype,
            "size_bytes": path.stat().st_size,
        }

        if program_id in self.program_lookup:
            other = self.program_lookup[program_id]
            self.add_issue("error", "duplicate_program_id",
                            f"Duplicate PROGRAM-ID '{program_id}' across two files",
                            path_a=other["path"], path_b=rel_path)
        else:
            self.program_lookup[program_id] = entry
            code = "\n".join(text for _, text in cobol_scannable_lines(raw_text))
            self.program_signals[program_id] = {
                "cics": bool(CICS_RE.search(code)),
                "db2": bool(SQL_RE.search(code)),
                "ims": bool(IMS_RE.search(code)),
                "ims_entry": bool(IMS_ENTRY_RE.search(code)),
                "mq": bool(MQ_RE.search(code)),
                "stop_run": bool(STOP_RUN_RE.search(code)),
                "has_params": bool(PROC_USING_RE.search(code)),
                "has_files": bool(FILE_SELECT_RE.search(code)),
                "calls": {normalise_target(t) for t in CALL_LITERAL_RE.findall(code)},
            }

        self.file_registry.append(entry)

    def process_copybook(self, path: Path, rel_path: str, kind: str):
        copybook_id = path.stem.upper()
        entry = {
            "id": copybook_id,
            "path": rel_path,
            "relative_path": rel_path,
            "type": kind,
            "used_by": [],
        }
        if copybook_id not in self.copybook_lookup:
            self.copybook_lookup[copybook_id] = entry
        self.copybook_registry.append(entry)

    def process_jcl(self, path: Path, rel_path: str):
        try:
            raw_text = read_text(path)
        except OSError as e:
            self.add_issue("error", "file_read_error", f"Could not read {rel_path}: {e}", path=rel_path)
            return

        lines = raw_text.splitlines()

        job_name = None
        for line in lines:
            m = JCL_JOB_RE.match(line)
            if m:
                job_name = m.group(1).upper()
                break

        if not job_name:
            job_name = path.stem.upper()
            self.add_issue("warning", "missing_job_name", "JOB name not found — using filename as fallback ID",
                            source_file=rel_path, fallback_id=job_name)

        steps = []
        for line in lines:
            m = JCL_EXEC_RE.match(line)
            if m:
                step_name, program = m.group(1).upper(), m.group(2).upper()
                steps.append({
                    "step_name": step_name,
                    "program": program,
                    "type": "utility" if is_utility_program(program) else "cobol",
                })

        self.jcl_registry.append({
            "id": job_name,
            "path": rel_path,
            "relative_path": rel_path,
            "job_name": job_name,
            "steps": steps,
        })

    # -- step 1b: run-mode classification ---------------------------------

    def collect_job_evidence(self):
        """Record which job/proc/control file runs each program (batch evidence)."""
        for path in sorted(self.repo_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in JOB_TEXT_EXTENSIONS:
                continue
            rel = path.relative_to(self.repo_root)
            if self.is_excluded(rel):
                continue
            try:
                lines = read_text(path).splitlines()
            except OSError:
                continue
            text = "\n".join(l for l in lines if not l.startswith("//*"))
            for rx in (JOB_PGM_RE, JOB_IMS_PARM_RE, JOB_TSO_RUN_RE):
                for m in rx.finditer(text):
                    self.job_runs.setdefault(m.group(1).upper(), rel.as_posix())

    def classify_programs(self):
        """Decide each program's run mode from its code, then from job streams.

        Order of evidence (first match wins):
          1. EXEC CICS in the code                      -> online
          2. run by a job step (PGM= / IMS PARM / RUN)  -> batch
          3. IMS batch entry point (ENTRY 'DLITCBL')    -> batch
          4. called by another program                  -> common (shared subroutine)
          5. STOP RUN or file SELECT/ASSIGN             -> batch
          6. parent folder name (programs/batch, ...)   -> hint only
          7. takes parameters (PROCEDURE DIVISION USING) -> common
        A program that takes parameters but has no visible caller may be a
        subroutine or a JCL main receiving PARM, so the folder hint wins there.
        """
        callers = {}
        for pid, sig in self.program_signals.items():
            for target in sig["calls"]:
                callers.setdefault(target, set()).add(pid)

        for entry in self.file_registry:
            pid = entry["id"]
            sig = self.program_signals.get(pid)
            if sig is None:  # duplicate PROGRAM-ID — already reported
                continue
            if sig["cics"]:
                subtype, basis = "online", "contains EXEC CICS"
            elif pid in self.job_runs:
                subtype, basis = "batch", f"run by job stream {self.job_runs[pid]}"
            elif sig["ims_entry"]:
                subtype, basis = "batch", "IMS batch entry point (DLITCBL)"
            elif pid in callers:
                subtype, basis = "common", f"called by {', '.join(sorted(callers[pid]))}"
            elif sig["stop_run"] or (sig["has_files"] and not sig["has_params"]):
                subtype, basis = "batch", "STOP RUN / file I/O without CICS"
            elif folder_hint(entry["path"]):
                subtype, basis = folder_hint(entry["path"]), "folder name hint"
            elif sig["has_params"]:
                subtype, basis = "common", "takes parameters (PROCEDURE DIVISION USING)"
            else:
                subtype, basis = "unknown", "no run-mode signal found"
                self.add_issue("info", "unclassified_program",
                               f"Could not determine run mode of {pid} from its code",
                               source=pid)

            entry["subtype"] = subtype
            entry["classification_basis"] = basis
            entry["runtime"] = [name for name, key in
                                (("CICS", "cics"), ("DB2", "db2"), ("IMS", "ims"), ("MQ", "mq"))
                                if sig[key]]

    # -- step 2: dependency graph -----------------------------------------

    def build_nodes(self):
        for entry in self.file_registry:
            self.nodes.append({
                "id": entry["id"], "type": "program",
                "subtype": entry["subtype"], "path": entry["path"],
            })
        for entry in self.copybook_registry:
            self.nodes.append({
                "id": entry["id"], "type": entry["type"], "path": entry["path"],
            })

    def resolve_target(self, target: str):
        if target in self.program_lookup or target in self.module_lookup:
            return True
        if target in self.copybook_lookup:
            return True
        return False

    def add_edge(self, source, edge_type, target, line_no, resolved, **extra):
        edge = {"from": source, "to": target, "type": edge_type,
                "resolved": resolved, "source_line_hint": line_no}
        edge.update(extra)
        self.edges.append(edge)

    def scan_program_edges(self, entry, raw_text):
        source = entry["id"]
        seen_this_line = set()

        for line_no, text in cobol_scannable_lines(raw_text):
            # COPY
            m = COPY_QUALIFIED_RE.search(text) or COPY_RE.search(text)
            if m:
                target = normalise_target(m.group(1))
                self.handle_copy_edge(source, target, line_no)

            # CALL — literal (static) takes priority over variable (dynamic)
            m_lit = CALL_LITERAL_RE.search(text)
            if m_lit:
                target = normalise_target(m_lit.group(1))
                resolved = self.resolve_target(target)
                if not resolved:
                    self.add_issue("warning", "unresolved_reference",
                                    f"CALL target '{target}' not found in file registry — may be external or in load library",
                                    source=source, reference=target, edge_type="STATIC_CALL")
                self.add_edge(source, "STATIC_CALL", target, line_no, resolved)
            else:
                # Ignore the word CALL inside literals, e.g. DISPLAY 'GU CALL FAIL'.
                m_var = CALL_VAR_RE.search(STRING_LITERAL_RE.sub("''", text))
                if m_var:
                    var_name = m_var.group(1)
                    if (len(var_name) >= 3 and var_name.upper() not in DYNAMIC_CALL_STOPWORDS
                            and var_name[0].isalpha()):
                        confirmed = variable_declared(raw_text, var_name)
                        self.add_edge(source, "DYNAMIC_CALL", None, line_no, False,
                                      variable=var_name, confirmed=confirmed)
                        self.add_issue("info", "dynamic_call",
                                        f"Dynamic CALL via variable {var_name} — cannot resolve statically",
                                        source=source, variable=var_name, confirmed=confirmed)

            # CICS LINK / XCTL / RETURN
            m = CICS_LINK_RE.search(text)
            if m:
                self.handle_cics_edge(source, "CICS_LINK", normalise_target(m.group(1)), line_no)
            m = CICS_XCTL_RE.search(text)
            if m:
                self.handle_cics_edge(source, "CICS_XCTL", normalise_target(m.group(1)), line_no)
            m = CICS_RETURN_RE.search(text)
            if m:
                self.add_edge(source, "CICS_RETURN", None, line_no, False,
                              transid=normalise_target(m.group(1)))

            # SQL INCLUDE
            m = SQL_INCLUDE_RE.search(text)
            if m:
                target = normalise_target(m.group(1))
                resolved = self.resolve_target(target)
                if not resolved:
                    self.add_issue("warning", "unresolved_reference",
                                    f"SQL INCLUDE target '{target}' not found in file registry",
                                    source=source, reference=target, edge_type="SQL_INCLUDE")
                self.add_edge(source, "SQL_INCLUDE", target, line_no, resolved)

    def handle_copy_edge(self, source, target, line_no):
        resolved = target in self.copybook_lookup
        if not resolved:
            self.add_issue("warning", "unresolved_reference",
                            f"COPY target '{target}' not found in file registry — may be external or in load library",
                            source=source, reference=target, edge_type="COPY")
        else:
            self.copybook_lookup[target]["used_by"].append(source)
        self.add_edge(source, "COPY", target, line_no, resolved)

    def handle_cics_edge(self, source, edge_type, target, line_no):
        resolved = self.resolve_target(target)
        if not resolved:
            self.add_issue("warning", "unresolved_reference",
                            f"{edge_type} target '{target}' not found in file registry",
                            source=source, reference=target, edge_type=edge_type)
        self.add_edge(source, edge_type, target, line_no, resolved)

    def scan_copybook_copy_edges(self, entry, raw_text):
        """Copybooks can COPY other copybooks — needed for circular-COPY detection."""
        source = entry["id"]
        for line_no, text in cobol_scannable_lines(raw_text):
            m = COPY_QUALIFIED_RE.search(text) or COPY_RE.search(text)
            if m:
                target = normalise_target(m.group(1))
                self.handle_copy_edge(source, target, line_no)

    def scan_all_edges(self):
        for entry in self.file_registry:
            full_path = self.repo_root / entry["relative_path"]
            try:
                raw_text = read_text(full_path)
            except OSError as e:
                self.add_issue("error", "file_read_error", f"Could not re-read {entry['relative_path']}: {e}",
                                path=entry["relative_path"])
                continue
            self.scan_program_edges(entry, raw_text)

        for entry in self.copybook_registry:
            if entry["type"] != "copybook":
                continue
            full_path = self.repo_root / entry["relative_path"]
            try:
                raw_text = read_text(full_path)
            except OSError:
                continue
            self.scan_copybook_copy_edges(entry, raw_text)

    def detect_circular_copies(self):
        adjacency = {}
        for edge in self.edges:
            if edge["type"] == "COPY" and edge["resolved"]:
                adjacency.setdefault(edge["from"], set()).add(edge["to"])

        reported = set()
        for a, targets in adjacency.items():
            for b in targets:
                if a in adjacency.get(b, ()):
                    key = tuple(sorted((a, b)))
                    if key in reported:
                        continue
                    reported.add(key)
                    self.add_issue("error", "circular_copy",
                                    f"Circular COPY chain detected: {a} COPY {b} which COPYs {a}",
                                    source=a, target=b)

    # -- step 3: stats -----------------------------------------------------

    def compute_stats(self):
        # Initialize buckets exactly matching the original JSON specification
        stats = {
            "programs": len(self.file_registry),
            "batch_programs": 0,
            "online_programs": 0,
            "common_programs": 0,
            "test_programs": 0,
            "utility_programs": 0,
            "unknown_programs": 0,
            "copybooks": 0,
            "jcl_jobs": len(self.jcl_registry),
            "bms_maps": 0,
            "db2_includes": 0,
            "assembler_modules": len(self.module_registry),
            "call_edges_total": len(self.edges),
            "call_edges_resolved": sum(1 for e in self.edges if e.get("resolved", True)),
            "call_edges_unresolved": sum(1 for e in self.edges if not e.get("resolved", True)),
            "dynamic_calls": 0,
            "copy_edges": sum(1 for e in self.edges if e.get("type") == "COPY"),
            "cics_link_edges": sum(1 for e in self.edges if e.get("type") == "CICS_LINK"),
            "cics_xctl_edges": sum(1 for e in self.edges if e.get("type") == "CICS_XCTL"),
            "sql_include_edges": sum(1 for e in self.edges if e.get("type") == "SQL_INCLUDE")
        }

        # Count program subtypes dynamically
        for prog in self.file_registry:
            subtype = prog.get("subtype", "unknown")
            key = f"{subtype}_programs"
            if key in stats:
                stats[key] += 1

        # Count copybooks and db2 include categories
        for cb in self.copybook_registry:
            if cb.get("type") == "db2":
                stats["db2_includes"] += 1
            elif cb.get("type") == "copybook":
                stats["copybooks"] += 1

        # Count BMS Maps if you track them via extensions (.bms)
        stats["bms_maps"] = sum(1 for p in self.repo_root.rglob("*") if p.suffix.lower() == ".bms")

        return stats
    # -- step 4: assemble ---------------------------------------------------

    def build_copybook_map(self):
        return {
            entry["id"]: entry["used_by"]
            for entry in self.copybook_lookup.values()
            if entry["used_by"]
        }
    
    def build(self):
        self.walk()
        self.collect_job_evidence()
        self.classify_programs()
        
        # Guardrail: Stop immediately if the directory was empty or wrong
        if not self.file_registry and not self.copybook_registry:
            self.add_issue(
                "error", 
                "empty_repository", 
                "File-walker discovered zero COBOL programs or copybooks. Scan aborted."
            )
            # Skip building graph/edges and return early with the error logged
            return {
                "meta": {
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "repo_root": str(self.repo_root),
                    "agent_version": "1_inventory_python@1.0",
                    "total_files_scanned": self.total_files_scanned,
                },
                "stats": self.compute_stats(),
                "file_registry": self.file_registry,
                "copybook_registry": self.copybook_registry,
                "jcl_registry": self.jcl_registry,
                "call_graph": {"nodes": [], "edges": []},
                "copybook_map": {},
                "issues": self.issues,
            }

        # Otherwise, proceed as normal
        self.build_nodes()
        self.scan_all_edges()
        self.detect_circular_copies()

        return {
            "meta": {
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "repo_root": str(self.repo_root),
                "agent_version": "1_inventory_python@1.0",
                "total_files_scanned": self.total_files_scanned,
            },
            "stats": self.compute_stats(),
            "file_registry": self.file_registry,
            "copybook_registry": self.copybook_registry,
            "jcl_registry": self.jcl_registry,
            "module_registry": self.module_registry,
            "call_graph": {
                "nodes": self.nodes,
                "edges": self.edges,
            },
            "copybook_map": self.build_copybook_map(),
            "issues": self.issues,
        }

    # def build(self):
    #     self.walk()
    #     self.build_nodes()
    #     self.scan_all_edges()
    #     self.detect_circular_copies()

    #     return {
    #         "meta": {
    #             "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    #             "repo_root": str(self.repo_root),
    #             "agent_version": "1_inventory_python@1.0",
    #             "total_files_scanned": self.total_files_scanned,
    #         },
    #         "stats": self.compute_stats(),
    #         "file_registry": self.file_registry,
    #         "copybook_registry": self.copybook_registry,
    #         "jcl_registry": self.jcl_registry,
    #         "call_graph": {
    #             "nodes": self.nodes,
    #             "edges": self.edges,
    #         },
    #         "copybook_map": self.build_copybook_map(),
    #         "issues": self.issues,
    #     }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(artifact: dict, output_path: Path):
    stats = artifact["stats"]
    print("=== Inventory Agent Complete ===")
    print(f"Repo scanned : {artifact['meta']['repo_root']}")
    print(f"Programs     : {stats['programs']}  (batch: {stats['batch_programs']}, online: {stats['online_programs']}, "
          f"common: {stats['common_programs']}, unknown: {stats['unknown_programs']})")
    print(f"Copybooks    : {stats['copybooks']}")
    print(f"JCL jobs     : {stats['jcl_jobs']}")
    print(f"BMS maps     : {stats['bms_maps']}")
    print(f"Call edges   : {stats['call_edges_total']} (resolved: {stats['call_edges_resolved']}, unresolved: {stats['call_edges_unresolved']})")
    print(f"Dynamic calls: {stats['dynamic_calls']}")
    print(f"Output       : {output_path}")
    print("================================")


def main():
    parser = argparse.ArgumentParser(description="Python port of the 1_inventory_c COBOL inventory agent.")
    parser.add_argument("--repo-root", required=True, help="Absolute path to root of the COBOL repository")
    parser.add_argument("--output-dir", default="./output/inventory", help="Directory to write inventory_artifact.json")
    parser.add_argument("--exclude-dirs", default=".git,bin,obj", help="Comma-separated dirs to skip")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        print(f"error: REPO_ROOT does not exist or is not a directory: {repo_root}", file=sys.stderr)
        sys.exit(1)

    exclude_dirs = DEFAULT_EXCLUDE_DIRS | {d.strip() for d in args.exclude_dirs.split(",") if d.strip()}

    builder = InventoryBuilder(repo_root, exclude_dirs)
    artifact = builder.build()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "inventory_artifact.json"
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    print_summary(artifact, output_path)


if __name__ == "__main__":
    main()
