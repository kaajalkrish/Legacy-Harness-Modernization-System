"""
Smoke tests for the harness — stdlib unittest, no API key, no network.

  * Phases 1-5 (deterministic) run end-to-end on inputs/sample_mini.
  * Phase 8 (BRD, templated/no-LLM) + Phase 9 (judge gate) rebuild from the
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


class BrdFromCarddemoArtifactsTest(unittest.TestCase):
    """Phase 8 + 9 rebuilt from the committed CardDemo artifacts (no LLM)."""

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
            self.assertEqual(verdict["groundedness_failures"], [],
                             "BRD cites ids/programs that do not exist in the artifacts")
            self.assertEqual(verdict["consistency_issues"], [], "consistency issues found")


if __name__ == "__main__":
    unittest.main()
