# Three-Way Agent Comparison — Udara vs Chaminda vs Ours

A simple, agent-by-agent comparison of the three repositories.
For each agent: a short table showing **what it does, its input, and its output** in each repo.

---

## Agent 1 — Discovery Agent

| Aspect | 🟠 Udara | 🟢 Chaminda | 🔵 Ours |
|---|---|---|---|
| **File** | `1_inventory_c.agent.md` | `ingestion.py` | `phases/p01_discovery/scanner.py` |
| **Type** | LLM agent (prompt) | Deterministic Python | Deterministic Python |
| **What it does** | LLM scans the codebase and catalogs every file + reference | Parses code and loads it into a Neo4j graph database | Scans the codebase with regex and catalogs every file + reference |
| **Input** | Raw COBOL folder | Raw COBOL folder | Raw COBOL folder |
| **Output** | `inventory_artifact.json` | Nodes/edges inside **Neo4j** | `inventory.json` |
| **Needs** | An LLM | Neo4j + parser JAR + git | Nothing (pure Python) |

---

## Agent 2 — Parser Agent

| Aspect | 🟠 Udara | 🟢 Chaminda | 🔵 Ours |
|---|---|---|---|
| **File** | `2_parser_c.agent.md` | `cobol/parser.py` | `phases/p02_parser/engine.py` + `phases/p02_parser/orchestrator.py` |
| **Type** | LLM agent (prompt) | Deterministic Python + Java JAR | Deterministic Python |
| **What it does** | LLM opens each program and extracts its structure — divisions, paragraphs, WORKING-STORAGE, PERFORM/GO TO flow | Runs a real COBOL grammar parser (JAR) to build a true AST, then loads it into Neo4j | Extracts the same structure with regex/stdlib — a Python port of Udara's parser skills |
| **Input** | `inventory_artifact.json` + raw COBOL | Raw COBOL folder | `inventory.json` + raw COBOL |
| **Output** | `raw_structure/{PROGRAM}.json` + `parser_artifact.json` | AST nodes/edges inside **Neo4j** | `raw_structure/{PROGRAM}.json` + `parser_artifact.json` |
| **Needs** | An LLM | Java + parser JAR + Neo4j | Nothing (pure Python) |

---

## Agent 3 — Topology / Graph Builder

| Aspect | 🟠 Udara | 🟢 Chaminda | 🔵 Ours |
|---|---|---|---|
| **File** | `8_neo4j_graph_c.agent.md` | `ingestion.py` + `neo4j_client.py` | `phases/p03_topology/graph_builder.py` |
| **Type** | LLM agent (prompt) | Deterministic Python + Neo4j | Deterministic Python |
| **What it does** | Generates Neo4j import files (Cypher + CSVs) for the **user to load into Neo4j by hand** | Loads nodes + edges into a **live Neo4j database** and queries it with Cypher | Builds the graph as a local `graph.json` — a "**local Neo4j replacement**" the pipeline reads directly |
| **Input** | All prior artifacts (inventory, parser, data, logic, rules) | Raw COBOL / parse results | `inventory.json` + parser AST |
| **Output** | `import.cypher`, `nodes/*.csv`, `rels/*.csv`, `cypher_library.md` | Graph inside **Neo4j** | `graph.json` (nodes + edges) |
| **Needs** | An LLM + Neo4j Desktop (to load) | Neo4j running | Nothing (pure Python) |
| **When it runs** | Optional, near the end (after synthesis) | During ingestion (up front) | Phase 3 (up front) |

**In one line:** Both Udara and Chaminda are built around Neo4j; **we removed Neo4j entirely** and replaced it with a self-contained `graph.json` that the rest of the pipeline consumes automatically — no database, no manual import.

---

## Agent 4 — Context Builder

| Aspect | 🟠 Udara | 🟢 Chaminda | 🔵 Ours |
|---|---|---|---|
| **File** | *(none — no context agent)* | `agent/context_pack.py` | `phases/p04_context/context_builder.py` |
| **Type** | — | Deterministic Python | Deterministic Python |
| **What it does** | No dedicated step — each later agent reads the prior artifacts directly | Builds a "**context pack**": the exact, hashed input contract fed to each LLM call, with citable refs + source slices | Pre-digests each program's AST into a **readable briefing sheet** (`PROGRAM_context.txt`) for later agents |
| **Input** | (prior artifacts, read per-agent) | Parsed entities + refs | Parser AST (`raw_structure/{PROGRAM}.json`) |
| **Output** | — | In-memory `ContextPack` (hashed, cacheable) | `PROGRAM_context.txt` per program + `system_index.json` |
| **Needs** | Nothing (implicit) | Nothing extra | Nothing (pure Python) |

**In one line:** Udara has no context step (agents read raw artifacts themselves); Chaminda packs a hashed machine-contract per LLM call; **we sit in between** — a readable per-program summary so the later Logic LLM gets a clean briefing instead of raw JSON.

---

## Agent 5 — Data Agent

| Aspect | 🟠 Udara | 🟢 Chaminda | 🔵 Ours |
|---|---|---|---|
| **File** | `3_data_c.agent.md` | *(no separate agent — in `parser.py`/`ingestion.py`)* | `phases/p05_data/data_builder.py` |
| **Type** | LLM agent (prompt) | Deterministic Python + Java JAR | Deterministic Python |
| **What it does** | LLM expands COPY stubs, decodes PIC, resolves REDEFINES / OCCURS / 88-levels into a data dictionary | The JAR parser extracts fields/records (with PIC, level, REDEFINES, OCCURS) as **entities in Neo4j** during parsing | Same as Udara but as rule-based Python — expands copybooks, decodes PIC, surfaces REDEFINES / OCCURS / 88-levels, builds a cross-program usage map |
| **Input** | `inventory.json` + `parser_artifact.json` + raw COBOL | Raw COBOL folder | `inventory.json` + parser AST |
| **Output** | `data_layouts/*.json` + `data_artifact.json` | Field/Record nodes inside **Neo4j** | `data_layouts/*.json` + `data_artifact.json` |
| **Needs** | An LLM | Java + JAR + Neo4j | Nothing (pure Python) |

**In one line:** COBOL data definitions are rigid and rule-based (PIC clauses, level numbers), so all three do it deterministically — we ported Udara's LLM agent to plain Python and reuse our Phase-2 parser, getting the full data dictionary with no LLM and no database.

---

## Agent 6 — Logic Agent  *(first hybrid — LLM enters here)*

| Aspect | 🟠 Udara | 🟢 Chaminda | 🔵 Ours |
|---|---|---|---|
| **File** | `4_logic_c.agent.md` | `codegen/behavior_model.py` (+ codegen LLM) | `phases/p06_logic/logic_builder.py` + `phases/p06_logic/logic_agent.md` |
| **Type** | LLM agent (prompt) | Deterministic signals → LLM (for Java) | **Hybrid** (Python prep + 1 LLM call) |
| **What it does** | LLM traces control flow and translates every paragraph into annotated **pseudocode** | Deterministically extracts behavior *signals* (conditions, moves, calcs, IO, CICS, calls) to feed an LLM that generates **Java** | Python gathers the clues (context + data + AST + source), one LLM call turns each paragraph into plain-English **pseudocode** (structured JSON, flags ambiguous + branches), Python writes the files |
| **Input** | `parser_artifact.json` + `data_artifact.json` + source | Bounded source pack per "story" | context + data + AST + raw source |
| **Output** | `program_logic/*.json` + `logic_artifact.json` | Behavior model → Java code | `program_logic/*.json` + `logic_artifact.json` |
| **LLM role** | Does everything (trace + translate) | Only consumes the signals to write code | Only the meaning step (pseudocode) |
| **Needs** | An LLM | LLM (for codegen) | LLM — or our no-key **AI-host** path |

**In one line:** Turning imperative COBOL into *meaning* genuinely needs judgment, so all three use an LLM here — but we copy Chaminda's discipline (Python pre-digests and bounds the input) and Udara's goal (readable pseudocode), so the LLM does **only** the one step it's actually needed for.

---

## Agent 7 — Rules Agent  *(hybrid — LLM role shrinks)*

| Aspect | 🟠 Udara | 🟢 Chaminda | 🔵 Ours |
|---|---|---|---|
| **File** | `5_rules_c.agent.md` | *(no rules catalogue — `domain/deterministic.py` + `agent/advisor.py`)* | `phases/p07_rules/rules_builder.py` + `phases/p07_rules/rules_agent.md` |
| **Type** | LLM agent (prompt) | Deterministic Cypher + LLM advisor | **Hybrid** (Python does most; LLM optional) |
| **What it does** | LLM mines every branch/condition + 88-level and classifies them into named business rules with IDs, category, confidence, source traceability | Queries the Neo4j graph to derive a **domain design** (bounded contexts, aggregates) for splitting the monolith into Java — not a rules list | Python collects branches + 88-levels, classifies them (category, pattern, signal 1–5), dedupes and groups into rule sets; LLM only writes the readable **name + description** |
| **Input** | `logic_artifact.json` + `data_artifact.json` | Neo4j graph | `logic_artifact.json` + `data_artifact.json` |
| **Output** | `classified_conditions.json` + `rules_artifact.json` | Domain/bounded-context design | `classified_conditions.json` + `rules_artifact.json` |
| **LLM role** | Does everything (find + classify + name) | Advises on domain decomposition | **Only wording** (optional — `--no-llm` templated fallback) |
| **Needs** | An LLM | Neo4j + LLM | LLM optional — AI-host or fallback |

**In one line:** A business rule must trace to a real source line (no inventing), so we keep the *finding, classifying, and grouping* deterministic and let the LLM touch **only the human wording** — the opposite of Udara, where the LLM does the whole job; Chaminda doesn't build a rules catalogue at all.

---

## Agent 8 — Diagram Agent  *(back to deterministic)*

| Aspect | 🟠 Udara | 🟢 Chaminda | 🔵 Ours |
|---|---|---|---|
| **File** | `6_diagram_c.agent.md` | `technical_design/render.py` (+ LLM design) | `phases/p08_diagram/diagram_builder.py` |
| **Type** | LLM agent (but only re-renders) | LLM-generated design → Mermaid | Deterministic Python |
| **What it does** | Translates prior artifacts into Mermaid diagrams (component, ERD, sequence, per-program flow) — "extract nothing new" | Renders Mermaid diagrams inside an **LLM-written technical-design doc** for the Java rewrite | Builds Mermaid diagrams directly from `graph.json`, data model, and logic files — component overview, ERD, per-program flow |
| **Input** | All prior artifacts | Neo4j graph + LLM design | `graph.json` + `data_artifact.json` + `logic_artifact.json` |
| **Output** | `.mmd` files + `diagrams_artifact.json` | Mermaid embedded in design doc | `.mmd` files + `diagrams_artifact.json` |
| **LLM role** | Runs the agent (though the work is mechanical) | Writes the design the diagrams depict | **None** |
| **Needs** | An LLM | Neo4j + LLM | Nothing (pure Python) |

**In one line:** A diagram is just a redrawing of facts we already have (nodes, edges, fields) — no new interpretation — so we make it pure deterministic Python; Udara routes it through the LLM needlessly, and Chaminda's diagrams describe its *future Java design*, not the legacy system as-is.

---

## Agent 9 — BRD Generation  *(hybrid — everything comes together)*

| Aspect | 🟠 Udara | 🟢 Chaminda | 🔵 Ours |
|---|---|---|---|
| **File** | `7_synthesis_c.agent.md` | `brd/pipeline.py` + `brd/renderer.py` | `phases/p09_brd/brd_builder.py` + `phases/p09_brd/brd_agent.md` |
| **Type** | LLM agent (prompt) | **Agentic LLM loop** (map / reduce / judge + retry) | **Hybrid** (Python assembles; LLM writes prose) |
| **What it does** | LLM runs a gap-detector, then writes the whole BRD chapter by chapter from the artifacts | LLM navigates the Neo4j graph, drafts the BRD, **judges it, and retries** with new strategies until quality passes; renders HTML | Python detects gaps and assembles every chapter (tables, data model, rules catalogue, gaps) from artifacts; LLM writes **only** the narrative prose (exec summary, system context, per-process stories) |
| **Input** | All 6 prior artifacts | Neo4j graph | inventory + parser + data + logic + rules + diagrams |
| **Output** | `brd.md` + `brd_summary.md` + gaps register | BRD (HTML) + judge report + rating | `brd.md` + `brd_summary.md` + gaps register |
| **LLM role** | Writes the entire document | Writes, judges, and re-writes the whole document | **Only the connecting prose** (optional — templated fallback) |
| **Needs** | An LLM | Neo4j + heavy LLM usage | LLM optional — AI-host or fallback |

**In one line:** The BRD's *facts* (rules, data, gaps, inventory) are assembled straight from the artifacts by Python so they **cannot drift from the truth** — the LLM only writes the readable narrative around them; Udara lets the LLM write everything, and Chaminda goes furthest with a self-judging, self-retrying agentic loop.

---

## Agent 10 — BRD Judge  *(hybrid — the quality gate)*

| Aspect | 🟠 Udara | 🟢 Chaminda | 🔵 Ours |
|---|---|---|---|
| **File** | *(none — no judge; pipeline ends at synthesis)* | `agent/brd_judge.py` | `phases/p10_judge/brd_judge.py` + `phases/p10_judge/brd_judge_agent.md` |
| **Type** | — | LLM-as-judge | **Hybrid** (deterministic Validation + LLM Judge) |
| **What it does** | Nothing — the BRD is the last step, no grading | LLM navigates the graph and scores the BRD on 5 weighted dimensions, feeding a retry loop | **Validation** (Python): groundedness gate — every `BR-`/`GAP-`/`RS-` id must exist in the artifacts, else accuracy is floored to 2 — plus consistency checks. **Judge** (LLM): scores the same 5 dimensions |
| **Input** | — | BRD + Neo4j graph | `brd.md` + all artifacts + gaps register |
| **Output** | — | Judge report + rating (drives retry) | `brd_judge.json` + `brd_judge.md` (PASS / REVISE) |
| **The 5 dimensions** | — | completeness .25, accuracy .30, clarity .15, consistency .15, actionability .15 | **identical** (lifted from Chaminda) |
| **Hallucination check** | — | Trusts the judge LLM (+ graph access) to notice | **Deterministic** groundedness gate catches it mechanically |
| **Needs** | — | Neo4j + LLM | LLM optional — AI-host or neutral default |

**In one line:** We took Chaminda's LLM-as-judge (same weights, same prompt) and put a **deterministic groundedness gate in front of it** — so a hallucinated rule/reference is caught by code, not left to the LLM to spot; Udara has no judge at all.

