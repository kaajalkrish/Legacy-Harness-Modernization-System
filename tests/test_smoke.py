"""
Smoke tests for the harness — stdlib unittest, no API key, no network.

  * Phases 1-5 (deterministic) run end-to-end on inputs/sample_mini.
  * Phase 9 (BRD, templated/no-LLM) + Phase 10 (judge gate) rebuild from the
    committed outputs/carddemo artifacts and must pass the groundedness gate.

Everything is written to a temp directory — committed outputs are never touched.

Run from the repo root:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from phases.p01_discovery.scanner import InventoryBuilder  # noqa: E402


def run(*args: str) -> None:
    """Run a phase module from the repo root; fail the test with its output on error."""
    res = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise AssertionError(f"{' '.join(args)} failed ({res.returncode}):\n"
                             f"{res.stdout[-2000:]}\n{res.stderr[-2000:]}")


class DeterministicPhasesTest(unittest.TestCase):
    """Phases 1-5 on the small sample input."""

    def test_phases_1_to_5_on_sample_mini(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            inv = out / "discovery" / "inventory.json"
            inv.parent.mkdir(parents=True)
            data = InventoryBuilder(repo_root=ROOT / "inputs" / "sample_mini",
                                    exclude_dirs={".git", "bin", "obj", "templates"}).build()
            inv.write_text(json.dumps(data, indent=2), encoding="utf-8")

            run("-m", "phases.p02_parser.orchestrator", "--inventory", str(inv),
                "--output-dir", str(out / "analysis"))
            run("-m", "phases.p03_topology.graph_builder", "--inventory", str(inv),
                "--ast-dir", str(out / "analysis"), "--output-dir", str(out / "topology"))
            run("phases/p04_context/context_builder.py", "--graph",
                str(out / "topology" / "graph.json"), "--out", str(out / "context"))
            run("-m", "phases.p05_data.data_builder", "--inventory", str(inv),
                "--ast-dir", str(out / "analysis"), "--output-dir", str(out / "data"))

            for p in (inv, out / "analysis" / "parser_artifact.json",
                      out / "topology" / "graph.json", out / "data" / "data_artifact.json"):
                self.assertTrue(p.exists(), f"missing artifact: {p}")
            self.assertTrue(data.get("stats"), "inventory has no stats")


class ProgramClassificationTest(unittest.TestCase):
    """Run mode is read from the code / job streams, not from naming conventions."""

    def test_carddemo_run_modes(self):
        data = InventoryBuilder(repo_root=ROOT / "inputs" / "carddemo",
                                exclude_dirs={".git", "bin", "obj", "templates"}).build()
        mode = {e["id"]: e["subtype"] for e in data["file_registry"]}
        self.assertEqual(data["stats"]["unknown_programs"], 0)
        expected = {
            "COSGN00C": "online", "COPAUA0C": "online",      # EXEC CICS
            "CBTRN02C": "batch", "COBSWAIT": "batch",        # EXEC PGM=
            "PAUDBLOD": "batch", "DBUNLDGS": "batch",        # IMS DFSRRC00 PARM
            "COBTUPDT": "batch",                             # DB2 RUN PROGRAM(...)
            "CBSTM03B": "common", "CSUTLDTC": "common",      # called subroutines
        }
        for pid, want in expected.items():
            self.assertEqual(mode[pid], want, pid)

    def test_free_format_source_is_scanned(self):
        data = InventoryBuilder(repo_root=ROOT / "inputs" / "sample",
                                exclude_dirs={".git", "bin", "obj", "templates"}).build()
        errhndl = next(e for e in data["file_registry"] if e["id"] == "ERRHNDL")
        self.assertEqual(errhndl["subtype"], "online")
        self.assertIn("CICS", errhndl["runtime"])


class RulesTieringTest(unittest.TestCase):
    """Business rules vs technical conditions, and the AI-host enrichment contract."""

    SRC = ROOT / "outputs" / "carddemo"

    def _build(self, out: Path) -> dict:
        run("-m", "phases.p07_rules.rules_builder",
            "--logic", str(self.SRC / "logic" / "logic_artifact.json"),
            "--data", str(self.SRC / "data" / "data_artifact.json"),
            "--inventory", str(self.SRC / "discovery" / "inventory.json"),
            "--output-dir", str(out), "--no-llm")
        return json.loads((out / "rules_artifact.json").read_text(encoding="utf-8"))

    def test_business_and_technical_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self._build(Path(tmp))
            business = {r["condition"]["text"] for r in a["business_rules"]}
            technical = {r["condition"]["text"] for r in a["technical_rules"]}
            self.assertIn("IF card inactive -> decline", business)
            self.assertIn("IF ACCT-CURR-BAL <= 0 -> 'nothing to pay'", business)
            self.assertTrue(any("EIBCALEN" in t for t in technical))
            self.assertTrue(any("PERFORM UNTIL END-OF-FILE" in t for t in technical))
            self.assertFalse(any("EIBCALEN" in t or "END-OF-FILE" in t for t in business))
            # every business rule sits in exactly one rule set
            in_sets = [rid for s in a["rule_sets"] for rid in s["rule_ids"]]
            self.assertEqual(sorted(in_sets), sorted(r["rule_id"] for r in a["business_rules"]))

    def test_ai_enrichment_applied_and_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self._build(out)
            brief = json.loads((out / "rules_brief.json").read_text(encoding="utf-8"))
            cand = next(c for c in brief["candidates"] if "card inactive" in c["text"])
            ai = {"meta": {"fingerprint": brief["meta"]["fingerprint"]},
                  "capabilities": [{"name": "Card Authorization", "description": "",
                                    "programs": ["COPAUA0C", "NOT-A-PROGRAM"]}],
                  "rules": {cand["condition_id"]: {"tier": "business", "name": "Decline inactive cards"},
                            "COND-INVENTED": {"name": "should be dropped"}}}
            (out / "rules_ai.json").write_text(json.dumps(ai), encoding="utf-8")
            a = self._build(out)
            rule = next(r for r in a["business_rules"] if r["condition"]["text"] == cand["text"])
            self.assertEqual(rule["name"], "Decline inactive cards")
            self.assertEqual(rule["rule_set"], "Card Authorization")
            caps = {c["name"]: c["programs"] for c in a["capabilities"]}
            self.assertEqual(caps["Card Authorization"], ["COPAUA0C"])
            self.assertEqual(len(a["meta"]["ai_warnings"]), 2)

            ai["meta"]["fingerprint"] = "stale"
            (out / "rules_ai.json").write_text(json.dumps(ai), encoding="utf-8")
            a = self._build(out)
            self.assertEqual(a["meta"]["ai_worded_rules"], 0)
            self.assertIn("rejected", a["meta"]["description_mode"])


class GapsRegisterTest(unittest.TestCase):
    """Platform components are external dependencies; each missing item is one gap."""

    def test_externals_and_dedup(self):
        sys.path.insert(0, str(ROOT))
        from phases.p09_brd.brd_builder import detect_gaps
        inv = InventoryBuilder(repo_root=ROOT / "inputs" / "carddemo",
                               exclude_dirs={".git", "bin", "obj", "templates"}).build()
        data = json.loads((ROOT / "outputs" / "carddemo" / "data" / "data_artifact.json")
                          .read_text(encoding="utf-8"))
        gaps, externals = detect_gaps(inv, {}, {}, data)
        ext = {e["component"]: e for e in externals}
        for name in ("DFHAID", "CMQV", "MQOPEN", "CBLTDLI", "CEE3ABD", "SQLCA"):
            self.assertIn(name, ext)
        refs = [g.get("reference") for g in gaps if g["type"] == "unresolved_reference"]
        self.assertEqual(len(refs), len(set(refs)), "duplicate gaps for the same target")
        self.assertIn("DCLTRTYP", refs)                    # genuinely missing DCLGEN
        for not_a_gap in ("DFHAID", "REPLACING", "COBDATFT", "MVSWAIT"):
            self.assertNotIn(not_a_gap, refs)
        self.assertFalse([g for g in gaps if g["type"] == "dynamic_call"],
                         "CALL inside a DISPLAY literal must not be a dynamic call")


class JudgeNarrativeTest(unittest.TestCase):
    """The judge catches prose that describes another domain or states unsupported counts."""

    def test_wrong_domain_and_numbers_are_caught(self):
        from phases.p10_judge import brd_judge as J
        o = ROOT / "outputs" / "carddemo"
        logic = J.load(o / "logic" / "logic_artifact.json")
        rules = J.load(o / "rules" / "rules_artifact.json")
        data = J.load(o / "data" / "data_artifact.json")
        inv = J.load(o / "discovery" / "inventory.json")
        vocab = J.evidence_vocabulary(logic, o / "logic", rules, data, inv)
        wrong = ("It manages portfolio positions, transactions and reference data. Shared services "
                 "provide connection management, audit trail and error logging.")
        self.assertIn("portfolio", J.unsupported_terms(wrong, vocab, set()))
        right = ("Card authorizations are approved or declined in real time; nightly batch jobs post "
                 "daily transactions, calculate interest and produce account statements.")
        self.assertEqual(J.unsupported_terms(right, vocab, set()), [])
        allowed = J.allowed_numbers(inv, logic, rules, data, {"gaps": []})
        self.assertEqual(J.unsupported_numbers("The system has 44 programs.", allowed), [])
        self.assertEqual(J.unsupported_numbers("The system has 52 programs.", allowed),
                         ["52 programs"])

    def test_old_portfolio_brd_is_revised(self):
        o = ROOT / "outputs" / "carddemo"
        with tempfile.TemporaryDirectory() as tmp:
            run("-m", "phases.p10_judge.brd_judge", "--brd", str(ROOT / "outputs" / "carddemo"
                / "final_report" / "brd.md"),
                "--inventory", str(o / "discovery" / "inventory.json"),
                "--data", str(o / "data" / "data_artifact.json"),
                "--logic", str(o / "logic" / "logic_artifact.json"),
                "--rules", str(o / "rules" / "rules_artifact.json"),
                "--gaps", str(o / "final_report" / "gaps_register.json"),
                "--output-dir", tmp, "--no-llm")
            v = json.loads((Path(tmp) / "brd_judge.json").read_text(encoding="utf-8"))
            if "portfolio" in (o / "final_report" / "brd.md").read_text(encoding="utf-8").lower():
                self.assertEqual(v["verdict"], "REVISE")
                self.assertLessEqual(v["dimensions"]["accuracy"]["score"], 2)


class BrdFromCarddemoArtifactsTest(unittest.TestCase):
    """Phase 9 + 9 rebuilt from the committed CardDemo artifacts (no LLM)."""

    SRC = ROOT / "outputs" / "carddemo"

    def test_brd_and_judge_gate(self):
        s = self.SRC
        with tempfile.TemporaryDirectory() as tmp:
            fr = Path(tmp) / "final_report"
            rules = Path(tmp) / "rules" / "rules_artifact.json"
            run("-m", "phases.p07_rules.rules_builder",
                "--logic", str(s / "logic" / "logic_artifact.json"),
                "--data", str(s / "data" / "data_artifact.json"),
                "--inventory", str(s / "discovery" / "inventory.json"),
                "--output-dir", str(rules.parent), "--no-llm")
            run("-m", "phases.p09_brd.brd_builder",
                "--inventory", str(s / "discovery" / "inventory.json"),
                "--parser", str(s / "analysis" / "parser_artifact.json"),
                "--data", str(s / "data" / "data_artifact.json"),
                "--logic", str(s / "logic" / "logic_artifact.json"),
                "--rules", str(rules),
                "--diagrams", str(s / "diagram"),
                "--output-dir", str(fr),
                "--system-name", "AWS CardDemo", "--no-llm")
            brd = fr / "brd.md"
            self.assertTrue(brd.exists())
            text = brd.read_text(encoding="utf-8")
            self.assertIn("## 1. Executive Summary", text)

            run("-m", "phases.p10_judge.brd_judge", "--brd", str(brd),
                "--inventory", str(s / "discovery" / "inventory.json"),
                "--data", str(s / "data" / "data_artifact.json"),
                "--logic", str(s / "logic" / "logic_artifact.json"),
                "--rules", str(rules),
                "--gaps", str(fr / "gaps_register.json"),
                "--diagrams-index", str(s / "diagram" / "diagrams_artifact.json"),
                "--output-dir", str(fr), "--no-llm")
            verdict = json.loads((fr / "brd_judge.json").read_text(encoding="utf-8"))
            self.assertEqual(verdict["verdict"], "REVISE", "an unscored BRD must never pass")
            self.assertEqual(verdict["groundedness_failures"], [],
                             "BRD cites ids/programs that do not exist in the artifacts")
            self.assertEqual(verdict["consistency_issues"], [], "consistency issues found")

            # neutral fallback: structure present, no wording from another domain
            for heading in ("## Table of Contents", "### 1.1 At a glance", "## 3. Business Capabilities",
                            "### 4.1 Key business rules", "### 7.3 Platform dependencies",
                            "## 10. Modernization Considerations and Next Steps"):
                self.assertIn(heading, text)
            self.assertNotIn("portfolio", text.lower())
            self.assertNotIn("kaaja", text)          # no absolute local paths

            # AI-host narratives: applied when grounded, dropped per section when not
            brief = json.loads((fr / "brd_brief.json").read_text(encoding="utf-8"))
            narr = {"meta": {"fingerprint": brief["meta"]["fingerprint"]},
                    "executive_summary": "Grounded summary citing BR-001.",
                    "business_purpose": "Cites BR-999, which does not exist.",
                    "key_rules": [{"rule_id": "BR-001", "why": "Impact."},
                                  {"rule_id": "BR-999", "why": "x"}]}
            (fr / "brd_narratives.json").write_text(json.dumps(narr), encoding="utf-8")
            run("-m", "phases.p09_brd.brd_builder",
                "--inventory", str(s / "discovery" / "inventory.json"),
                "--parser", str(s / "analysis" / "parser_artifact.json"),
                "--data", str(s / "data" / "data_artifact.json"),
                "--logic", str(s / "logic" / "logic_artifact.json"),
                "--rules", str(rules), "--diagrams", str(s / "diagram"),
                "--output-dir", str(fr), "--system-name", "AWS CardDemo", "--no-llm")
            text = brd.read_text(encoding="utf-8")
            self.assertIn("Grounded summary citing BR-001.", text)
            self.assertNotIn("BR-999", text)
            self.assertNotIn("### 2.1 Business purpose", text)
            self.assertIn("narrative: AI-host", text)

            narr["meta"]["fingerprint"] = "stale"
            (fr / "brd_narratives.json").write_text(json.dumps(narr), encoding="utf-8")
            run("-m", "phases.p09_brd.brd_builder",
                "--inventory", str(s / "discovery" / "inventory.json"),
                "--parser", str(s / "analysis" / "parser_artifact.json"),
                "--data", str(s / "data" / "data_artifact.json"),
                "--logic", str(s / "logic" / "logic_artifact.json"),
                "--rules", str(rules), "--diagrams", str(s / "diagram"),
                "--output-dir", str(fr), "--system-name", "AWS CardDemo", "--no-llm")
            self.assertNotIn("Grounded summary citing BR-001.", brd.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
