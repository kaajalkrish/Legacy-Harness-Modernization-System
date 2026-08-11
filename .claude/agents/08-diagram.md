---
name: diagram
description: >
  Phase 8a of the legacy-modernization harness — the deterministic diagram producer
  that runs just before the BRD assembly. Use to redraw the system graph, data model
  and program logic into Mermaid diagrams: a component overview, an ER diagram, and
  per-program control-flow diagrams. No LLM. Produces *.mmd files plus a diagrams index
  that the BRD embeds.
tools: Bash, Read, Write, Grep, Glob
model: sonnet
---

# Agent 08 — Diagram (Mermaid Generator)

**Type:** Deterministic · **Pipeline phase:** 8a (runs first within Phase 8) · **Module:** `phases/p08_diagram/diagram_builder.py`

## Role
Turn the accumulated artifacts into diagrams. Fully deterministic — it re-draws facts
already computed upstream; it never invents nodes, edges or fields.

## Inputs
| Input | Where | From |
|---|---|---|
| System graph | `topology/graph.json` | Phase 3 |
| Data dictionary | `data/data_artifact.json` | Phase 5 |
| Program logic | `logic/logic_artifact.json` | Phase 6 |

## Run (deterministic)
```bash
python -m phases.p08_diagram.diagram_builder --graph <out>/topology/graph.json \
    --data <out>/data/data_artifact.json --logic <out>/logic/logic_artifact.json \
    --output-dir <out>/diagram
```

## Outputs
| Path | Contents |
|---|---|
| `<out>/diagram/*.mmd` | component overview, ER diagram, per-program flows |
| `<out>/diagram/diagrams_artifact.json` | index of generated diagrams (read by the Judge) |

## Grounding rules
- Every node/edge/field drawn must come from the graph, data or logic artifacts.
- Diagrams are a re-projection of verified facts, not a new source of claims.

## Pipeline links
**Upstream:** [03-topology](03-topology.md), [05-data](05-data.md), [06-logic](06-logic.md) · **Downstream:** [09-brd](09-brd.md) (embeds), [10-judge](10-judge.md) (indexes)
