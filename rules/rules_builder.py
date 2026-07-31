#!/usr/bin/env python3
"""
rules_builder.py  —  Phase 7: Rules phase (HYBRID).

Python port of the "5_rules" agent (condition-classifier + rule-tagger).

  Deterministic (Python, NO LLM):
    * collect every branch/condition from the Phase 6 logic files and every
      88-level condition from the Phase 5 data dictionary
    * classify each one (category, structural pattern, signal strength 1-5)
      -> outputs/rules/classified_conditions.json
    * promote the significant ones (signal >= 2), deduplicate them across
      programs, and group them into rule sets

  LLM (the paid step — only if a key is available, else a templated fallback):
    * write the business-readable rule NAME and DESCRIPTION for each rule
      grounded in the condition + its source

  Output: outputs/rules/rules_artifact.json  (the business-rules catalogue)

Inputs
  --logic   outputs/logic/logic_artifact.json   (Phase 6; also reads program_logic/*.json)
  --data    outputs/data/data_artifact.json     (Phase 5; 88-level conditions + field types)
  --output-dir  outputs/rules
  --model   Claude model id (default env ANTHROPIC_MODEL or claude-opus-4-8)
  --no-llm  force the deterministic templated fallback (no API call)

Usage
    python -m rules.rules_builder --logic outputs/logic/logic_artifact.json \
        --data outputs/data/data_artifact.json --output-dir outputs/rules
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

AGENT_VERSION = "5_rules_python@1.0"
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
    "ACCT": "Account", "TRANS": "Transaction", "AMT": "Amount", "BAL": "Balance",
    "CUST": "Customer", "CARD": "Card", "STAT": "Status", "TYPE": "Type",
    "CD": "Code", "CODE": "Code", "NBR": "Number", "NUM": "Number", "NO": "Number",
    "DT": "Date", "DATE": "Date", "PMT": "Payment", "AUTH": "Authorisation",
    "EXP": "Expiry", "LMT": "Limit", "LIMIT": "Limit", "CURR": "Currency",
    "INT": "Interest", "FEE": "Fee", "CR": "Credit", "DR": "Debit", "CTR": "Counter",
    "MAX": "Maximum", "MIN": "Minimum", "RATE": "Rate", "IND": "Indicator",
    "FLAG": "Indicator", "SW": "Indicator", "ERR": "Error", "RC": "Response",
    "RESP": "Response", "PORT": "Portfolio", "POS": "Position", "SEQ": "Sequence",
    "PROC": "Process", "BCT": "Batch Control", "PSR": "Process Sequence",
    "CK": "Checkpoint", "DB2": "DB2", "SEC": "Security", "CURS": "Cursor",
}

VERB = {
    CAT_VALIDATION: "Validate", CAT_CALCULATION: "Calculate", CAT_ROUTING: "Route",
    CAT_LIMIT: "Enforce", CAT_ERROR: "Handle", CAT_COMPLIANCE: "Flag",
}


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

def collect_conditions(logic_path: Path, data_path: Path) -> list[dict]:
    conds: list[dict] = []
    logic_dir = logic_path.parent
    logic = load_json(logic_path)

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
    for fld in data.get("fields", []):
        cnd = fld.get("conditions")
        if not cnd:
            continue
        conds.append({
            "condition_id": f"COND88-{fld.get('name')}",
            "program_id": (fld.get("used_by") or ["?"])[0],
            "paragraph": None, "source_line": fld.get("line"),
            "condition_text": f"88-level values on {fld.get('name')}: " + ", ".join(cnd.keys()),
            "fields": [fld.get("name")], "is_88": True,
            "field_name": fld.get("name"), "values": list(cnd.keys()),
            "used_by": fld.get("used_by") or [],
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
    elif "evaluate" in text or "select case" in text or "/" in text and "evaluate" in text:
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
        if any(s in fields_up for s in ("-STAT", "STATUS", "-PHASE", "-MODE")):
            category = CAT_VALIDATION
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


# ---------------------------------------------------------------------------
# Step 3 (deterministic) — templated naming / dedup / grouping / confidence
# ---------------------------------------------------------------------------

def business_name(field: str) -> str:
    if not field:
        return "value"
    f = re.sub(r"^(WS|WRK|IO|DB|PROC|LS|BCT|CK|PSR)-", "", field.upper())
    parts = [ABBREV.get(p, p.capitalize()) for p in f.split("-") if p]
    return " ".join(parts) if parts else field


def templated_rule(c: dict) -> dict:
    subj = (c.get("field_name") or (c["fields"][0] if c.get("fields") else "")) or ""
    verb = VERB.get(c["category"], "Check")
    if c["is_88"]:
        name = f"Validate {business_name(subj)} is a recognised value"
        desc = (f"The {business_name(subj)} field is constrained to a fixed set of allowed "
                f"values ({', '.join(c.get('values', [])[:6])}). Used by "
                f"{', '.join(c.get('used_by', [])[:4])}.")
    elif c["category"] == CAT_ROUTING:
        name = f"Route processing by {business_name(subj) or 'request type'}"
        desc = (f"The system selects a processing path based on the condition "
                f"“{c['condition_text']}”. Implemented in {c['program_id']}"
                + (f", paragraph {c['paragraph']}." if c.get("paragraph") else "."))
    elif c["category"] == CAT_LIMIT:
        name = f"Enforce {business_name(subj) or 'value'} limit"
        desc = (f"Enforces a threshold: “{c['condition_text']}”. Implemented in "
                f"{c['program_id']}" + (f", paragraph {c['paragraph']}." if c.get("paragraph") else "."))
    else:
        name = f"{verb} {business_name(subj) or 'condition'}"
        desc = (f"{name}. Condition: “{c['condition_text']}”. Implemented in "
                f"{c['program_id']}" + (f", paragraph {c['paragraph']}." if c.get("paragraph") else "."))
    conf = {5: "confirmed", 4: "high", 3: "medium", 2: "low"}[c["signal_strength"]]
    return {"name": name, "description": desc, "confidence": conf,
            "requires_sme_review": c["signal_strength"] <= 2}


def dedup_key(c: dict) -> str:
    subj = (c.get("field_name") or (c["fields"][0] if c.get("fields") else "")) or ""
    return f"{c['category']}|{c['structural_pattern']}|{subj}|{c['condition_text'][:40]}"


def rule_set_for(c: dict) -> str:
    subj = (c.get("field_name") or (c["fields"][0] if c.get("fields") else "")) or ""
    bn = business_name(subj).split(" ")[0] if subj else ""
    if c["category"] == CAT_ROUTING:
        return "Transaction routing rules"
    if c["category"] == CAT_LIMIT:
        return "Limit and threshold rules"
    if c["category"] == CAT_COMPLIANCE:
        return "Compliance and audit rules"
    if c["category"] == CAT_CALCULATION:
        return "Calculation rules"
    return f"{bn} validation rules" if bn else "General validation rules"


def build_rules(classified: list[dict], describe) -> dict:
    promoted = [c for c in classified if c["signal_strength"] >= 2]
    merged: dict[str, dict] = {}
    for c in promoted:
        k = dedup_key(c)
        src = {"program_id": c["program_id"], "paragraph": c.get("paragraph"),
               "line": c.get("source_line"), "condition_id": c["condition_id"]}
        if k in merged:
            merged[k]["sources"].append(src)
            if c["program_id"] not in merged[k]["implemented_in_programs"]:
                merged[k]["implemented_in_programs"].append(c["program_id"])
            merged[k]["is_duplicated"] = True
        else:
            info = describe(c)
            merged[k] = {
                "rule_id": "", "rule_set": rule_set_for(c), "name": info["name"],
                "category": c["category"], "confidence": info["confidence"],
                "requires_sme_review": info["requires_sme_review"],
                "description": info["description"],
                "condition": {"text": c["condition_text"], "pattern": c["structural_pattern"]},
                "is_duplicated": False,
                "implemented_in_programs": [c["program_id"]],
                "primary_source": src, "sources": [src],
            }

    rules = list(merged.values())
    rules.sort(key=lambda r: (r["rule_set"], r["name"]))
    for i, r in enumerate(rules, start=1):
        r["rule_id"] = f"BR-{i:03d}"

    # rule sets
    sets: dict[str, dict] = {}
    for r in rules:
        s = sets.setdefault(r["rule_set"], {"name": r["rule_set"], "rule_ids": [], "programs": set()})
        s["rule_ids"].append(r["rule_id"])
        s["programs"].update(r["implemented_in_programs"])
    rule_sets = []
    for i, (name, s) in enumerate(sorted(sets.items()), start=1):
        rule_sets.append({"rule_set_id": f"RS-{i:03d}", "name": name,
                          "rule_count": len(s["rule_ids"]), "rule_ids": s["rule_ids"],
                          "programs": sorted(s["programs"])})

    error_catalogue = [
        {"error_id": f"EH-{i:03d}", "condition_text": c["condition_text"],
         "program_id": c["program_id"], "paragraph": c.get("paragraph"), "line": c.get("source_line")}
        for i, c in enumerate((x for x in classified if x["signal_strength"] == 1), start=1)
    ]

    by_cat: dict[str, int] = {}
    for r in rules:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    by_conf: dict[str, int] = {}
    for r in rules:
        by_conf[r["confidence"]] = by_conf.get(r["confidence"], 0) + 1

    rules_by_prog: dict[str, list[str]] = {}
    for r in rules:
        for p in r["implemented_in_programs"]:
            rules_by_prog.setdefault(p, []).append(r["rule_id"])

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_version": AGENT_VERSION, "total_rules": len(rules),
            "total_rule_sets": len(rule_sets),
            "requires_sme_review": sum(1 for r in rules if r["requires_sme_review"]),
            "duplicates_merged": sum(len(r["sources"]) - 1 for r in rules if r["is_duplicated"]),
        },
        "stats": {"by_category": by_cat, "by_confidence": by_conf,
                  "noise_conditions": len(error_catalogue)},
        "rule_sets": rule_sets,
        "business_rules": rules,
        "error_handling_catalogue": error_catalogue,
        "rules_by_program": rules_by_prog,
    }


# ---------------------------------------------------------------------------
# LLM description pass (the hybrid step)
# ---------------------------------------------------------------------------

LLM_SYSTEM = (
    "You are a COBOL business-rules analyst. You are given a list of already-classified "
    "conditions extracted from a COBOL program (each with its raw condition text, category, "
    "pattern, program and paragraph). For each, write a concise business-readable rule NAME "
    "(imperative, e.g. 'Enforce transaction amount does not exceed credit limit') and a 2-3 "
    "sentence plain-English DESCRIPTION a business analyst can validate. Describe only what the "
    "condition shows; never invent thresholds or outcomes. Keep the same order."
)

LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {"type": "array", "items": {
            "type": "object",
            "properties": {"condition_id": {"type": "string"}, "name": {"type": "string"},
                           "description": {"type": "string"}},
            "required": ["condition_id", "name", "description"], "additionalProperties": False}}
    },
    "required": ["rules"], "additionalProperties": False,
}


def make_llm_describer(client, model, promoted, usage_acc):
    """Batch-describe all promoted conditions with one LLM call; return a describe(c) closure."""
    payload = [{"condition_id": c["condition_id"], "program": c["program_id"],
                "paragraph": c.get("paragraph"), "category": c["category"],
                "pattern": c["structural_pattern"], "text": c["condition_text"]}
               for c in promoted]
    msg = ("Write a business rule name + description for each condition below. Return JSON.\n\n"
           + json.dumps(payload, indent=1))
    resp = client.messages.create(
        model=model, max_tokens=16000, system=LLM_SYSTEM,
        messages=[{"role": "user", "content": msg}],
        output_config={"format": {"type": "json_schema", "schema": LLM_SCHEMA}})
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(text)
    usage_acc["in"] += resp.usage.input_tokens
    usage_acc["out"] += resp.usage.output_tokens
    by_id = {r["condition_id"]: r for r in data.get("rules", [])}

    def describe(c):
        r = by_id.get(c["condition_id"])
        base = templated_rule(c)
        if r:
            base["name"] = r.get("name") or base["name"]
            base["description"] = r.get("description") or base["description"]
        return base

    return describe


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build(logic_path: Path, data_path: Path, output_dir: Path, model: str, use_llm: bool) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    conds = collect_conditions(logic_path, data_path)
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

    usage_acc = {"in": 0, "out": 0}
    describe = templated_rule
    mode = "templated (deterministic)"
    if use_llm:
        import anthropic
        client = anthropic.Anthropic()
        promoted = [c for c in conds if c["signal_strength"] >= 2]
        describe = make_llm_describer(client, model, promoted, usage_acc)
        mode = f"LLM ({model})"

    artifact = build_rules(conds, describe)
    artifact["meta"]["description_mode"] = mode
    if usage_acc["in"] or usage_acc["out"]:
        in_p, out_p = PRICING.get(model, (5.0, 25.0))
        artifact["meta"]["usage"] = {
            "input_tokens": usage_acc["in"], "output_tokens": usage_acc["out"],
            "estimated_cost_usd": round(usage_acc["in"] / 1e6 * in_p + usage_acc["out"] / 1e6 * out_p, 4)}
    (output_dir / "rules_artifact.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return classified_doc, artifact


def print_summary(classified: dict, artifact: dict, out: Path) -> None:
    s = artifact["stats"]
    print("=== Rules Agent Complete ===")
    print(f"Conditions classified : {classified['meta']['total_conditions_classified']}")
    print(f"Noise (error-handling): {classified['meta']['noise_excluded']}")
    print(f"Business rules         : {artifact['meta']['total_rules']}")
    for cat, n in sorted(s["by_category"].items()):
        print(f"   {cat:<16}: {n}")
    print(f"Rule sets              : {artifact['meta']['total_rule_sets']}")
    print(f"Duplicates merged      : {artifact['meta']['duplicates_merged']}")
    print(f"Needs SME review       : {artifact['meta']['requires_sme_review']}")
    print(f"Description mode        : {artifact['meta']['description_mode']}")
    if "usage" in artifact["meta"]:
        print(f"Estimated cost          : ${artifact['meta']['usage']['estimated_cost_usd']}")
    print(f"Output                  : {out}")
    print("============================")


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 7 — hybrid COBOL business-rules builder.")
    ap.add_argument("--logic", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--output-dir", default="./outputs/rules")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-llm", action="store_true", help="Force deterministic templated descriptions.")
    args = ap.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    load_dotenv(base_dir)

    use_llm = (not args.no_llm) and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not args.no_llm and not use_llm:
        print("[note] No ANTHROPIC_API_KEY found — using deterministic templated descriptions. "
              "(Add a key, or run the logic_agent-style AI-host path, for LLM-written rules.)")

    classified, artifact = build(Path(args.logic).resolve(), Path(args.data).resolve(),
                                 Path(args.output_dir), args.model, use_llm)
    print_summary(classified, artifact, Path(args.output_dir) / "rules_artifact.json")


if __name__ == "__main__":
    main()
