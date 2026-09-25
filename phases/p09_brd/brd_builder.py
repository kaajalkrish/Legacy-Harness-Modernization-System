#!/usr/bin/env python3
"""
brd_builder.py  —  Phase 8: BRD Generation (HYBRID).

  Deterministic (Python, NO LLM) — every fact, table and id:
    * gap detection — unresolved references (one gap per missing item), dynamic
      CALLs, empty/truncated/skeleton programs, low-confidence rules; platform
      components (CICS/MQ/IMS/DB2/LE) listed as external dependencies
      -> final_report/gaps_register.json + gaps_register.md
    * document assembly — cover, table of contents, at-a-glance facts, capability
      and program tables, the business-rules catalogue, data model, process
      descriptions, architecture/inventory, error handling, technical conditions,
      gaps, structural risk indicators, appendices.

  AI step — the connecting narrative only (Claude Code AI-host with NO key, or
  the API when a key is set):
    * executive summary, business purpose, users & actors, scope, system context,
      one narrative per business capability, the key-rules selection,
      modernization considerations and next steps.
    The builder always writes brd_brief.json (the facts the AI step may use) and
    applies brd_narratives.json when present. Every section is validated: a
    wrong fingerprint rejects the file, and a section citing a BR-/TR-/RS-/GAP-
    id that does not exist is dropped. Without AI prose a neutral, fact-based
    template is used — it contains no domain wording of its own.

  Output: final_report/brd.md + brd_summary.md (+ the gaps register, brd_brief.json).

Inputs (all from earlier phases)
  --inventory  <out>/discovery/inventory.json
  --parser     <out>/analysis/parser_artifact.json
  --data       <out>/data/data_artifact.json
  --logic      <out>/logic/logic_artifact.json
  --rules      <out>/rules/rules_artifact.json
  --diagrams   <out>/diagram
  --output-dir <out>/final_report
  --system-name  display name (default: the analysed source folder's name)
  --narratives   AI-host prose JSON (default: <output-dir>/brd_narratives.json when present)
  --model / --no-llm
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

AGENT_VERSION = "brd_python@2.0"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")


def load_dotenv(base: Path) -> None:
    env = base / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else {}


def embed_mmd(path: Path, caption: str) -> str:
    p = Path(path)
    if p.exists():
        body = p.read_text(encoding="utf-8").strip()
        return f"**{caption}**\n\n```mermaid\n{body}\n```\n"
    return f"*{caption}: (diagram not available.)*\n"


# ---------------------------------------------------------------------------
# Gap detection (deterministic)
# ---------------------------------------------------------------------------

SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 3}

# Platform components supplied by the mainframe runtime (IBM CICS, MQ, IMS, DB2,
# Language Environment). They are never in an application repository, so an
# "unresolved" reference to them is an external dependency, not a gap.
EXTERNAL_COMPONENTS = [
    (r"^DFH", "CICS", "CICS system copybook / interface"),
    (r"^CMQ", "IBM MQ", "MQ API copybook"),
    (r"^MQ(OPEN|CLOSE|GET|PUT1?|CONNX?|DISC|INQ|SET|BEGIN|CMIT|BACK|SUB|SUBRQ|CB|CTL|STAT)$",
     "IBM MQ", "MQ API call"),
    (r"^(CBLTDLI|AIBTDLI|AERTDLI|CEETDLI|DFSLI000)$", "IMS", "IMS DL/I interface"),
    (r"^(SQLCA|SQLDA|DSNTIAR|DSNTIAC|DSNHLI|DSNALI|DSNELI|DSNRLI)$", "DB2", "DB2 interface"),
    (r"^(CEE|IGZ)", "Language Environment", "LE runtime service"),
    (r"^(ILBO|IGY)", "COBOL runtime", "COBOL runtime routine"),
]


def external_component(name: str) -> Optional[tuple[str, str]]:
    for pattern, subsystem, kind in EXTERNAL_COMPONENTS:
        if re.match(pattern, name or ""):
            return subsystem, kind
    return None


def detect_gaps(inv: dict, logic: dict, rules: dict, data: dict) -> tuple[list[dict], list[dict]]:
    """Return (gaps, external_dependencies). Each missing item is one gap however many
    programs reference it; platform components go to the external-dependency list."""
    gaps: list[dict] = []
    externals: dict[str, dict] = {}
    missing: dict[str, dict] = {}  # target -> merged unresolved-reference gap
    seen_dynamic: set[str] = set()

    def add(sev, gtype, msg, source, **extra):
        gaps.append({"gap_id": "", "severity": sev, "type": gtype,
                     "description": msg, "source": source, **extra})

    def unresolved(target, kind, program, source):
        ext = external_component(target)
        if ext:
            e = externals.setdefault(target, {"component": target, "subsystem": ext[0],
                                              "kind": ext[1], "used_by": set()})
            if program:
                e["used_by"].add(program)
            return
        m = missing.setdefault(target, {"kind": kind, "programs": set(), "sources": set()})
        if program:
            m["programs"].add(program)
        m["sources"].add(source)

    for iss in inv.get("issues", []):
        t = iss.get("type")
        if t == "unresolved_reference":
            unresolved(iss.get("reference", ""), iss.get("edge_type", "reference"),
                       iss.get("source"), "inventory")
        elif t in ("circular_copy", "duplicate_program_id"):
            add("high", t, iss.get("message", ""), "inventory")
        elif t == "dynamic_call":
            key = f"{iss.get('source')}|{iss.get('variable')}"
            if key in seen_dynamic:
                continue
            seen_dynamic.add(key)
            add("medium", t, f"{iss.get('source')}: dynamic CALL via variable "
                f"{iss.get('variable')} — target program cannot be determined statically.",
                "inventory")
        elif t == "unclassified_program":
            add("low", t, iss.get("message", ""), "inventory")

    for iss in data.get("issues", []):
        m = re.match(r"COPY (\S+) not found", iss.get("message", ""))
        if iss.get("type") == "unresolved_copy_stub" and m:
            unresolved(m.group(1), "COPY", None, "data")
        else:
            add("medium", iss.get("type", "data_issue"), iss.get("message", ""), "data")

    for target, m in sorted(missing.items()):
        progs = sorted(m["programs"])
        where = f"referenced by {', '.join(progs)}" if progs else "referenced in the data layouts"
        add("medium", "unresolved_reference",
            f"{m['kind']} target '{target}' is not in the repository ({where}) — its definition "
            f"is needed to complete the data model / call graph.",
            "+".join(sorted(m["sources"])), reference=target, programs=progs)

    for iss in logic.get("issues", []):
        t = iss.get("type", "")
        if iss.get("severity") == "info" and "finding" not in t:
            continue  # run status messages, not gaps
        sev = "high" if t in ("empty_source", "truncated_source") else \
              ("medium" if t == "skeletons" else "low")
        add(sev, t or "logic_issue", iss.get("message", ""), "logic")
    for prog in logic.get("programs", []):
        if prog.get("ambiguous_paragraphs", 0):
            add("low", "ambiguous_logic",
                f"{prog['program_id']}: {prog['ambiguous_paragraphs']} paragraph(s) flagged ambiguous "
                f"during pseudocode extraction.", "logic")

    for r in rules.get("business_rules", []):
        if r.get("requires_sme_review"):
            add("medium", "rule_sme_review",
                f"{r['rule_id']} “{r['name']}” — low confidence, requires SME confirmation.", "rules")

    gaps.sort(key=lambda g: SEV_RANK.get(g["severity"], 3))
    for i, g in enumerate(gaps, 1):
        g["gap_id"] = f"GAP-{i:03d}"
    ext_list = [{**e, "used_by": sorted(e["used_by"])}
                for e in sorted(externals.values(), key=lambda e: (e["subsystem"], e["component"]))]
    return gaps, ext_list


def externals_markdown(externals: list[dict]) -> str:
    if not externals:
        return ""
    out = ["| Component | Subsystem | Kind | Used by |", "|---|---|---|---|"]
    for e in externals:
        used = ", ".join(e["used_by"][:8]) + (f" (+{len(e['used_by']) - 8})" if len(e["used_by"]) > 8 else "")
        out.append(f"| {e['component']} | {e['subsystem']} | {e['kind']} | {used or '—'} |")
    return "\n".join(out) + "\n"


def gaps_markdown(gaps: list[dict], externals: Optional[list[dict]] = None) -> str:
    counts: dict[str, int] = {}
    for g in gaps:
        counts[g["severity"]] = counts.get(g["severity"], 0) + 1
    out = ["# Gaps and Assumptions Register", "",
           f"Total gaps: **{len(gaps)}**  ·  "
           + "  ·  ".join(f"{k}: {counts.get(k,0)}" for k in ("critical", "high", "medium", "low")),
           "", "| Gap ID | Severity | Type | Description | Source |",
           "|---|---|---|---|---|"]
    for g in gaps:
        out.append(f"| {g['gap_id']} | {g['severity'].upper()} | {g['type']} | "
                   f"{g['description'].replace('|', '/')} | {g['source']} |")
    if externals:
        out += ["", "## External system dependencies (not gaps)", "",
                "Platform components provided by the mainframe runtime; they are expected to be "
                "absent from the application repository.", "", externals_markdown(externals)]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Facts (deterministic) — everything the narrative may draw on
# ---------------------------------------------------------------------------

RUN_MODE_LABEL = {"online": "Online", "batch": "Batch", "common": "Shared subroutine",
                  "utility": "Utility", "test": "Test", "unknown": "Unclassified"}
ID_RE = re.compile(r"\b(?:BR|TR|RS|GAP)-\d{3}\b")


def first_sentence(text: str, limit: int = 120) -> str:
    """First sentence of a summary, cut at a word boundary (never mid-word)."""
    s = re.sub(r"\s+", " ", (text or "").strip())
    m = re.search(r"(?<!\be\.g)(?<!\bi\.e)(?<!\betc)\.(\s+[A-Z(]|$)", s)
    s = s[:m.start()] if m else s
    if len(s) <= limit:
        return s
    return s[:limit].rsplit(" ", 1)[0].rstrip(",;:-(") + "…"


def short_title(summary: str, limit: int = 80) -> str:
    """First sentence without trailing parenthetical notes — for use inside running text."""
    s = first_sentence(summary, limit)
    return re.sub(r"\s*\([^()]*\)\s*$", "", s).replace(" -- ", " — ").strip()


def complexity_band(score: int) -> str:
    return "Low" if score <= 3 else ("Medium" if score <= 6 else "High")


def cell(text: Any) -> str:
    return str(text if text is not None else "").replace("|", "/").replace("\n", " ")


def collect_facts(sysname: str, inv, parser, data, logic, rules, gaps, externals) -> dict:
    st = inv.get("stats", {})
    reg = {e["id"]: e for e in inv.get("file_registry", [])}
    runtime: dict[str, int] = {}
    for e in reg.values():
        for r in e.get("runtime", []):
            runtime[r] = runtime.get(r, 0) + 1
    pstats = parser.get("stats", {})
    unstructured = sorted(p["program_id"] for p in parser.get("programs", [])
                          if p.get("has_unstructured_flow"))
    alter = sorted(p["program_id"] for p in parser.get("programs", []) if p.get("has_alter"))
    high_cx = sorted(p["program_id"] for p in logic.get("programs", [])
                     if complexity_band(p.get("max_complexity", 0)) == "High")
    rmeta = rules.get("meta", {})
    return {
        "system_name": sysname,
        "source_folder": Path(inv.get("meta", {}).get("repo_root", "") or "").name or "n/a",
        "programs": st.get("programs", 0), "batch": st.get("batch_programs", 0),
        "online": st.get("online_programs", 0), "common": st.get("common_programs", 0),
        "unclassified": st.get("unknown_programs", 0),
        "copybooks": st.get("copybooks", 0), "jcl": st.get("jcl_jobs", 0),
        "bms": st.get("bms_maps", 0), "runtime_usage": runtime,
        "rules": rmeta.get("total_rules", 0), "rule_sets": rmeta.get("total_rule_sets", 0),
        "technical_conditions": rmeta.get("technical_conditions", 0),
        "error_conditions": len(rules.get("error_handling_catalogue", [])),
        "records": data.get("stats", {}).get("records", 0),
        "fields": data.get("stats", {}).get("fields", 0),
        "entities": len(data.get("data_model", {}).get("entities", [])),
        "paragraphs": logic.get("stats", {}).get("total_paragraphs_explained", 0),
        "gaps": len(gaps), "high_gaps": sum(1 for g in gaps if g["severity"] in ("critical", "high")),
        "sme_rules": rmeta.get("requires_sme_review", 0),
        "external_components": len(externals),
        "external_subsystems": sorted({e["subsystem"] for e in externals}),
        "goto_edges": pstats.get("total_goto_edges", 0),
        "alter_statements": pstats.get("total_alter_statements", 0),
        "unstructured_programs": unstructured, "alter_programs": alter,
        "high_complexity_programs": high_cx,
        "dead_code_candidates": pstats.get("total_dead_code_candidates", 0),
        "capability_source": rmeta.get("capability_source", "per-program fallback"),
    }


def capabilities_of(rules: dict, inv: dict, logic: dict) -> list[dict]:
    """AI capabilities from the rules artifact, else functional areas by run mode."""
    if rules.get("meta", {}).get("capability_source") == "ai" and rules.get("capabilities"):
        return [dict(c) for c in rules["capabilities"]]
    mode = {e["id"]: e.get("subtype", "unknown") for e in inv.get("file_registry", [])}
    areas = [("online", "Online functions",
              "Interactive screens and online services used by end users and operators."),
             ("batch", "Batch processing", "Scheduled jobs run through the job streams."),
             ("common", "Shared services", "Subroutines called by other programs.")]
    out, placed = [], set()
    for key, name, desc in areas:
        progs = [p["program_id"] for p in logic.get("programs", []) if mode.get(p["program_id"]) == key]
        if progs:
            out.append({"name": name, "description": desc, "programs": progs})
            placed.update(progs)
    rest = [p["program_id"] for p in logic.get("programs", []) if p["program_id"] not in placed]
    if rest:
        out.append({"name": "Other programs", "description": "", "programs": rest})
    return out


# ---------------------------------------------------------------------------
# AI step — brief (facts in) / narratives (AI prose out)
# ---------------------------------------------------------------------------

NARRATIVE_TEXT_KEYS = ("executive_summary", "business_purpose", "users_and_actors", "scope",
                       "system_context", "modernization")


def brd_fingerprint(sysname: str, logic: dict, rules: dict, gaps: list[dict]) -> str:
    parts = [sysname] + sorted(p["program_id"] for p in logic.get("programs", [])) \
        + sorted(r["rule_id"] for r in rules.get("business_rules", [])) \
        + sorted(g["gap_id"] for g in gaps)
    return hashlib.sha1("\n".join(parts).encode()).hexdigest()[:16]


def build_brief(facts: dict, fp: str, inv, logic, rules, gaps, externals, caps) -> dict:
    reg = {e["id"]: e for e in inv.get("file_registry", [])}
    rbp = rules.get("rules_by_program", {})
    return {
        "meta": {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "agent_version": AGENT_VERSION, "fingerprint": fp},
        "instructions": (
            "Write brd_narratives.json next to this file (see phases/p09_brd/brd_agent.md). Copy "
            "meta.fingerprint. Use ONLY the facts below; never invent numbers, programs, ids, "
            "thresholds or business terms not supported by the program summaries and rules."),
        "facts": facts,
        "capabilities": [{"name": c["name"], "description": c.get("description", ""),
                          "programs": c["programs"]} for c in caps],
        "programs": [{"program_id": p["program_id"],
                      "run_mode": reg.get(p["program_id"], {}).get("subtype"),
                      "runtime": reg.get(p["program_id"], {}).get("runtime", []),
                      "complexity": complexity_band(p.get("max_complexity", 0)),
                      "business_rules": rbp.get(p["program_id"], []),
                      "summary": p.get("summary", "")} for p in logic.get("programs", [])],
        "business_rules": [{"rule_id": r["rule_id"], "rule_set": r["rule_set"], "name": r["name"],
                            "description": r["description"], "category": r["category"],
                            "confidence": r["confidence"]} for r in rules.get("business_rules", [])],
        "gaps": [{"gap_id": g["gap_id"], "severity": g["severity"], "type": g["type"],
                  "description": g["description"]} for g in gaps],
        "external_dependencies": externals,
    }


def validate_narratives(raw: dict, fp: str, known_ids: set[str], cap_names: set[str],
                        rule_ids: set[str]) -> tuple[dict, list[str]]:
    """Keep only sections whose every cited id exists; reject a stale/foreign file."""
    if raw.get("meta", {}).get("fingerprint") != fp:
        return {}, ["BRD narratives ignored: fingerprint does not match this codebase/run "
                    "(regenerate from the current brd_brief.json)."]
    warnings, out = [], {}

    def grounded(label: str, text: str) -> bool:
        bad = sorted(set(ID_RE.findall(text or "")) - known_ids)
        if bad:
            warnings.append(f"{label}: cites unknown id(s) {', '.join(bad)} — section dropped")
        return not bad

    for k in NARRATIVE_TEXT_KEYS:
        v = raw.get(k)
        if isinstance(v, str) and v.strip() and grounded(k, v):
            out[k] = v.strip()
    caps = {}
    for name, text in (raw.get("capabilities") or {}).items():
        if name not in cap_names:
            warnings.append(f"capability narrative for unknown capability '{name}' dropped")
        elif isinstance(text, str) and text.strip() and grounded(f"capability '{name}'", text):
            caps[name] = text.strip()
    out["capabilities"] = caps
    key_rules = []
    for kr in raw.get("key_rules") or []:
        rid = kr.get("rule_id") if isinstance(kr, dict) else None
        if rid not in rule_ids:
            warnings.append(f"key rule {rid} is not a business rule — dropped")
        elif grounded(f"key rule {rid}", kr.get("why", "")):
            key_rules.append({"rule_id": rid, "why": str(kr.get("why", "")).strip()})
    out["key_rules"] = key_rules
    steps = [s.strip() for s in raw.get("next_steps") or [] if isinstance(s, str) and s.strip()]
    if steps and all(grounded("next_steps", s) for s in steps):
        out["next_steps"] = steps
    return out, warnings


def llm_narratives(client, model: str, brief: dict, usage: dict) -> dict:
    schema = {"type": "object", "properties": {
        **{k: {"type": "string"} for k in NARRATIVE_TEXT_KEYS},
        "capabilities": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "narrative": {"type": "string"}},
            "required": ["name", "narrative"], "additionalProperties": False}},
        "key_rules": {"type": "array", "items": {"type": "object", "properties": {
            "rule_id": {"type": "string"}, "why": {"type": "string"}},
            "required": ["rule_id", "why"], "additionalProperties": False}},
        "next_steps": {"type": "array", "items": {"type": "string"}}},
        "required": list(NARRATIVE_TEXT_KEYS) + ["capabilities", "key_rules", "next_steps"],
        "additionalProperties": False}
    system = ("You write the narrative sections of a reverse-engineered Business Requirements "
              "Document for senior business and technology leaders. Plain English, present tense, "
              "no COBOL jargon. Use only the facts in the brief — never invent numbers, programs, "
              "ids, thresholds or business terms. Cite rule ids (BR-###) and gap ids (GAP-###) "
              "exactly as given.")
    resp = client.messages.create(
        model=model, max_tokens=16000, system=system,
        messages=[{"role": "user", "content": json.dumps(brief, indent=1)}],
        output_config={"format": {"type": "json_schema", "schema": schema}})
    text = next((b.text for b in resp.content if b.type == "text"), "")
    usage["in"] += resp.usage.input_tokens
    usage["out"] += resp.usage.output_tokens
    data = json.loads(text)
    data["capabilities"] = {c["name"]: c["narrative"] for c in data.get("capabilities", [])}
    data["meta"] = {"fingerprint": brief["meta"]["fingerprint"]}
    return data


# ---------------------------------------------------------------------------
# Neutral fallback prose — built only from facts, no domain wording of its own
# ---------------------------------------------------------------------------

def n_of(n: int, word: str, plural: Optional[str] = None) -> str:
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def templated_narratives(f: dict, caps: list[dict], logic: dict, rules: dict) -> dict:
    mix = _join([f"{f['online']} online" if f["online"] else "",
                 f"{f['batch']} batch" if f["batch"] else "",
                 f"{f['common']} shared subroutines" if f["common"] else ""])
    subsystems = _join(sorted(f["runtime_usage"])) or "no online or database subsystem"
    by_rules = sorted(logic.get("programs", []),
                      key=lambda p: -len(rules.get("rules_by_program", {}).get(p["program_id"], [])))
    notable = [f"{p['program_id']} — {short_title(p.get('summary', ''))}"
               for p in by_rules[:4] if p.get("summary")]
    if f["capability_source"] == "ai":
        functions = "Its business capabilities are " + _join([c["name"] for c in caps]) + "."
    elif notable:
        functions = "The programs carrying the most business rules are " + "; ".join(notable) + "."
    else:
        functions = ""
    exec_summary = (
        f"{f['system_name']} is a COBOL application of {f['programs']} programs ({mix}) that uses "
        f"{subsystems}. {functions}\n\n"
        f"This document was reverse-engineered from the source code. It records the business "
        f"rules found in the code, the data the system holds, how each program works, and "
        f"{f['gaps']} open questions that need subject-matter-expert confirmation (Chapter 9).")
    context_bits = []
    if f["online"]:
        context_bits.append(f"{f['online']} online programs that serve interactive users"
                            + (" under CICS" if "CICS" in f["runtime_usage"] else ""))
    if f["batch"]:
        context_bits.append(f"{f['batch']} batch programs run from {f['jcl']} job streams")
    if f["common"]:
        context_bits.append(f"{f['common']} shared subroutines called by other programs")
    stores = [s for s in ("DB2", "IMS", "MQ") if s in f["runtime_usage"]]
    system_context = (f"{f['system_name']} consists of " + _join(context_bits) + "."
                      + (f" Programs also use {_join(stores)} "
                         f"({', '.join(f'{s}: {f['runtime_usage'][s]} programs' for s in stores)})."
                         if stores else "")
                      + (f" It depends on {n_of(f['external_components'], 'platform component')} "
                         f"({_join(f['external_subsystems'])}) listed in section 7.3."
                         if f["external_components"] else ""))
    return {"executive_summary": exec_summary, "system_context": system_context,
            "capabilities": {}, "key_rules": []}


DECISION_RE = re.compile(r"declin|reject|approv|deny|denied|limit|reason|fraud|expir|password"
                         r"|admin|delete|purge|post\b|pay", re.IGNORECASE)


def default_key_rules(rules: dict, limit: int = 15) -> list[dict]:
    """Fallback selection: explicit decisions first (approve/decline/reject/limit/reason ...),
    then limits and calculations; plain allowed-value lists last."""
    order = {"LIMIT_CHECK": 0, "CALCULATION": 1, "COMPLIANCE": 2, "ROUTING": 3, "VALIDATION": 4}
    conf = {"confirmed": 0, "high": 1, "medium": 2, "low": 3}

    def rank(r):
        text = r.get("condition", {}).get("text", "") + " " + r["name"]
        return (0 if DECISION_RE.search(text) else 1,
                1 if r.get("condition", {}).get("field") else 0,   # 88-level value lists last
                order.get(r["category"], 5), conf.get(r["confidence"], 4))
    picked = sorted(rules.get("business_rules", []), key=rank)[:limit]
    return [{"rule_id": r["rule_id"], "why": ""} for r in
            sorted(picked, key=lambda r: r["rule_id"])]


def default_next_steps(f: dict) -> list[str]:
    steps = []
    if f["high_gaps"]:
        steps.append(f"Resolve the {n_of(f['high_gaps'], 'high-severity gap')} in Chapter 9 before this "
                     f"document drives design or testing.")
    if f["sme_rules"]:
        steps.append(f"Confirm the {n_of(f['sme_rules'], 'business rule')} marked ⚠ with the business owners.")
    if f["gaps"] - f["high_gaps"]:
        steps.append(f"Work through the remaining {n_of(f['gaps'] - f['high_gaps'], 'gap')} and assumptions "
                     f"(missing definitions, ambiguous logic) with subject-matter experts.")
    steps.append("Have a data architect confirm the estimated entity relationships in Chapter 5.")
    if f["external_components"]:
        steps.append(f"Plan target-platform equivalents for the {n_of(f['external_components'], 'platform component')} "
                     f"in section 7.3 ({_join(f['external_subsystems'])}).")
    return steps


# ---------------------------------------------------------------------------
# Section assembly (deterministic)
# ---------------------------------------------------------------------------

def slug(title: str) -> str:
    s = re.sub(r"[^\w\s-]", "", title.lower()).strip()
    return re.sub(r"\s+", "-", s)


def assemble_brd(f: dict, narr: dict, mode: str, inv, parser, data, logic, rules, gaps,
                 externals, caps, diagrams_dir: Path, rel: dict) -> str:
    body: list[str] = []
    toc: list[tuple[int, str]] = []
    w = body.append

    def h2(title):
        toc.append((2, title)); w(f"## {title}\n")

    def h3(title, in_toc=True):
        if in_toc:
            toc.append((3, title))
        w(f"### {title}\n")

    reg = {e["id"]: e for e in inv.get("file_registry", [])}
    lmap = {p["program_id"]: p for p in logic.get("programs", [])}
    rbp = rules.get("rules_by_program", {})
    rules_by_id = {r["rule_id"]: r for r in rules.get("business_rules", [])}
    cap_of = {p: c["name"] for c in caps for p in c["programs"]}
    conf_mark = {"confirmed": "✓", "high": "✓", "medium": "⚠", "low": "⚠ SME review"}

    def run_mode(pid):
        return RUN_MODE_LABEL.get(reg.get(pid, {}).get("subtype", "unknown"), "Unclassified")

    # 1 — Executive summary
    h2("1. Executive Summary")
    w(narr["executive_summary"] + "\n")
    h3("1.1 At a glance")
    w("| Measure | Value |")
    w("|---|---|")
    unclassified = f" · {f['unclassified']} unclassified" if f["unclassified"] else ""
    w(f"| Programs | {f['programs']} ({f['online']} online · {f['batch']} batch · "
      f"{f['common']} shared subroutines{unclassified}) |")
    w(f"| Business capabilities | {len(caps)} |")
    w(f"| Business rules | {f['rules']} in {f['rule_sets']} rule sets ({f['sme_rules']} {'needs' if f['sme_rules'] == 1 else 'need'} SME confirmation) |")
    w(f"| Data | {f['entities']} entities · {f['records']} records · {f['fields']} fields |")
    w(f"| Platform subsystems used | {_join(sorted(f['runtime_usage'])) or '—'} |")
    w(f"| Open gaps | {f['gaps']} ({f['high_gaps']} high/critical) |")
    w("")
    h3("1.2 Scope of analysis")
    w(f"The analysed codebase comprises {f['programs']} programs, {f['copybooks']} copybooks, "
      f"{f['jcl']} job streams and {f['bms']} screen maps. Static analysis extracted "
      f"{f['rules']} business rules, set aside {f['technical_conditions']} technical conditions and "
      f"{f['error_conditions']} error-handling checks as program mechanics, and explained "
      f"{f['paragraphs']} paragraphs in plain English.\n")

    # 2 — Business context
    h2("2. Business Context and Scope")
    if narr.get("business_purpose"):
        h3("2.1 Business purpose"); w(narr["business_purpose"] + "\n")
    if narr.get("users_and_actors"):
        h3("2.2 Users and actors"); w(narr["users_and_actors"] + "\n")
    if narr.get("scope"):
        h3("2.3 Scope"); w(narr["scope"] + "\n")
    h3("2.4 System context")
    w(narr["system_context"] + "\n")
    w(embed_mmd(diagrams_dir / "component_overview.mmd", "Figure 2.1 — System component overview"))
    w("*Each box is a program; an arrow means the source program calls, links to or transfers "
      "control to the target.*\n")

    # 3 — Capabilities
    h2("3. Business Capabilities")
    w("Programs grouped by the business capability they support"
      + (" (grouping reviewed by AI from the program summaries)." if f["capability_source"] == "ai"
         else " (grouped by run mode — no AI capability grouping was supplied).") + "\n")
    for i, c in enumerate(caps, start=1):
        h3(f"3.{i} {c['name']}")
        text = narr.get("capabilities", {}).get(c["name"]) or c.get("description", "")
        if text:
            w(text + "\n")
        w("| Program | Run mode | What it does | Rules |")
        w("|---|---|---|---|")
        for pid in c["programs"]:
            w(f"| {pid} | {run_mode(pid)} | {cell(first_sentence(lmap.get(pid, {}).get('summary', '')))} | "
              f"{len(rbp.get(pid, []))} |")
        cap_rules = [r["rule_id"] for r in rules.get("business_rules", [])
                     if cap_of.get(r["primary_source"].get("program_id")
                                   or next(iter(r["implemented_in_programs"]), None)) == c["name"]]
        if cap_rules:
            w(f"\n*Business rules: {', '.join(cap_rules)} — see Chapter 4.*")
        w("")

    # 4 — Business rules
    h2("4. Business Rules")
    w(f"{f['rules']} business rules were identified — decisions and domain constraints a business "
      f"owner can confirm. Program mechanics (loop control, screen handling, file status, flags) "
      f"are listed separately in Chapter 8. Confidence: ✓ confirmed/high · ⚠ needs SME review.\n")
    h3("4.1 Key business rules")
    key_rules = narr.get("key_rules") or default_key_rules(rules)
    has_why = any(k.get("why") for k in key_rules)
    w("| Rule | Statement | Capability |" + (" Why it matters |" if has_why else ""))
    w("|---|---|---|" + ("---|" if has_why else ""))
    for k in key_rules:
        r = rules_by_id.get(k["rule_id"])
        if r:
            owner = r["primary_source"].get("program_id") or next(iter(r["implemented_in_programs"]), None)
            w(f"| {r['rule_id']} | {cell(r['name'])} | {cell(cap_of.get(owner, r['rule_set']))} |"
              + (f" {cell(k.get('why', ''))} |" if has_why else ""))
    w("")
    h3("4.2 Business rules catalogue")
    for rset in rules.get("rule_sets", []):
        w(f"#### {rset['rule_set_id']} — {rset['name']}\n")
        w(f"*Programs: {', '.join(rset.get('programs', [])[:8])} · Rules: {rset.get('rule_count', 0)}*\n")
        for rid in rset.get("rule_ids", []):
            r = rules_by_id.get(rid)
            if not r:
                continue
            src = r.get("primary_source", {})
            where = (src.get("program_id") or r.get("defined_in") or "") \
                + (f", {src.get('paragraph')}" if src.get("paragraph") else "") \
                + (f", line {src.get('line')}" if src.get("line") else "")
            w(f"**{r['rule_id']} — {r['name']}** {conf_mark.get(r['confidence'], '')}  ")
            w(r.get("description", "") + "  ")
            w(f"*{r['category'].replace('_', ' ').title()} · {r['confidence']} confidence · "
              f"Source: {where}*\n")
    w("")

    # 5 — Data model
    h2("5. Data Model and Definitions")
    dm = data.get("data_model", {})
    w(f"The data model comprises **{len(dm.get('entities', []))} entities** and "
      f"**{len(dm.get('relationships', []))} estimated relationships**, with "
      f"**{f['fields']} fields** across **{f['records']} records**.\n")
    w(embed_mmd(diagrams_dir / "erd.mmd", "Figure 5.1 — Key entities and relationships"))
    w("*Relationships are inferred from shared key fields and should be confirmed by a data "
      "architect.*\n")
    h3("5.1 Key entities")
    w("| Entity | Defined in | Fields | Used by |")
    w("|---|---|---|---|")
    for ent in sorted(dm.get("entities", []), key=lambda e: -e.get("field_count", 0))[:20]:
        w(f"| {ent['name']} | {ent.get('source', '')} | {ent.get('field_count', 0)} | "
          f"{', '.join(ent.get('used_by', [])[:4])} |")
    w("")

    # 6 — Process descriptions (ordered by capability)
    h2("6. Process Descriptions")
    fig = 0
    for ci, c in enumerate(caps, start=1):
        h3(f"6.{ci} {c['name']}")
        for pid in c["programs"]:
            p = lmap.get(pid, {})
            fig += 1
            w(f"#### {pid} — {first_sentence(p.get('summary', ''), 90) or run_mode(pid)}\n")
            w(f"*{run_mode(pid)}"
              + (f" · {'/'.join(reg.get(pid, {}).get('runtime', []))}" if reg.get(pid, {}).get("runtime") else "")
              + f" · Complexity: {complexity_band(p.get('max_complexity', 0))}"
              + f" · Business rules: {', '.join(rbp.get(pid, [])) or 'none'}*\n")
            w((p.get("summary", "") or "No narrative available.") + "\n")
            w(embed_mmd(diagrams_dir / "diagrams" / f"flow_{pid}.mmd", f"Figure 6.{fig} — {pid} flow"))

    # 7 — Architecture & inventory
    h2("7. System Architecture and Inventory")
    h3("7.1 Program inventory")
    w("| Program | Run mode | Subsystems | Capability | Complexity | Rules |")
    w("|---|---|---|---|---|---|")
    for e in inv.get("file_registry", []):
        pid = e["id"]
        w(f"| {pid} | {run_mode(pid)} | {'/'.join(e.get('runtime', [])) or '—'} | "
          f"{cell(cap_of.get(pid, '—'))} | {complexity_band(lmap.get(pid, {}).get('max_complexity', 0))} | "
          f"{len(rbp.get(pid, []))} |")
    w("")
    h3("7.2 Shared copybooks")
    w("| Copybook | Used by (programs) |")
    w("|---|---|")
    for cb, users in sorted(inv.get("copybook_map", {}).items(), key=lambda x: -len(x[1]))[:20]:
        w(f"| {cb} | {len(users)} |")
    w("")
    h3("7.3 Platform dependencies")
    if externals:
        w("Components supplied by the mainframe platform. They are not in the repository by design, "
          "and each needs an equivalent in the target architecture.\n")
        w(externals_markdown(externals))
    else:
        w("No platform components were referenced.\n")
    h3("7.4 Integration hotspots")
    prog_ids = set(reg)
    fan_in: dict[str, set] = {}
    for e in inv.get("call_graph", {}).get("edges", []):
        if e.get("to") in prog_ids and e.get("type") != "COPY":
            fan_in.setdefault(e["to"], set()).add(e["from"])
    hubs = sorted(fan_in.items(), key=lambda x: -len(x[1]))[:8]
    w("**Most-invoked programs:** " + (", ".join(
        f"{k} (called by {_join(sorted(v))})" for k, v in hubs)
                                        or "none — programs do not call one another") + ".\n")

    # 8 — Error handling & technical conditions
    h2("8. Error Handling and Technical Conditions")
    h3("8.1 Error handling")
    eh = rules.get("error_handling_catalogue", [])
    w(f"{len(eh)} error-handling checks were found (file status, SQLCODE, CICS RESP and similar), "
      f"typically after each input/output or database operation.\n")
    w("| Program | Paragraph | Condition |")
    w("|---|---|---|")
    for e in eh[:15]:
        w(f"| {e.get('program_id', '')} | {e.get('paragraph', '') or ''} | {cell(e.get('condition_text', ''))[:80]} |")
    if len(eh) > 15:
        w(f"| … | … | {len(eh) - 15} more in the rules artifact |")
    w("")
    h3("8.2 Technical conditions")
    tech = rules.get("technical_rules", [])
    w(f"{len(tech)} conditions describe program mechanics rather than business policy. They matter "
      f"for a faithful re-implementation but not for business sign-off. Full list: Appendix D.\n")
    w("| Kind | Count | Example |")
    w("|---|---|---|")
    for reason, n in sorted(rules.get("stats", {}).get("technical_by_reason", {}).items(), key=lambda x: -x[1]):
        ex = next((t for t in tech if t["reason"] == reason), {})
        w(f"| {reason} | {n} | {cell(ex.get('condition', {}).get('text', ''))[:70]} |")
    w("")

    # 9 — Gaps
    h2("9. Gaps and Assumptions Register")
    w("Everything static analysis could not fully resolve. High-severity gaps should be resolved "
      "with subject-matter experts before this document drives design or testing. Platform "
      "components are not gaps — see 7.3.\n")
    w(gaps_markdown(gaps).split("\n", 2)[2])

    # 10 — Modernization
    h2("10. Modernization Considerations and Next Steps")
    if narr.get("modernization"):
        w(narr["modernization"] + "\n")
    h3("10.1 Structural risk indicators")
    w("| Indicator | Value | Programs |")
    w("|---|---|---|")
    w(f"| GO TO transfers | {f['goto_edges']} | {len(f['unstructured_programs'])} programs with unstructured flow: "
      f"{', '.join(f['unstructured_programs'][:10])}{' …' if len(f['unstructured_programs']) > 10 else ''} |")
    w(f"| ALTER statements | {f['alter_statements']} | {', '.join(f['alter_programs']) or '—'} |")
    w(f"| High-complexity programs | {len(f['high_complexity_programs'])} | "
      f"{', '.join(f['high_complexity_programs'][:12])} |")
    w(f"| Dead-code candidates (paragraphs) | {f['dead_code_candidates']} | — |")
    w(f"| Platform components to replace | {f['external_components']} | {_join(f['external_subsystems']) or '—'} |")
    w("")
    h3("10.2 Next steps")
    for i, s in enumerate(narr.get("next_steps") or default_next_steps(f), start=1):
        w(f"{i}. {s}")
    w("")

    # Appendices
    h2("Appendices")
    w(f"- **Appendix A — Data dictionary:** `{rel['data']}` ({f['fields']} fields) and "
      f"`{rel['data_layouts']}`.")
    w(f"- **Appendix B — Program pseudocode:** `{rel['logic']}` ({f['paragraphs']} paragraphs).")
    w("- **Appendix C — Diagram index:** see below.")
    w("- **Appendix D — Technical conditions:** see below.\n")
    idx = load(diagrams_dir / "diagrams_artifact.json").get("diagrams", [])
    if idx:
        h3("Appendix C — Diagram index", in_toc=False)
        w("| Diagram | Type | File |")
        w("|---|---|---|")
        for d in idx:
            w(f"| {cell(d.get('title', d.get('id')))} | {d.get('type', '')} | `{d.get('file', '')}` |")
        w("")
    if tech:
        h3("Appendix D — Technical conditions", in_toc=False)
        w("| ID | Kind | Condition | Programs |")
        w("|---|---|---|---|")
        for t in tech:
            w(f"| {t['rule_id']} | {t['reason']} | {cell(t.get('condition', {}).get('text', ''))[:90]} | "
              f"{', '.join(t.get('implemented_in_programs', [])[:4])} |")
        w("")

    # Cover + document control + TOC
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    head = [f"# Business Requirements Document\n## {f['system_name']}\n",
            "| | |", "|---|---|",
            "| **Document type** | Reverse-engineered Business Requirements Document |",
            "| **Status** | Draft — generated; requires subject-matter-expert review |",
            f"| **Source analysed** | `{f['source_folder']}` ({f['programs']} programs) |",
            f"| **Generated** | {date} |",
            "| **Prepared by** | Legacy Modernization Harness — facts by static analysis; "
            f"narrative: {mode} |", "",
            "> Every fact, count and rule in this document is derived from the source code. "
            "Items marked ⚠ need subject-matter-expert confirmation before the document is "
            "treated as authoritative.\n", "---\n", "## Table of Contents\n"]
    for level, title in toc:
        head.append(("" if level == 2 else "   ") + f"- [{title}](#{slug(title)})")
    head.append("\n---\n")
    return "\n".join(head + body) + "\n"


def brd_summary_md(f: dict, narr: dict, caps: list[dict], rules: dict, gaps: list[dict]) -> str:
    rules_by_id = {r["rule_id"]: r for r in rules.get("business_rules", [])}
    high = [g for g in gaps if g["severity"] in ("critical", "high")]
    out = [f"# {f['system_name']} — Business Requirements Summary", "",
           f"**Full BRD:** brd.md · **Generated:** {datetime.now(timezone.utc):%Y-%m-%d}", "",
           "## What this system does", "", narr["executive_summary"].split("\n\n")[0], "",
           "## At a glance", "",
           f"- Programs: {f['programs']} ({f['online']} online, {f['batch']} batch, {f['common']} shared)",
           f"- Business rules: {f['rules']} in {f['rule_sets']} rule sets",
           f"- Data: {f['entities']} entities, {f['records']} records, {f['fields']} fields",
           f"- Open gaps: {f['gaps']} ({f['high_gaps']} high/critical)", "",
           "## Business capabilities", ""]
    out += [f"- **{c['name']}** — {len(c['programs'])} programs" for c in caps]
    out += ["", "## Key business rules", ""]
    for k in (narr.get("key_rules") or default_key_rules(rules))[:10]:
        r = rules_by_id.get(k["rule_id"])
        if r:
            out.append(f"- **{r['rule_id']}** — {r['name']}")
    out += ["", "## High-severity gaps", ""]
    out += [f"- **{g['gap_id']}** — {g['description']}" for g in high[:10]] or ["- None."]
    out += ["", "## Next steps", ""]
    out += [f"{i}. {s}" for i, s in enumerate(narr.get("next_steps") or default_next_steps(f), start=1)]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build(paths: dict, output_dir: Path, sysname: Optional[str], model: str, use_llm: bool,
          diagrams_dir: Path, narratives_path: Optional[Path] = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    inv = load(paths["inventory"]); parser = load(paths["parser"]); data = load(paths["data"])
    logic = load(paths["logic"]); rules = load(paths["rules"])
    sysname = sysname or Path(inv.get("meta", {}).get("repo_root", "") or "system").name

    gaps, externals = detect_gaps(inv, logic, rules, data)
    (output_dir / "gaps_register.json").write_text(
        json.dumps({"meta": {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "total_gaps": len(gaps), "external_dependencies": len(externals)},
                    "gaps": gaps, "external_dependencies": externals}, indent=2), encoding="utf-8")
    (output_dir / "gaps_register.md").write_text(gaps_markdown(gaps, externals), encoding="utf-8")

    facts = collect_facts(sysname, inv, parser, data, logic, rules, gaps, externals)
    caps = capabilities_of(rules, inv, logic)
    fp = brd_fingerprint(sysname, logic, rules, gaps)
    brief = build_brief(facts, fp, inv, logic, rules, gaps, externals, caps)
    (output_dir / "brd_brief.json").write_text(json.dumps(brief, indent=2), encoding="utf-8")

    usage = {"in": 0, "out": 0}
    raw, mode = None, "templated (deterministic)"
    npath = narratives_path or output_dir / "brd_narratives.json"
    if npath.exists():
        raw, mode = load(npath), f"AI-host ({npath.name})"
    elif use_llm:
        import anthropic
        raw, mode = llm_narratives(anthropic.Anthropic(), model, brief, usage), f"LLM ({model})"

    base = templated_narratives(facts, caps, logic, rules)
    warnings: list[str] = []
    narr = dict(base)
    if raw:
        known = ({r["rule_id"] for r in rules.get("business_rules", [])}
                 | {r["rule_id"] for r in rules.get("technical_rules", [])}
                 | {s["rule_set_id"] for s in rules.get("rule_sets", [])}
                 | {g["gap_id"] for g in gaps})
        ai, warnings = validate_narratives(raw, fp, known, {c["name"] for c in caps},
                                           {r["rule_id"] for r in rules.get("business_rules", [])})
        if ai:
            narr.update({k: v for k, v in ai.items() if v})
        else:
            mode = "templated (deterministic) — AI narratives rejected"
    for w_ in warnings:
        print(f"[warn] {w_}", file=sys.stderr)

    out_root = output_dir.resolve()

    def rel(p: Path) -> str:
        try:
            return Path(os.path.relpath(Path(p).resolve(), out_root)).as_posix()
        except ValueError:
            return Path(p).name

    relpaths = {"data": rel(paths["data"]),
                "data_layouts": rel(Path(paths["data"]).parent / "data_layouts") + "/",
                "logic": rel(Path(paths["logic"]).parent / "program_logic") + "/"}
    brd = assemble_brd(facts, narr, mode, inv, parser, data, logic, rules, gaps, externals, caps,
                       diagrams_dir, relpaths)
    (output_dir / "brd.md").write_text(brd, encoding="utf-8")
    (output_dir / "brd_summary.md").write_text(brd_summary_md(facts, narr, caps, rules, gaps),
                                               encoding="utf-8")
    return {"facts": facts, "gaps": gaps, "mode": mode, "usage": usage, "warnings": warnings,
            "sections": sum(1 for line in brd.splitlines() if line.startswith("## ")),
            "pages_est": max(1, len(brd) // 2800)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 8 — hybrid BRD generator.")
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--parser", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--logic", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--output-dir", default="./outputs/final_report")
    ap.add_argument("--diagrams", default="./outputs/diagram")
    ap.add_argument("--system-name", default=None,
                    help="Display name (default: the analysed source folder's name)")
    ap.add_argument("--narratives", default=None,
                    help="AI-host prose JSON (default: <output-dir>/brd_narratives.json if present)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-llm", action="store_true", help="Never call the API.")
    args = ap.parse_args()

    load_dotenv(Path(__file__).resolve().parent.parent.parent)
    use_llm = (not args.no_llm) and bool(os.environ.get("ANTHROPIC_API_KEY"))
    out = Path(args.output_dir)
    npath = Path(args.narratives) if args.narratives else None
    if not use_llm and not (npath or out / "brd_narratives.json").exists():
        print("[note] No API key and no brd_narratives.json — using the neutral templated narrative. "
              "For AI prose without a key, have Claude Code write brd_narratives.json from "
              "brd_brief.json (see phases/p09_brd/brd_agent.md) and re-run.")

    paths = {k: getattr(args, k) for k in ("inventory", "parser", "data", "logic", "rules")}
    res = build(paths, out, args.system_name, args.model, use_llm, Path(args.diagrams), npath)

    f = res["facts"]
    print("=== BRD Agent Complete ===")
    print(f"System                 : {f['system_name']}")
    print(f"Chapters               : {res['sections']}  (~{res['pages_est']} pages)")
    print(f"Business rules         : {f['rules']}")
    print(f"Gaps identified        : {f['gaps']} ({f['high_gaps']} high/critical)")
    print(f"External dependencies  : {f['external_components']}")
    print(f"Narrative mode         : {res['mode']}")
    print(f"Output                 : {out / 'brd.md'}")
    print(f"AI-host brief          : {out / 'brd_brief.json'}")
    print("==========================")


if __name__ == "__main__":
    main()
