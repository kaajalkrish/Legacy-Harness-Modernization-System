import { useEffect, useRef, useState } from 'react'
import type { PhaseDef } from '../../types'

// ── Per-phase Mermaid diagrams (sourced from flow.md) ─────────────────────────

const PHASE_FLOWS: Record<string, string> = {
  discovery: `flowchart LR
A[Raw COBOL Codebase]
A --> B[Discovery Scanner]
B --> C[inventory.json]`,

  parser: `flowchart LR
A[Raw COBOL]
B[inventory.json]
A --> C[Analysis Parser]
B --> C
C --> D[PROGRAM.json]
C --> E[parser_artifact.json]`,

  topology: `flowchart LR
A[inventory.json]
B[PROGRAM.json]
A --> C[Topology Builder]
B --> C
C --> D[graph.json]`,

  context: `flowchart LR
A[graph.json]
B[PROGRAM.json]
A --> C[Context Builder]
B --> C
C --> D[PROGRAM_context.txt]
C --> E[system_index.json]`,

  data: `flowchart LR
A[Raw COBOL]
B[inventory.json]
C[PROGRAM.json]
A --> D[Data Agent]
B --> D
C --> D
D --> E[data_artifact.json]
D --> F[data_layouts]`,

  logic: `flowchart LR
A[Raw COBOL]
B[Context Sheets]
C[Parser Output]
D[Data Artifact]
A --> E[Logic Agent]
B --> E
C --> E
D --> E
E --> F[PROGRAM_logic.json]
E --> G[logic_artifact.json]`,

  rules: `flowchart LR
A[Logic Outputs]
B[Data Outputs]
A --> C[Rules Agent]
B --> C
C --> D[classified_conditions.json]
C --> E[rules_artifact.json]`,

  diagram: `flowchart LR
A[Topology]
B[Data]
C[Logic]
A --> D[Diagram Agent]
B --> D
C --> D
D --> E[Component Diagram]
D --> F[ER Diagram]
D --> G[Program Flow Diagrams]
D --> H[diagrams_artifact.json]`,

  brd: `flowchart TB
A[Inventory]
B[Parser Artifact]
C[Data Dictionary]
D[Logic Outputs]
E[Rules Catalogue]
F[Diagrams]
A --> G[BRD Generator]
B --> G
C --> G
D --> G
E --> G
F --> G
G --> H[brd.md]
G --> I[brd_summary.md]
G --> J[gaps_register.json]`,

  judge: `flowchart TB
A[brd.md]
B[rules_artifact.json]
C[data_artifact.json]
D[inventory.json]
E[gaps_register.json]
A --> V[Groundedness Gate]
B --> V
C --> V
D --> V
E --> V
V --> J[LLM Judge — 5-dimension scoring]
J --> W[Apply Gate and Rate]
W --> X[brd_judge.md]
W --> Y[brd_judge.json]`,
}

// ── Per-phase inputs / outputs / notes ───────────────────────────────────────

const PHASE_DETAIL: Record<string, {
  inputs:  string[]
  outputs: string[]
  note:    string
}> = {
  discovery: {
    inputs:  ['Raw COBOL source folder (programs, copybooks, JCL, BMS)'],
    outputs: ['discovery/inventory.json'],
    note:    'Resolves all COPY, CALL and CICS LINK-XCTL references into a dependency graph. Every later phase reads inventory.json as its starting catalogue.',
  },
  parser: {
    inputs:  ['Raw COBOL programs', 'inventory.json'],
    outputs: ['analysis/raw_structure/PROGRAM.json (one per program)', 'analysis/parser_artifact.json'],
    note:    'Extracts the full structural skeleton — DATA DIVISION, all paragraphs with line ranges, and the PERFORM / GO TO control-flow graph. Every GO TO is flagged.',
  },
  topology: {
    inputs:  ['inventory.json', 'PROGRAM.json (all programs)'],
    outputs: ['topology/graph.json'],
    note:    'Merges file-level dependencies from inventory with parsed call edges into a single typed graph: INCLUDES_COPYBOOK, CALLS_PROGRAM, etc. Local replacement for Neo4j.',
  },
  context: {
    inputs:  ['graph.json', 'PROGRAM.json (all programs)'],
    outputs: ['context/PROGRAM_context.txt (one per program)', 'context/system_index.json'],
    note:    'Condenses each program\'s raw AST into a compact briefing sheet — data structures, entry points, paragraph shape, dependencies — so the Logic phase gets focused, high-signal input rather than raw JSON.',
  },
  data: {
    inputs:  ['Raw COBOL', 'inventory.json', 'PROGRAM.json'],
    outputs: ['data/data_artifact.json', 'data/data_layouts/*.json'],
    note:    'Expands COPY stubs, decodes PIC clauses into type / size / decimals, resolves REDEFINES and OCCURS, and surfaces 88-level condition names (the seeds of business rules).',
  },
  logic: {
    inputs:  ['Raw COBOL', 'context sheets', 'parser output', 'data artifact'],
    outputs: ['logic/program_logic/PROGRAM_logic.json', 'logic/logic_artifact.json'],
    note:    'LLM-powered: translates each COBOL paragraph into plain-English pseudocode with branches, called programs, field references, and a complexity score. Python bounds and validates; LLM writes meaning.',
  },
  rules: {
    inputs:  ['logic_artifact.json', 'data_artifact.json (88-levels)'],
    outputs: ['rules/classified_conditions.json', 'rules/rules_artifact.json'],
    note:    'Mines every branch condition and 88-level name, classifies and tiers each as a business rule or technical condition, de-duplicates across programs, and assigns stable BR-XXX identifiers.',
  },
  diagram: {
    inputs:  ['graph.json', 'data_artifact.json', 'logic_artifact.json'],
    outputs: ['diagram/component_overview.mmd', 'diagram/erd.mmd', 'diagram/diagrams/flow_PROGRAM.mmd', 'diagram/diagrams_artifact.json'],
    note:    'Fully deterministic. Produces three diagram types: a system component graph, an entity-relationship model, and per-program control-flow diagrams. All rendered as Mermaid.',
  },
  brd: {
    inputs:  ['inventory.json', 'parser_artifact.json', 'data_artifact.json', 'logic_artifact.json', 'rules_artifact.json', 'all diagrams'],
    outputs: ['final_report/brd.md', 'final_report/brd_summary.md', 'final_report/gaps_register.json'],
    note:    'Hybrid: Python assembles all facts, tables and rule catalogues into a structured brief; LLM writes the connecting narrative — executive summary, system context and per-process prose. LLM never invents facts.',
  },
  judge: {
    inputs:  ['brd.md', 'rules_artifact.json', 'data_artifact.json', 'inventory.json', 'gaps_register.json'],
    outputs: ['final_report/brd_judge.md', 'final_report/brd_judge.json'],
    note:    'Two-part hybrid: (1) deterministic groundedness gate — every cited BR-/GAP-/RS- id must exist in the artifacts; (2) LLM scores 5 dimensions (completeness 25%, accuracy 30%, clarity 15%, consistency 15%, actionability 15%) → PASS or REVISE.',
  },
}

const AGENT_BUSINESS_NAME: Record<string, string> = {
  discovery: '1 · Source Discovery',
  parser:    '2 · Structure Extraction',
  topology:  '3 · Dependency Mapping',
  context:   '4 · Context Distillation',
  data:      '5 · Data Dictionary',
  logic:     '6 · Logic Translation',
  rules:     '7 · Rules Mining',
  diagram:   '8 · Diagram Generation',
  brd:       '9 · BRD Assembly',
  judge:     '10 · Quality Gate',
}

const AGENT_DESCRIPTIONS: Record<string, string> = {
  discovery: 'Scans the COBOL source folder and catalogues every program, copybook, JCL and BMS file. Builds the dependency map by resolving COPY, CALL and CICS references.',
  parser:    'Opens each COBOL program and extracts its structural skeleton — divisions, sections, paragraphs with line ranges, data definitions, and the control-flow graph.',
  topology:  'Merges the file catalogue and parsed structures into a single system dependency graph showing which programs call which, and which data definitions are shared.',
  context:   'Condenses each program\'s raw structure into a compact briefing sheet so the AI logic phase has focused, high-signal input.',
  data:      'Turns raw DATA DIVISION entries into a clean data dictionary — expands shared copybooks, decodes PIC clauses, and surfaces business-meaningful field names.',
  logic:     'Uses AI to translate each COBOL paragraph into plain-English pseudocode, capturing branches, called programs, field references, and a complexity score.',
  rules:     'Mines business rules from every branch condition and 88-level name. Classifies, tiers and de-duplicates rules across all programs, assigning stable BR-XXX identifiers.',
  diagram:   'Generates three Mermaid diagrams automatically: a system component overview, an entity-relationship model, and a control-flow diagram for each program.',
  brd:       'Assembles the Business Requirements Document — embedding all facts, rules, diagrams and gaps into a structured, client-ready report. LLM writes only the narrative.',
  judge:     'Validates the finished BRD: deterministic groundedness gate (every cited rule and program must exist) plus five-dimension AI quality scoring → PASS or REVISE verdict.',
}

// ── Mermaid diagram renderer ──────────────────────────────────────────────────

function PhaseDiagram({ diagram }: { diagram: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const theme = document.documentElement.getAttribute('data-theme') || 'dark'

  useEffect(() => {
    if (!ref.current || !diagram) return
    const el = ref.current
    import('mermaid').then(m => {
      m.default.initialize({
        startOnLoad: false,
        theme: theme === 'light' ? 'default' : 'dark',
        flowchart: { curve: 'basis', useMaxWidth: true },
        securityLevel: 'loose',
      })
      m.default.render(`phase-diag-${Date.now()}`, diagram)
        .then(({ svg }) => { if (el) el.innerHTML = svg })
        .catch(() => { if (el) el.innerHTML = '<div style="color:var(--color-text-muted);font-size:12px;padding:8px">Diagram unavailable</div>' })
    })
  }, [diagram, theme])

  return <div ref={ref} style={{ minHeight: 80 }} />
}

// ── Main tab ──────────────────────────────────────────────────────────────────

interface Props { phases: PhaseDef[] }

export default function AgentsTab({ phases }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const done = phases.filter(p => p.status === 'done').length

  return (
    <div>
      <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Agentic Workflow</h2>
      <p style={{ margin: '0 0 20px', color: 'var(--color-text-muted)', fontSize: 13 }}>
        {phases.length} automated agents chain in sequence — {phases.filter(p => p.type === 'Deterministic').length} deterministic and {phases.filter(p => p.type !== 'Deterministic').length} LLM-powered — to transform raw COBOL into a validated Business Requirements Document.
        {done === phases.length && <span style={{ marginLeft: 8, color: 'var(--color-green)', fontWeight: 600 }}>All {done} agents complete.</span>}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {phases.map(p => {
          const isDone    = p.status === 'done'
          const isLLM     = p.type === 'LLM + Python'
          const isOpen    = expanded === p.id
          const accentColor = isDone ? (isLLM ? 'var(--color-blue)' : 'var(--color-green)') : 'var(--color-border)'
          const detail    = PHASE_DETAIL[p.id]
          const flowDiag  = PHASE_FLOWS[p.id]

          return (
            <div key={p.id}>
              {/* Phase header card — always visible */}
              <div
                className="card"
                onClick={() => setExpanded(isOpen ? null : p.id)}
                style={{
                  borderLeft: `3px solid ${isOpen ? 'var(--color-accent)' : accentColor}`,
                  cursor: 'pointer',
                  display: 'grid',
                  gridTemplateColumns: '220px 1fr auto',
                  gap: 20,
                  alignItems: 'center',
                  borderRadius: isOpen ? '8px 8px 0 0' : 8,
                  borderBottom: isOpen ? '1px solid var(--color-border)' : undefined,
                  marginBottom: isOpen ? 0 : undefined,
                  transition: 'border-color 0.15s',
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>{AGENT_BUSINESS_NAME[p.id] || p.name}</div>
                  <div style={{ display: 'flex', gap: 6, marginTop: 5 }}>
                    <span className={`badge ${isLLM ? 'badge-llm' : 'badge-det'}`}>{isLLM ? 'LLM-powered' : 'Deterministic'}</span>
                    <span className={`badge ${isDone ? 'badge-done' : 'badge-pending'}`}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: isDone ? 'var(--color-green)' : 'var(--color-text-muted)', display: 'inline-block' }} />
                      {isDone ? 'Complete' : 'Pending'}
                    </span>
                  </div>
                </div>
                <div style={{ fontSize: 13, color: 'var(--color-text)', lineHeight: 1.5 }}>
                  {AGENT_DESCRIPTIONS[p.id] || ''}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  {isDone && (
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{p.artifact_kb > 0 ? `${p.artifact_kb} KB` : '—'}</div>
                      <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>{p.duration_fmt}</div>
                    </div>
                  )}
                  <span style={{ fontSize: 13, color: 'var(--color-text-muted)', userSelect: 'none' }}>
                    {isOpen ? '▲' : '▼'}
                  </span>
                </div>
              </div>

              {/* Expanded detail panel */}
              {isOpen && (
                <div style={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderTop: 'none',
                  borderRadius: '0 0 8px 8px',
                  padding: '20px 20px 16px',
                  marginBottom: 0,
                }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24 }}>

                    {/* Left: flow diagram */}
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: 10 }}>
                        Data Flow
                      </div>
                      <div style={{
                        background: 'var(--color-surface-2)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 8,
                        padding: '16px',
                        overflow: 'auto',
                      }}>
                        {flowDiag
                          ? <PhaseDiagram diagram={flowDiag} />
                          : <div style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>No diagram available</div>
                        }
                      </div>
                    </div>

                    {/* Right: inputs / outputs / note */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

                      {detail && (
                        <>
                          <div>
                            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: 6 }}>
                              Inputs
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                              {detail.inputs.map(inp => (
                                <div key={inp} style={{ display: 'flex', alignItems: 'flex-start', gap: 7, fontSize: 12 }}>
                                  <span style={{ color: 'var(--color-blue)', fontWeight: 700, flexShrink: 0, marginTop: 1 }}>↓</span>
                                  <span style={{ fontFamily: 'monospace', color: 'var(--color-text)', lineHeight: 1.4 }}>{inp}</span>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div>
                            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: 6 }}>
                              Outputs
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                              {detail.outputs.map(out => (
                                <div key={out} style={{ display: 'flex', alignItems: 'flex-start', gap: 7, fontSize: 12 }}>
                                  <span style={{ color: 'var(--color-green)', fontWeight: 700, flexShrink: 0, marginTop: 1 }}>↑</span>
                                  <span style={{ fontFamily: 'monospace', color: 'var(--color-text)', lineHeight: 1.4 }}>{out}</span>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div style={{
                            padding: '10px 12px', borderRadius: 7,
                            background: isLLM ? 'rgba(59,130,246,0.06)' : 'rgba(34,197,94,0.06)',
                            border: `1px solid ${isLLM ? 'rgba(59,130,246,0.18)' : 'rgba(34,197,94,0.18)'}`,
                            fontSize: 12, lineHeight: 1.6, color: 'var(--color-text)',
                          }}>
                            <span style={{ fontWeight: 700, color: isLLM ? 'var(--color-blue)' : 'var(--color-green)', marginRight: 4 }}>
                              {isLLM ? 'Hybrid:' : 'Deterministic:'}
                            </span>
                            {detail.note}
                          </div>
                        </>
                      )}

                      {isDone && (
                        <div style={{
                          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
                        }}>
                          {[
                            { label: 'Artifact', val: p.artifact },
                            { label: 'Size',     val: p.artifact_kb > 0 ? `${p.artifact_kb} KB` : '—' },
                            { label: 'Duration', val: p.duration_fmt },
                            { label: 'Completed', val: p.generated_at ? new Date(p.generated_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : '—' },
                          ].map(({ label, val }) => (
                            <div key={label} style={{ background: 'var(--color-surface-2)', borderRadius: 6, padding: '8px 10px' }}>
                              <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--color-text-muted)', marginBottom: 2 }}>{label}</div>
                              <div style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--color-text)', wordBreak: 'break-all' }}>{val}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
