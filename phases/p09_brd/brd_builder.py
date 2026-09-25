#!/usr/bin/env python3
"""
brd_builder.py  —  Phase 8: BRD Generation (HYBRID).

Python port of the "7_synthesis" agent (gap-detector + section-assembler).

  Deterministic (Python, NO LLM):
    * gap detection — aggregate every unresolved reference, low-confidence rule,
      empty/truncated/skeleton program and SME flag from the earlier artifacts
      -> outputs/final_report/gaps_register.json + gaps_register.md
    * document assembly — build brd.md chapter by chapter from the artifacts:
      inventory tables, the data model, the full business-rules catalogue
      (descriptions already written in Phase 7), program process summaries,
      error-handling catalogue, the gaps register, appendices.

  LLM (the paid step — only if a key is available, else a templated fallback):
    * the synthesis prose — executive summary, system-context narrative and the
      per-process narratives that weave logic + rules together.

  Output: outputs/final_report/brd.md + brd_summary.md (+ the gaps register).

Inputs (all from earlier phases)
  --inventory outputs/discovery/inventory.json
  --parser    outputs/analysis/parser_artifact.json
  --data      outputs/data/data_artifact.json
  --logic     outputs/logic/logic_artifact.json
  --rules     outputs/rules/rules_artifact.json
  --output-dir outputs/final_report
  --system-name "Portfolio Management System"
  --model / --no-llm  (as in the other phases)

Diagrams are referenced but shown as placeholders until the Diagram agent is built.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

AGENT_VERSION = "7_synthesis_python@1.0"
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


def detect_gaps(inv: dict, logic: dict, rules: dict, data: dict) -> list[dict]:
    gaps: list[dict] = []
    gid = 1

    def add(sev, gtype, msg, source):
        nonlocal gid
        gaps.append({"gap_id": f"GAP-{gid:03d}", "severity": sev, "type": gtype,
                     "description": msg, "source": source})
        gid += 1

    for iss in inv.get("issues", []):
        sev = {"error": "high", "warning": "medium"}.get(iss.get("severity"), "low")
        if iss.get("type") in ("unresolved_reference", "circular_copy", "duplicate_program_id"):
            add(sev, iss.get("type"), iss.get("message", ""), "inventory")

    for iss in logic.get("issues", []):
        t = iss.get("type", "")
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

    for iss in data.get("issues", []):
        add("medium", iss.get("type", "data_issue"), iss.get("message", ""), "data")

    gaps.sort(key=lambda g: SEV_RANK.get(g["severity"], 3))
    for i, g in enumerate(gaps, 1):
        g["gap_id"] = f"GAP-{i:03d}"
    return gaps


def gaps_markdown(gaps: list[dict]) -> str:
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
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Narrative prose (LLM when available; deterministic template otherwise)
# ---------------------------------------------------------------------------

def templated_narratives(ctx: dict) -> dict:
    s = ctx
    exec_summary = (
        f"The {s['system_name']} is a COBOL-based application comprising {s['programs']} programs "
        f"({s['batch']} batch, {s['online']} online), {s['copybooks']} shared copybooks and "
        f"{s['jcl']} JCL jobs. It manages portfolio positions, transactions and reference data "
        f"through a mix of batch processing and online CICS inquiry, backed by VSAM files and DB2.\n\n"
        f"Automated static analysis extracted {s['rules']} business rules across {s['rule_sets']} "
        f"rule sets, {s['records']} data records with {s['fields']} fields, and plain-English "
        f"pseudocode for {s['paragraphs']} paragraphs. {s['gaps']} gaps were identified "
        f"({s['high_gaps']} high severity) that require subject-matter-expert review before this "
        f"document is treated as authoritative (see Chapter 9)."
    )
    system_context = (
        f"The {s['system_name']} is a mixed batch/online system. Online inquiry transactions run "
        f"under CICS (screen handlers such as the portfolio and history inquiries), while batch "
        f"jobs perform bulk maintenance, reporting and data loads. Shared services provide DB2 "
        f"connection management, commit control, error logging and audit trail writing. Data is held "
        f"in indexed VSAM files (portfolio master, position, transaction history) and DB2 tables."
    )
    return {"exec_summary": exec_summary, "system_context": system_context}


def llm_narratives(client, model, ctx: dict, usage) -> dict:
    schema = {"type": "object", "properties": {
        "exec_summary": {"type": "string"}, "system_context": {"type": "string"}},
        "required": ["exec_summary", "system_context"], "additionalProperties": False}
    system = ("You write Business Requirements Documents from static-analysis facts. Plain English, "
              "present tense, active voice, for business analysts — no COBOL jargon. Use only the "
              "facts provided; never invent numbers.")
    msg = ("Write two sections for a BRD of this system, as JSON.\n"
           "1) exec_summary: 3-4 short paragraphs (purpose, scale, key findings, gaps).\n"
           "2) system_context: 1 paragraph describing the architecture.\n\nFacts:\n"
           + json.dumps(ctx, indent=1))
    resp = client.messages.create(model=model, max_tokens=4000, system=system,
                                  messages=[{"role": "user", "content": msg}],
                                  output_config={"format": {"type": "json_schema", "schema": schema}})
    text = next((b.text for b in resp.content if b.type == "text"), "")
    usage["in"] += resp.usage.input_tokens
    usage["out"] += resp.usage.output_tokens
    return json.loads(text)


# ---------------------------------------------------------------------------
# Section assembly (deterministic)
# ---------------------------------------------------------------------------

def complexity_band(score: int) -> str:
    return "Low" if score <= 3 else ("Medium" if score <= 6 else "High")


def assemble_brd(sysname: str, inv, parser, data, logic, rules, gaps, narr, diagrams_dir: Path) -> str:
    L: list[str] = []
    w = L.append
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    st = inv.get("stats", {})
    n_high = sum(1 for g in gaps if g["severity"] in ("critical", "high"))

    # Cover
    w(f"# Business Requirements Document\n## {sysname}\n")
    w(f"**Document type:** Reverse-engineered Business Requirements Document  ")
    w(f"**Generated by:** new_legacy_harness (agents 1–8)  ")
    w(f"**Generation date:** {date}  ")
    w(f"**Repository analysed:** {inv.get('meta', {}).get('repo_root', 'n/a')}\n")
    w("> **Important:** This document was generated by automated static analysis of COBOL source "
      "code. All content is derived from the source as analysed. Confidence levels are indicated "
      "throughout; items marked ⚠ require subject-matter-expert review before the document is "
      "authoritative.\n")
    w(f"> **Gaps identified:** {len(gaps)} ({n_high} high/critical). See Chapter 9.\n")
    w("---\n")

    # Ch1
    w("## 1. Executive Summary\n")
    w(narr["exec_summary"] + "\n")

    # Ch2
    w("## 2. System Overview\n")
    w("### 2.1 System context\n")
    w(narr["system_context"] + "\n")
    w("### 2.2 Program inventory summary\n")
    w("| Program | Type | Rules | Complexity | Summary |")
    w("|---|---|---|---|---|")
    rbp = rules.get("rules_by_program", {})
    lmap = {p["program_id"]: p for p in logic.get("programs", [])}
    for e in inv.get("file_registry", []):
        pid = e["id"]
        lp = lmap.get(pid, {})
        summ = (lp.get("summary", "") or "").split(". ")[0]
        w(f"| {pid} | {e.get('subtype','')} | {len(rbp.get(pid, []))} | "
          f"{complexity_band(lp.get('max_complexity', 0))} | {summ[:90]} |")
    w("")
    w("### 2.3 System component diagram\n")
    w(embed_mmd(diagrams_dir / "component_overview.mmd", "Figure 2.1 — System component overview"))
    w("*This diagram shows the programs of the system and the calls/links between them. Each box is a "
      "program; an arrow means the source program calls or CICS-links the target. Shared helper "
      "programs (DB2, error, audit, cursor, security) appear as common call targets.*\n")

    # Ch3
    w("## 3. System Inventory\n")
    w(f"Programs: **{st.get('programs',0)}** ({st.get('batch_programs',0)} batch, "
      f"{st.get('online_programs',0)} online) · Copybooks: **{st.get('copybooks',0)}** · "
      f"JCL jobs: **{st.get('jcl_jobs',0)}** · Call edges: {st.get('call_edges_total',0)} "
      f"({st.get('call_edges_unresolved',0)} unresolved).\n")
    w("### 3.1 Copybooks (shared data definitions)\n")
    w("| Copybook | Used by (count) |")
    w("|---|---|")
    for cb, users in sorted(inv.get("copybook_map", {}).items(), key=lambda x: -len(x[1]))[:25]:
        tag = " — shared infrastructure" if len(users) >= 5 else ""
        w(f"| {cb} | {len(users)}{tag} |")
    w("")

    # Ch4
    w("## 4. Data Model and Definitions\n")
    dm = data.get("data_model", {})
    w(f"The data model comprises **{len(dm.get('entities', []))} entities** and "
      f"**{len(dm.get('relationships', []))} (estimated) relationships**, with "
      f"**{data.get('stats',{}).get('fields',0)} fields** across "
      f"**{data.get('stats',{}).get('records',0)} records**.\n")
    w(embed_mmd(diagrams_dir / "erd.mmd", "Figure 4.1 — Entity-relationship diagram (key entities)"))
    w("*This diagram shows the key data entities (by field count and shared usage) and their "
      "estimated relationships. Relationships are inferred from shared key-ish fields and are marked "
      "for data-architect confirmation.*\n")
    w("### 4.1 Key entities (top by field count)\n")
    w("| Entity | Source | Fields | Used by |")
    w("|---|---|---|---|")
    for ent in sorted(dm.get("entities", []), key=lambda e: -e.get("field_count", 0))[:20]:
        w(f"| {ent['name']} | {ent.get('source','')} | {ent.get('field_count',0)} | "
          f"{', '.join(ent.get('used_by', [])[:4])} |")
    w("")

    # Ch5 — business rules
    w("## 5. Business Rules Catalogue\n")
    rs_stats = rules.get("stats", {})
    w("Rules by category: " + ", ".join(f"{k} {v}" for k, v in rs_stats.get("by_category", {}).items())
      + f". Total **{rules.get('meta',{}).get('total_rules',0)}** rules in "
      f"{rules.get('meta',{}).get('total_rule_sets',0)} rule sets.\n")
    conf_mark = {"confirmed": "✓", "high": "✓", "medium": "⚠", "low": "⚠ — SME review required"}
    rules_by_id = {r["rule_id"]: r for r in rules.get("business_rules", [])}
    for rset in rules.get("rule_sets", []):
        w(f"### {rset['name']}\n")
        w(f"*Programs: {', '.join(rset.get('programs', [])[:6])} · Rules: {rset.get('rule_count',0)}*\n")
        for rid in rset.get("rule_ids", []):
            r = rules_by_id.get(rid)
            if not r:
                continue
            w(f"**{r['rule_id']} — {r['name']}**  ")
            w(f"Category: {r['category']} · Confidence: {r['confidence']} "
              f"{conf_mark.get(r['confidence'],'')}  ")
            w(r.get("description", "") + "  ")
            src = r.get("primary_source", {})
            w(f"*Source: {src.get('program_id') or r.get('defined_in') or ''}"
              + (f", {src.get('paragraph')}" if src.get("paragraph") else "")
              + (f", line {src.get('line')}" if src.get("line") else "") + "*\n")
    w("")

    # Ch6 — process descriptions
    w("## 6. Process Descriptions\n")
    for i, p in enumerate(logic.get("programs", []), start=1):
        pid = p["program_id"]
        w(f"### {pid}\n")
        w(f"*Complexity: {complexity_band(p.get('max_complexity',0))} · "
          f"Rules: {len(rbp.get(pid, []))}*\n")
        w((p.get("summary", "") or "No narrative available.") + "\n")
        w(embed_mmd(diagrams_dir / "diagrams" / f"flow_{pid}.mmd",
                    f"Figure 6.{i} — {pid} process/call flow"))
        w("*Solid arrows are calls to the program's own paragraphs; dashed arrows are calls to other "
          "programs or paragraphs.*\n")

    # Ch7 — component architecture
    w("## 7. Component Architecture\n")
    edges = inv.get("call_graph", {}).get("edges", [])
    fan_in: dict[str, int] = {}
    for e in edges:
        if e.get("to"):
            fan_in[e["to"]] = fan_in.get(e["to"], 0) + 1
    hubs = sorted(fan_in.items(), key=lambda x: -x[1])[:8]
    w("**Most-called programs (hubs):** " + ", ".join(f"{k} ({v})" for k, v in hubs) + ".\n")
    shared = sorted(((cb, len(u)) for cb, u in inv.get("copybook_map", {}).items()),
                    key=lambda x: -x[1])[:6]
    w("**Most-shared copybooks:** " + ", ".join(f"{k} ({v})" for k, v in shared) + ".\n")

    # Ch8 — error handling
    w("## 8. Error Handling and Recovery\n")
    eh = rules.get("error_handling_catalogue", [])
    w(f"{len(eh)} technical error-handling conditions were catalogued (file status, SQLCODE, CICS "
      f"RESP and similar checks). These are handled by standard status-code checks after each I/O "
      f"or SQL operation.\n")
    w("| Program | Paragraph | Condition |")
    w("|---|---|---|")
    for e in eh[:25]:
        w(f"| {e.get('program_id','')} | {e.get('paragraph','')} | "
          f"{(e.get('condition_text','') or '').replace('|','/')[:70]} |")
    if len(eh) > 25:
        w(f"| … | … | … and {len(eh)-25} more |")
    w("")

    # Ch9 — gaps
    w("## 9. Gaps and Assumptions Register\n")
    w("This chapter lists everything static analysis could not fully resolve. Critical and high "
      "gaps should be resolved with SME input before this document drives modernisation or testing.\n")
    w(gaps_markdown(gaps).split("\n", 2)[2])  # drop the gaps file's own H1 + count line-ish

    # Appendices
    w("## Appendices\n")
    w("- **Appendix A — Full data dictionary:** see `outputs/data/data_artifact.json` "
      f"({data.get('stats',{}).get('fields',0)} fields) and `outputs/data/data_layouts/`.")
    w("- **Appendix B — Program pseudocode:** see `outputs/logic/program_logic/*.json` "
      f"({logic.get('stats',{}).get('total_paragraphs_explained',0)} paragraphs).")
    w("- **Appendix C — Diagram index:** pending the Diagram agent.")
    w("")
    return "\n".join(L) + "\n"


def brd_summary_md(sysname, ctx, rules, data, gaps) -> str:
    top_sets = sorted(rules.get("rule_sets", []), key=lambda r: -r.get("rule_count", 0))[:5]
    crit = [g for g in gaps if g["severity"] in ("critical", "high")]
    out = [f"# {sysname} — Business Requirements Summary", "",
           f"**Full BRD:** brd.md · **Generated:** {datetime.now(timezone.utc):%Y-%m-%d}", "",
           "## What this system does", "", ctx["system_context"], "",
           "## Scale", "",
           f"- Programs: {ctx['programs']} ({ctx['batch']} batch, {ctx['online']} online)",
           f"- Business rules: {ctx['rules']} in {ctx['rule_sets']} rule sets",
           f"- Data: {ctx['records']} records, {ctx['fields']} fields",
           f"- Gaps: {ctx['gaps']} ({ctx['high_gaps']} high/critical)", "",
           "## Key rule sets", ""]
    for r in top_sets:
        out.append(f"- **{r['name']}** — {r.get('rule_count',0)} rules")
    out += ["", "## Critical / high gaps", ""]
    for g in crit[:10]:
        out.append(f"- **{g['gap_id']} ({g['severity']})** — {g['description']}")
    if not crit:
        out.append("- None flagged at critical/high severity.")
    out += ["", "## Next steps", "",
            f"1. Resolve {len(crit)} high/critical gaps with SME review (Chapter 9).",
            f"2. Validate the {rules.get('meta',{}).get('requires_sme_review',0)} low-confidence rules.",
            "3. Confirm the estimated data relationships with a data architect.",
            "4. Generate diagrams (Diagram agent) and embed them into the BRD.", ""]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build(paths: dict, output_dir: Path, sysname: str, model: str, use_llm: bool, diagrams_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    inv = load(paths["inventory"]); parser = load(paths["parser"]); data = load(paths["data"])
    logic = load(paths["logic"]); rules = load(paths["rules"])

    gaps = detect_gaps(inv, logic, rules, data)
    (output_dir / "gaps_register.json").write_text(
        json.dumps({"meta": {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "total_gaps": len(gaps)}, "gaps": gaps}, indent=2), encoding="utf-8")
    (output_dir / "gaps_register.md").write_text(gaps_markdown(gaps), encoding="utf-8")

    st = inv.get("stats", {})
    ctx = {
        "system_name": sysname, "programs": st.get("programs", 0),
        "batch": st.get("batch_programs", 0), "online": st.get("online_programs", 0),
        "copybooks": st.get("copybooks", 0), "jcl": st.get("jcl_jobs", 0),
        "rules": rules.get("meta", {}).get("total_rules", 0),
        "rule_sets": rules.get("meta", {}).get("total_rule_sets", 0),
        "records": data.get("stats", {}).get("records", 0),
        "fields": data.get("stats", {}).get("fields", 0),
        "paragraphs": logic.get("stats", {}).get("total_paragraphs_explained", 0),
        "gaps": len(gaps),
        "high_gaps": sum(1 for g in gaps if g["severity"] in ("critical", "high")),
    }

    usage = {"in": 0, "out": 0}
    mode = "templated (deterministic)"
    if use_llm:
        import anthropic
        narr = llm_narratives(anthropic.Anthropic(), model, ctx, usage)
        mode = f"LLM ({model})"
    else:
        narr = templated_narratives(ctx)

    ctx["system_context"] = narr.get("system_context", "")
    brd = assemble_brd(sysname, inv, parser, data, logic, rules, gaps, narr, diagrams_dir)
    (output_dir / "brd.md").write_text(brd, encoding="utf-8")
    (output_dir / "brd_summary.md").write_text(brd_summary_md(sysname, ctx, rules, data, gaps),
                                               encoding="utf-8")

    return {"ctx": ctx, "gaps": gaps, "mode": mode, "usage": usage,
            "chapters": 9, "pages_est": max(1, len(brd) // 2800)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 8 — hybrid BRD generator.")
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--parser", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--logic", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--output-dir", default="./outputs/final_report")
    ap.add_argument("--diagrams", default="./outputs/diagram")
    ap.add_argument("--system-name", default="Portfolio Management System")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    load_dotenv(base_dir)
    use_llm = (not args.no_llm) and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not args.no_llm and not use_llm:
        print("[note] No ANTHROPIC_API_KEY — using templated narratives. "
              "(Add a key, or use the AI-host path, for LLM-written synthesis prose.)")

    paths = {k: getattr(args, k) for k in ("inventory", "parser", "data", "logic", "rules")}
    res = build(paths, Path(args.output_dir), args.system_name, args.model, use_llm,
                Path(args.diagrams))

    print("=== Synthesis (BRD) Agent Complete ===")
    print(f"System                : {args.system_name}")
    print(f"BRD chapters written  : {res['chapters']}")
    print(f"Estimated pages       : ~{res['pages_est']}")
    print(f"Business rules         : {res['ctx']['rules']}")
    print(f"Data entities          : (see data model)")
    print(f"Gaps identified        : {len(res['gaps'])} "
          f"({sum(1 for g in res['gaps'] if g['severity'] in ('critical','high'))} high/critical)")
    print(f"Narrative mode         : {res['mode']}")
    print(f"Output                 : {Path(args.output_dir) / 'brd.md'}")
    print("======================================")


if __name__ == "__main__":
    main()
