import type { PhaseDef } from '../../types'

const AGENT_DESCRIPTIONS: Record<string, string> = {
  discovery: 'Scans the COBOL source folder and catalogues every program, copybook, JCL and BMS file. Builds the dependency map by resolving COPY, CALL and CICS references.',
  parser:    'Opens each COBOL program and extracts its structural skeleton — divisions, sections, paragraphs with line ranges, data definitions, and the control-flow graph.',
  topology:  'Merges the file catalogue and parsed structures into a single system dependency graph showing which programs call which, and which data definitions are shared.',
  context:   'Condenses each program\'s raw structure into a compact briefing sheet (data types, entry points, paragraph shape) so the AI logic phase has focused, high-signal input.',
  data:      'Turns raw DATA DIVISION entries into a clean data dictionary — expands shared copybooks, decodes PIC clauses into readable type / size / decimals, and surfaces business-meaningful field names.',
  logic:     'Uses AI to translate each COBOL paragraph into plain-English pseudocode, capturing branches, called programs, field references, and a complexity score per paragraph.',
  rules:     'Mines business rules from every branch condition and data-level condition name. Classifies, tiers and de-duplicates rules across all programs, assigning each a stable BR-XXX identifier.',
  diagram:   'Generates three Mermaid diagrams automatically: a system component overview, an entity-relationship model, and a control-flow diagram for each program.',
  brd:       'Uses AI to assemble the Business Requirements Document — embedding all facts, rules, diagrams and gaps into a structured, client-ready Word-compatible report.',
  judge:     'Validates the finished BRD: a deterministic groundedness check (every cited rule and program must exist) plus a five-dimension AI quality score → PASS or REVISE verdict.',
}

// Business-friendly names shown to clients
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

interface Props { phases: PhaseDef[] }

export default function AgentsTab({ phases }: Props) {
  const done = phases.filter(p => p.status === 'done').length

  return (
    <div>
      <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>How It Works</h2>
      <p style={{ margin: '0 0 20px', color: 'var(--color-text-muted)', fontSize: 13 }}>
        The pipeline runs {phases.length} automated agents in sequence — {phases.filter(p => p.type === 'Deterministic').length} deterministic and {phases.filter(p => p.type !== 'Deterministic').length} LLM-powered — to turn raw COBOL source into a validated Business Requirements Document.
        {done === phases.length && <span style={{ marginLeft: 8, color: 'var(--color-green)', fontWeight: 600 }}>All {done} agents complete.</span>}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {phases.map(p => {
          const isDone = p.status === 'done'
          const isLLM  = p.type === 'LLM + Python'
          return (
            <div key={p.id} className="card" style={{
              borderLeft: `3px solid ${isDone ? (isLLM ? 'var(--color-blue)' : 'var(--color-green)') : 'var(--color-border)'}`,
              display: 'grid', gridTemplateColumns: '220px 1fr auto', gap: 20, alignItems: 'center',
            }}>
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
              <div style={{ textAlign: 'right', minWidth: 90 }}>
                {isDone && (
                  <>
                    <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{p.artifact_kb > 0 ? `${p.artifact_kb} KB` : '—'}</div>
                    <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>{p.duration_fmt}</div>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
