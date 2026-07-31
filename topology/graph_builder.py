import os
import json
import argparse
from datetime import datetime

def load_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_system_graph(inventory_path, ast_dir_path, output_dir):
    print("🚀 Initializing High-Fidelity Graph Builder (Local Neo4j Replacement)...")
    
    inventory_data = load_json_file(inventory_path)
    file_registry = inventory_data.get("file_registry", [])
    
    nodes = []
    edges = []
    processed_node_ids = set()

    # 1. Seed base nodes from inventory
    for file_entry in file_registry:
        raw_id = file_entry.get("id") or file_entry.get("program_id")
        if not raw_id: continue
        
        node_id = raw_id.upper()
        if node_id not in processed_node_ids:
            nodes.append({
                "id": node_id,
                "type": str(file_entry.get("type", "UNKNOWN")).upper(),
                "source_path": file_entry.get("path", ""),
                "entry_points": [],
                "metadata": {"subtype": file_entry.get("subtype", "")}
            })
            processed_node_ids.add(node_id)

    # 2. Merge Inventory-based Relationship Edges (COPY, CALL, CICS, SQL INCLUDE)
    INVENTORY_EDGE_MAP = {
        "COPY": ("INCLUDES_COPYBOOK", "COPYBOOK"),
        "STATIC_CALL": ("CALLS_PROGRAM", "PROGRAM"),
        "CICS_LINK": ("CALLS_PROGRAM", "PROGRAM"),
        "CICS_XCTL": ("CALLS_PROGRAM", "PROGRAM"),
        "SQL_INCLUDE": ("INCLUDES_DB2", "DB2"),
    }

    all_inv_edges = inventory_data.get("call_graph", {}).get("edges", []) or inventory_data.get("edges", [])
    for edge in all_inv_edges:
        mapping = INVENTORY_EDGE_MAP.get(edge.get("type"))
        if not mapping:
            continue
        graph_edge_type, target_node_type = mapping
        src, tgt = edge.get("from", "").upper(), edge.get("to", "").upper()
        if src and tgt:
            if tgt not in processed_node_ids:
                nodes.append({"id": tgt, "type": target_node_type, "source_path": "Inventory/Common"})
                processed_node_ids.add(tgt)
            edges.append({
                "source": src,
                "target": tgt,
                "type": graph_edge_type,
                "line_number": edge.get("source_line_hint")
            })

    # 3. Deep-scanning structured ASTs for File and Call dependencies
    raw_structure_dir = os.path.join(ast_dir_path, "raw_structure")
    if not os.path.exists(raw_structure_dir) or not any(fname.endswith('.json') for fname in os.listdir(raw_structure_dir)):
        raw_structure_dir = ast_dir_path

    print(f"🔍 Deep-scanning structured ASTs in: {raw_structure_dir}")
    
    if os.path.exists(raw_structure_dir):
        for filename in os.listdir(raw_structure_dir):
            if not filename.endswith(".json") or filename in ("parser_artifact.json", "graph.json"): continue
            
            try:
                ast_data = load_json_file(os.path.join(raw_structure_dir, filename))
                program_id = ast_data.get("meta", {}).get("program_id", filename.replace("_ast.json", "").replace(".json", "")).upper()
                
                # Update entry points
                for node in nodes:
                    if node["id"] == program_id:
                        cfg = ast_data.get("control_flow_graph", {})
                        if cfg and "entry_points" in cfg: node["entry_points"] = cfg["entry_points"]
                        break

                # File Tracking
                for fd in ast_data.get("data_division", {}).get("file_section", {}).get("entries", []):
                    file_name = fd.get("file_name", "").upper()
                    if file_name:
                        if file_name not in processed_node_ids:
                            nodes.append({"id": file_name, "type": "FILE_CONTROL", "source_path": f"Logical Volume inside {program_id}"})
                            processed_node_ids.add(file_name)
                        edges.append({"source": program_id, "target": file_name, "type": "USES_FILE"})

                # Dynamic Call Tracking
                for cfg_node in ast_data.get("control_flow_graph", {}).get("nodes", []):
                    desc = cfg_node.get("description", "")
                    if "CALL" in desc:
                        target = desc.split()[1].strip(".'\"").upper()
                        if target not in processed_node_ids:
                            nodes.append({"id": target, "type": "PROGRAM", "source_path": "External/Subroutine"})
                            processed_node_ids.add(target)
                        edges.append({"source": program_id, "target": target, "type": "CALLS_PROGRAM"})
            except Exception as e:
                print(f"⚠️ Error processing {filename}: {e}")

    # 4. Finalize & Save Telemetry
    graph_payload = {
      "meta": {
        "generated_at": datetime.now().isoformat(),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "node_types": {
            "PROGRAM": len([n for n in nodes if n["type"] == "PROGRAM"]),
            "COPYBOOK": len([n for n in nodes if n["type"] == "COPYBOOK"]),
            "FILE_CONTROL": len([n for n in nodes if n["type"] == "FILE_CONTROL"]),
            "OTHER": len([n for n in nodes if n["type"] not in ("PROGRAM", "COPYBOOK", "FILE_CONTROL")])
        }
      },
      "nodes": nodes,
      "edges": edges
    }

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "graph.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(graph_payload, f, indent=2)
        
    print(f"\n✨ Global Semantic Graph Built successfully!")
    print(f"📊 Summary: {graph_payload['meta']['node_types']['PROGRAM']} Programs, {graph_payload['meta']['node_types']['COPYBOOK']} Copybooks, {graph_payload['meta']['node_types']['FILE_CONTROL']} File Handles.")
    print(f"💾 Graph artifact serialized to: {output_path}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 - High Fidelity Local Graph Builder")
    parser.add_argument("--inventory", required=True, help="Path to outputs/inventory.json")
    parser.add_argument("--ast-dir", required=True, help="Path to outputs/parser_output folder")
    parser.add_argument("--output-dir", required=True, help="Folder to write graph.json")
    
    args = parser.parse_args()
    build_system_graph(args.inventory, args.ast_dir, args.output_dir)