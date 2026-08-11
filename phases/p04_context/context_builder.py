import os
import json
import argparse
from pathlib import Path


def load_ast(analysis_dir: Path, program_id: str):
    """Loads the Agent 2 (Analysis) AST/CFG artifact for a program, if it exists."""
    ast_path = analysis_dir / f"{program_id}.json"
    if not ast_path.exists():
        return None
    try:
        with open(ast_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def summarize_data_structures(ast):
    """Renders top-level WORKING-STORAGE record structures as context lines."""
    if not ast:
        return ["- Not available (no parsed AST found for this program)"]

    entries = ast.get('data_division', {}).get('working_storage_section', {}).get('entries', [])
    if not entries:
        return ["- None (no WORKING-STORAGE entries found)"]

    lines = []
    for entry in entries:
        if entry.get('type') == 'copy_stub':
            lines.append(f"- COPY {entry.get('copybook')} (external structure, expanded via copybook)")
            continue

        level = entry.get('level')
        level_str = f"{level:02d}" if isinstance(level, int) else str(level)
        name = entry.get('name', 'FILLER')
        pic = entry.get('pic')
        children = entry.get('children') or []

        if pic:
            lines.append(f"- {level_str} {name} PIC {pic}")
        else:
            lines.append(f"- {level_str} {name} (group item, {len(children)} sub-field(s))")
    return lines


def summarize_procedure(ast):
    """Extracts entry points and procedure-division shape from the AST/CFG."""
    if not ast:
        return {
            "entry_points": [],
            "using_parameters": [],
            "paragraph_count": 0,
            "section_count": 0,
            "terminal_statements": [],
            "paragraphs": [],
        }

    proc = ast.get('procedure_division', {}) or {}
    cfg = ast.get('control_flow_graph', {}) or {}
    return {
        "entry_points": cfg.get('entry_points') or [],
        "using_parameters": proc.get('using_parameters') or [],
        "paragraph_count": len(proc.get('paragraphs') or []),
        "section_count": len(proc.get('sections') or []),
        "terminal_statements": proc.get('terminal_statements') or [],
        "paragraphs": [p['name'] for p in (proc.get('paragraphs') or [])],
    }


def build_dynamic_summary(node_id, node, files, copies, calls, data_structure_count, proc_info):
    """Builds a factual one-paragraph summary from extracted metadata (no hardcoded template)."""
    subtype = (node.get('metadata') or {}).get('subtype') or 'unclassified'
    fragments = [f"{node_id} is a {subtype}-type COBOL program"]

    entry_points = proc_info['entry_points']
    if entry_points:
        fragments.append(f"entered at {', '.join(entry_points)}")

    fragments.append(
        f"with {proc_info['paragraph_count']} paragraph(s) across {proc_info['section_count']} section(s)"
    )

    if calls:
        fragments.append(f"calling {len(calls)} other program(s)")
    if files:
        fragments.append(f"reading/writing {len(files)} data file(s)")
    if copies:
        fragments.append(f"sharing {len(copies)} copybook(s)")

    return ", ".join(fragments) + f". It defines {data_structure_count} top-level data structure(s) in WORKING-STORAGE."


def generate_context_sheets(graph_path, output_dir):
    with open(graph_path, 'r', encoding='utf-8') as f:
        graph = json.load(f)

    os.makedirs(output_dir, exist_ok=True)
    nodes = {n['id']: n for n in graph['nodes']}
    edges = graph['edges']

    # Agent 2 (Analysis) writes one AST/CFG file per program under outputs/analysis/raw_structure.
    # graph.json lives at outputs/topology/graph.json, so we derive the sibling analysis folder from it.
    analysis_dir = Path(graph_path).resolve().parent.parent / "analysis" / "raw_structure"

    # This list will become our "Overall System Index"
    system_index = []

    print(f"📝 Creating AI-Optimized Context Sheets and System Index...")

    for node_id, node in nodes.items():
        if node.get('type') != 'PROGRAM': continue

        # Get connections
        files = [e['target'] for e in edges if e['source'] == node_id and e['type'] == 'USES_FILE']
        copies = [e['target'] for e in edges if e['source'] == node_id and e['type'] == 'INCLUDES_COPYBOOK']
        calls = [e['target'] for e in edges if e['source'] == node_id and e['type'] == 'CALLS_PROGRAM']

        ast = load_ast(analysis_dir, node_id)
        data_structure_lines = summarize_data_structures(ast)
        proc_info = summarize_procedure(ast)

        # 1. Save individual .txt for AI prompts
        program_summary = build_dynamic_summary(
            node_id, node, files, copies, calls, len(data_structure_lines), proc_info
        )

        entry_points_text = ', '.join(proc_info['entry_points']) if proc_info['entry_points'] else 'None'
        using_params_text = ', '.join(proc_info['using_parameters']) if proc_info['using_parameters'] else 'None'
        terminal_text = ', '.join(
            f"{t['type']} (line {t['line']})" for t in proc_info['terminal_statements']
        ) if proc_info['terminal_statements'] else 'None'
        paragraphs_text = '\n'.join(f'- {p}' for p in proc_info['paragraphs']) if proc_info['paragraphs'] else '- None'

        content = f"""# System Context: {node_id}
## 📝 Summary
{program_summary}
## 📌 Identification
- **Program ID**: {node_id}
- **Source Path**: {node.get('source_path', 'N/A')}
- **Main Entry Point**: {', '.join(node.get('entry_points', ['None']))}
## 🏗️ Architectural Dependencies
### 📂 Data Files
{chr(10).join([f'- {f}' for f in files]) if files else '- None'}
### 📚 Shared Logic (Copybooks)
{chr(10).join([f'- {c}' for c in copies]) if copies else '- None'}
### 🔗 Execution Flow (Calls)
{chr(10).join([f'- {p}' for p in calls]) if calls else '- None'}
## Key Data Structures
{chr(10).join(data_structure_lines)}
## Procedure Summary
- **Entry Point(s)**: {entry_points_text}
- **Using Parameters (Linkage)**: {using_params_text}
- **Paragraphs / Sections**: {proc_info['paragraph_count']} / {proc_info['section_count']}
- **Terminal Statements**: {terminal_text}
- **Paragraph List**:
{paragraphs_text}
"""
        with open(os.path.join(output_dir, f"{node_id}_context.txt"), 'w', encoding='utf-8') as f:
            f.write(content)

        # 2. Add to system_index list
        system_index.append({
            "program": node_id,
            "path": node.get('source_path'),
            "files": files,
            "copybooks": copies,
            "calls": calls,
            "entry_points": proc_info['entry_points'],
            "paragraph_count": proc_info['paragraph_count'],
        })

    # 3. Save the overall JSON index
    with open(os.path.join(output_dir, "system_index.json"), 'w', encoding='utf-8') as f:
        json.dump(system_index, f, indent=2)

    print(f"✅ Success! Generated {len(system_index)} sheets and 1 system_index.json in: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    generate_context_sheets(args.graph, args.out)
