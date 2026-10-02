import { useEffect, useState } from 'react'
import type { SyntestData, Scenario, CoverageEntry } from '../../types'
import ScenarioModal from '../ScenarioModal'

interface Props {
  outputDir: string
}

const TYPE_LABELS: Record<string, string> = {
  happy_path:       'Happy Path',
  negative_path:    'Negative Path',
  boundary:         'Boundary',
  exception:        'Exception',
  state_transition: 'State Transition',
  integration:      'Integration',
}

const TYPE_PREFIX: Record<string, string> = {
  happy_path: 'H', negative_path: 'N', boundary: 'B',
  exception: 'E', state_transition: 'S', integration: 'I',
}

const TYPE_COLOR: Record<string, string> = {
  happy_path:       'var(--color-green)',
  negative_path:    'var(--color-red)',
  boundary:         'var(--color-blue)',
  exception:        'var(--color-orange)',
  state_transition: '#a78bfa',
  integration:      'var(--color-accent)',
}

const READINESS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  test_ready:       { label: 'Test-ready',     color: 'var(--color-green)',  bg: 'rgba(34,197,94,0.12)'  },
  needs_detail:     { label: 'Needs detail',   color: 'var(--color-accent)', bg: 'rgba(232,184,0,0.12)'  },
  needs_sme_review: { label: 'Needs SME',      color: 'var(--color-orange)', bg: 'rgba(249,115,22,0.12)' },
}

const SCENARIO_TYPES = ['happy_path', 'negative_path', 'boundary', 'exception', 'state_transition', 'integration']
const READINESS_LEVELS = ['test_ready', 'needs_sme_review', 'needs_detail']

const TYPE_DESCRIPTIONS: Record<string, string> = {
  happy_path:       'The rule fires and everything works correctly — no errors, no edge cases. Tests the normal success flow.',
  negative_path:    'The rule is NOT satisfied — e.g. invalid input or a failed condition. Tests that the system correctly rejects or routes away.',
  boundary:         'The value sits right at the edge of a limit (at, just above, or just below a threshold). Catches off-by-one and rounding errors.',
  exception:        'Something unexpected happens in the error-handling path. Tests that the system fails gracefully without crashing.',
  state_transition: 'After the rule fires, all downstream fields and records must update consistently. Tests that no stale values remain in the system.',
  integration:      'The same business rule spans multiple COBOL programs. Tests that every program involved agrees on the outcome end-to-end.',
}

// ── CSV export ────────────────────────────────────────────────────────────────

function exportCSV(scenarios: Scenario[]) {
  const header = ['ID', 'Name', 'Type', 'Status', 'Readiness', 'Confidence', 'Rule ID',
                  'Checklist Score', 'Programs', 'Gap Reasons', 'SME Action']
  const rows = scenarios.map(s => [
    s.id,
    s.name,
    TYPE_LABELS[s.type] || s.type,
    s.status,
    s.readiness_level,
    s.confidence,
    s.rule_id,
    String(s.checklist_score ?? ''),
    s.programs.join('; '),
    (s.gap_reasons || []).join(' | '),
    s.sme_action || '',
  ])
  const csv = [header, ...rows]
    .map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = 'synthetic_tests.csv'
  a.click()
  URL.revokeObjectURL(url)
}

// ── Coverage row ──────────────────────────────────────────────────────────────

function CoverageRow({ entry }: { entry: CoverageEntry }) {
  const color    = TYPE_COLOR[entry.type] || 'var(--color-text-muted)'
  const achieved = Math.min(entry.achieved_pct, 100)

  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12, marginBottom: 5 }}>
        <span style={{ color: 'var(--color-text)', fontWeight: 500, minWidth: 130 }}>
          {TYPE_LABELS[entry.type] || entry.type}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, justifyContent: 'flex-end' }}>
          <span style={{ color: 'var(--color-text-muted)', fontSize: 11 }}>
            {entry.achieved_pct.toFixed(0)}% achieved · min {entry.min_pct}%
          </span>
          <span style={{
            fontWeight: 700, fontSize: 11, padding: '2px 8px', borderRadius: 4,
            background: entry.meets_target ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
            color: entry.meets_target ? 'var(--color-green)' : 'var(--color-red)',
          }}>
            {entry.meets_target ? '✓ meets target' : '✗ below target'}
          </span>
        </div>
      </div>
      <div style={{ position: 'relative', height: 8, background: 'var(--color-border)', borderRadius: 4, overflow: 'visible' }}>
        <div style={{
          position: 'absolute', left: 0, top: 0, height: '100%',
          width: `${achieved}%`, background: color,
          borderRadius: 4, transition: 'width 0.4s ease',
        }} />
        <div style={{
          position: 'absolute', top: -3, bottom: -3,
          left: `${entry.min_pct}%`, width: 2,
          background: 'var(--color-green)', borderRadius: 1,
          transform: 'translateX(-50%)',
        }} />
      </div>
      {entry.interpretation && (
        <div style={{ marginTop: 5, fontSize: 11, color: 'var(--color-text-muted)', lineHeight: 1.5 }}>
          {entry.interpretation}
        </div>
      )}
    </div>
  )
}

// ── Scenario list panel ───────────────────────────────────────────────────────

function ScenarioList({
  scenarios, typeFilter, readinessFilter, searchQuery, onSelect, selectedId,
}: {
  scenarios:       Scenario[]
  typeFilter:      string
  readinessFilter: string
  searchQuery:     string
  onSelect:        (s: Scenario) => void
  selectedId:      string | null
}) {
  const q = searchQuery.trim().toLowerCase()

  const filtered = scenarios.filter(s => {
    if (typeFilter !== 'ALL' && s.type !== typeFilter) return false
    if (readinessFilter !== 'ALL' && s.readiness_level !== readinessFilter) return false
    if (q && !s.id.toLowerCase().includes(q) &&
             !s.name.toLowerCase().includes(q) &&
             !s.rule_id.toLowerCase().includes(q)) return false
    return true
  })

  return (
    <div style={{ overflowY: 'auto', maxHeight: 440, borderRadius: 8, border: '1px solid var(--color-border)' }}>
      {filtered.length === 0 && (
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>
          No scenarios match the current filters.
        </div>
      )}
      {filtered.map(s => {
        const tColor   = TYPE_COLOR[s.type] || 'var(--color-text-muted)'
        const rc       = READINESS_CONFIG[s.readiness_level] || READINESS_CONFIG['needs_detail']
        const isSelected = s.id === selectedId
        return (
          <div
            key={s.id}
            onClick={() => onSelect(s)}
            style={{
              padding: '10px 14px',
              borderBottom: '1px solid var(--color-border)',
              cursor: 'pointer',
              background: isSelected ? 'var(--color-surface-2)' : 'var(--color-surface)',
              borderLeft: isSelected ? `3px solid ${tColor}` : '3px solid transparent',
              transition: 'background 0.1s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
              <span style={{ fontWeight: 700, fontSize: 12, color: 'var(--color-accent)', fontFamily: 'monospace' }}>
                {s.id}
              </span>
              <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
                <span style={{ fontSize: 10, fontWeight: 600, color: rc.color }}>{rc.label}</span>
                <span className={`badge badge-${s.status === 'pass' ? 'pass' : 'pending'}`} style={{ fontSize: 10 }}>
                  {s.status === 'pass' ? '✓ PASS' : '~ GAPS'}
                </span>
              </div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text)', marginBottom: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {s.name}
            </div>
            <div style={{ fontSize: 11, color: tColor }}>
              {TYPE_LABELS[s.type] || s.type}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Main tab ──────────────────────────────────────────────────────────────────

export default function SyntheticTestingTab({ outputDir }: Props) {
  const [data, setData]                         = useState<SyntestData | null>(null)
  const [loading, setLoading]                   = useState(true)
  const [typeFilter, setTypeFilter]             = useState('ALL')
  const [readinessFilter, setReadinessFilter]   = useState('ALL')
  const [searchQuery, setSearchQuery]           = useState('')
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null)
  const [expandedStep, setExpandedStep]         = useState<number | null>(null)
  const [showLegend, setShowLegend]             = useState(false)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/syntest?outputDir=${encodeURIComponent(outputDir)}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [outputDir])

  if (loading) return (
    <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--color-text-muted)' }}>
      Loading synthetic tests…
    </div>
  )

  if (!data || !data.scenarios?.length) return (
    <div style={{ padding: '40px 0', textAlign: 'center' }}>
      <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>No synthetic tests yet</div>
      <div style={{ color: 'var(--color-text-muted)', fontSize: 13, maxWidth: 480, margin: '0 auto', lineHeight: 1.6 }}>
        Run Phase 11 to generate test scenarios from your business rules:
      </div>
      <code style={{ display: 'block', marginTop: 12, padding: '8px 16px', background: 'var(--color-surface-2)', borderRadius: 6, fontSize: 12, color: 'var(--color-accent)' }}>
        python -m phases.p11_syntest.syntest_builder --output outputs/carddemo
      </code>
    </div>
  )

  const { stats, coverage, score_breakdown: sb, scenarios, executive_summary, generated_at } = data

  const scoreColor = stats.quality_score >= 80 ? 'var(--color-green)'
    : stats.quality_score >= 60 ? 'var(--color-accent)'
    : 'var(--color-red)'

  const byReadiness = stats.by_readiness || {}

  // Counts for pills
  const countByType = scenarios.reduce((acc, s) => {
    acc[s.type] = (acc[s.type] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  const countByReadiness = scenarios.reduce((acc, s) => {
    acc[s.readiness_level] = (acc[s.readiness_level] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  // Formatted generated_at
  const generatedLabel = generated_at
    ? new Date(generated_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
    : null

  return (
    <div>
      {selectedScenario && (
        <ScenarioModal scenario={selectedScenario} onClose={() => setSelectedScenario(null)} />
      )}

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
        <div>
          <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Synthetic Testing</h2>
          <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: 13 }}>
            Quality gate · {stats.total} scenarios · score {stats.quality_score}/100
            {generatedLabel && <span style={{ marginLeft: 12, color: 'var(--color-border)', fontSize: 12 }}>· Last run: {generatedLabel}</span>}
          </p>
        </div>
        <button
          onClick={() => exportCSV(scenarios)}
          style={{
            padding: '6px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
            color: 'var(--color-text)', display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          ↓ Export CSV
        </button>
      </div>

      {/* Executive Summary */}
      {executive_summary && (
        <div style={{
          marginBottom: 20, padding: '16px 20px',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderLeft: `4px solid ${scoreColor}`,
          borderRadius: 8,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: scoreColor, marginBottom: 8 }}>
            Executive Summary
          </div>
          <p style={{ margin: 0, fontSize: 13, lineHeight: 1.7, color: 'var(--color-text)' }}>
            {executive_summary}
          </p>
          <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
            {byReadiness.test_ready != null && (
              <span style={{ fontSize: 12, padding: '3px 12px', borderRadius: 99, background: 'rgba(34,197,94,0.12)', color: 'var(--color-green)', border: '1px solid rgba(34,197,94,0.25)', fontWeight: 600 }}>
                {byReadiness.test_ready} test-ready
              </span>
            )}
            {(byReadiness.needs_detail ?? 0) > 0 && (
              <span style={{ fontSize: 12, padding: '3px 12px', borderRadius: 99, background: 'rgba(232,184,0,0.12)', color: 'var(--color-accent)', border: '1px solid rgba(232,184,0,0.25)', fontWeight: 600 }}>
                {byReadiness.needs_detail} needs detail
              </span>
            )}
            {(byReadiness.needs_sme_review ?? 0) > 0 && (
              <span style={{ fontSize: 12, padding: '3px 12px', borderRadius: 99, background: 'rgba(249,115,22,0.12)', color: 'var(--color-orange)', border: '1px solid rgba(249,115,22,0.25)', fontWeight: 600 }}>
                {byReadiness.needs_sme_review} needs SME review
              </span>
            )}
          </div>
        </div>
      )}

      {/* "Why this score?" insight panel — shown when quality < 80 */}
      {stats.quality_score < 80 && sb.deductions.length > 0 && (
        <div style={{
          marginBottom: 20, padding: '16px 20px',
          background: stats.quality_score < 60 ? 'rgba(239,68,68,0.05)' : 'rgba(249,115,22,0.05)',
          border: `1px solid ${stats.quality_score < 60 ? 'rgba(239,68,68,0.25)' : 'rgba(249,115,22,0.25)'}`,
          borderLeft: `4px solid ${scoreColor}`,
          borderRadius: 8,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 16 }}>⚠</span>
            <span style={{ fontWeight: 700, fontSize: 13, color: scoreColor }}>
              Why this score is {stats.quality_score}/100
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: 6 }}>
                Drawbacks
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {sb.deductions.slice(0, 3).map((d, i) => (
                  <div key={i} style={{ fontSize: 12, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                    <span style={{ color: 'var(--color-red)', fontWeight: 700, flexShrink: 0 }}>−{d.penalty}</span>
                    <span style={{ color: 'var(--color-text)', lineHeight: 1.4 }}>{d.label}{d.explanation ? ` — ${d.explanation}` : ''}</span>
                  </div>
                ))}
              </div>
            </div>
            {sb.next_steps && sb.next_steps.length > 0 && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: 6 }}>
                  Suggested Improvements
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {sb.next_steps.slice(0, 3).map(step => (
                    <div key={step.priority} style={{ fontSize: 12, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                      <span style={{
                        width: 18, height: 18, borderRadius: '50%', flexShrink: 0, marginTop: 1,
                        background: step.priority === 1 ? 'var(--color-red)' : step.priority === 2 ? 'var(--color-orange)' : 'var(--color-accent)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 9, fontWeight: 800, color: '#111',
                      }}>{step.priority}</span>
                      <span style={{ color: 'var(--color-text)', lineHeight: 1.4 }}>
                        <strong>{step.title}</strong>
                        {step.impact && <span style={{ color: 'var(--color-text-muted)' }}> · {step.impact}</span>}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* KPI strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'QUALITY SCORE', val: stats.quality_score,     color: scoreColor,                                                              unit: '/100' },
          { label: 'BLOCKING',      val: stats.blocking_findings, color: stats.blocking_findings > 0 ? 'var(--color-red)' : 'var(--color-green)', unit: '' },
          { label: 'SCENARIOS',     val: stats.total,             color: 'var(--color-text)',                                                      unit: '' },
          { label: 'PASSED',        val: stats.passed,            color: 'var(--color-green)',                                                     unit: '' },
          { label: 'WITH GAPS',     val: stats.with_gaps,         color: 'var(--color-accent)',                                                    unit: '' },
          { label: 'FAILED',        val: stats.failed,            color: 'var(--color-red)',                                                       unit: '' },
        ].map(k => (
          <div className="kpi-tile" key={k.label}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value" style={{ color: k.color, fontSize: 26 }}>{k.val}{k.unit}</div>
          </div>
        ))}
      </div>

      {/* Main 2-col layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 20, marginBottom: 20 }}>

        {/* Left: Coverage + Score + Next Steps */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Coverage */}
          <div className="card">
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>Coverage by Scenario Type</div>
            <p style={{ margin: '0 0 16px', color: 'var(--color-text-muted)', fontSize: 12 }}>
              Coloured bar = achieved coverage. Green line = minimum required threshold. Each category must reach its target to avoid a score deduction.
            </p>
            {coverage.map(entry => <CoverageRow key={entry.type} entry={entry} />)}
          </div>

          {/* Score calculation */}
          <div className="card">
            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16 }}>Score Calculation</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
              {[
                { label: 'Starting Score', val: sb.starting_score,  color: 'var(--color-text)',   sub: 'before deductions' },
                { label: 'Final Score',    val: sb.final_score,     color: scoreColor,            sub: 'after penalties'   },
                { label: 'Blocking',       val: sb.blocking_count,  color: sb.blocking_count > 0 ? 'var(--color-red)' : 'var(--color-green)', sub: 'gate-impacting' },
              ].map(t => (
                <div key={t.label} style={{ background: 'var(--color-surface-2)', borderRadius: 8, padding: '12px 14px' }}>
                  <div style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>{t.label}</div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: t.color }}>{t.val}</div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{t.sub}</div>
                </div>
              ))}
            </div>

            {sb.deductions.length > 0 && (
              <>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: 8 }}>Deductions</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
                  {sb.deductions.map((d, i) => (
                    <div key={i} style={{ padding: '8px 12px', borderRadius: 6, fontSize: 12, background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: d.explanation ? 4 : 0 }}>
                        <span style={{ fontWeight: 600, color: 'var(--color-red)' }}>{d.label}</span>
                        <span style={{ fontWeight: 700, color: 'var(--color-red)' }}>{d.penalty}</span>
                      </div>
                      {d.explanation && <div style={{ fontSize: 11, color: 'var(--color-text-muted)', lineHeight: 1.5 }}>{d.explanation}</div>}
                    </div>
                  ))}
                </div>
              </>
            )}

            {sb.blocking_findings.length > 0 && (
              <>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: 8 }}>Blocking Findings</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {sb.blocking_findings.map(f => (
                    <div key={f.id} style={{ padding: '8px 12px', borderRadius: 6, fontSize: 12, background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: f.action ? 4 : 0 }}>
                        <span style={{ fontWeight: 700, color: 'var(--color-red)' }}>{f.id}</span>
                        <span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--color-text-muted)' }}>{f.scenario} · {f.rule_id}</span>
                      </div>
                      {f.action && <div style={{ fontSize: 11, color: 'var(--color-text-muted)', lineHeight: 1.5 }}>{f.action}</div>}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Next Steps */}
          {sb.next_steps && sb.next_steps.length > 0 && (
            <div className="card">
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>Prioritised Next Steps</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {sb.next_steps.map(step => (
                  <div
                    key={step.priority}
                    onClick={() => setExpandedStep(expandedStep === step.priority ? null : step.priority)}
                    style={{
                      padding: '10px 14px', borderRadius: 8, cursor: 'pointer',
                      border: '1px solid var(--color-border)',
                      background: expandedStep === step.priority ? 'var(--color-surface-2)' : 'var(--color-surface)',
                      transition: 'background 0.1s',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{
                        width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
                        background: step.priority === 1 ? 'var(--color-red)' : step.priority === 2 ? 'var(--color-orange)' : 'var(--color-accent)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 800, color: '#111',
                      }}>{step.priority}</span>
                      <span style={{ fontWeight: 600, fontSize: 13, flex: 1 }}>{step.title}</span>
                      <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{expandedStep === step.priority ? '▲' : '▼'}</span>
                    </div>
                    {expandedStep === step.priority && (
                      <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--color-border)' }}>
                        <p style={{ margin: '0 0 8px', fontSize: 12, lineHeight: 1.6, color: 'var(--color-text)' }}>{step.detail}</p>
                        <div style={{ fontSize: 11, padding: '6px 10px', borderRadius: 6, background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', color: 'var(--color-blue)' }}>
                          <strong>Impact:</strong> {step.impact}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Scenario list with search + filters */}
        <div>
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10 }}>Scenarios</div>

          {/* Search box */}
          <input
            type="text"
            placeholder="Search ID, name, or rule ID…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              width: '100%', boxSizing: 'border-box',
              padding: '7px 12px', borderRadius: 6, marginBottom: 8,
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              color: 'var(--color-text)', fontSize: 12, outline: 'none',
            }}
          />

          {/* Readiness filter */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 8 }}>
            {['ALL', ...READINESS_LEVELS].map(r => {
              const rc = r !== 'ALL' ? READINESS_CONFIG[r] : null
              const count = r === 'ALL' ? scenarios.length : (countByReadiness[r] || 0)
              return (
                <button
                  key={r}
                  onClick={() => setReadinessFilter(r)}
                  className={`pill${readinessFilter === r ? ' active' : ''}`}
                  style={{
                    fontSize: 11, padding: '3px 10px',
                    ...(readinessFilter === r && rc ? { background: rc.bg, borderColor: rc.color, color: rc.color } : {}),
                  }}
                >
                  {r === 'ALL' ? `All (${count})` : `${rc!.label} (${count})`}
                </button>
              )
            })}
          </div>

          {/* Type filter */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 10 }}>
            {['ALL', ...SCENARIO_TYPES].map(t => {
              const count = t === 'ALL' ? scenarios.length : (countByType[t] || 0)
              return (
                <button
                  key={t}
                  onClick={() => setTypeFilter(t)}
                  className={`pill${typeFilter === t ? ' active' : ''}`}
                  style={{
                    fontSize: 11, padding: '3px 10px',
                    ...(typeFilter === t && t !== 'ALL' ? { background: TYPE_COLOR[t], borderColor: TYPE_COLOR[t], color: '#111' } : {}),
                  }}
                >
                  {t === 'ALL' ? `All (${count})` : `${TYPE_PREFIX[t]} · ${TYPE_LABELS[t]} (${count})`}
                </button>
              )
            })}
          </div>

          {/* Scenario type legend */}
          <div style={{ marginBottom: 10 }}>
            <button
              onClick={() => setShowLegend(v => !v)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontSize: 11, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <span>{showLegend ? '▲' : '▼'}</span>
              <span>What do these scenario types mean?</span>
            </button>
            {showLegend && (
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {SCENARIO_TYPES.map(t => (
                  <div key={t} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                    <span style={{
                      marginTop: 2, flexShrink: 0,
                      width: 10, height: 10, borderRadius: '50%',
                      background: TYPE_COLOR[t],
                      display: 'inline-block',
                    }} />
                    <div>
                      <span style={{ fontSize: 11, fontWeight: 700, color: TYPE_COLOR[t] }}>
                        {TYPE_LABELS[t]}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--color-text-muted)', marginLeft: 6 }}>
                        {TYPE_DESCRIPTIONS[t]}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <ScenarioList
            scenarios={scenarios}
            typeFilter={typeFilter}
            readinessFilter={readinessFilter}
            searchQuery={searchQuery}
            onSelect={setSelectedScenario}
            selectedId={selectedScenario?.id || null}
          />

          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--color-text-muted)' }}>
            Click any scenario to see the full detail, gap analysis, and SME action.
          </div>
        </div>
      </div>
    </div>
  )
}
