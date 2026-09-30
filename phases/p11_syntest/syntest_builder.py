"""
Phase 11 — Synthetic Test Scenario Generator.

Reads rules_artifact.json (and optionally logic_artifact.json) and produces
synthetic_tests/synthetic_tests.json with:
  - SCN-XXX scenario objects (happy path, negative, boundary, exception,
    state transition, integration)
  - coverage per scenario type vs. minimum thresholds
  - a score breakdown (start 100, deductions, final score)
  - summary stats

Run from repo root:
    python -m phases.p11_syntest.syntest_builder [--output outputs/carddemo]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORY_TO_TYPES: dict[str, list[str]] = {
    "VALIDATION":  ["exception", "negative_path"],
    "LIMIT_CHECK": ["boundary"],
    "ROUTING":     ["happy_path"],
    "CALCULATION": ["state_transition"],
}

SCENARIO_PREFIX: dict[str, str] = {
    "happy_path":       "H",
    "negative_path":    "N",
    "boundary":         "B",
    "exception":        "E",
    "state_transition": "S",
    "integration":      "I",
}

COVERAGE_THRESHOLDS: dict[str, float] = {
    "happy_path":       95.0,
    "negative_path":    85.0,
    "boundary":         80.0,
    "exception":        80.0,
    "state_transition": 90.0,
    "integration":      85.0,
}

CONFIDENCE_RANK = {"confirmed": 4, "high": 3, "medium": 2, "low": 1}

DEDUCTION_WEIGHTS: dict[str, float] = {
    "happy_path":       0,     # no penalty for meeting target (only penalise deficit)
    "negative_path":    0.07,
    "boundary":         0.10,
    "exception":        0.07,
    "state_transition": 0.10,
    "integration":      0.11,
}

BLOCKING_PENALTY  = 4   # points per blocking finding
REPEATED_PENALTY  = 2   # flat penalty if any duplicate rules exist


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _det_checklist(rule: dict, scenario_type: str) -> dict[str, bool]:
    cat   = rule.get("category", "")
    conf  = rule.get("confidence", "low")
    prog  = (rule.get("primary_source") or {}).get("program_id", "")
    cond  = (rule.get("condition") or {}).get("text", "")
    progs = rule.get("implemented_in_programs", [])
    rank  = CONFIDENCE_RANK.get(conf, 0)

    return {
        "actor_defined":              bool(prog),
        "inputs_defined":             bool(cond),
        "expected_behavior_defined":  bool(rule.get("description", "")),
        "resulting_state_defined":    cat in ("ROUTING", "CALCULATION"),
        "external_dependencies_defined": len(progs) > 1,
        "starting_state_defined":     bool((rule.get("condition") or {}).get("pattern", "")),
        "business_rules_defined":     bool(rule.get("rule_id", "")),
        "failure_behavior_defined":   cat in ("VALIDATION", "LIMIT_CHECK"),
        "downstream_effects_defined": len(progs) > 1,
        "acceptance_test_ready":      rank >= 3,   # confirmed or high
    }


def _what_it_tests(scenario_type: str, checklist: dict[str, bool]) -> list[str]:
    base = ["actor", "inputs", "business rules", "expected behavior"]
    if checklist.get("resulting_state_defined"):
        base.append("resulting state")
    if checklist.get("acceptance_test_ready"):
        base.append("acceptance-test readiness")
    if scenario_type in ("negative_path", "exception") and checklist.get("failure_behavior_defined"):
        base.append("failure behavior")
    if scenario_type == "integration":
        base.append("cross-program behavior")
    return base


def _condition_text(rule: dict, scenario_type: str) -> str:
    cond  = (rule.get("condition") or {}).get("text", "—")
    prog  = (rule.get("primary_source") or {}).get("program_id", "")
    para  = (rule.get("primary_source") or {}).get("paragraph", "")
    loc   = f"{prog} / {para}" if para else prog

    if scenario_type == "happy_path":
        return (f"GIVEN the system is in normal operational state at {loc}; "
                f"WHEN {cond.lower().rstrip('.')} is satisfied; "
                f"THEN the rule applies successfully and processing continues.")
    if scenario_type in ("negative_path", "exception"):
        return (f"GIVEN the system is at {loc}; "
                f"WHEN {cond.lower().rstrip('.')} is NOT met; "
                f"THEN the rule fires the exception / rejection path.")
    if scenario_type == "boundary":
        return (f"GIVEN the system is at {loc}; "
                f"WHEN the value is at or near the limit boundary of '{cond.lower().rstrip('.')}'; "
                f"THEN the system handles both sides of the threshold correctly.")
    if scenario_type == "state_transition":
        return (f"GIVEN {loc} receives a trigger; "
                f"WHEN {cond.lower().rstrip('.')} evaluates; "
                f"THEN the system transitions to the correct state and all side-effects apply.")
    if scenario_type == "integration":
        return (f"GIVEN multiple programs participate in the flow originating at {loc}; "
                f"WHEN {cond.lower().rstrip('.')} spans program boundaries; "
                f"THEN the end-to-end chain produces a consistent result.")
    return f"GIVEN/WHEN/THEN derived from: {cond}"


def _expected_result(rule: dict, scenario_type: str) -> str:
    name = rule.get("name", "—")
    cat  = rule.get("category", "—")
    prog = (rule.get("primary_source") or {}).get("program_id", "")
    progs = rule.get("implemented_in_programs", [])

    if scenario_type == "happy_path":
        return (f"'{name}' rule is satisfied. {prog} routes to the correct success path. "
                f"No error codes raised.")
    if scenario_type == "negative_path":
        return (f"'{name}' rule rejects the input. {prog} sets the appropriate error indicator "
                f"and control returns to the caller.")
    if scenario_type == "exception":
        return (f"'{name}' exception branch is executed. {prog} handles the failure case "
                f"gracefully without abnormal termination.")
    if scenario_type == "boundary":
        return (f"At exactly the threshold defined by '{name}', {prog} produces the "
                f"boundary outcome — neither over-limit nor under-limit path is skipped.")
    if scenario_type == "state_transition":
        return (f"After '{name}' evaluates in {prog}, the system state is updated "
                f"consistently and downstream fields reflect the new state.")
    if scenario_type == "integration":
        all_progs = ", ".join(progs[:4]) + ("…" if len(progs) > 4 else "")
        return (f"All programs involved ({all_progs}) agree on the outcome of '{name}'. "
                f"No duplicate processing or conflicting state across program boundaries.")
    return f"Expected result for {cat} rule '{name}'."


def _why_generated(rule: dict, scenario_type: str) -> str:
    name = rule.get("name", "—")
    conf = rule.get("confidence", "—")
    rs   = rule.get("rule_set", "—")

    phrases = {
        "happy_path":       f"Confirm the primary success path for '{name}' is fully rule-backed (rule set: {rs}).",
        "negative_path":    f"Verify the system correctly rejects or routes away when '{name}' fails.",
        "boundary":         f"Stress-test the boundary condition in '{name}' to prevent off-by-one defects.",
        "exception":        f"Ensure the exception branch of '{name}' is exercised and produces a clean exit.",
        "state_transition": f"Validate that the state change driven by '{name}' propagates correctly to all dependents.",
        "integration":      f"Confirm '{name}' behaves consistently across all programs that implement it (confidence: {conf}).",
    }
    return phrases.get(scenario_type, f"Cover '{name}' at scenario level.")


def _scenario_status(checklist: dict[str, bool], rule: dict) -> str:
    conf = rule.get("confidence", "low")
    if CONFIDENCE_RANK.get(conf, 0) >= 3:
        return "pass"
    return "pass" if all(checklist.values()) else "with_gaps"


# ---------------------------------------------------------------------------
# Core builders
# ---------------------------------------------------------------------------

def _build_scenarios_from_rules(rules: list[dict]) -> list[dict]:
    counters: dict[str, int] = {t: 0 for t in SCENARIO_PREFIX}
    scenarios: list[dict] = []

    # Generate one or two scenarios per rule (skip very low confidence duplicates)
    for rule in rules:
        cat   = rule.get("category", "")
        conf  = rule.get("confidence", "low")
        is_dup = rule.get("is_duplicated", False)

        types_for_rule = CATEGORY_TO_TYPES.get(cat, [])
        if not types_for_rule:
            continue

        # Only generate for rules with medium confidence or better (filter noise)
        if CONFIDENCE_RANK.get(conf, 0) < 2:
            continue

        # If duplicated, only generate for confirmed rules (avoid scenario bloat)
        if is_dup and CONFIDENCE_RANK.get(conf, 0) < 4:
            continue

        for stype in types_for_rule:
            counters[stype] += 1
            prefix = SCENARIO_PREFIX[stype]
            scn_id = f"SCN-{prefix}{counters[stype]:02d}"
            checklist = _det_checklist(rule, stype)
            status    = _scenario_status(checklist, rule)

            scenarios.append({
                "id":              scn_id,
                "type":            stype,
                "status":          status,
                "rule_id":         rule.get("rule_id", ""),
                "rule_set":        rule.get("rule_set", ""),
                "name":            rule.get("name", "—"),
                "confidence":      conf,
                "persona":         f"PER-{counters[stype]:03d}",
                "requirements":    [rule.get("rule_id", "")],
                "condition":       _condition_text(rule, stype),
                "expected_result": _expected_result(rule, stype),
                "why_generated":   _why_generated(rule, stype),
                "what_it_tests":   _what_it_tests(stype, checklist),
                "determinism":     checklist,
                "programs":        rule.get("implemented_in_programs", []),
            })

    return scenarios


def _build_integration_scenarios(rule_sets: list[dict], rules_by_id: dict[str, dict]) -> list[dict]:
    counters_i = 0
    scenarios: list[dict] = []

    for rs in rule_sets:
        rule_ids = rs.get("rule_ids", [])
        programs = rs.get("programs", [])
        # Only generate integration scenarios for sets that span 2+ programs
        if len(programs) < 2:
            continue

        # Pick the highest-confidence rule in this set as the anchor
        anchor = None
        for rid in rule_ids:
            r = rules_by_id.get(rid)
            if r and CONFIDENCE_RANK.get(r.get("confidence", "low"), 0) >= 2:
                if anchor is None or CONFIDENCE_RANK.get(r["confidence"], 0) > CONFIDENCE_RANK.get(anchor["confidence"], 0):
                    anchor = r
        if not anchor:
            continue

        counters_i += 1
        scn_id    = f"SCN-I{counters_i:02d}"
        checklist = _det_checklist(anchor, "integration")
        status    = _scenario_status(checklist, anchor)

        scenarios.append({
            "id":              scn_id,
            "type":            "integration",
            "status":          status,
            "rule_id":         anchor.get("rule_id", ""),
            "rule_set":        rs.get("name", rs.get("rule_set_id", "—")),
            "name":            rs.get("name", anchor.get("name", "—")),
            "confidence":      anchor.get("confidence", "—"),
            "persona":         f"PER-I{counters_i:02d}",
            "requirements":    rule_ids[:5],
            "condition":       _condition_text(anchor, "integration"),
            "expected_result": _expected_result(anchor, "integration"),
            "why_generated":   _why_generated(anchor, "integration"),
            "what_it_tests":   _what_it_tests("integration", checklist),
            "determinism":     checklist,
            "programs":        programs,
        })

    return scenarios


# ---------------------------------------------------------------------------
# Coverage + scoring
# ---------------------------------------------------------------------------

def _compute_coverage(scenarios: list[dict]) -> list[dict]:
    by_type: dict[str, dict] = {t: {"total": 0, "passed": 0} for t in SCENARIO_PREFIX}

    for s in scenarios:
        t = s["type"]
        if t not in by_type:
            continue
        by_type[t]["total"] += 1
        if s["status"] == "pass":
            by_type[t]["passed"] += 1

    coverage = []
    for stype, threshold in COVERAGE_THRESHOLDS.items():
        totl   = by_type[stype]["total"]
        passed = by_type[stype]["passed"]
        achieved = round(passed / totl * 100, 1) if totl else 0.0
        coverage.append({
            "type":         stype,
            "total":        totl,
            "passed":       passed,
            "achieved_pct": achieved,
            "min_pct":      threshold,
            "meets_target": achieved >= threshold,
        })

    return coverage


def _compute_score(coverage: list[dict], scenarios: list[dict]) -> dict:
    score     = 100.0
    deductions: list[dict] = []

    # 1. Coverage deficit deductions
    for entry in coverage:
        stype    = entry["type"]
        deficit  = max(0.0, entry["min_pct"] - entry["achieved_pct"])
        if deficit > 0:
            weight   = DEDUCTION_WEIGHTS.get(stype, 0.07)
            penalty  = round(deficit * weight, 1)
            score   -= penalty
            deductions.append({
                "label":   f"{stype} (deficit {deficit:.0f}pp)",
                "penalty": -round(penalty),
            })

    # 2. Blocking scenarios (acceptance_test_ready = False)
    blocking = [s for s in scenarios if not s["determinism"].get("acceptance_test_ready", True)]
    blocking_count = len(blocking)
    if blocking_count:
        penalty  = min(blocking_count * BLOCKING_PENALTY, 20)
        score   -= penalty
        deductions.append({"label": f"Blocking penalty ({blocking_count} scenarios)", "penalty": -penalty})

    # 3. Repeated evidence (any duplicate rules used)
    has_dups = any(len(s.get("requirements", [])) > 0 and
                   sum(1 for s2 in scenarios if s2.get("rule_id") == s.get("rule_id")) > 1
                   for s in scenarios)
    if has_dups:
        score -= REPEATED_PENALTY
        deductions.append({"label": "Repeated evidence", "penalty": -REPEATED_PENALTY})

    # 4. Coverage penalty (number of categories below threshold)
    below = sum(1 for e in coverage if not e["meets_target"])
    if below:
        cov_penalty = below * 3
        score      -= cov_penalty
        deductions.append({"label": f"Coverage penalty ({below} categories below target)", "penalty": -cov_penalty})

    final_score = max(0, round(score))

    # Build finding IDs for blocking scenarios
    blocking_findings = []
    for i, s in enumerate(blocking[:5], 1):
        fid = f"FIND-ST-{i:03d}"
        blocking_findings.append({
            "id":       fid,
            "severity": "HIGH" if not s["determinism"].get("acceptance_test_ready") else "MEDIUM",
            "scenario": s["id"],
            "rule_id":  s["rule_id"],
            "n":        1,
        })

    return {
        "starting_score":    100,
        "final_score":       final_score,
        "deductions":        deductions,
        "blocking_count":    blocking_count,
        "blocking_findings": blocking_findings,
        "quality_rating":    "pass" if final_score >= 70 and blocking_count == 0 else "needs_review",
    }


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build(out_dir: Path) -> dict:
    rules_data = _read(out_dir / "rules/rules_artifact.json") or {}
    rules: list[dict] = rules_data.get("business_rules", [])
    rule_sets: list[dict] = rules_data.get("rule_sets", [])

    if not rules:
        print(f"[WARN] No rules found in {out_dir}/rules/rules_artifact.json — nothing to generate.")
        return {}

    rules_by_id = {r["rule_id"]: r for r in rules}

    print(f"[p11_syntest] Loaded {len(rules)} rules, {len(rule_sets)} rule sets")

    # Generate scenarios
    rule_scenarios = _build_scenarios_from_rules(rules)
    integ_scenarios = _build_integration_scenarios(rule_sets, rules_by_id)
    all_scenarios = rule_scenarios + integ_scenarios

    print(f"[p11_syntest] Generated {len(all_scenarios)} scenarios "
          f"({len(rule_scenarios)} rule-based, {len(integ_scenarios)} integration)")

    coverage       = _compute_coverage(all_scenarios)
    score_breakdown = _compute_score(coverage, all_scenarios)

    total   = len(all_scenarios)
    passed  = sum(1 for s in all_scenarios if s["status"] == "pass")
    with_gaps = sum(1 for s in all_scenarios if s["status"] == "with_gaps")

    by_type = {}
    for s in all_scenarios:
        by_type[s["type"]] = by_type.get(s["type"], 0) + 1

    stats = {
        "total":     total,
        "passed":    passed,
        "with_gaps": with_gaps,
        "failed":    total - passed - with_gaps,
        "by_type":   by_type,
        "quality_score": score_breakdown["final_score"],
        "blocking_findings": score_breakdown["blocking_count"],
    }

    artifact = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rules_source": str(out_dir / "rules/rules_artifact.json"),
            "total_rules_processed": len(rules),
        },
        "stats":           stats,
        "scenarios":       all_scenarios,
        "coverage":        coverage,
        "score_breakdown": score_breakdown,
    }

    # Write output
    out_path = out_dir / "synthetic_tests"
    out_path.mkdir(parents=True, exist_ok=True)
    dest = out_path / "synthetic_tests.json"
    dest.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[p11_syntest] Written → {dest}")

    return artifact


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 11 — Synthetic Test Scenario Generator")
    ap.add_argument("--output", default="outputs/carddemo",
                    help="Path to harness output directory (default: outputs/carddemo)")
    args = ap.parse_args()

    out_dir = Path(args.output).resolve()
    if not out_dir.exists():
        print(f"[ERROR] Output directory not found: {out_dir}")
        sys.exit(1)

    result = build(out_dir)
    if not result:
        sys.exit(1)

    stats = result.get("stats", {})
    print(f"\n  Scenarios : {stats.get('total', 0)}")
    print(f"  Passed    : {stats.get('passed', 0)}")
    print(f"  With gaps : {stats.get('with_gaps', 0)}")
    print(f"  Score     : {stats.get('quality_score', '—')}/100")


if __name__ == "__main__":
    main()
