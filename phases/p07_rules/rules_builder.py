#!/usr/bin/env python3
"""
rules_builder.py  —  Phase 7: Rules phase (HYBRID).

Python port of the "5_rules" agent (condition-classifier + rule-tagger).

  Deterministic (Python, NO LLM):
    * collect every branch/condition from the Phase 6 logic files and every
      88-level condition from the Phase 5 data dictionary
    * classify each one (category, structural pattern, signal strength 1-5)
      -> outputs/rules/classified_conditions.json
    * split the significant ones (signal >= 2) into BUSINESS rules and
      TECHNICAL conditions (loop/EOF control, screen handling, input-edit flags,
      I/O status, ...) using COBOL/CICS idioms that hold for any codebase
    * deduplicate across programs; group business rules into rule sets
      (one per business capability, or one per program as the fallback)

  AI step (Claude Code AI-host with NO key, or the API when a key is set):
    * group programs into named business CAPABILITIES
    * write the business-readable rule NAME and DESCRIPTION, and confirm or
      correct the business/technical TIER of each candidate
    The builder always writes rules_brief.json (the facts the AI step needs) and
    applies rules_ai.json when present (the AI output). Without either, an
    honest templated fallback is used — names come from the condition itself.

  Output: outputs/rules/rules_artifact.json  (the business-rules catalogue)

Inputs
  --logic      outputs/logic/logic_artifact.json   (Phase 6; also reads program_logic/*.json)
  --data       outputs/data/data_artifact.json     (Phase 5; 88-level conditions + values)
  --inventory  outputs/discovery/inventory.json    (optional; program run modes + copybook users)
  --output-dir outputs/rules
  --ai-input   AI-host enrichment JSON (default: <output-dir>/rules_ai.json when it exists)
  --model      Claude model id (default env ANTHROPIC_MODEL or claude-opus-4-8)
  --no-llm     never call the API (AI-host file is still applied if present)

Usage
    python -m phases.p07_rules.rules_builder --logic outputs/logic/logic_artifact.json \
        --data outputs/data/data_artifact.json --inventory outputs/discovery/inventory.json \
        --output-dir outputs/rules
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
from typing import Optional

AGENT_VERSION = "rules_python@2.0"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

PRICING = {
    "claude-opus-4-8": (5.0, 25.0), "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0), "claude-sonnet-4-6": (3.0, 15.0),
}

# ---------------------------------------------------------------------------
# Classification signal tables (from Udara's condition-classifier)
# ---------------------------------------------------------------------------

ERR_KW = ("sqlcode", "file status", "status <", "status =", "status<>", "response",
          "resp", " rc", "return code", "return-code", "invalid key", "at end",
          "not found", "abend", "handle condition", "open failed", "write failed",
          "rollback", "error", "err ")
ROUTE_KW = ("evaluate function", "evaluate request", "evaluate command", "evaluate entry",
            "dispatch", "go to", "depending on", "menu", "option", "request type",
            "action", "command", "eibaid")
LIMIT_KW = ("limit", " max", " min", "thresh", "cap ", "ceiling", "floor", "overdraft",
            "balance", "amount", "frequency", "count >", "count <", "count >=", "retry",
            ">=", "<=", " > ", " < ")
CALC_KW = ("compute", "add ", "subtract", "multiply", "divide", "total", "accum",
           "rate", "interest", "tax", "fee ", "premium", "charge", "size error")
VALID_PARA_KW = ("validate", "edit", "check", "verify", "scrn", "screen")
COMPLIANCE_KW = ("audit", "security", " auth", "permission", "restrict", "regulatory",
                 "compliance", "log ")
VALID_FIELD_SUFFIX = ("-TYPE", "-CODE", "-STATUS", "-FLAG", "-IND", "-SW", "-CLASS", "-KIND")

CAT_VALIDATION = "VALIDATION"
CAT_CALCULATION = "CALCULATION"
CAT_ROUTING = "ROUTING"
CAT_LIMIT = "LIMIT_CHECK"
CAT_ERROR = "ERROR_HANDLING"
CAT_COMPLIANCE = "COMPLIANCE"

ABBREV = {
    "ACCT": "Account", "TRANS": "Transaction", "TRAN": "Transaction", "AMT": "Amount",
    "BAL": "Balance", "CUST": "Customer", "CARD": "Card", "STAT": "Status", "TYPE": "Type",
    "CD": "Code", "CODE": "Code", "NBR": "Number", "NUM": "Number",
    "DT": "Date", "DATE": "Date", "PMT": "Payment", "AUTH": "Authorization",
    "EXP": "Expiry", "LMT": "Limit", "LIMIT": "Limit", "CURR": "Current",
    "INT": "Interest", "FEE": "Fee", "CR": "Credit", "DR": "Debit", "CTR": "Counter",
    "MAX": "Maximum", "MIN": "Minimum", "RATE": "Rate", "IND": "Indicator",
    "FLAG": "Indicator", "FLG": "Indicator", "SW": "Indicator", "ERR": "Error",
    "RC": "Return Code", "RESP": "Response", "SEQ": "Sequence", "USR": "User",
    "USRTYP": "User Type", "DB2": "DB2", "SEC": "Security", "CURS": "Cursor",
    "CYC": "Cycle", "ADDR": "Address", "MSG": "Message", "FRD": "Fraud",
}

VERB = {
    CAT_VALIDATION: "Validate", CAT_CALCULATION: "Calculate", CAT_ROUTING: "Route",
    CAT_LIMIT: "Enforce", CAT_ERROR: "Handle", CAT_COMPLIANCE: "Flag",
}

# ---------------------------------------------------------------------------
# Business vs technical tiering — generic COBOL / CICS / IMS / MQ idioms
# ---------------------------------------------------------------------------

TIER_BUSINESS = "business"
TIER_TECHNICAL = "technical"

# (reason, patterns) — first match wins; patterns are regexes on the lower-cased text.
TECH_BRANCH_PATTERNS = [
    ("Loop and end-of-file control", (
        r"\bperform until\b", r"end-of-file", r"\beof\b", r"\bbof\b", r"end-of-db",
        r"end-of-input", r"no-more", r"\bloop\b", r"readnext", r"readprev", r"startbr",
        r"\(guard", r"top-of-db", r"page full", r"end-of-tiot", r"end-of-daily",
        r"perform varying", r"^\s*while\b")),
    ("Screen and session handling", (
        r"eibcalen", r"eibaid", r"\bpf\d", r"send (map|screen|menu)", r"first page",
        r"screen-array", r"screen-vars", r"one call per field", r"\bheaders?\b",
        r"\bxctl\b", r"first[- ]time", r"line-counter", r"page-size")),
    ("File, database and messaging status", (
        r"io-status", r"io-stat", r"-status\b", r"status '", r"mq get", r"no-message",
        r"m03b-", r"\btiot\b", r"\bucb\b", r"ws-fl-dd", r"sqlcode", r"\bims end\b",
        r"cbltdli", r"feedback severity", r"\b(declare|fetch|commit|rollback|cursor)\b",
        r"\bopen ok\b", r"\bconnected\b", r"\bretries\b")),
    ("Record persistence", (
        r"^\s*else\s+(re)?write", r"\brewrite\b", r"\(create\)", r"insert (root|child)",
        r"\bif (found|type exists) -> (rewrite|update)")),
    ("Program state and run parameters", (
        r"evaluate state", r"program state", r"\bdebug\b", r"field differs", r"!= baseline",
        r"evaluate ws-func", r"evaluate record type", r"\bbreak\)", r"chkp", r"checkpoint",
        r"evaluate (function|entry point|command|request type)\b")),
]

# 88-level names containing any of these tokens describe program mechanics.
TECH_88_STRONG = {
    "EOF", "BOF", "FOUND", "NFOUND", "ISVALID", "BLANK", "OPEN", "CLOSE", "CLSE", "READ",
    "WRITE", "REWRITE", "ERASE", "PFK", "AID", "DEBUG", "PSB", "SCHD", "SEGMENT", "QUEUE",
    "LOOP", "TIOT", "UCB", "HTML", "PAGE", "PROMPT", "INFORM", "MSG", "MESSAGE", "MESG",
    "ENTER", "REENTER", "CLEAR", "ERR", "ERROR", "CHANGES", "CHANGE", "CHANGED", "FETCHED",
    "SHOW", "SELECT", "REQUESTED", "DB", "DATABASE", "EXIT", "RETURN", "CONTEXT", "SCREEN",
    "INPUT", "FEEDBACK", "TOKEN", "OPER", "APPL", "FUNCTION", "FUNC", "DB2", "SQL", "CURSOR",
}
# Decision words — an 88-level carrying one of these is a business outcome.
DECISION_WORDS = {
    "APPROVE", "APPROVED", "DECLINE", "DECLINED", "REJECT", "REJECTED", "ACCEPT", "ACCEPTED",
    "FRAUD", "EXPIRED", "CLOSED", "ACTIVE", "INACTIVE", "SUSPENDED", "PENDING", "OVERDUE",
    "DELINQUENT", "INSUFFICIENT", "BLOCKED", "CANCELLED", "QUALIFIED", "ELIGIBLE", "ADMIN",
    "MATCHED", "DISPUTED", "OVERLIMIT",
}
TRIVIAL_88_VALUES = {"'Y'", "'N'", "'0'", "'1'", "0", "1", "SPACES", "SPACE", "LOW-VALUES",
                     "HIGH-VALUES", "ZERO", "ZEROS", "ZEROES", "TRUE", "FALSE", "' '", "''"}


def load_dotenv(base: Path) -> None:
    env = base / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Step 1 (deterministic) — collect conditions
# ---------------------------------------------------------------------------

def collect_conditions(logic_path: Path, data_path: Path,
                       copybook_users: Optional[dict] = None) -> list[dict]:
    conds: list[dict] = []
    logic_dir = logic_path.parent
    logic = load_json(logic_path)
    programs = {p["program_id"] for p in logic.get("programs", [])}
    copybook_users = copybook_users or {}

    for prog in logic.get("programs", []):
        pid = prog["program_id"]
        lf = logic_dir / prog.get("logic_file", f"program_logic/{pid}_logic.json")
        if not lf.exists():
            continue
        pl = load_json(lf)
        for para in pl.get("paragraphs", []):
            pname = para.get("name")
            line = (para.get("line_range") or [None])[0]
            fields = para.get("field_references", []) or []
            for i, branch in enumerate(para.get("branches", []) or [], start=1):
                conds.append({
                    "condition_id": f"COND-{pid}-{pname}-{i}",
                    "program_id": pid, "paragraph": pname, "source_line": line,
                    "condition_text": branch, "fields": fields, "is_88": False,
                })

    data = load_json(data_path)
    seen_ids: set[str] = set()
    for fld in data.get("fields", []):
        cnd = fld.get("conditions")
        if not cnd:
            continue
        src = fld.get("source") or ""
        # Programs that use this 88-level: the data dictionary's list, else the
        # defining program, else every program that COPYs the defining copybook.
        users = [u for u in (fld.get("used_by") or []) if u in programs] \
            or ([src] if src in programs else sorted(copybook_users.get(src, [])))
        cid = f"COND88-{src}-{fld.get('name')}"
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        conds.append({
            "condition_id": cid,
            "program_id": users[0] if users else None,
            "paragraph": None, "source_line": fld.get("line"), "defined_in": src,
            "condition_text": f"88-level values on {fld.get('name')}: " + ", ".join(cnd.keys()),
            "fields": [fld.get("name")], "is_88": True,
            "field_name": fld.get("name"), "values": list(cnd.keys()),
            "value_literals": cnd, "used_by": users,
        })
    return conds


# ---------------------------------------------------------------------------
# Step 2 (deterministic) — classify each condition
# ---------------------------------------------------------------------------

def _has(kws, text):
    return any(k in text for k in kws)


def classify(c: dict) -> dict:
    text = (c["condition_text"] or "").lower()
    para = (c.get("paragraph") or "").lower()
    fields_up = " ".join(c.get("fields", [])).upper()

    # structural pattern
    if c["is_88"]:
        pattern = "CONDITION_NAME"
    elif "evaluate" in text or "select case" in text:
        pattern = "SET_MEMBERSHIP"
    elif " and " in text or " or " in text:
        pattern = "MULTI_CONDITION"
    elif any(op in text for op in (">=", "<=", " > ", " < ")):
        pattern = "RANGE_CHECK"
    elif "zero" in text or "spaces" in text or "low-values" in text or "empty" in text:
        pattern = "NULL_ZERO_CHECK"
    elif "sqlcode" in text or "status" in text or "resp" in text:
        pattern = "STATUS_CODE_CHECK"
    else:
        pattern = "FIELD_VALUE_COMPARE"
    if text.strip().startswith("not") or " not " in text:
        pattern = "NEGATION"

    # category + signal
    if c["is_88"]:
        category, signal = CAT_VALIDATION, 5
    elif _has(ERR_KW, text) and not _has(("limit", "balance", "amount", "credit"), text):
        category, signal = CAT_ERROR, 1
    elif _has(("evaluate function", "evaluate request", "evaluate command",
               "evaluate entry", "depending on", "go to"), text):
        category, signal = CAT_ROUTING, 4
    elif _has(("limit", "overdraft", "credit", "threshold", "frequency", "retry",
               "balance", "amount"), text) and _has((">=", "<=", " > ", " < ", "reached", "exceed"), text):
        category, signal = CAT_LIMIT, 4
    elif _has(COMPLIANCE_KW, text) or _has(COMPLIANCE_KW, para):
        category, signal = CAT_COMPLIANCE, 3
    elif _has(CALC_KW, text) or _has(CALC_KW, para):
        category, signal = CAT_CALCULATION, 3
    elif _has(VALID_PARA_KW, para) or any(fields_up.find(s) >= 0 for s in VALID_FIELD_SUFFIX):
        category, signal = CAT_VALIDATION, 3
    elif "evaluate" in text:
        category, signal = CAT_ROUTING, 4
    else:
        category, signal = CAT_VALIDATION, 2

    c["category"] = category
    c["structural_pattern"] = pattern
    c["signal_strength"] = signal
    c["signal_label"] = {5: "certain", 4: "high", 3: "medium", 2: "low", 1: "noise"}[signal]
    return c


def _tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^A-Z0-9]+", (name or "").upper()) if t}


def _has_domain_values(literals: dict) -> bool:
    """True when an 88-level encodes a real domain constraint (a value list or range)."""
    vals: list[str] = []
    for v in literals.values():
        s = str(v).strip().upper()
        if re.search(r"\bTHRU\b|\bTHROUGH\b", s):
            lo_hi = re.findall(r"-?\d+", s)
            if len(lo_hi) >= 2 and lo_hi[:2] not in (["0", "1"], ["0", "9"]):
                return True
        vals += [x.strip() for x in s.split(",") if x.strip()]
    meaningful = {v for v in vals if v not in TRIVIAL_88_VALUES}
    return len(meaningful) >= 3


def tier_of(c: dict) -> tuple[str, str]:
    """First-pass business/technical split (the AI step may correct it)."""
    if c["is_88"]:
        name_tokens = [_tokens(n) for n in c.get("values", [])]
        # A field named for mechanics (…-MSG, …-FEEDBACK, …-REQUESTED) is technical.
        if _tokens(c.get("field_name")) & TECH_88_STRONG:
            return TIER_TECHNICAL, "Program flags and status switches"
        # A decision word counts only in a condition name free of mechanics vocabulary
        # (so APPROVE-AUTH is business, INPUT-PENDING is not).
        if any(toks & DECISION_WORDS and not toks & TECH_88_STRONG for toks in name_tokens):
            return TIER_BUSINESS, ""
        if any(toks & TECH_88_STRONG for toks in name_tokens):
            return TIER_TECHNICAL, "Program flags and status switches"
        if _has_domain_values(c.get("value_literals") or {}):
            return TIER_BUSINESS, ""
        return TIER_TECHNICAL, "Program flags and status switches"
    text = (c["condition_text"] or "").lower()
    # An IF that tests a business decision (approve / decline / fraud / admin ...)
    # outranks the mechanics (e.g. the XCTL) that carry it out.
    if text.lstrip().startswith("if ") and _tokens(text) & DECISION_WORDS:
        return TIER_BUSINESS, ""
    for reason, patterns in TECH_BRANCH_PATTERNS:
        if any(re.search(p, text) for p in patterns):
            return TIER_TECHNICAL, reason
    return TIER_BUSINESS, ""


# ---------------------------------------------------------------------------
# Step 3 (deterministic) — templated naming / dedup / grouping / confidence
# ---------------------------------------------------------------------------

def business_name(field: str) -> str:
    if not field:
        return "value"
    f = re.sub(r"^(WS|WRK|IO|DB|LS|LK)-", "", field.upper())
    f = re.sub(r"^EDIT-|-(N|X|TO-EDIT)$", "", f)  # edit-buffer / numeric-view noise
    parts = [ABBREV.get(p, p.capitalize()) for p in f.split("-") if p]
    return " ".join(parts) if parts else field


def _values_text(literals: dict, limit: int = 6) -> str:
    items = [f"{k} = {str(v).strip()}" for k, v in list(literals.items())[:limit]]
    more = len(literals) - limit
    return "; ".join(items) + (f"; and {more} further defined values" if more > 0 else "")


def _sentence(text: str) -> str:
    """Tidy a pseudocode branch into a readable rule statement (no invention)."""
    s = re.sub(r"\s+", " ", (text or "").strip()).replace("->", "→")
    return s[:1].upper() + s[1:] if s else s


def templated_rule(c: dict) -> dict:
    """Honest fallback wording: derived from the condition itself, never from an
    unrelated field, so it can be plain but never wrong."""
    where = (f"{c['program_id']}" + (f", paragraph {c['paragraph']}" if c.get("paragraph") else "")
             if c.get("program_id") else (c.get("defined_in") or "the data dictionary"))
    if c["is_88"]:
        subj = business_name(c.get("field_name", ""))
        name = f"Allowed values for {subj}"
        desc = (f"{subj} ({c.get('field_name')}) is restricted to the defined values: "
                f"{_values_text(c.get('value_literals') or {})}. Defined in {c.get('defined_in') or where}"
                + (f"; used by {', '.join(c.get('used_by', [])[:5])}." if c.get("used_by") else "."))
    else:
        stmt = _sentence(c["condition_text"])
        name = stmt
        desc = f"{VERB.get(c['category'], 'Check')} rule: “{stmt}”. Implemented in {where}."
    conf = {5: "confirmed", 4: "high", 3: "medium", 2: "low"}[c["signal_strength"]]
    return {"name": name, "description": desc, "confidence": conf,
            "requires_sme_review": c["signal_strength"] <= 2}


def dedup_key(c: dict) -> str:
    if c["is_88"]:
        vals = json.dumps(c.get("value_literals") or {}, sort_keys=True)
        return f"88|{c.get('field_name')}|{vals}"
    norm = re.sub(r"\s+", " ", (c["condition_text"] or "").lower()).strip()
    return f"{c['category']}|{norm}"


def merge_candidates(classified: list[dict]) -> list[dict]:
    """Promote signal >= 2, tier them, and merge duplicates across programs."""
    merged: dict[str, dict] = {}
    for c in classified:
        if c["signal_strength"] < 2:
            continue
        progs = c.get("used_by") if c["is_88"] else [c["program_id"]]
        progs = [p for p in (progs or []) if p]
        src = {"program_id": c.get("program_id"), "paragraph": c.get("paragraph"),
               "line": c.get("source_line"), "condition_id": c["condition_id"]}
        k = dedup_key(c)
        if k in merged:
            m = merged[k]
            m["sources"].append(src)
            for p in progs:
                if p not in m["programs"]:
                    m["programs"].append(p)
            continue
        tier, reason = tier_of(c)
        merged[k] = {"cond": c, "tier": tier, "technical_reason": reason,
                     "programs": list(progs), "sources": [src]}
    return list(merged.values())


# ---------------------------------------------------------------------------
# AI step — brief (facts in) / enrichment (AI output) contract
# ---------------------------------------------------------------------------

def fingerprint(program_ids: list[str], candidate_ids: list[str]) -> str:
    h = hashlib.sha1("\n".join(sorted(program_ids) + ["--"] + sorted(candidate_ids)).encode())
    return h.hexdigest()[:16]


def build_brief(logic: dict, inventory: dict, candidates: list[dict]) -> dict:
    subtype = {e["id"]: e for e in inventory.get("file_registry", [])}
    programs = []
    for p in logic.get("programs", []):
        e = subtype.get(p["program_id"], {})
        programs.append({"program_id": p["program_id"], "run_mode": e.get("subtype"),
                         "runtime": e.get("runtime", []), "summary": p.get("summary", "")})
    cands = []
    for m in candidates:
        c = m["cond"]
        item = {"condition_id": c["condition_id"], "programs": m["programs"],
                "paragraph": c.get("paragraph"), "category": c["category"],
                "first_pass_tier": m["tier"], "text": c["condition_text"]}
        if c["is_88"]:
            item["field"] = c.get("field_name")
            item["values"] = c.get("value_literals")
        cands.append(item)
    pids = [p["program_id"] for p in programs]
    return {
        "meta": {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "agent_version": AGENT_VERSION,
                 "fingerprint": fingerprint(pids, [c["condition_id"] for c in cands]),
                 "programs": len(programs), "candidates": len(cands)},
        "instructions": (
            "Write rules_ai.json next to this file (see phases/p07_rules/rules_agent.md). "
            "Copy meta.fingerprint. 1) capabilities: group EVERY program into a named business "
            "capability (name, 1-2 sentence description, programs). 2) rules: keyed by "
            "condition_id — for each candidate give tier ('business'|'technical'); for business "
            "rules also a name (imperative, business language) and a 1-3 sentence description "
            "grounded ONLY in the text/values shown. Never invent thresholds, outcomes or ids."),
        "programs": programs,
        "candidates": cands,
    }


def validate_enrichment(ai: dict, brief: dict) -> tuple[dict, list[str]]:
    """Keep only what refers to real programs / candidates; report everything dropped."""
    warnings: list[str] = []
    if ai.get("meta", {}).get("fingerprint") != brief["meta"]["fingerprint"]:
        return {}, ["AI enrichment ignored: fingerprint does not match this codebase/run "
                    "(regenerate it from the current rules_brief.json)."]
    pids = {p["program_id"] for p in brief["programs"]}
    cids = {c["condition_id"] for c in brief["candidates"]}

    caps, assigned = [], set()
    for cap in ai.get("capabilities", []) or []:
        name = str(cap.get("name", "")).strip()
        progs = []
        for p in cap.get("programs", []) or []:
            if p not in pids:
                warnings.append(f"capability '{name}': unknown program {p} dropped")
            elif p in assigned:
                warnings.append(f"capability '{name}': {p} already assigned — dropped")
            else:
                progs.append(p)
                assigned.add(p)
        if name and progs:
            caps.append({"name": name, "description": str(cap.get("description", "")).strip(),
                         "programs": progs})

    rules = {}
    for cid, r in (ai.get("rules", {}) or {}).items():
        if cid not in cids:
            warnings.append(f"rule for unknown condition {cid} dropped")
            continue
        entry = {}
        if r.get("tier") in (TIER_BUSINESS, TIER_TECHNICAL):
            entry["tier"] = r["tier"]
        for k in ("name", "description"):
            if isinstance(r.get(k), str) and r[k].strip():
                entry[k] = r[k].strip()
        rules[cid] = entry
    return {"capabilities": caps, "rules": rules, "mode": ai.get("meta", {}).get("mode")}, warnings


LLM_SYSTEM = (
    "You are a COBOL business-rules analyst. You receive a brief with every program (id, run "
    "mode, plain-English summary) and every candidate rule (condition text or 88-level values, "
    "programs, paragraph, first-pass tier). Return JSON: capabilities — group every program into "
    "a named business capability; rules — keyed by condition_id with tier ('business' for "
    "decisions/constraints a business owner would recognise, 'technical' for program mechanics) "
    "and, for business rules, an imperative business-language name and a 1-3 sentence "
    "description. Use only facts in the brief; never invent thresholds, outcomes or ids."
)


def llm_enrichment(client, model: str, brief: dict, usage_acc: dict) -> dict:
    schema = {"type": "object", "properties": {
        "capabilities": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "description": {"type": "string"},
            "programs": {"type": "array", "items": {"type": "string"}}},
            "required": ["name", "description", "programs"], "additionalProperties": False}},
        "rules": {"type": "array", "items": {"type": "object", "properties": {
            "condition_id": {"type": "string"}, "tier": {"type": "string"},
            "name": {"type": "string"}, "description": {"type": "string"}},
            "required": ["condition_id", "tier", "name", "description"],
            "additionalProperties": False}}},
        "required": ["capabilities", "rules"], "additionalProperties": False}
    resp = client.messages.create(
        model=model, max_tokens=32000, system=LLM_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(
            {"programs": brief["programs"], "candidates": brief["candidates"]}, indent=1)}],
        output_config={"format": {"type": "json_schema", "schema": schema}})
    text = next((b.text for b in resp.content if b.type == "text"), "")
    usage_acc["in"] += resp.usage.input_tokens
    usage_acc["out"] += resp.usage.output_tokens
    data = json.loads(text)
    return {"meta": {"fingerprint": brief["meta"]["fingerprint"], "mode": f"LLM ({model})"},
            "capabilities": data.get("capabilities", []),
            "rules": {r["condition_id"]: r for r in data.get("rules", [])}}


# ---------------------------------------------------------------------------
# Step 4 — assemble the catalogue
# ---------------------------------------------------------------------------

def _first_sentence(summary: str) -> str:
    """Whole first sentence (never cut mid-way), minus a trailing parenthetical note."""
    s = re.sub(r"\s+", " ", (summary or "").strip())
    m = re.search(r"(?<!\be\.g)(?<!\bi\.e)(?<!\betc)\.(\s+[A-Z(]|$)", s)
    s = s[:m.start()] if m else s.rstrip(".")
    return re.sub(r"\s*\([^()]*\)\s*$", "", s).replace(" -- ", " — ").strip()


def build_rules(classified: list[dict], candidates: list[dict], logic: dict,
                enrichment: dict) -> dict:
    ai_rules = enrichment.get("rules", {})
    program_order = [p["program_id"] for p in logic.get("programs", [])]
    summaries = {p["program_id"]: p.get("summary", "") for p in logic.get("programs", [])}

    # Capability of each program: AI grouping, else one rule set per program.
    cap_of: dict[str, str] = {}
    capabilities = []
    for cap in enrichment.get("capabilities", []):
        capabilities.append(dict(cap))
        for p in cap["programs"]:
            cap_of[p] = cap["name"]
    unassigned = [p for p in program_order if p not in cap_of]
    if capabilities and unassigned:
        capabilities.append({"name": "Other programs", "description": "", "programs": unassigned})
        for p in unassigned:
            cap_of[p] = "Other programs"
    if not capabilities:
        for p in program_order:
            title = _first_sentence(summaries.get(p, ""))
            name = f"{p} — {title}" if title else p
            capabilities.append({"name": name, "description": summaries.get(p, ""), "programs": [p]})
            cap_of[p] = name
    cap_rank = {c["name"]: i for i, c in enumerate(capabilities)}

    business, technical = [], []
    for m in candidates:
        c = m["cond"]
        ai = ai_rules.get(c["condition_id"], {})
        tier = ai.get("tier", m["tier"])
        info = templated_rule(c)
        primary = m["sources"][0]
        base = {
            "category": c["category"],
            "condition": {"text": c["condition_text"], "pattern": c["structural_pattern"]},
            "implemented_in_programs": m["programs"],
            "primary_source": primary, "sources": m["sources"],
            "is_duplicated": len(m["sources"]) > 1,
        }
        if c["is_88"]:
            base["condition"]["field"] = c.get("field_name")
            base["condition"]["values"] = c.get("value_literals")
            base["defined_in"] = c.get("defined_in")
        if tier == TIER_TECHNICAL:
            technical.append({**base, "rule_id": "", "reason": m["technical_reason"]
                              or "Reclassified as technical by the AI review",
                              "name": info["name"]})
            continue
        owner = next((p for p in m["programs"] if p in cap_of), None)
        business.append({**base, "rule_id": "",
                         "rule_set": cap_of.get(owner, "Shared definitions"),
                         "name": ai.get("name", info["name"]),
                         "description": ai.get("description", info["description"]),
                         "wording": "ai" if ai.get("name") else "templated",
                         "confidence": info["confidence"],
                         "requires_sme_review": info["requires_sme_review"]})

    def src_rank(r):
        p = r["primary_source"].get("program_id")
        return program_order.index(p) if p in program_order else len(program_order)

    business.sort(key=lambda r: (cap_rank.get(r["rule_set"], len(cap_rank)), src_rank(r),
                                 r["primary_source"].get("condition_id") or ""))
    for i, r in enumerate(business, start=1):
        r["rule_id"] = f"BR-{i:03d}"
    technical.sort(key=lambda r: (r["reason"], src_rank(r)))
    for i, r in enumerate(technical, start=1):
        r["rule_id"] = f"TR-{i:03d}"

    # Rule sets = capabilities that own at least one business rule (plus shared definitions).
    set_members: dict[str, list[dict]] = {}
    for r in business:
        set_members.setdefault(r["rule_set"], []).append(r)
    ordered = [c for c in capabilities if c["name"] in set_members]
    if "Shared definitions" in set_members:
        ordered.append({"name": "Shared definitions", "description": "", "programs": []})
    rule_sets = []
    for i, cap in enumerate(ordered, start=1):
        members = set_members[cap["name"]]
        progs = sorted({p for r in members for p in r["implemented_in_programs"]})
        rule_sets.append({"rule_set_id": f"RS-{i:03d}", "name": cap["name"],
                          "description": cap.get("description", ""),
                          "rule_count": len(members), "rule_ids": [r["rule_id"] for r in members],
                          "programs": progs})

    error_catalogue = [
        {"error_id": f"EH-{i:03d}", "condition_text": c["condition_text"],
         "program_id": c["program_id"], "paragraph": c.get("paragraph"), "line": c.get("source_line")}
        for i, c in enumerate((x for x in classified if x["signal_strength"] == 1), start=1)
    ]

    def count(items, key):
        out: dict[str, int] = {}
        for it in items:
            out[it[key]] = out.get(it[key], 0) + 1
        return out

    rules_by_prog: dict[str, list[str]] = {}
    for r in business:
        for p in r["implemented_in_programs"]:
            rules_by_prog.setdefault(p, []).append(r["rule_id"])

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_version": AGENT_VERSION, "total_rules": len(business),
            "total_rule_sets": len(rule_sets), "technical_conditions": len(technical),
            "requires_sme_review": sum(1 for r in business if r["requires_sme_review"]),
            "duplicates_merged": sum(len(m["sources"]) - 1 for m in candidates),
            "ai_worded_rules": sum(1 for r in business if r["wording"] == "ai"),
            "capability_source": "ai" if enrichment.get("capabilities") else "per-program fallback",
        },
        "stats": {"by_category": count(business, "category"),
                  "by_confidence": count(business, "confidence"),
                  "technical_by_reason": count(technical, "reason"),
                  "noise_conditions": len(error_catalogue)},
        "capabilities": capabilities,
        "rule_sets": rule_sets,
        "business_rules": business,
        "technical_rules": technical,
        "error_handling_catalogue": error_catalogue,
        "rules_by_program": rules_by_prog,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build(logic_path: Path, data_path: Path, output_dir: Path, model: str, use_llm: bool,
          inventory_path: Optional[Path] = None, ai_input: Optional[Path] = None) -> tuple[dict, dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory = load_json(inventory_path) if inventory_path and inventory_path.exists() else {}
    logic = load_json(logic_path)

    conds = collect_conditions(logic_path, data_path,
                               {k: set(v) for k, v in inventory.get("copybook_map", {}).items()})
    for c in conds:
        classify(c)

    by_category: dict[str, int] = {}
    for c in conds:
        by_category[c["category"]] = by_category.get(c["category"], 0) + 1
    classified_doc = {
        "meta": {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "agent_version": AGENT_VERSION,
                 "total_conditions_classified": len(conds),
                 "noise_excluded": sum(1 for c in conds if c["signal_strength"] == 1)},
        "classified_conditions": conds, "by_category": by_category,
    }
    (output_dir / "classified_conditions.json").write_text(
        json.dumps(classified_doc, indent=2), encoding="utf-8")

    candidates = merge_candidates(conds)
    brief = build_brief(logic, inventory, candidates)
    (output_dir / "rules_brief.json").write_text(json.dumps(brief, indent=2), encoding="utf-8")

    usage_acc = {"in": 0, "out": 0}
    raw_ai, mode = None, "templated (deterministic)"
    ai_path = ai_input or output_dir / "rules_ai.json"
    if ai_path.exists():
        raw_ai, mode = load_json(ai_path), f"AI-host ({ai_path.name})"
    elif use_llm:
        import anthropic
        raw_ai = llm_enrichment(anthropic.Anthropic(), model, brief, usage_acc)
        mode = f"LLM ({model})"

    enrichment, warnings = validate_enrichment(raw_ai, brief) if raw_ai else ({}, [])
    if raw_ai and not enrichment:
        mode = "templated (deterministic) — AI enrichment rejected"
    for w in warnings:
        print(f"[warn] {w}", file=sys.stderr)

    artifact = build_rules(conds, candidates, logic, enrichment)
    artifact["meta"]["description_mode"] = mode
    artifact["meta"]["ai_warnings"] = warnings
    if usage_acc["in"] or usage_acc["out"]:
        in_p, out_p = PRICING.get(model, (5.0, 25.0))
        artifact["meta"]["usage"] = {
            "input_tokens": usage_acc["in"], "output_tokens": usage_acc["out"],
            "estimated_cost_usd": round(usage_acc["in"] / 1e6 * in_p + usage_acc["out"] / 1e6 * out_p, 4)}
    (output_dir / "rules_artifact.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return classified_doc, artifact


def print_summary(classified: dict, artifact: dict, out: Path) -> None:
    s, m = artifact["stats"], artifact["meta"]
    print("=== Rules Agent Complete ===")
    print(f"Conditions classified : {classified['meta']['total_conditions_classified']}")
    print(f"Noise (error-handling): {classified['meta']['noise_excluded']}")
    print(f"Business rules         : {m['total_rules']}  (AI-worded: {m['ai_worded_rules']})")
    for cat, n in sorted(s["by_category"].items()):
        print(f"   {cat:<16}: {n}")
    print(f"Technical conditions   : {m['technical_conditions']}")
    for reason, n in sorted(s["technical_by_reason"].items()):
        print(f"   {reason:<38}: {n}")
    print(f"Rule sets              : {m['total_rule_sets']}  ({m['capability_source']})")
    print(f"Duplicates merged      : {m['duplicates_merged']}")
    print(f"Needs SME review       : {m['requires_sme_review']}")
    print(f"Description mode       : {m['description_mode']}")
    if "usage" in m:
        print(f"Estimated cost         : ${m['usage']['estimated_cost_usd']}")
    print(f"Output                 : {out}")
    print(f"AI-host brief          : {out.parent / 'rules_brief.json'}")
    print("============================")


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 7 — hybrid COBOL business-rules builder.")
    ap.add_argument("--logic", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--inventory", default=None, help="inventory.json (run modes, copybook users)")
    ap.add_argument("--output-dir", default="./outputs/rules")
    ap.add_argument("--ai-input", default=None,
                    help="AI-host enrichment JSON (default: <output-dir>/rules_ai.json if present)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-llm", action="store_true", help="Never call the API.")
    args = ap.parse_args()

    base_dir = Path(__file__).resolve().parent.parent.parent
    load_dotenv(base_dir)

    use_llm = (not args.no_llm) and bool(os.environ.get("ANTHROPIC_API_KEY"))
    out = Path(args.output_dir)
    ai_input = Path(args.ai_input) if args.ai_input else None
    if not use_llm and not (ai_input or out / "rules_ai.json").exists():
        print("[note] No API key and no rules_ai.json — using templated wording. For AI wording "
              "without a key, have Claude Code write rules_ai.json from rules_brief.json "
              "(see phases/p07_rules/rules_agent.md) and re-run.")

    classified, artifact = build(Path(args.logic).resolve(), Path(args.data).resolve(), out,
                                 args.model, use_llm,
                                 Path(args.inventory).resolve() if args.inventory else None,
                                 ai_input)
    print_summary(classified, artifact, out / "rules_artifact.json")


if __name__ == "__main__":
    main()
