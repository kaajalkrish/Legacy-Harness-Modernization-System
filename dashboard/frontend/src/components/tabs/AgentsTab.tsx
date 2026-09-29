import type { PhaseDef } from '../../types'

const AGENT_DESCRIPTIONS: Record<string, string> = {
  discovery: 'Scans the COBOL source root. Catalogs every program, copybook, JCL and BMS file. Resolves COPY / CALL / CICS dependencies into inventory.json.',
  parser:    'Opens each COBOL program and extracts its structural skeleton — divisions, sections, paragraphs with line ranges, WORKING-STORAGE, and the PERFORM/GO TO control-flow graph.',
  topology:  'Merges the inventory edges and parsed ASTs into one system dependency graph — nodes (programs, copybooks, DB2) and typed relationships.',
  context:   'Pre-digests each program\'s raw AST into a compact human-readable briefing sheet for the Logic phase.',
  data:      'Turns the DATA DIVISION into a clean data dictionary — expands COPY stubs, decodes PIC clauses, resolves REDEFINES and OCCURS.',
  logic:     'Translates each COBOL paragraph into plain-English pseudocode and captures branches, calls, field references and complexity scores.',
  rules:     'Mines business rules from branch conditions and 88-levels, classifies and tiers each, and de-duplicates across programs.',
  diagram:   'Produces Mermaid diagrams: a component overview, an ER diagram, and per-program control-flow diagrams.',
  brd:       'Assembles all knowledge artifacts into the Business Requirements Document, embedding diagrams and a gaps register.',
  judge:     'Validates the BRD: deterministic groundedness gate + 5-dimension LLM scoring → PASS or REVISE verdict.',
}

interface Props { phases: PhaseDef[] }

export default function AgentsTab({ phases }: Props) {
  return (
    <div>
      <h2 style={{ margin: '0 0 16px', fontSize: 18, fontWeight: 700 }}>Agents</h2>
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Agent</th>
              <th>Type</th>
              <th>Backing module</th>
              <th>Output artifact</th>
              <th>Status</th>
              <th>Size</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {phases.map(p => (
              <tr key={p.id}>
                <td style={{ fontWeight: 700, color: 'var(--color-accent)' }}>{p.num}</td>
                <td>
                  <div style={{ fontWeight: 600 }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>
                    {AGENT_DESCRIPTIONS[p.id] || ''}
                  </div>
                </td>
                <td>
                  <span className={`badge ${p.type === 'Deterministic' ? 'badge-det' : 'badge-llm'}`}>{p.type}</span>
                </td>
                <td style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--color-text-muted)' }}>{p.module}</td>
                <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{p.artifact}</td>
                <td><span className={`badge ${p.status === 'done' ? 'badge-done' : 'badge-pending'}`}>{p.status}</span></td>
                <td style={{ color: 'var(--color-text-muted)' }}>{p.artifact_kb > 0 ? `${p.artifact_kb} KB` : '—'}</td>
                <td style={{ color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>{p.duration_fmt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
