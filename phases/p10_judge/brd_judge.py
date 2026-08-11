#!/usr/bin/env python3
"""
brd_judge.py  —  Phase 9: BRD Judge (Validation + Judge).  HYBRID.

Two labelled parts:
  * Validation (deterministic Python) — the groundedness gate + consistency checks.
  * Judge (LLM) — the 5-dimension quality scoring + feedback.

Python port of Chaminda's agent/brd_judge.py — an LLM-as-judge with a
deterministic groundedness gate.

  Deterministic (Python, NO LLM):
    * groundedness gate — every BR-/GAP-/RS- id and program reference the BRD
      cites must exist in the artifacts; anything invented is a groundedness
      failure that hard-floors the accuracy score to 2.
    * consistency checks — all 9 chapters present, headline numbers agree with
      the artifacts (programs / rules / gaps), every rule + gap is covered,
      diagrams embedded.

  LLM (the paid step — AI-host when no key, else a neutral default of 3):
    * score 5 dimensions (completeness, accuracy, clarity, consistency,
      actionability) 1-5 with rationale, and write feedback items.

  Then (Python): apply the gate, compute the weighted score, rating and a
  PASS / REVISE verdict.

  Output: outputs/final_report/brd_validation.json + brd_validation.md

Inputs
  --brd outputs/final_report/brd.md
  --inventory / --data / --logic / --rules / --gaps  (the artifacts)
  --output-dir outputs/final_report
  --scores-file  optional JSON of AI-host dimension scores + feedback
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AGENT_VERSION = "8_validation_python@1.0"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

WEIGHTS = {"completeness": 0.25, "accuracy": 0.30, "clarity": 0.15,
           "consistency": 0.15, "actionability": 0.15}
DIMENSIONS = list(WEIGHTS.keys())

JUDGE_SYSTEM = (
    "You are a BRD reviewer. Evaluate the Business Requirements Document generated from static "
    "analysis of a COBOL codebase. Score five dimensions 1-5 each with a brief rationale: "
    "completeness, accuracy, clarity, consistency, actionability. Also list concrete feedback items "
    "for revision. Judge only what is present; do not reward or penalise things you cannot see."
)
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "dimensions": {"type": "object", "properties": {
            d: {"type": "object", "properties": {
                "score": {"type": "integer"}, "rationale": {"type": "string"}},
                "required": ["score", "rationale"], "additionalProperties": False}
            for d in ("completeness", "accuracy", "clarity", "consistency", "actionability")},
            "required": ["completeness", "accuracy", "clarity", "consistency", "actionability"],
            "additionalProperties": False},
        "feedback": {"type": "array", "items": {"type": "object", "properties": {
            "dimension": {"type": "string"}, "severity": {"type": "string"},
            "suggestion": {"type": "string"}, "target_section": {"type": "string"}},
            "required": ["dimension", "severity", "suggestion", "target_section"],
            "additionalProperties": False}},
    },
    "required": ["dimensions", "feedback"], "additionalProperties": False,
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


def judge_llm(model: str, brd_text: str) -> tuple[dict, list]:
    import anthropic
    resp = anthropic.Anthropic().messages.create(
        model=model, max_tokens=4000, system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": "## BRD under review\n\n" + brd_text[:120000]}],
        output_config={"format": {"type": "json_schema", "schema": JUDGE_SCHEMA}})
    data = json.loads(next((b.text for b in resp.content if b.type == "text"), "{}"))
    return data.get("dimensions", {}), data.get("feedback", [])


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else {}


# ---------------------------------------------------------------------------
# Known references (from the artifacts) — the groundedness truth set
# ---------------------------------------------------------------------------

def known_refs(inv, logic, rules, data, gaps) -> dict:
    prog = {e["id"] for e in inv.get("file_registry", [])}
    # external call targets are legitimate references too
    for e in inv.get("call_graph", {}).get("edges", []):
        if e.get("to"):
            prog.add(e["to"])
    br = {r["rule_id"] for r in rules.get("business_rules", [])}
    rs = {s["rule_set_id"] for s in rules.get("rule_sets", [])}
    gp = {g["gap_id"] for g in gaps.get("gaps", [])}
    ent = {e["name"] for e in data.get("data_model", {}).get("entities", [])}
    return {"program": prog, "BR": br, "RS": rs, "GAP": gp, "entity": ent}


# ---------------------------------------------------------------------------
# Groundedness gate — references cited in the BRD that don't exist
# ---------------------------------------------------------------------------

def groundedness_failures(brd_text: str, known: dict) -> list[str]:
    fails: list[str] = []
    for m in set(re.findall(r"\bBR-\d{3}\b", brd_text)):
        if m not in known["BR"]:
            fails.append(m)
    for m in set(re.findall(r"\bGAP-\d{3}\b", brd_text)):
        if m not in known["GAP"]:
            fails.append(m)
    for m in set(re.findall(r"\bRS-\d{3}\b", brd_text)):
        if m not in known["RS"]:
            fails.append(m)
    return sorted(fails)


# ---------------------------------------------------------------------------
# Consistency / completeness checks (deterministic)
# ---------------------------------------------------------------------------

def consistency_checks(brd_text: str, inv, rules, gaps, expected_diagrams: int) -> list[dict]:
    issues: list[dict] = []

    def add(sev, kind, msg):
        issues.append({"severity": sev, "type": kind, "message": msg})

    for n in range(1, 10):
        if not re.search(rf"^##\s*{n}\.", brd_text, re.M):
            add("high", "missing_chapter", f"Chapter {n} appears to be missing.")

    # headline numbers
    def num_after(pattern):
        m = re.search(pattern, brd_text)
        return int(m.group(1).replace(",", "")) if m else None

    prog_stated = num_after(r"comprises\s+([\d,]+)\s+programs")
    prog_actual = inv.get("stats", {}).get("programs")
    if prog_stated is not None and prog_actual is not None and prog_stated != prog_actual:
        add("high", "number_mismatch",
            f"Executive summary says {prog_stated} programs but inventory has {prog_actual}.")

    rules_stated = num_after(r"extracted\s+([\d,]+)\s+business rules")
    rules_actual = rules.get("meta", {}).get("total_rules")
    if rules_stated is not None and rules_actual is not None and rules_stated != rules_actual:
        add("high", "number_mismatch",
            f"Executive summary says {rules_stated} rules but the catalogue has {rules_actual}.")

    # coverage — every rule and gap id must be referenced somewhere in the BRD
    missing_rules = [r["rule_id"] for r in rules.get("business_rules", [])
                     if r["rule_id"] not in brd_text]
    if missing_rules:
        add("medium", "coverage",
            f"{len(missing_rules)} business rule(s) not referenced in the BRD "
            f"(e.g. {', '.join(missing_rules[:5])}).")
    missing_gaps = [g["gap_id"] for g in gaps.get("gaps", []) if g["gap_id"] not in brd_text]
    if missing_gaps:
        add("medium", "coverage", f"{len(missing_gaps)} gap(s) not listed in Chapter 9.")

    # diagrams embedded
    embedded = brd_text.count("```mermaid")
    if embedded < expected_diagrams:
        add("low", "diagrams",
            f"{embedded} diagrams embedded but {expected_diagrams} were generated.")

    return issues


# ---------------------------------------------------------------------------
# Dimension scoring (LLM / AI-host / default) + gate + rating
# ---------------------------------------------------------------------------

def default_scores() -> dict:
    return {d: {"score": 3, "rationale": "(not scored — neutral default)"} for d in DIMENSIONS}


def rate(weighted: float, dims: dict) -> str:
    if weighted >= 4.2 and all(d["score"] >= 3 for d in dims.values()):
        return "high"
    if weighted >= 3.2 and all(d["score"] >= 2 for d in dims.values()):
        return "medium"
    return "low"


def judge(brd_text: str, inv, logic, rules, data, gaps, dim_scores: dict,
          feedback: list, expected_diagrams: int) -> dict:
    known = known_refs(inv, logic, rules, data, gaps)
    g_fail = groundedness_failures(brd_text, known)
    issues = consistency_checks(brd_text, inv, rules, gaps, expected_diagrams)

    dims = {d: dict(dim_scores.get(d, {"score": 3, "rationale": "(not scored)"})) for d in DIMENSIONS}

    # groundedness gate: hallucinated refs floor accuracy at 2
    if g_fail and dims["accuracy"]["score"] > 2:
        dims["accuracy"]["score"] = 2
        dims["accuracy"]["rationale"] += f"  [forced to 2 by ungrounded refs: {g_fail}]"
    # a high-severity consistency issue also caps consistency
    if any(i["severity"] == "high" for i in issues) and dims["consistency"]["score"] > 2:
        dims["consistency"]["score"] = 2
        dims["consistency"]["rationale"] += "  [capped at 2 by a high-severity consistency issue]"

    weighted = round(sum(dims[d]["score"] * w for d, w in WEIGHTS.items()), 3)
    rating = rate(weighted, dims)
    high_issue = any(i["severity"] == "high" for i in issues) or bool(g_fail)
    verdict = "PASS" if rating in ("high", "medium") and not high_issue else "REVISE"

    return {
        "meta": {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "agent_version": AGENT_VERSION},
        "verdict": verdict, "rating": rating, "weighted_score": weighted,
        "dimensions": dims,
        "groundedness_failures": g_fail,
        "consistency_issues": issues,
        "feedback": feedback,
    }


def report_md(v: dict) -> str:
    L = ["# BRD Validation Report (Judge)", "",
         f"**Verdict:** {v['verdict']}  ·  **Rating:** {v['rating']}  ·  "
         f"**Weighted score:** {v['weighted_score']} / 5", "",
         "## Dimension scores", "", "| Dimension | Score | Rationale |", "|---|---|---|"]
    for d, s in v["dimensions"].items():
        L.append(f"| {d.capitalize()} | {s['score']}/5 | {s['rationale']} |")
    L += ["", "## Groundedness gate", ""]
    if v["groundedness_failures"]:
        L.append(f"⚠ **{len(v['groundedness_failures'])} ungrounded reference(s)** "
                 f"(accuracy floored to 2): {', '.join(v['groundedness_failures'])}")
    else:
        L.append("✓ All BR / GAP / RS references in the BRD trace to the artifacts.")
    L += ["", "## Consistency & completeness issues", ""]
    if v["consistency_issues"]:
        L.append("| Severity | Type | Message |")
        L.append("|---|---|---|")
        for i in v["consistency_issues"]:
            L.append(f"| {i['severity'].upper()} | {i['type']} | {i['message']} |")
    else:
        L.append("✓ No consistency issues found.")
    L += ["", "## Feedback for BRD Improvement", ""]
    if v["feedback"]:
        for f in v["feedback"]:
            L.append(f"- **[{f.get('severity','').upper()} · {f.get('dimension','')}]** "
                     f"{f.get('suggestion','')}  *(→ {f.get('target_section','')})*")
    else:
        L.append("- (No specific feedback items.)")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 9 — BRD validation (the Judge).")
    ap.add_argument("--brd", required=True)
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--logic", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--gaps", required=True)
    ap.add_argument("--diagrams-index", default=None, help="diagrams_artifact.json (for expected count)")
    ap.add_argument("--scores-file", default=None, help="AI-host dimension scores + feedback JSON")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-llm", action="store_true", help="Force neutral default scores (no API call).")
    ap.add_argument("--output-dir", default="./outputs/final_report")
    args = ap.parse_args()

    load_dotenv(Path(__file__).resolve().parent.parent)
    brd_text = Path(args.brd).read_text(encoding="utf-8")
    inv, data = load(Path(args.inventory)), load(Path(args.data))
    logic, rules = load(Path(args.logic)), load(Path(args.rules))
    gaps = load(Path(args.gaps))

    expected = 0
    if args.diagrams_index:
        expected = len(load(Path(args.diagrams_index)).get("diagrams", []))

    scores, feedback = default_scores(), []
    if args.scores_file and Path(args.scores_file).exists():
        sf = load(Path(args.scores_file))
        for d, s in (sf.get("dimensions", {}) or {}).items():
            if d in scores:
                scores[d] = s
        feedback = sf.get("feedback", [])
    elif (not args.no_llm) and os.environ.get("ANTHROPIC_API_KEY"):
        dims, feedback = judge_llm(args.model, brd_text)
        for d, s in (dims or {}).items():
            if d in scores and isinstance(s, dict):
                scores[d] = s
    elif not args.no_llm:
        print("[note] No ANTHROPIC_API_KEY and no --scores-file — dimensions default to neutral 3s. "
              "(Provide --scores-file from the AI-host path, or a key, for real scoring.)")

    v = judge(brd_text, inv, logic, rules, data, gaps, scores, feedback, expected)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "brd_judge.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
    (out / "brd_judge.md").write_text(report_md(v), encoding="utf-8")

    print("=== BRD Judge Complete ===")
    print(f"Verdict         : {v['verdict']}")
    print(f"Rating          : {v['rating']}  (weighted {v['weighted_score']}/5)")
    for d, s in v["dimensions"].items():
        print(f"   {d:<14}: {s['score']}/5")
    print(f"Groundedness    : {'PASS' if not v['groundedness_failures'] else 'FAIL — ' + ', '.join(v['groundedness_failures'])}")
    print(f"Consistency     : {len(v['consistency_issues'])} issue(s)")
    print(f"Output          : {out / 'brd_judge.md'}")
    print("==========================")


if __name__ == "__main__":
    main()
