"""
Phase 11 — Synthetic Test Scenario Generator.

Reads rules_artifact.json and produces synthetic_tests/synthetic_tests.json with:
  - SCN-XXX scenario objects with full BDD conditions, gap reasons, SME actions
  - coverage per scenario type vs. minimum thresholds
  - a score breakdown with plain-English next steps
  - executive summary readable by business leaders and SMEs alike

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

TYPE_LABELS: dict[str, str] = {
    "happy_path":       "Happy Path",
    "negative_path":    "Negative Path",
    "boundary":         "Boundary",
    "exception":        "Exception",
    "state_transition": "State Transition",
    "integration":      "Integration",
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

CONFIDENCE_LABELS = {
    "confirmed": "confirmed — evidence is unambiguous in the source code",
    "high":      "high — strong pattern match, business meaning very likely correct",
    "medium":    "medium — condition is documented, but business meaning needs SME confirmation",
    "low":       "low — weak pattern match, needs significant SME clarification",
}

DEDUCTION_WEIGHTS: dict[str, float] = {
    "happy_path":       0,
    "negative_path":    0.07,
    "boundary":         0.10,
    "exception":        0.07,
    "state_transition": 0.10,
    "integration":      0.11,
}

BLOCKING_PENALTY = 4
REPEATED_PENALTY = 2


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
        "actor_defined":               bool(prog),
        "inputs_defined":              bool(cond),
        "expected_behavior_defined":   bool(rule.get("description", "")),
        "resulting_state_defined":     cat in ("ROUTING", "CALCULATION"),
        "external_dependencies_defined": len(progs) > 1,
        "starting_state_defined":      bool((rule.get("condition") or {}).get("pattern", "")),
        "business_rules_defined":      bool(rule.get("rule_id", "")),
        "failure_behavior_defined":    cat in ("VALIDATION", "LIMIT_CHECK"),
        "downstream_effects_defined":  len(progs) > 1,
        "acceptance_test_ready":       rank >= 3,
    }


def _gap_reasons(rule: dict, checklist: dict[str, bool], scenario_type: str) -> list[str]:
    """
    Plain-English explanations of gaps that actually block or meaningfully limit testing.
    Only reports items that a QA engineer or SME needs to act on — not structural nice-to-haves.
    """
    reasons = []
    conf  = rule.get("confidence", "low")
    cat   = rule.get("category", "—")
    prog  = (rule.get("primary_source") or {}).get("program_id", "—")
    para  = (rule.get("primary_source") or {}).get("paragraph", "—")
    progs = rule.get("implemented_in_programs", [])

    # BLOCKING: low/medium confidence means the business meaning is uncertain
    if not checklist["acceptance_test_ready"]:
        reasons.append(
            f"Rule confidence is '{conf}' — the automated analysis identified this condition in "
            f"{prog} / {para} but cannot fully determine its business intent. "
            f"An SME must confirm what this rule means before it becomes a runnable test."
        )

    # BLOCKING for state-transition: without a defined post-state, the test has no pass criterion
    if scenario_type == "state_transition" and not checklist["resulting_state_defined"]:
        reasons.append(
            f"State Transition scenarios require a defined post-condition (what the system state "
            f"looks like AFTER the rule fires). The rule category ({cat}) does not define this — "
            f"the expected field values, return codes, or records after execution must be documented."
        )

    # BLOCKING for exception/negative: without a failure path the test cannot assert the right outcome
    if scenario_type in ("exception", "negative_path") and not checklist["failure_behavior_defined"]:
        reasons.append(
            f"Exception and Negative Path scenarios must define what happens when the rule is NOT "
            f"satisfied — which error code is returned, what message is written, or whether "
            f"processing halts. The rule category ({cat}) does not define this failure path."
        )

    # ADVISORY for integration scenarios with no cross-program evidence
    if scenario_type == "integration" and not checklist["downstream_effects_defined"]:
        reasons.append(
            f"This integration scenario is anchored to a single program ({prog}). "
            f"Cross-program behaviour has not been verified automatically. "
            f"Confirm with the development team whether other programs consume this rule's outcome."
        )

    return reasons


def _sme_action(rule: dict, checklist: dict[str, bool], scenario_type: str) -> str | None:
    """
    A single, clear directive telling the SME exactly what to do to make this scenario test-ready.
    Returns None when the scenario is already fully ready.
    """
    conf = rule.get("confidence", "low")
    cond = (rule.get("condition") or {}).get("text", "—")
    prog = (rule.get("primary_source") or {}).get("program_id", "—")
    para = (rule.get("primary_source") or {}).get("paragraph", "—")
    cat  = rule.get("category", "")

    if not checklist["acceptance_test_ready"]:
        return (
            f"Open program {prog}, paragraph {para}. Review the condition "
            f"'{cond}' and confirm: (1) what business event triggers it, "
            f"(2) what the correct outcome is, and (3) whether the current rule "
            f"description matches the actual business intent. Update the rule "
            f"confidence to 'confirmed' once verified."
        )

    if not checklist["resulting_state_defined"]:
        return (
            f"Document the expected system state after '{rule.get('name', '—')}' fires: "
            f"which fields are updated, what return codes are set, and whether any "
            f"downstream records are written. Add this as the 'post-condition' for the test."
        )

    if not checklist["failure_behavior_defined"]:
        return (
            f"Define what the system does when '{rule.get('name', '—')}' is NOT satisfied — "
            f"for example, which error code is returned, what message is written, "
            f"and whether processing stops or continues."
        )

    return None


def _readiness_level(checklist: dict[str, bool], rule: dict) -> str:
    """
    Three-tier readiness classification:
      test_ready       — confidence confirmed/high AND at least 7/10 checklist items pass;
                         can be handed to QA as-is
      needs_detail     — confidence confirmed/high but fewer checklist items pass;
                         QA can start but some post-conditions need documenting
      needs_sme_review — confidence is medium/low; SME must validate meaning first
    """
    if not checklist["acceptance_test_ready"]:
        return "needs_sme_review"
    checklist_score = sum(1 for v in checklist.values() if v)
    if checklist_score >= 6:
        return "test_ready"
    return "needs_detail"


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
    cond = (rule.get("condition") or {}).get("text", "—")
    prog = (rule.get("primary_source") or {}).get("program_id", "")
    para = (rule.get("primary_source") or {}).get("paragraph", "")
    loc  = f"{prog} / {para}" if para else prog

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
    name  = rule.get("name", "—")
    cat   = rule.get("category", "—")
    prog  = (rule.get("primary_source") or {}).get("program_id", "")
    progs = rule.get("implemented_in_programs", [])

    if scenario_type == "happy_path":
        return (f"The '{name}' rule is satisfied. {prog} routes to the correct success path "
                f"with no error codes raised and all required outputs populated.")
    if scenario_type == "negative_path":
        return (f"The '{name}' rule rejects the input. {prog} sets the appropriate error "
                f"indicator and returns control to the caller with a non-zero return code.")
    if scenario_type == "exception":
        return (f"The '{name}' exception branch is executed. {prog} handles the failure case "
                f"gracefully — no abnormal termination, error is logged or surfaced correctly.")
    if scenario_type == "boundary":
        return (f"At exactly the threshold defined by '{name}', {prog} produces the boundary "
                f"outcome — neither over-limit nor under-limit path is skipped, and the "
                f"edge value is handled without rounding or truncation error.")
    if scenario_type == "state_transition":
        return (f"After '{name}' evaluates in {prog}, the system state is updated consistently "
                f"— all downstream fields reflect the new state and no stale values remain.")
    if scenario_type == "integration":
        all_progs = ", ".join(progs[:4]) + ("…" if len(progs) > 4 else "")
        return (f"All programs involved ({all_progs}) agree on the outcome of '{name}'. "
                f"No duplicate processing or conflicting state exists across program boundaries.")
    return f"Expected result for {cat} rule '{name}'."


def _why_generated(rule: dict, scenario_type: str) -> str:
    name = rule.get("name", "—")
    conf = rule.get("confidence", "—")
    rs   = rule.get("rule_set", "—")

    phrases = {
        "happy_path":       f"Confirm the primary success path for '{name}' is fully rule-backed end-to-end (rule set: {rs}).",
        "negative_path":    f"Verify the system correctly rejects or routes away when '{name}' is not satisfied.",
        "boundary":         f"Stress-test the boundary condition in '{name}' to prevent off-by-one and edge-case defects.",
        "exception":        f"Ensure the exception branch of '{name}' is exercised and produces a clean, predictable exit.",
        "state_transition": f"Validate that the state change driven by '{name}' propagates correctly to all dependent fields.",
        "integration":      f"Confirm '{name}' behaves consistently across all programs that implement it (evidence confidence: {conf}).",
    }
    return phrases.get(scenario_type, f"Provide scenario-level coverage for '{name}'.")


def _scenario_status(checklist: dict[str, bool], rule: dict) -> str:
    conf = rule.get("confidence", "low")
    if CONFIDENCE_RANK.get(conf, 0) >= 3:
        return "pass"
    return "pass" if all(checklist.values()) else "with_gaps"


# ---------------------------------------------------------------------------
# Core scenario builders
# ---------------------------------------------------------------------------

def _make_scenario(scn_id: str, stype: str, rule: dict, programs: list[str],
                   requirements: list[str], rule_set_name: str) -> dict:
    checklist      = _det_checklist(rule, stype)
    status         = _scenario_status(checklist, rule)
    gaps           = _gap_reasons(rule, checklist, stype)
    action         = _sme_action(rule, checklist, stype)
    readiness      = _readiness_level(checklist, rule)
    checklist_score = sum(1 for v in checklist.values() if v)
    conf           = rule.get("confidence", "low")

    return {
        "id":              scn_id,
        "type":            stype,
        "status":          status,
        "readiness_level": readiness,
        "checklist_score": checklist_score,
        "rule_id":         rule.get("rule_id", ""),
        "rule_set":        rule_set_name,
        "name":            rule.get("name", "—"),
        "confidence":      conf,
        "confidence_label": CONFIDENCE_LABELS.get(conf, conf),
        "persona":         f"PER-{scn_id.split('-')[1]}",
        "requirements":    requirements,
        "condition":       _condition_text(rule, stype),
        "expected_result": _expected_result(rule, stype),
        "why_generated":   _why_generated(rule, stype),
        "what_it_tests":   _what_it_tests(stype, checklist),
        "determinism":     checklist,
        "gap_reasons":     gaps,
        "sme_action":      action,
        "programs":        programs,
    }


def _build_scenarios_from_rules(rules: list[dict]) -> list[dict]:
    counters: dict[str, int] = {t: 0 for t in SCENARIO_PREFIX}
    scenarios: list[dict] = []

    for rule in rules:
        cat    = rule.get("category", "")
        conf   = rule.get("confidence", "low")
        is_dup = rule.get("is_duplicated", False)

        types_for_rule = CATEGORY_TO_TYPES.get(cat, [])
        if not types_for_rule:
            continue
        if CONFIDENCE_RANK.get(conf, 0) < 2:
            continue
        if is_dup and CONFIDENCE_RANK.get(conf, 0) < 4:
            continue

        for stype in types_for_rule:
            counters[stype] += 1
            scn_id = f"SCN-{SCENARIO_PREFIX[stype]}{counters[stype]:02d}"
            scenarios.append(_make_scenario(
                scn_id=scn_id,
                stype=stype,
                rule=rule,
                programs=rule.get("implemented_in_programs", []),
                requirements=[rule.get("rule_id", "")],
                rule_set_name=rule.get("rule_set", "—"),
            ))

    return scenarios


def _build_integration_scenarios(rule_sets: list[dict], rules_by_id: dict[str, dict]) -> list[dict]:
    scenarios: list[dict] = []
    counter = 0

    for rs in rule_sets:
        rule_ids = rs.get("rule_ids", [])
        programs = rs.get("programs", [])
        if len(programs) < 2:
            continue

        anchor = None
        for rid in rule_ids:
            r = rules_by_id.get(rid)
            if r and CONFIDENCE_RANK.get(r.get("confidence", "low"), 0) >= 2:
                if anchor is None or (CONFIDENCE_RANK.get(r["confidence"], 0) >
                                      CONFIDENCE_RANK.get(anchor["confidence"], 0)):
                    anchor = r
        if not anchor:
            continue

        counter += 1
        scn_id = f"SCN-I{counter:02d}"
        scenarios.append(_make_scenario(
            scn_id=scn_id,
            stype="integration",
            rule=anchor,
            programs=programs,
            requirements=rule_ids[:5],
            rule_set_name=rs.get("name", rs.get("rule_set_id", "—")),
        ))

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
        totl     = by_type[stype]["total"]
        passed   = by_type[stype]["passed"]
        with_gaps = totl - passed
        achieved = round(passed / totl * 100, 1) if totl else 0.0
        deficit  = max(0.0, threshold - achieved)
        coverage.append({
            "type":         stype,
            "label":        TYPE_LABELS.get(stype, stype),
            "total":        totl,
            "passed":       passed,
            "with_gaps":    with_gaps,
            "achieved_pct": achieved,
            "min_pct":      threshold,
            "meets_target": achieved >= threshold,
            "deficit_pct":  round(deficit, 1),
            "interpretation": _coverage_interpretation(stype, achieved, threshold, totl, passed),
        })

    return coverage


def _coverage_interpretation(stype: str, achieved: float, threshold: float,
                              total: int, passed: int) -> str:
    label = TYPE_LABELS.get(stype, stype)
    if total == 0:
        return (f"No {label} scenarios could be generated. "
                f"This usually means no rules of the corresponding category exist with "
                f"sufficient confidence. Run Phase 7 with an LLM step to improve rule confidence.")
    deficit = threshold - achieved
    if deficit <= 0:
        return (f"{label} coverage meets the {threshold:.0f}% target. "
                f"{passed} of {total} scenarios are fully test-ready.")
    return (f"{label} coverage is {achieved:.0f}% against a {threshold:.0f}% target — "
            f"{total - passed} of {total} scenarios still need SME review or additional detail. "
            f"Improving rule confidence in Phase 7 will raise this automatically.")


def _compute_score(coverage: list[dict], scenarios: list[dict]) -> dict:
    score = 100.0
    deductions: list[dict] = []

    for entry in coverage:
        stype   = entry["type"]
        deficit = entry["deficit_pct"]
        if deficit > 0:
            weight  = DEDUCTION_WEIGHTS.get(stype, 0.07)
            penalty = round(deficit * weight, 1)
            score  -= penalty
            deductions.append({
                "label":       f"{TYPE_LABELS.get(stype, stype)} (deficit {deficit:.0f}pp)",
                "penalty":     -round(penalty),
                "explanation": entry["interpretation"],
            })

    blocking = [s for s in scenarios if not s["determinism"].get("acceptance_test_ready", True)]
    blocking_count = len(blocking)
    if blocking_count:
        penalty = min(blocking_count * BLOCKING_PENALTY, 20)
        score  -= penalty
        deductions.append({
            "label":       f"Blocking penalty ({blocking_count} scenarios need SME review)",
            "penalty":     -penalty,
            "explanation": (f"{blocking_count} scenarios are based on medium or low confidence rules "
                            f"and cannot be used as runnable tests until an SME confirms their meaning."),
        })

    has_dups = any(
        sum(1 for s2 in scenarios if s2.get("rule_id") == s.get("rule_id")) > 1
        for s in scenarios if s.get("requirements")
    )
    if has_dups:
        score -= REPEATED_PENALTY
        deductions.append({
            "label":       "Repeated evidence",
            "penalty":     -REPEATED_PENALTY,
            "explanation": ("Some business rules appear in multiple programs. Scenarios generated "
                            "from duplicated rules carry a small penalty as they overlap in coverage."),
        })

    below = sum(1 for e in coverage if not e["meets_target"])
    if below:
        cov_penalty = below * 3
        score      -= cov_penalty
        deductions.append({
            "label":       f"Coverage gap ({below} scenario categories below minimum threshold)",
            "penalty":     -cov_penalty,
            "explanation": (f"{below} scenario type(s) have not reached their minimum coverage target. "
                            f"Each missing category represents a class of business behaviour "
                            f"that is not yet fully verified."),
        })

    final_score = max(0, round(score))

    blocking_findings = []
    for i, s in enumerate(blocking[:5], 1):
        blocking_findings.append({
            "id":       f"FIND-ST-{i:03d}",
            "severity": "HIGH",
            "scenario": s["id"],
            "rule_id":  s["rule_id"],
            "n":        1,
            "action":   s.get("sme_action") or "Review this scenario with your SME.",
        })

    next_steps = _next_steps(coverage, blocking_count, final_score)
    quality_rating = "pass" if final_score >= 70 and blocking_count == 0 else "needs_review"

    return {
        "starting_score":    100,
        "final_score":       final_score,
        "quality_rating":    quality_rating,
        "deductions":        deductions,
        "blocking_count":    blocking_count,
        "blocking_findings": blocking_findings,
        "next_steps":        next_steps,
    }


def _next_steps(coverage: list[dict], blocking_count: int, score: int) -> list[dict]:
    steps = []
    priority = 1

    if blocking_count > 0:
        steps.append({
            "priority": priority,
            "title":    f"SME review: {blocking_count} scenarios need confidence confirmation",
            "detail":   ("These scenarios are based on rules with medium or low confidence. "
                         "An SME must review the original COBOL condition and confirm its "
                         "business meaning before the scenario can be handed to QA. "
                         "Open each scenario marked 'needs_sme_review' and follow its SME action."),
            "impact":   f"Could remove the blocking penalty and raise the score by up to 20 points.",
        })
        priority += 1

    below_types = [e for e in coverage if not e["meets_target"] and e["total"] > 0]
    for entry in below_types:
        steps.append({
            "priority": priority,
            "title":    f"Improve {entry['label']} coverage ({entry['achieved_pct']:.0f}% → target {entry['min_pct']:.0f}%)",
            "detail":   entry["interpretation"],
            "impact":   f"Closing this gap would remove the {entry['label']} coverage deduction.",
        })
        priority += 1

    zero_types = [e for e in coverage if e["total"] == 0]
    for entry in zero_types:
        steps.append({
            "priority": priority,
            "title":    f"Generate {entry['label']} scenarios (currently 0)",
            "detail":   entry["interpretation"],
            "impact":   f"Adding {entry['label']} scenarios would fill a complete gap in test coverage.",
        })
        priority += 1

    if score >= 80:
        steps.append({
            "priority": priority,
            "title":    "Maintain coverage — run Phase 11 after each Phase 7 update",
            "detail":   ("The score is healthy. Re-run the Synthetic Test Generator whenever "
                         "business rules are updated to keep the scenarios current."),
            "impact":   "Keeps the test specification aligned with the codebase.",
        })

    return steps


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

def _build_executive_summary(stats: dict, coverage: list[dict],
                              score: int, blocking: int) -> str:
    total         = stats.get("total", 0)
    by_readiness  = stats.get("by_readiness", {})
    test_ready    = by_readiness.get("test_ready", 0)
    needs_detail  = by_readiness.get("needs_detail", 0)
    needs_sme     = by_readiness.get("needs_sme_review", 0)
    ready_pct     = round(test_ready / total * 100) if total else 0
    below         = [e for e in coverage if not e["meets_target"] and e["total"] > 0]
    zero          = [e for e in coverage if e["total"] == 0]
    gap_names     = ", ".join(e["label"] for e in below)
    zero_names    = ", ".join(e["label"] for e in zero)

    lines = []
    lines.append(
        f"The automated analysis generated {total} test scenarios from the extracted business rules. "
        f"{test_ready} of those ({ready_pct}%) are fully test-ready and can be handed to a QA team "
        f"as runnable test cases today."
    )

    if needs_detail > 0:
        lines.append(
            f"A further {needs_detail} scenarios have high-confidence rules but are missing some "
            f"structural detail (such as post-conditions or downstream effects). "
            f"QA can begin work on these while SMEs fill in the remaining detail."
        )

    if needs_sme > 0:
        lines.append(
            f"{needs_sme} scenarios are based on medium or low-confidence rules. "
            f"A subject-matter expert must confirm the business meaning of each rule "
            f"before those scenarios can be used as runnable tests. "
            f"Each scenario marked 'Needs SME Review' includes a specific action for the SME."
        )

    if below:
        lines.append(
            f"Coverage is below the minimum threshold in: {gap_names}. "
            f"These are areas of business behaviour not yet fully specified as tests."
        )

    if zero:
        lines.append(
            f"No scenarios could be generated for: {zero_names}. "
            f"This typically means no rules of that type have sufficient confidence yet. "
            f"Running Phase 7 with an LLM step will improve this."
        )

    if score >= 80:
        lines.append(
            f"Overall quality score: {score}/100 — the codebase is well-documented "
            f"and the majority of business rules are ready for automated testing."
        )
    elif score >= 60:
        lines.append(
            f"Overall quality score: {score}/100 — solid foundation. "
            f"SME input on the {needs_sme} flagged scenarios will have the biggest impact on the score. "
            f"Follow the prioritised next steps below."
        )
    else:
        lines.append(
            f"Overall quality score: {score}/100 — significant SME review is required "
            f"before automated testing can begin at scale. "
            f"Prioritise the scenarios marked 'Needs SME Review' using the action items provided."
        )

    return " ".join(lines)


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

    rule_scenarios  = _build_scenarios_from_rules(rules)
    integ_scenarios = _build_integration_scenarios(rule_sets, rules_by_id)
    all_scenarios   = rule_scenarios + integ_scenarios

    print(f"[p11_syntest] Generated {len(all_scenarios)} scenarios "
          f"({len(rule_scenarios)} rule-based, {len(integ_scenarios)} integration)")

    coverage        = _compute_coverage(all_scenarios)
    score_breakdown = _compute_score(coverage, all_scenarios)

    total      = len(all_scenarios)
    passed     = sum(1 for s in all_scenarios if s["status"] == "pass")
    with_gaps  = sum(1 for s in all_scenarios if s["status"] == "with_gaps")
    by_type    = {}
    by_readiness = {"test_ready": 0, "needs_sme_review": 0, "needs_detail": 0}
    for s in all_scenarios:
        by_type[s["type"]] = by_type.get(s["type"], 0) + 1
        rl = s.get("readiness_level", "needs_detail")
        by_readiness[rl] = by_readiness.get(rl, 0) + 1

    stats = {
        "total":             total,
        "passed":            passed,
        "with_gaps":         with_gaps,
        "failed":            total - passed - with_gaps,
        "by_type":           by_type,
        "by_readiness":      by_readiness,
        "quality_score":     score_breakdown["final_score"],
        "blocking_findings": score_breakdown["blocking_count"],
    }

    executive_summary = _build_executive_summary(
        stats, coverage, score_breakdown["final_score"], score_breakdown["blocking_count"]
    )

    artifact = {
        "meta": {
            "generated_at":          datetime.now(timezone.utc).isoformat(),
            "rules_source":          str(out_dir / "rules/rules_artifact.json"),
            "total_rules_processed": len(rules),
        },
        "executive_summary": executive_summary,
        "stats":             stats,
        "scenarios":         all_scenarios,
        "coverage":          coverage,
        "score_breakdown":   score_breakdown,
    }

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
    br    = result.get("by_readiness", {})
    print(f"\n  Scenarios      : {stats.get('total', 0)}")
    print(f"  Test-ready     : {stats.get('by_readiness', {}).get('test_ready', 0)}")
    print(f"  Needs SME      : {stats.get('by_readiness', {}).get('needs_sme_review', 0)}")
    print(f"  Needs detail   : {stats.get('by_readiness', {}).get('needs_detail', 0)}")
    print(f"  Quality score  : {stats.get('quality_score', '—')}/100")
    print(f"\n  Executive summary:")
    print(f"  {result.get('executive_summary', '')[:200]}…")


if __name__ == "__main__":
    main()
