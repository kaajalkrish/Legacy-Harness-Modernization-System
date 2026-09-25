import argparse
import json
import subprocess
import sys
from pathlib import Path
from phases.p01_discovery.scanner import InventoryBuilder

def ask_choice(message, options_text="[y/n/s]", default='y'):
    """Prompts user with flexible options: Yes, No, or Skip."""
    response = input(f"\n👉 {message} {options_text}: ").strip().lower()
    if response == "":
        return default
    return response

def main():
    ap = argparse.ArgumentParser(description="COBOL legacy-analysis pipeline (Phases 1-4)")
    ap.add_argument("--input", default=None,
                    help="Path to the COBOL source root to analyse (default: inputs/sample)")
    ap.add_argument("--output", default=None,
                    help="Path to the output root (default: outputs/sample). "
                         "Use a separate folder per codebase, e.g. outputs/carddemo")
    ap.add_argument("--system-name", default=None,
                    help="System name shown in the BRD (default: the input folder's name)")
    args = ap.parse_args()

    base_dir = Path(__file__).resolve().parent
    out_dir = Path(args.output).resolve() if args.output else base_dir / "outputs" / "sample"
    print(f"Writing outputs to: {out_dir}")
    
    # 1. Paths definition (Organized by agent)
    input_dir = Path(args.input).resolve() if args.input else base_dir / "inputs" / "sample"
    print(f"Using COBOL source root: {input_dir}")
    inventory_file = out_dir / "discovery" / "inventory.json"
    parser_output_dir = out_dir / "analysis"
    graph_file = out_dir / "topology" / "graph.json"
    context_output_dir = out_dir / "context"
    data_output_dir = out_dir / "data"
    logic_output_dir = out_dir / "logic"
    rules_output_dir = out_dir / "rules"
    diagram_output_dir = out_dir / "diagram"
    final_report_dir = out_dir / "final_report"

    # 2. Ensure every agent's folder exists
    for folder in [inventory_file.parent, parser_output_dir, graph_file.parent, context_output_dir, data_output_dir, logic_output_dir, rules_output_dir, diagram_output_dir, final_report_dir]:
        folder.mkdir(parents=True, exist_ok=True)
    
    exclude_folders = {".git", "bin", "obj", "templates"}
    
    print("====================================================")
    # --- PHASE 1: Discovery (Inventory Scan) ---
    print("Checking Phase 1: Repository Discovery Scan...")
    run_phase1 = True
    
    if inventory_file.exists():
        choice = ask_choice(
            f"Found existing inventory data at '{inventory_file.name}'. Re-run scan? (y=Re-run, s=Skip to Phase 2)", 
            "[y/s]", default='s'
        )
        if choice == 's':
            run_phase1 = False
            print("[SKIPPED] Using existing inventory mapping.")
            
    if run_phase1:
        print(f"\nStarting Phase 1: Repository Inventory Scan")
        builder = InventoryBuilder(repo_root=input_dir, exclude_dirs=exclude_folders)
        inventory_data = builder.build()
        
        inventory_file.parent.mkdir(parents=True, exist_ok=True)
        with open(inventory_file, "w", encoding="utf-8") as f:
            json.dump(inventory_data, f, indent=2)
        print(f"[SUCCESS] Agent 1 (Discovery) finished. Saved to: {inventory_file.name}")


    choice = ask_choice(
    "Proceed to Phase 2 (Structural Analysis)?",
    "[y/n]",
    default="y"
    )

    if choice in ("n", "no"):
        print("Pipeline stopped after Phase 1.")
        return
        
    print("====================================================")
    # --- PHASE 2: Analysis (Parsing Orchestrator) ---
    print("Checking Phase 2: Structural Analysis Parsing...")
    run_phase2 = True
    
    # Check if we have files inside the output folder
    if parser_output_dir.exists() and any(parser_output_dir.iterdir()):
        choice = ask_choice(
            f"Found existing parsed AST files in '{parser_output_dir.name}'. Re-run parser? (y=Re-run, s=Skip to Phase 3)", 
            "[y/s]", default='s'
        )
        if choice == 's':
            run_phase2 = False
            print("[SKIPPED] Using existing AST parsing data.")

    if run_phase2:
        if not inventory_file.exists():
            print(f"[ERROR] Cannot run Phase 2. Missing dependency: {inventory_file.name}")
            sys.exit(1)
            
        print(f"\nStarting Phase 2: Analysis & Orchestration...")
        agent2_cmd = [
            sys.executable, "-m", "phases.p02_parser.orchestrator",
            "--inventory", str(inventory_file),
            "--output-dir", str(parser_output_dir)
        ]
        try:
            subprocess.run(agent2_cmd, check=True)
            print(f"[SUCCESS] Agent 2 (Analysis) finished processing.")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Agent 2 failed with exit code {e.returncode}", file=sys.stderr)
            sys.exit(e.returncode)

    

    print("====================================================")

    choice = ask_choice(
    "Proceed to Phase 3 (Topology Graph Builder)?",
    "[y/n]",
    default="y"
    )

    if choice in ("n", "no"):
        print("Pipeline stopped after Phase 2.")
        return
    # --- PHASE 3: Topology (Graph Builder) ---
    print("Checking Phase 3: Topology Graph Generation...")
    run_phase3 = True
    
    if graph_file.exists():
        choice = ask_choice(
            f"Found existing system map graph file at '{graph_file.name}'. Re-run Graph Builder?", 
            "[y/n]", default='y'
        )
        if choice in ('n', 'no'):
            run_phase3 = False
            print("[SKIPPED] Keeping current graph file.")

    if run_phase3:
        if not inventory_file.exists() or not parser_output_dir.exists():
            print("[ERROR] Cannot run Phase 3. Missing upstream input inventory or AST data.")
            sys.exit(1)
            
        print(f"\nStarting Phase 3: Topology Graph Building...")
        agent3_cmd = [
            sys.executable, "-m", "phases.p03_topology.graph_builder",
            "--inventory", str(inventory_file),
            "--ast-dir", str(parser_output_dir),
            "--output-dir", str(graph_file.parent)
        ]
        try:
            subprocess.run(agent3_cmd, check=True)
            print(f"[SUCCESS] Agent 3 (Topology) built relationships cleanly.")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Agent 3 failed with exit code {e.returncode}", file=sys.stderr)
            sys.exit(e.returncode)

    print("====================================================")
    print("🎉 Pipeline run update evaluation completed successfully!")

    choice = ask_choice(
    "Proceed to Phase 4 (Context Builder)?",
    "[y/n]",
    default="y"
    )

    if choice in ("n", "no"):
        print("Pipeline stopped after Phase 3.")
        return


    # --- PHASE 4: Context Building (Agent 4) ---
    print("Checking Phase 4: Context Cheat-Sheet Generation...")
    run_phase4 = True

    # Check if context files already exist
    if context_output_dir.exists() and any(context_output_dir.iterdir()):
        choice = ask_choice(
            f"Found existing context sheets in '{context_output_dir.name}'. Re-run Context Builder?", 
            "[y/n]", default='n'
        )
        if choice in ('n', 'no'):
            run_phase4 = False
            print("[SKIPPED] Keeping existing context sheets.")

    if run_phase4:
        if not graph_file.exists():
            print("[ERROR] Cannot run Phase 4. Missing dependency: graph.json")
            sys.exit(1)
            
        print(f"\nStarting Phase 4: Context Sheet Generation...")
        agent4_cmd = [
            sys.executable, "phases/p04_context/context_builder.py",
            "--graph", str(graph_file),
            "--out", str(context_output_dir)
        ]
        try:
            subprocess.run(agent4_cmd, check=True)
            print(f"[SUCCESS] Agent 4 (Context Builder) generated sheets in: {context_output_dir.name}")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Agent 4 failed with exit code {e.returncode}", file=sys.stderr)
            sys.exit(e.returncode)

    print("====================================================")

    choice = ask_choice(
    "Proceed to Phase 5 (Data Dictionary Builder)?",
    "[y/n]",
    default="y"
    )

    if choice in ("n", "no"):
        print("Pipeline stopped after Phase 4.")
        return

    # --- PHASE 5: Data phase (Agent 5) ---
    print("Checking Phase 5: Data Dictionary & Model Generation...")
    run_phase5 = True

    data_artifact_file = data_output_dir / "data_artifact.json"
    if data_artifact_file.exists():
        choice = ask_choice(
            f"Found existing data dictionary at '{data_artifact_file.name}'. Re-run Data Builder?",
            "[y/n]", default='n'
        )
        if choice in ('n', 'no'):
            run_phase5 = False
            print("[SKIPPED] Keeping existing data dictionary.")

    if run_phase5:
        if not inventory_file.exists() or not parser_output_dir.exists():
            print("[ERROR] Cannot run Phase 5. Missing upstream inventory.json or AST data.")
            sys.exit(1)

        print(f"\nStarting Phase 5: Data Dictionary Building...")
        agent5_cmd = [
            sys.executable, "-m", "phases.p05_data.data_builder",
            "--inventory", str(inventory_file),
            "--ast-dir", str(parser_output_dir),
            "--output-dir", str(data_output_dir),
        ]
        try:
            subprocess.run(agent5_cmd, check=True)
            print(f"[SUCCESS] Agent 5 (Data Builder) built dictionary in: {data_output_dir.name}")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Agent 5 failed with exit code {e.returncode}", file=sys.stderr)
            sys.exit(e.returncode)

    print("====================================================")

    choice = ask_choice(
    "Proceed to Phase 6 (Logic — uses the LLM, costs tokens)?",
    "[y/n]",
    default="n"
    )

    if choice in ("n", "no"):
        print("Pipeline stopped after Phase 5. (Phase 6 skipped — no LLM call made.)")
        return

    # --- PHASE 6: Logic phase (Agent 6) — the only LLM-backed phase ---
    print("Checking Phase 6: Logic (plain-English pseudocode) Generation...")
    run_phase6 = True

    logic_artifact_file = logic_output_dir / "logic_artifact.json"
    if logic_artifact_file.exists():
        choice = ask_choice(
            f"Found existing logic output at '{logic_artifact_file.name}'. Re-run Logic (spends tokens again)?",
            "[y/n]", default='n'
        )
        if choice in ('n', 'no'):
            run_phase6 = False
            print("[SKIPPED] Keeping existing logic output.")

    if run_phase6:
        if not parser_output_dir.exists() or not context_output_dir.exists():
            print("[ERROR] Cannot run Phase 6. Missing upstream AST (Phase 2) or context sheets (Phase 4).")
            sys.exit(1)

        print(f"\nStarting Phase 6: Logic Building (LLM)...")
        agent6_cmd = [
            sys.executable, "-m", "phases.p06_logic.logic_builder",
            "--inventory", str(inventory_file),
            "--ast-dir", str(parser_output_dir),
            "--context-dir", str(context_output_dir),
            "--data", str(data_output_dir / "data_artifact.json"),
            "--output-dir", str(logic_output_dir),
        ]
        try:
            subprocess.run(agent6_cmd, check=True)
            print(f"[SUCCESS] Agent 6 (Logic) built pseudocode in: {logic_output_dir.name}")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Agent 6 failed with exit code {e.returncode}", file=sys.stderr)
            sys.exit(e.returncode)

    print("====================================================")

    choice = ask_choice(
    "Proceed to Phase 7 (Rules — hybrid; LLM writes rule descriptions if a key is set)?",
    "[y/n]",
    default="n"
    )

    if choice in ("n", "no"):
        print("Pipeline stopped after Phase 6.")
        return

    # --- PHASE 7: Rules phase (Agent 7) — hybrid (deterministic classify + LLM descriptions) ---
    print("Checking Phase 7: Business Rules Extraction...")
    run_phase7 = True

    rules_artifact_file = rules_output_dir / "rules_artifact.json"
    if rules_artifact_file.exists():
        choice = ask_choice(
            f"Found existing rules output at '{rules_artifact_file.name}'. Re-run Rules Builder?",
            "[y/n]", default='n'
        )
        if choice in ('n', 'no'):
            run_phase7 = False
            print("[SKIPPED] Keeping existing rules output.")

    if run_phase7:
        if not (logic_output_dir / "logic_artifact.json").exists() or not (data_output_dir / "data_artifact.json").exists():
            print("[ERROR] Cannot run Phase 7. Missing upstream logic (Phase 6) or data (Phase 5) artifacts.")
            sys.exit(1)

        print(f"\nStarting Phase 7: Rules Building (deterministic classify + LLM descriptions)...")
        agent7_cmd = [
            sys.executable, "-m", "phases.p07_rules.rules_builder",
            "--logic", str(logic_output_dir / "logic_artifact.json"),
            "--data", str(data_output_dir / "data_artifact.json"),
            "--inventory", str(inventory_file),
            "--output-dir", str(rules_output_dir),
        ]
        try:
            subprocess.run(agent7_cmd, check=True)
            print(f"[SUCCESS] Agent 7 (Rules) built the rules catalogue in: {rules_output_dir.name}")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Agent 7 failed with exit code {e.returncode}", file=sys.stderr)
            sys.exit(e.returncode)

    print("====================================================")

    choice = ask_choice(
    "Proceed to Phase 8 (BRD Generation — hybrid; LLM writes the synthesis prose if a key is set)?",
    "[y/n]",
    default="n"
    )

    if choice in ("n", "no"):
        print("Pipeline stopped after Phase 7.")
        return

    # --- PHASE 8: BRD Generation (Agent 8) — hybrid (deterministic assembly + LLM narratives) ---
    print("Checking Phase 8: BRD Generation...")
    run_phase8 = True

    brd_file = final_report_dir / "brd.md"
    if brd_file.exists():
        choice = ask_choice(
            f"Found existing BRD at '{brd_file.name}'. Re-generate?",
            "[y/n]", default='n'
        )
        if choice in ('n', 'no'):
            run_phase8 = False
            print("[SKIPPED] Keeping existing BRD.")

    if run_phase8:
        need = [inventory_file, parser_output_dir / "parser_artifact.json",
                data_output_dir / "data_artifact.json", logic_output_dir / "logic_artifact.json",
                rules_output_dir / "rules_artifact.json"]
        if not all(p.exists() for p in need):
            print("[ERROR] Cannot run Phase 8. Missing one of inventory / parser / data / logic / rules artifacts.")
            sys.exit(1)

        # 8a. Diagram agent (deterministic) — produce Mermaid diagrams the BRD embeds.
        print(f"\nStarting Diagram agent (deterministic Mermaid generation)...")
        diagram_cmd = [
            sys.executable, "-m", "phases.p08_diagram.diagram_builder",
            "--graph", str(graph_file),
            "--data", str(data_output_dir / "data_artifact.json"),
            "--logic", str(logic_output_dir / "logic_artifact.json"),
            "--output-dir", str(diagram_output_dir),
        ]
        try:
            subprocess.run(diagram_cmd, check=True)
            print(f"[SUCCESS] Diagram agent generated diagrams in: {diagram_output_dir.name}")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Diagram agent failed with exit code {e.returncode}", file=sys.stderr)
            sys.exit(e.returncode)

        # 8b. BRD Generation (hybrid) — assemble the document and embed the diagrams.
        print(f"\nStarting Phase 8: BRD Generation (deterministic assembly + LLM narratives)...")
        agent8_cmd = [
            sys.executable, "-m", "phases.p09_brd.brd_builder",
            "--inventory", str(inventory_file),
            "--parser", str(parser_output_dir / "parser_artifact.json"),
            "--data", str(data_output_dir / "data_artifact.json"),
            "--logic", str(logic_output_dir / "logic_artifact.json"),
            "--rules", str(rules_output_dir / "rules_artifact.json"),
            "--diagrams", str(diagram_output_dir),
            "--output-dir", str(final_report_dir),
            "--system-name", args.system_name or input_dir.name,
        ]
        try:
            subprocess.run(agent8_cmd, check=True)
            print(f"[SUCCESS] Agent 8 (BRD) wrote the document in: {final_report_dir.name}")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Agent 8 failed with exit code {e.returncode}", file=sys.stderr)
            sys.exit(e.returncode)

    print("====================================================")

    choice = ask_choice(
    "Proceed to Phase 9 (BRD Validation — the Judge; deterministic gate + LLM scoring)?",
    "[y/n]",
    default="n"
    )

    if choice in ("n", "no"):
        print("Pipeline stopped after Phase 8.")
        return

    # --- PHASE 9: BRD Validation / Judge (Agent 9) — hybrid (deterministic gate + LLM scoring) ---
    print("Checking Phase 9: BRD Validation (Judge)...")
    brd_md = final_report_dir / "brd.md"
    if not brd_md.exists() or not (final_report_dir / "gaps_register.json").exists():
        print("[ERROR] Cannot run Phase 9. Missing brd.md / gaps_register.json (run Phase 8 first).")
        sys.exit(1)

    print(f"\nStarting Phase 9: BRD Validation (groundedness gate + 5-dimension scoring)...")
    agent9_cmd = [
        sys.executable, "-m", "phases.p10_judge.brd_judge",
        "--brd", str(brd_md),
        "--inventory", str(inventory_file),
        "--data", str(data_output_dir / "data_artifact.json"),
        "--logic", str(logic_output_dir / "logic_artifact.json"),
        "--rules", str(rules_output_dir / "rules_artifact.json"),
        "--gaps", str(final_report_dir / "gaps_register.json"),
        "--diagrams-index", str(diagram_output_dir / "diagrams_artifact.json"),
        "--output-dir", str(final_report_dir),
    ]
    try:
        subprocess.run(agent9_cmd, check=True)
        print(f"[SUCCESS] Agent 9 (Validation & Judge) wrote the report in: {final_report_dir.name}")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Agent 9 failed with exit code {e.returncode}", file=sys.stderr)
        sys.exit(e.returncode)

    print("====================================================")
    print("🎉 All phases complete.")

if __name__ == "__main__":
    main()
