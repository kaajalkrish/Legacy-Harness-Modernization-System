#!/usr/bin/env python3
"""
logic_builder.py  —  Phase 6: Logic phase.

Python port of the "4_logic" agent. For each COBOL program it:

  Steps 1-2 (deterministic Python, NO LLM):
    * gathers the program's clues — context sheet (Phase 4), data fields
      (Phase 5), paragraphs + control-flow (Phase 2) — and the raw COBOL source
    * packages them into one message

  Step 3 (LLM — the ONLY paid step):
    * asks Claude to explain each paragraph in plain-English pseudocode,
      returned as structured JSON (flags ambiguous logic and branches)

  Step 4 (deterministic Python, NO LLM):
    * writes program_logic/<PROGRAM>_logic.json + a combined logic_artifact.json

Inputs
  --inventory    outputs/discovery/inventory.json   (Phase 1: repo_root)
  --ast-dir      outputs/analysis                    (Phase 2: raw_structure/<PROGRAM>.json)
  --context-dir  outputs/context                     (Phase 4: <PROGRAM>_context.txt)
  --data         outputs/data/data_artifact.json     (Phase 5: field dictionary)
  --output-dir   outputs/logic                       (where to write)
  --model        Claude model id (default: env ANTHROPIC_MODEL or claude-opus-4-8)
  --program-filter  comma-separated PROGRAM-IDs to limit scope

Usage
    python -m logic.logic_builder --inventory <inv.json> --ast-dir <outputs/analysis> \
        --context-dir <outputs/context> --data <outputs/data/data_artifact.json> \
        --output-dir <outputs/logic>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

AGENT_VERSION = "4_logic_python@1.0"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

# Rough per-1M-token pricing for a cost estimate (input, output), USD.
PRICING = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

MAX_FIELDS_IN_PROMPT = 80  # keep the prompt small; the dictionary can be huge

SYSTEM_PROMPT = """You are a COBOL reverse-engineering assistant. You are given ONE COBOL program:
background about it, its data fields, and its raw source split into paragraphs. Translate every
paragraph into clear, structured, plain-English pseudocode a business analyst who does not know
COBOL can read. NEVER leave raw COBOL untranslated in the output.

STYLE CONVENTIONS
- Conditionals: IF / ELSE IF / ELSE / END IF
- PERFORM UNTIL (test before): WHILE condition DO / END WHILE
- PERFORM WITH TEST AFTER: DO / WHILE condition END DO
- PERFORM VARYING: FOR index FROM x TO y STEP z / END FOR
- EVALUATE: SELECT CASE field / WHEN value / ELSE / END SELECT
- EVALUATE TRUE: expand to IF / ELSE IF / ELSE
- Static CALL: CALL program-name PASSING (params). Dynamic CALL: CALL [dynamic: variable] PASSING (params)  !! REVIEW
- File I/O: READ file INTO record; WRITE record TO file; keyed READ: READ file WHERE key = ...
- Arithmetic: COMPUTE field = expression (ROUNDED -> ROUND(...); ON SIZE ERROR -> an overflow branch)
- Condense trivial init (MOVE ZEROS / MOVE SPACES) as CLEAR field
- Expand 88-level condition names to their meaning (e.g. IF ACCT-OVERDRAWN -> IF account balance is negative)
- Inline explanations of COBOL idioms with `-- annotation`; indent 2 spaces per nesting level

VERB GUIDANCE
- MOVE -> SET target = source (ZEROS/SPACES -> CLEAR; HIGH-VALUES -> end-of-file sentinel; CORRESPONDING -> copy matching fields)
- COMPUTE/ADD/SUBTRACT/MULTIPLY/DIVIDE -> COMPUTE result = expression
- READ ... AT END / NOT AT END -> READ next record; IF end of file THEN ... ELSE ...
- WRITE/REWRITE/DELETE ... INVALID KEY -> WRITE/UPDATE/DELETE record; handle the key/write-error branch
- EXEC CICS -> CICS <verb> (READ/WRITE/REWRITE/DELETE/SEND MAP/RECEIVE MAP/LINK/XCTL/RETURN/GETMAIN/ABEND) with file/key/into + a response-code check
- EXEC SQL -> SQL SELECT/INSERT/UPDATE/DELETE/DECLARE/OPEN/FETCH/CLOSE ...; ALWAYS add CHECK SQLCODE as a branch
- STRING -> CONCATENATE ...; UNSTRING -> SPLIT ... BY delimiter; INSPECT -> COUNT / REPLACE characters
- OPEN INPUT/OUTPUT/I-O -> OPEN file for READ-ONLY / WRITE / READ-WRITE; CLOSE -> CLOSE file
- STOP RUN -> TERMINATE program; GOBACK / EXIT PROGRAM -> RETURN to caller

GROUNDING RULES
- Describe only what the code actually does. Never invent logic or literal values; use named placeholders for runtime values.
- If a statement is ambiguous or its target cannot be determined (e.g. a dynamic CALL), set ambiguous=true, explain in notes, and mark the line in annotations.
- If a verb cannot be translated, keep the raw line prefixed with `!! UNTRANSLATED:` and set ambiguous=true.
- Use the provided data fields to expand field meaning; if a field is unknown, use its name as-is.

PER PARAGRAPH, ALSO REPORT
- branches: each IF / EVALUATE / GO TO / PERFORM decision (short text)
- calls_made: paragraph or program names this paragraph PERFORMs or CALLs
- field_references: the key data fields this paragraph reads or writes
- complexity_score (1-10): +1 per IF, +1 per EVALUATE, +2 per nested IF, +1 per loop, +2 per GO TO, +3 per ALTER, +1 per CALL, +1 per I/O op. (1-3 simple, 4-6 moderate, 7-9 complex, 10+ critical.)
- annotations: {line, note} for COBOL idioms or anything needing SME review

PROGRAM SUMMARY (3-8 sentences): what the program is (batch/online), what it reads/writes, the main loop, the top business operations, and the error conditions handled."""

# Structured-output schema: exactly what we want back (Udara-style rich per-paragraph fields).
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "program_summary": {"type": "string"},
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "pseudocode": {"type": "string"},
                    "branches": {"type": "array", "items": {"type": "string"}},
                    "calls_made": {"type": "array", "items": {"type": "string"}},
                    "field_references": {"type": "array", "items": {"type": "string"}},
                    "complexity_score": {"type": "integer"},
                    "ambiguous": {"type": "boolean"},
                    "annotations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "line": {"type": "integer"},
                                "note": {"type": "string"},
                            },
                            "required": ["line", "note"],
                            "additionalProperties": False,
                        },
                    },
                    "notes": {"type": "string"},
                },
                "required": ["name", "pseudocode", "branches", "calls_made",
                             "field_references", "complexity_score", "ambiguous",
                             "annotations", "notes"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["program_summary", "paragraphs"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def load_dotenv(base: Path) -> None:
    """Minimal .env loader so ANTHROPIC_API_KEY in the project .env is picked up."""
    env_path = base / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_source_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


# ---------------------------------------------------------------------------
# Step 1 — gather the clues for one program (deterministic)
# ---------------------------------------------------------------------------

def gather_fields(program_id: str, data_artifact: dict) -> list[dict]:
    """The data-dictionary fields this program declares or uses."""
    out = []
    for f in data_artifact.get("fields", []):
        used_by = f.get("used_by") or []
        if f.get("source") == program_id or program_id in used_by:
            out.append(f)
    return out[:MAX_FIELDS_IN_PROMPT]


def paragraph_slices(ast: dict, source_lines: list[str]) -> list[dict]:
    """Each paragraph with its raw COBOL source text."""
    paras = ast.get("procedure_division", {}).get("paragraphs", []) or []
    slices = []
    for p in paras:
        start = p.get("start_line") or 1
        end = p.get("end_line") or start
        text = "\n".join(source_lines[start - 1:end])
        slices.append({"name": p.get("name"), "start_line": start, "end_line": end, "source": text})
    return slices


# ---------------------------------------------------------------------------
# Step 2 — package the clues + raw COBOL into one message (deterministic)
# ---------------------------------------------------------------------------

def build_user_message(program_id: str, context_text: str, fields: list[dict],
                       paragraphs: list[dict]) -> str:
    lines = [f"# Program: {program_id}", ""]

    lines.append("## Background (context sheet)")
    lines.append(context_text.strip() if context_text else "(none available)")
    lines.append("")

    lines.append("## Data fields (name : type : picture)")
    if fields:
        for f in fields:
            desc = f.get("type", "?")
            if f.get("pic"):
                desc += f" PIC {f['pic']}"
            if f.get("conditions"):
                desc += f"  [values: {', '.join(f['conditions'].keys())}]"
            lines.append(f"- {f.get('name')} : {desc}")
    else:
        lines.append("(none found)")
    lines.append("")

    lines.append("## Raw COBOL source, by paragraph")
    for p in paragraphs:
        lines.append(f"\n### Paragraph: {p['name']}  (lines {p['start_line']}-{p['end_line']})")
        lines.append("```cobol")
        lines.append(p["source"] or "(empty)")
        lines.append("```")

    lines.append("")
    lines.append("Explain every paragraph above in plain-English pseudocode, following the rules.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 3 — the LLM call (the only paid step)
# ---------------------------------------------------------------------------

def explain_program(client, model: str, user_message: str) -> tuple[dict, dict]:
    """Returns (parsed_logic, usage_dict). Raises on API error."""
    resp = client.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = json.loads(text)
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }
    return data, usage


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def build(inventory_path: Path, ast_dir: Path, context_dir: Path, data_path: Path,
          output_dir: Path, model: str, program_filter: Optional[set]) -> dict:
    import anthropic  # imported here so the module loads even without the key/SDK for --help

    inventory = load_json(inventory_path)
    repo_root = Path(inventory.get("meta", {}).get("repo_root", "."))
    data_artifact = load_json(data_path) if data_path.exists() else {"fields": []}

    program_logic_dir = output_dir / "program_logic"
    program_logic_dir.mkdir(parents=True, exist_ok=True)

    raw_structure = ast_dir / "raw_structure"
    ast_files = sorted(raw_structure.glob("*.json")) if raw_structure.exists() else []

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY / profile

    program_summaries: list[dict] = []
    issues: list[dict] = []
    total_in = total_out = 0
    programs_done = programs_failed = 0

    for ast_path in ast_files:
        try:
            ast = load_json(ast_path)
        except (OSError, json.JSONDecodeError) as exc:
            issues.append({"severity": "warning", "type": "ast_read_error",
                           "message": f"{ast_path.name}: {exc}"})
            continue

        program_id = ast.get("meta", {}).get("program_id", ast_path.stem).upper()
        if program_filter and program_id not in program_filter:
            continue

        # --- Step 1: gather clues (deterministic) ---
        context_path = context_dir / f"{program_id}_context.txt"
        context_text = context_path.read_text(encoding="utf-8", errors="replace") if context_path.exists() else ""

        source_file = ast.get("meta", {}).get("source_file")
        source_lines: list[str] = []
        if source_file and Path(source_file).exists():
            source_lines = read_source_lines(Path(source_file))
        elif inventory:  # fallback via repo_root + relative path
            entry = next((e for e in inventory.get("file_registry", []) if e.get("id") == program_id), None)
            if entry:
                cand = repo_root / (entry.get("relative_path") or entry.get("path"))
                if cand.exists():
                    source_lines = read_source_lines(cand)

        fields = gather_fields(program_id, data_artifact)
        paragraphs = paragraph_slices(ast, source_lines)
        if not paragraphs:
            issues.append({"severity": "info", "type": "no_paragraphs",
                           "message": f"{program_id}: no paragraphs to explain, skipped"})
            continue

        # --- Step 2: package the message (deterministic) ---
        user_message = build_user_message(program_id, context_text, fields, paragraphs)

        # --- Step 3: the LLM call (paid) ---
        print(f"  · {program_id}: explaining {len(paragraphs)} paragraph(s) via {model} ...")
        try:
            logic, usage = explain_program(client, model, user_message)
        except Exception as exc:  # keep the batch alive on any single failure
            programs_failed += 1
            issues.append({"severity": "error", "type": "llm_error",
                           "message": f"{program_id}: {type(exc).__name__}: {exc}"})
            continue

        total_in += usage["input_tokens"]
        total_out += usage["output_tokens"]
        programs_done += 1

        # --- Step 4: save (deterministic) ---
        # Attach line ranges from Phase 2 (deterministic — we don't ask the LLM for them).
        para_lines = {p["name"]: [p["start_line"], p["end_line"]] for p in paragraphs}
        explained = logic.get("paragraphs", [])
        for p in explained:
            if p.get("name") in para_lines:
                p["line_range"] = para_lines[p["name"]]

        out = {
            "meta": {"program_id": program_id, "source_file": source_file,
                     "model": model, "agent_version": AGENT_VERSION},
            "summary": logic.get("program_summary", ""),
            "paragraphs": explained,
            "usage": usage,
        }
        (program_logic_dir / f"{program_id}_logic.json").write_text(
            json.dumps(out, indent=2), encoding="utf-8")

        complexities = [p.get("complexity_score", 0) or 0 for p in explained]
        program_summaries.append({
            "program_id": program_id,
            "logic_file": f"program_logic/{program_id}_logic.json",
            "paragraphs_explained": len(explained),
            "ambiguous_paragraphs": sum(1 for p in explained if p.get("ambiguous")),
            "max_complexity": max(complexities) if complexities else 0,
            "critical_paragraphs": sum(1 for c in complexities if c >= 10),
            "summary": logic.get("program_summary", ""),
        })

    in_price, out_price = PRICING.get(model, (5.0, 25.0))
    est_cost = total_in / 1_000_000 * in_price + total_out / 1_000_000 * out_price

    artifact = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_version": AGENT_VERSION,
            "model": model,
            "programs_explained": programs_done,
            "programs_failed": programs_failed,
        },
        "stats": {
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "estimated_cost_usd": round(est_cost, 4),
            "total_paragraphs_explained": sum(p["paragraphs_explained"] for p in program_summaries),
            "total_ambiguous_paragraphs": sum(p["ambiguous_paragraphs"] for p in program_summaries),
            "total_critical_paragraphs": sum(p["critical_paragraphs"] for p in program_summaries),
        },
        "programs": program_summaries,
        "issues": issues,
    }
    return artifact


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(artifact: dict, output_path: Path) -> None:
    m, s = artifact["meta"], artifact["stats"]
    print("=== Logic Agent Complete ===")
    print(f"Programs explained     : {m['programs_explained']}")
    print(f"Programs failed        : {m['programs_failed']}")
    print(f"Paragraphs translated  : {s['total_paragraphs_explained']}")
    print(f"Ambiguous paragraphs   : {s['total_ambiguous_paragraphs']}")
    print(f"Critical paragraphs    : {s['total_critical_paragraphs']}  (complexity >= 10)")
    print(f"Model                  : {m['model']}")
    print(f"Tokens (in/out)        : {s['total_input_tokens']} / {s['total_output_tokens']}")
    print(f"Estimated cost         : ${s['estimated_cost_usd']}")
    print(f"Output                 : {output_path}")
    print("============================")


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 6 — LLM-assisted COBOL logic / pseudocode builder.")
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--ast-dir", required=True, help="Phase 2 output dir (contains raw_structure/)")
    ap.add_argument("--context-dir", required=True, help="Phase 4 output dir (context sheets)")
    ap.add_argument("--data", required=True, help="Phase 5 data_artifact.json")
    ap.add_argument("--output-dir", default="./outputs/logic")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--program-filter", default=None, help="Comma-separated PROGRAM-IDs")
    args = ap.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    load_dotenv(base_dir)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[ERROR] ANTHROPIC_API_KEY is not set. Put it in the project .env file:\n"
              "        ANTHROPIC_API_KEY=sk-ant-...\n"
              "        (Phase 6 is the only phase that calls the LLM.)", file=sys.stderr)
        sys.exit(2)

    program_filter = None
    if args.program_filter:
        program_filter = {p.strip().upper() for p in args.program_filter.split(",") if p.strip()}

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting Phase 6: Logic (model={args.model}) ...")
    artifact = build(
        Path(args.inventory).resolve(), Path(args.ast_dir).resolve(),
        Path(args.context_dir).resolve(), Path(args.data).resolve(),
        output_dir, args.model, program_filter,
    )

    output_path = output_dir / "logic_artifact.json"
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print_summary(artifact, output_path)


if __name__ == "__main__":
    main()
