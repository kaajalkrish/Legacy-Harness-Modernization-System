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


class BrdFromCarddemoArtifactsTest(unittest.TestCase):
    """Phase 8 + 9 rebuilt from the committed CardDemo artifacts (no LLM)."""

    SRC = ROOT / "outputs" / "carddemo"

    def test_brd_and_judge_gate(self):
        s = self.SRC
        with tempfile.TemporaryDirectory() as tmp:
            fr = Path(tmp) / "final_report"
            run("-m", "phases.p09_brd.brd_builder",
                "--inventory", str(s / "discovery" / "inventory.json"),
                "--parser", str(s / "analysis" / "parser_artifact.json"),
                "--data", str(s / "data" / "data_artifact.json"),
                "--logic", str(s / "logic" / "logic_artifact.json"),
                "--rules", str(s / "rules" / "rules_artifact.json"),
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
                "--rules", str(s / "rules" / "rules_artifact.json"),
                "--gaps", str(fr / "gaps_register.json"),
                "--diagrams-index", str(s / "diagram" / "diagrams_artifact.json"),
                "--output-dir", str(fr), "--no-llm")
            verdict = json.loads((fr / "brd_judge.json").read_text(encoding="utf-8"))
            self.assertEqual(verdict["groundedness_failures"], [],
                             "BRD cites ids/programs that do not exist in the artifacts")
            self.assertEqual(verdict["consistency_issues"], [], "consistency issues found")


if __name__ == "__main__":
    unittest.main()
