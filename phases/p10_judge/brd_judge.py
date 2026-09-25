#!/usr/bin/env python3
"""
brd_judge.py  —  Phase 10: BRD Judge (Validation + Judge).  HYBRID.

Two labelled parts:
  * Validation (deterministic Python) — the groundedness gate + consistency checks.
  * Judge (LLM) — the 5-dimension quality scoring + feedback.

Python port of Chaminda's agent/brd_judge.py — an LLM-as-judge with a
deterministic groundedness gate.

  Deterministic (Python, NO LLM):
    * groundedness gate — every BR-/TR-/RS-/GAP- id the BRD cites must exist in
      the artifacts; anything invented hard-floors the accuracy score to 2.
    * narrative grounding — business terms in the prose must appear in the
      evidence (summaries, pseudocode, rules, data names), and every count in the
      prose must be one the artifacts support; a violation caps accuracy at 2.
    * consistency checks — chapters 1-9 present, headline numbers agree with
      the artifacts, every rule + gap is covered, diagrams embedded.

  AI step (Claude Code AI-host with no key, or the API; neutral 3s otherwise):
    * score 5 dimensions (completeness, accuracy, clarity, consistency,
      actionability) 1-5 with rationale, and write feedback items. The judge
      writes brd_judge_brief.json (brd_sha + findings); the AI-host writes
      brd_scores.json, which is applied only if its brd_sha matches brd.md.

  Then (Python): apply the gate, compute the weighted score, rating and a
  PASS / REVISE verdict.

  Output: final_report/brd_judge.json + brd_judge.md (+ brd_judge_brief.json)

Inputs
  --brd <out>/final_report/brd.md
  --inventory / --data / --logic / --rules / --gaps  (the artifacts)
  --output-dir <out>/final_report
  --scores-file  AI-host scores (default: <output-dir>/brd_scores.json when present)
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
from typing import Any

AGENT_VERSION = "8_validation_python@1.0"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

WEIGHTS = {"completeness": 0.25, "accuracy": 0.30, "clarity": 0.15,
           "consistency": 0.15, "actionability": 0.15}
DIMENSIONS = list(WEIGHTS.keys())

JUDGE_SYSTEM = (
    "You are a strict BRD reviewer writing for senior business and technology leaders. Evaluate the "
    "Business Requirements Document generated from static analysis of a COBOL codebase. Score five "
    "dimensions 1-5 each with a brief rationale: completeness, accuracy, clarity, consistency, "
    "actionability — using the rubric in phases/p10_judge/brd_judge_agent.md. Treat the "
    "deterministic findings as facts: any ungrounded reference, unsupported term or unsupported "
    "number means accuracy cannot exceed 2. Also list concrete feedback items for revision. Judge "
    "only what is present; do not reward or penalise things you cannot see."
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


def judge_llm(model: str, brd_text: str, g_fail: list, issues: list) -> tuple[dict, list]:
    import anthropic
    findings = json.dumps({"groundedness_failures": g_fail, "consistency_issues": issues}, indent=1)
    resp = anthropic.Anthropic().messages.create(
        model=model, max_tokens=4000, system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": "## Deterministic findings\n\n" + findings
                   + "\n\n## BRD under review\n\n" + brd_text[:120000]}],
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
    tr = {r["rule_id"] for r in rules.get("technical_rules", [])}
    rs = {s["rule_set_id"] for s in rules.get("rule_sets", [])}
    gp = {g["gap_id"] for g in gaps.get("gaps", [])}
    ent = {e["name"] for e in data.get("data_model", {}).get("entities", [])}
    return {"program": prog, "BR": br, "TR": tr, "RS": rs, "GAP": gp, "entity": ent}


# ---------------------------------------------------------------------------
# Groundedness gate — references cited in the BRD that don't exist
# ---------------------------------------------------------------------------

def groundedness_failures(brd_text: str, known: dict) -> list[str]:
    fails: list[str] = []
    for kind in ("BR", "TR", "RS", "GAP"):
        for m in set(re.findall(rf"\b{kind}-\d{{3}}\b", brd_text)):
            if m not in known[kind]:
                fails.append(m)
    return sorted(fails)


# ---------------------------------------------------------------------------
# Narrative checks — does the prose describe THIS system, with THESE numbers?
# ---------------------------------------------------------------------------

# Generic English / business / IT vocabulary a BRD may use about any system. A word outside
# this list must be supported by the analysed code (summaries, pseudocode, rules, data names).
GENERIC_VOCAB = set("""
about above access accessed according account accounting across action actions active activity
actor actors actual added adding additional address addressed after again against aligned allow
allowed allows almost along already also alternative although always among amount analysed
analysis analyst analysts another answer anything application applications applied applies apply
approach appropriate architect architecture areas around assess assessment associated assumption
assumptions attention authoritative automated automatic automatically available avoid aware back
backed backend based basic basis batch batches because become before begin behaviour behavior
being believe below benefit best better between beyond block blocks board both boundary boundaries
branch branches breadth brief bring broad build builds built bulk business businesses called
calling calls cannot capabilities capability capture captured carries carry carrying cases catalogue
catalog central centre certain chain change changes channel chapter chapters check checked checks
choice clear clearly close closely code codebase coded coding collection combination combine
combined combines comes coming command common commonly compared complete completed completely
complex complexity compliance component components comprehensive comprises computed concern
concerns condition conditions confidence confirm confirmation confirmed connect connected
consider considerations consistent consists constraint constraints contain contained contains
content context continue continues control controls core correct correctly could count counts
cover covered covers create created creates creating critical current currently daily dashboard
data database databases date dates decide decides decision decisions deep default define defined
defines definition definitions delete deleted deliver demand depend dependencies dependency depends
describe described describes description descriptions design designed detail detailed details
determine developer developers different directly discover document documentation documented
documents domain drive driven drives during each early effect effort either elements else embedded
enable enables encoded end-to-end enforce enforced enforces ensure ensures enter entered entire
entities entity entry environment equivalent equivalents error errors especially essential
establish estimate estimated evaluate even event events every everything evidence exactly example
examples except exception exceptions execution exist existing exists expected experts explain
explained explicit extend external extracted fact facts fails failure feature features field fields
figure final finally find finding findings first flow flows focus follow following follows form
format found foundation from front full fully function functional functionality functions further
future gather general generated given governed greater group grouped groups guide handle handled
handles handling have having heavy help helps hidden high higher highest hold holds however human
identified identifies identify immediately impact impacts implement implementation implemented
important include included includes including increase independent indicate indicates indicator
individual information infrastructure initial input inputs inside instead integrate integrated
integration integrations intended interactive interface interfaces internal into introduce
inventory involve issue issues item items itself jobs keep keeps key kinds known labelled large
larger largest later layer layers leaders legacy less level levels like likely limited line lines
link linked links list listed lists little local logic logical long look main mainframe mainly
maintain maintained maintenance major make makes manage managed management manages manual many
mapping marked matter matters mean means measure mechanics meets messaging method might migration
minimal mixed model modern modernisation modernise modernization modernize modernizing module
modules more most move much multiple must named nature near need needed needs never next night
nightly none normal note noted notes number numbers object objects obvious occurs offer often
once online only open operate operates operating operation operational operations operator
operators order orders organisation organization origin original other others otherwise outcome
outcomes output outputs outside overall overview owner owners ownership pages paragraph paragraphs
part particular parts path pattern patterns pending perform performed performs period place
placed plain plan planning platform platforms plus point points policies policy portion possible
potential practice precise prepared present preserve previous primary principal prior priorities
priority problem problems procedure procedures process processed processes processing produce
produced produces product production program programs project proper protect provide provided
provides purpose purposes quality question questions quick quickly range rather reach read reads
real really reason reasons receive received recommend recommendation recommended record records
reduce reference referenced references reflect regular related relationship relationships relevant
reliable rely remain remaining replace replaced replacement report reported reporting reports
represent request requests require required requirement requirements requires resolve resolved
responsible restricted result results retain return returns reverse reverse-engineered review
reviewed right risk risks role roles routine routines rule rules runs same scheduled scope screen
screens second section sections security see seen select selected send separate separately
sequence serve served serves service services session several shape shared short should shown
shows side sign-off significant similar simple since single size small software some something
source sources specific stable stage standard start state stated statement statements states
static status step steps still storage store stored stores strategy structure structured
structural subject subject-matter subroutine subroutines subsystem subsystems such suggest summary
supplied support supported supports system systems table tables take target targets team teams
technical technology template term terms test tested testing than that their them themselves
then there these they thing things third this those though three through throughout thus tied
time timely today together tools total touch trace traced traces track trail transfer transfers
treated trigger triggered true type types typical typically under underlying understand
understanding unit units unless unstructured until update updated updates upon usage used useful
user users uses using usually valid validate validated validates validation value values various
verify version very view visible volume want well were what when where whether which while whole
whose wide will with within without work workflow workflows works would write written years
comprising edges english expert experts matter plain pseudocode stream streams unresolved
calculate calculates calculated calculation calculations compute computes computation cancel
cancels search searches searched schedule schedules submit submits submitted browse browses
maintains maintaining reviews reviewing lookup lookups entering adjusts adjust adjusted
reverse-engineered static-analysis walkthrough cobol copybook copybooks jcl vsam cics
""".split())


def _stem(word: str) -> str:
    w = word.lower()
    for suf in ("ies", "es", "s", "ing", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def evidence_vocabulary(logic: dict, logic_dir: Path, rules: dict, data: dict, inv: dict) -> set[str]:
    """Every word the analysis itself produced — the only domain vocabulary prose may use."""
    texts = [p.get("summary", "") for p in logic.get("programs", [])]
    for p in logic.get("programs", []):
        lf = logic_dir / p.get("logic_file", f"program_logic/{p['program_id']}_logic.json")
        if lf.exists():
            for para in load(lf).get("paragraphs", []):
                texts += [para.get("pseudocode", ""), para.get("notes", "") or "",
                          " ".join(para.get("branches", []) or [])]
    for r in rules.get("business_rules", []) + rules.get("technical_rules", []):
        texts += [r.get("name", ""), r.get("description", ""), r.get("condition", {}).get("text", ""),
                  " ".join(r.get("condition", {}).get("values", {}) or {})]
    for c in rules.get("capabilities", []):
        texts += [c.get("name", ""), c.get("description", "")]
    for f in data.get("fields", []):
        texts += [f.get("name", ""), f.get("record", ""), " ".join(f.get("conditions", {}) or {})]
    texts += [e["id"] for e in inv.get("file_registry", [])]
    vocab: set[str] = set()
    for t in texts:
        for w in re.findall(r"[A-Za-z]{4,}", t or ""):
            vocab.add(_stem(w))
    return vocab


def narrative_sections(brd_text: str) -> str:
    """The AI-written prose: chapter 1 before its tables, chapter 2, chapter 3 intros, chapter 10."""
    keep, out, in_code = False, [], False
    for line in brd_text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith("## "):
            keep = bool(re.match(r"## (1|2|3|10)\. ", line))
        elif line.startswith("### 1.1") or line.startswith("### 1.2") or line.startswith("### 10.1"):
            keep = False
        elif line.startswith("### 10.2"):
            keep = True
        if keep and not line.startswith(("|", "#", "*", "**Figure")):
            out.append(line)
    return "\n".join(out)


def unsupported_terms(prose: str, vocab: set[str], known_ids: set[str]) -> list[str]:
    terms = set()
    for w in re.findall(r"\b[A-Za-z][A-Za-z-]{4,}\b", prose):
        lw = w.lower()
        if w.upper() in known_ids or lw in GENERIC_VOCAB or _stem(lw) in GENERIC_VOCAB:
            continue
        parts = [p for p in lw.split("-") if len(p) >= 4]
        if all(_stem(p) in vocab or p in GENERIC_VOCAB for p in parts) if parts else True:
            continue
        terms.add(lw)
    return sorted(terms)


NUMBER_NOUNS = {
    "programs": "programs", "program": "programs", "business rules": "rules", "rules": "rules",
    "gaps": "gaps", "copybooks": "copybooks", "job streams": "jcl", "jobs": "jcl",
    "capabilities": "capabilities", "fields": "fields", "records": "records",
    "entities": "entities", "subroutines": "programs", "screens": "screens",
    "technical conditions": "technical", "paragraphs": "paragraphs",
}


def allowed_numbers(inv, logic, rules, data, gaps) -> dict[str, set[int]]:
    """Every count the facts support, per noun (totals and meaningful subsets)."""
    st = inv.get("stats", {})
    reg = inv.get("file_registry", [])
    progs = {st.get("programs", 0), st.get("batch_programs", 0), st.get("online_programs", 0),
             st.get("common_programs", 0), st.get("unknown_programs", 0), len(logic.get("programs", []))}
    runtime: dict[str, int] = {}
    for e in reg:
        for r in e.get("runtime", []):
            runtime[r] = runtime.get(r, 0) + 1
    progs |= set(runtime.values())
    progs |= {len(c.get("programs", [])) for c in rules.get("capabilities", [])}
    progs |= {len(s.get("programs", [])) for s in rules.get("rule_sets", [])}
    gl = gaps.get("gaps", [])
    sev: dict[str, int] = {}
    for g in gl:
        sev[g["severity"]] = sev.get(g["severity"], 0) + 1
    rmeta = rules.get("meta", {})
    return {
        "programs": progs,
        "rules": {rmeta.get("total_rules", 0), rmeta.get("requires_sme_review", 0)}
                 | {s.get("rule_count", 0) for s in rules.get("rule_sets", [])}
                 | set(rules.get("stats", {}).get("by_category", {}).values()),
        "gaps": {len(gl)} | set(sev.values()) | {len(gl) - sev.get("high", 0) - sev.get("critical", 0)},
        "copybooks": {st.get("copybooks", 0)}, "jcl": {st.get("jcl_jobs", 0)},
        "capabilities": {len(rules.get("capabilities", []))} | {len(rules.get("rule_sets", []))},
        "fields": {data.get("stats", {}).get("fields", 0)},
        "records": {data.get("stats", {}).get("records", 0)},
        "entities": {len(data.get("data_model", {}).get("entities", []))},
        "screens": {st.get("bms_maps", 0)},
        "technical": {rmeta.get("technical_conditions", 0)},
        "paragraphs": {logic.get("stats", {}).get("total_paragraphs_explained", 0)},
    }


def unsupported_numbers(prose: str, allowed: dict[str, set[int]]) -> list[str]:
    bad = []
    pattern = r"\b(\d[\d,]*)\s+(?:[a-z-]+\s+)?(" + "|".join(
        sorted(map(re.escape, NUMBER_NOUNS), key=len, reverse=True)) + r")\b"
    for m in re.finditer(pattern, prose, re.I):
        n, noun = int(m.group(1).replace(",", "")), m.group(2).lower()
        key = NUMBER_NOUNS[noun]
        if key in allowed and n not in allowed[key]:
            bad.append(m.group(0))
    return sorted(set(bad))


# ---------------------------------------------------------------------------
# Consistency / completeness checks (deterministic)
# ---------------------------------------------------------------------------

def consistency_checks(brd_text: str, inv, rules, gaps, expected_diagrams: int,
                       logic: dict = None, data: dict = None, vocab: set = None) -> list[dict]:
    issues: list[dict] = []
    logic, data = logic or {}, data or {}

    def add(sev, kind, msg):
        issues.append({"severity": sev, "type": kind, "message": msg})

    # narrative grounding — domain terms and numbers in the prose must come from the analysis
    prose = narrative_sections(brd_text)
    if vocab:
        known_ids = {e["id"] for e in inv.get("file_registry", [])} \
            | {e.get("to") for e in inv.get("call_graph", {}).get("edges", []) if e.get("to")}
        terms = unsupported_terms(prose, vocab, known_ids)
        if terms:
            add("high" if len(terms) >= 3 else "medium", "unsupported_terms",
                f"Narrative uses {len(terms)} term(s) found nowhere in the analysed code, program "
                f"summaries, rules or data names: {', '.join(terms[:15])}. Confirm they describe "
                f"this system.")
    bad_numbers = unsupported_numbers(prose, allowed_numbers(inv, logic, rules, data, gaps))
    if bad_numbers:
        add("high", "number_mismatch",
            f"Narrative states counts that no artifact supports: {'; '.join(bad_numbers[:10])}.")

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
    if weighted >= 3.0 and all(d["score"] >= 2 for d in dims.values()):
        return "medium"
    return "low"


def validate(brd_text: str, inv, logic, rules, data, gaps, expected_diagrams: int,
             vocab: set = None) -> tuple[list[str], list[dict]]:
    """The deterministic half: groundedness failures + consistency issues."""
    known = known_refs(inv, logic, rules, data, gaps)
    return (groundedness_failures(brd_text, known),
            consistency_checks(brd_text, inv, rules, gaps, expected_diagrams, logic, data, vocab))


def judge(brd_text: str, inv, logic, rules, data, gaps, dim_scores: dict,
          feedback: list, expected_diagrams: int, vocab: set = None) -> dict:
    g_fail, issues = validate(brd_text, inv, logic, rules, data, gaps, expected_diagrams, vocab)

    dims = {d: dict(dim_scores.get(d, {"score": 3, "rationale": "(not scored)"})) for d in DIMENSIONS}

    # groundedness gate: hallucinated refs floor accuracy at 2
    if g_fail and dims["accuracy"]["score"] > 2:
        dims["accuracy"]["score"] = 2
        dims["accuracy"]["rationale"] += f"  [forced to 2 by ungrounded refs: {g_fail}]"
    # prose that describes another domain, or states unsupported counts, caps accuracy at 2
    wrong = [i for i in issues if i["severity"] == "high"
             and i["type"] in ("unsupported_terms", "number_mismatch")]
    if wrong and dims["accuracy"]["score"] > 2:
        dims["accuracy"]["score"] = 2
        dims["accuracy"]["rationale"] += "  [capped at 2: narrative not grounded in the analysis]"
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
         f"**Weighted score:** {v['weighted_score']} / 5  ·  "
         f"**Scored by:** {v['meta'].get('scoring_mode', 'n/a')}", "",
         "## Dimension scores", "", "| Dimension | Score | Rationale |", "|---|---|---|"]
    for d, s in v["dimensions"].items():
        L.append(f"| {d.capitalize()} | {s['score']}/5 | {s['rationale']} |")
    L += ["", "## Groundedness gate", ""]
    if v["groundedness_failures"]:
        L.append(f"**Failed** — {len(v['groundedness_failures'])} ungrounded reference(s) "
                 f"(accuracy floored to 2): {', '.join(v['groundedness_failures'])}")
    else:
        L.append("**Passed** — every BR / TR / RS / GAP reference in the BRD traces to the artifacts.")
    L += ["", "## Consistency & completeness issues", ""]
    if v["consistency_issues"]:
        L.append("| Severity | Type | Message |")
        L.append("|---|---|---|")
        for i in v["consistency_issues"]:
            L.append(f"| {i['severity'].upper()} | {i['type']} | {i['message']} |")
    else:
        L.append("**Passed** — no consistency issues found.")
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
    ap = argparse.ArgumentParser(description="Phase 10 — BRD validation (the Judge).")
    ap.add_argument("--brd", required=True)
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--logic", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--gaps", required=True)
    ap.add_argument("--diagrams-index", default=None, help="diagrams_artifact.json (for expected count)")
    ap.add_argument("--scores-file", default=None,
                    help="AI-host dimension scores + feedback JSON "
                         "(default: <output-dir>/brd_scores.json when present)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-llm", action="store_true", help="Never call the API.")
    ap.add_argument("--output-dir", default="./outputs/final_report")
    args = ap.parse_args()

    load_dotenv(Path(__file__).resolve().parent.parent.parent)
    brd_text = Path(args.brd).read_text(encoding="utf-8")
    inv, data = load(Path(args.inventory)), load(Path(args.data))
    logic, rules = load(Path(args.logic)), load(Path(args.rules))
    gaps = load(Path(args.gaps))
    vocab = evidence_vocabulary(logic, Path(args.logic).parent, rules, data, inv)

    expected = 0
    if args.diagrams_index:
        expected = len(load(Path(args.diagrams_index)).get("diagrams", []))

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Brief for the AI-host scorer: the exact BRD it must score + the deterministic findings.
    brd_sha = hashlib.sha1(brd_text.encode("utf-8")).hexdigest()[:16]
    g_fail, issues = validate(brd_text, inv, logic, rules, data, gaps, expected, vocab)
    (out / "brd_judge_brief.json").write_text(json.dumps({
        "meta": {"brd_sha": brd_sha, "brd": str(Path(args.brd).name)},
        "instructions": ("Score brd.md per phases/p10_judge/brd_judge_agent.md and write "
                         "brd_scores.json next to this file with meta.brd_sha copied from here."),
        "groundedness_failures": g_fail, "consistency_issues": issues,
        "weights": WEIGHTS}, indent=2), encoding="utf-8")

    scores, feedback, mode = default_scores(), [], "neutral default (not scored)"
    sfile = Path(args.scores_file) if args.scores_file else out / "brd_scores.json"
    if sfile.exists():
        sf = load(sfile)
        if sf.get("meta", {}).get("brd_sha") != brd_sha:
            print(f"[warn] {sfile.name} ignored: it was written for a different version of the BRD "
                  f"(re-score the current brd.md).", file=sys.stderr)
        else:
            for d, s in (sf.get("dimensions", {}) or {}).items():
                if d in scores and isinstance(s, dict) and s.get("score") in (1, 2, 3, 4, 5):
                    scores[d] = s
            feedback, mode = sf.get("feedback", []), f"AI-host ({sfile.name})"
    elif (not args.no_llm) and os.environ.get("ANTHROPIC_API_KEY"):
        dims, feedback = judge_llm(args.model, brd_text, g_fail, issues)
        for d, s in (dims or {}).items():
            if d in scores and isinstance(s, dict):
                scores[d] = s
        mode = f"LLM ({args.model})"
    elif not args.no_llm:
        print("[note] No API key and no brd_scores.json — dimensions default to neutral 3s. For real "
              "scoring without a key, have Claude Code write brd_scores.json from brd_judge_brief.json "
              "(see phases/p10_judge/brd_judge_agent.md) and re-run.")

    v = judge(brd_text, inv, logic, rules, data, gaps, scores, feedback, expected, vocab)
    v["meta"]["scoring_mode"] = mode
    if mode.startswith("neutral"):
        # Neutral defaults are a placeholder, not a review: an unscored BRD never passes.
        v["verdict"] = "REVISE"
        v["rating"] = "not scored"
    v["meta"]["brd_sha"] = brd_sha
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
