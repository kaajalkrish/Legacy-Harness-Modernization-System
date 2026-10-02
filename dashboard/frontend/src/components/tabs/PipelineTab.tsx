import { useState } from 'react'
import type { PhaseDef, Verdict } from '../../types'

const SCORE_COLOR = (s: number) =>
  s >= 4 ? 'var(--color-green)' : s >= 3 ? 'var(--color-accent)' : 'var(--color-red)'

const SCORE_BG = (s: number) =>
  s >= 4 ? 'rgba(34,197,94,0.08)' : s >= 3 ? 'rgba(232,184,0,0.08)' : 'rgba(239,68,68,0.08)'

interface Props {
  phases: PhaseDef[]
  overallPct: number
  verdict?: Verdict
}

export default function PipelineTab({ phases, overallPct, verdict }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)

  return (
    <div>
      <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Pipeline overview</h2>
      <p style={{ margin: '0 0 16px', color: 'var(--color-text-muted)', fontSize: 13 }}>Overall progress</p>

      {/* Full-width progress bar */}
      <div className="progress-bar" style={{ height: 8, marginBottom: 20 }}>
        <div className="progress-bar-fill" style={{ width: `${overallPct}%` }} />
      </div>

      {/* Color key */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 12, alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Phase type:</span>
        {[
          { color: 'var(--color-green)', label: 'Deterministic' },
          { color: 'var(--color-blue)',  label: 'LLM-powered' },
          { color: 'var(--color-border)',label: 'Pending' },
        ].map(({ color, label }) => (
          <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--color-text-muted)' }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: color, display: 'inline-block', flexShrink: 0 }} />
            {label}
          </span>
        ))}
      </div>

      {/* Phase summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 28 }}>
        {phases.map(phase => {
          const isDone = phase.status === 'done'
          const isLLM  = phase.type === 'LLM + Python'
          const accentColor = isDone ? (isLLM ? 'var(--color-blue)' : 'var(--color-green)') : 'var(--color-border)'
          return (
          <div
            key={phase.id}
            className="card"
            style={{
              cursor: 'pointer',
              borderLeft: `3px solid ${expanded === phase.id ? 'var(--color-accent)' : accentColor}`,
              borderColor: expanded === phase.id ? 'var(--color-accent)' : undefined,
            }}
            onClick={() => setExpanded(expanded === phase.id ? null : phase.id)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>
                Phase {phase.num}
              </div>
              <span style={{ fontSize: 14 }}>{isDone ? '✓' : '○'}</span>
            </div>
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>{phase.name}</div>
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
              <span className={`badge ${isDone ? 'badge-done' : 'badge-pending'}`}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: isDone ? 'var(--color-green)' : 'var(--color-text-muted)', display: 'inline-block' }} />
                {phase.status}
              </span>
              <span className={`badge ${isLLM ? 'badge-llm' : 'badge-det'}`}>{isLLM ? 'LLM' : 'Det'}</span>
            </div>
          </div>
          )
        })}
      </div>

      {/* Expanded phase detail */}
      {phases.map(phase => (
        expanded === phase.id && (
          <div key={phase.id} className="card" style={{ marginBottom: 12, borderColor: 'var(--color-accent)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15 }}>Phase {phase.num}: {phase.name}</div>
                <div style={{ color: 'var(--color-text-muted)', fontSize: 12, marginTop: 2 }}>{phase.module}</div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <span className={`badge ${phase.type === 'Deterministic' ? 'badge-det' : 'badge-llm'}`}>{phase.type}</span>
                <span className={`badge ${phase.status === 'done' ? 'badge-done' : 'badge-pending'}`}>{phase.status}</span>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, fontSize: 12 }}>
              <div>
                <div style={{ color: 'var(--color-text-muted)', marginBottom: 2 }}>Artifact</div>
                <div style={{ fontFamily: 'monospace', fontSize: 11 }}>{phase.artifact}</div>
              </div>
              <div>
                <div style={{ color: 'var(--color-text-muted)', marginBottom: 2 }}>Size</div>
                <div>{phase.artifact_kb > 0 ? `${phase.artifact_kb} KB` : '—'}</div>
              </div>
              <div>
                <div style={{ color: 'var(--color-text-muted)', marginBottom: 2 }}>Duration</div>
                <div>{phase.duration_fmt}</div>
              </div>
              {phase.generated_at && (
                <div style={{ gridColumn: '1/-1' }}>
                  <div style={{ color: 'var(--color-text-muted)', marginBottom: 2 }}>Completed at</div>
                  <div style={{ fontFamily: 'monospace', fontSize: 11 }}>{phase.generated_at}</div>
                </div>
              )}
            </div>
          </div>
        )
      ))}

      {/* Judge verdict card */}
      {verdict && verdict.verdict && verdict.verdict !== '—' && (
        <div className="card" style={{ marginTop: 8, borderColor: verdict.verdict === 'PASS' ? 'var(--color-green)' : 'var(--color-orange)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <span style={{ fontWeight: 700, fontSize: 15 }}>BRD Judge Verdict</span>
            <span className={`badge ${verdict.verdict === 'PASS' ? 'badge-pass' : 'badge-revise'}`} style={{ fontSize: 13 }}>
              {verdict.verdict}
            </span>
            <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Rating: {verdict.rating} · Score: {verdict.weighted_score?.toFixed(2)}/5.0</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
            {Object.entries(verdict.dimensions).map(([dim, d]) => {
              const suggestion = verdict.feedback?.find(f => f.dimension === dim)
              return (
                <div key={dim} className="card" style={{ padding: '10px 12px', borderLeft: `3px solid ${SCORE_COLOR(d.score)}`, background: SCORE_BG(d.score) }}>
                  <div style={{ fontSize: 10, textTransform: 'capitalize', color: 'var(--color-text-muted)', marginBottom: 4, fontWeight: 700, letterSpacing: '0.05em' }}>{dim}</div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: SCORE_COLOR(d.score), lineHeight: 1 }}>
                    {d.score}<span style={{ fontSize: 11, color: 'var(--color-text-muted)', fontWeight: 400 }}>/5</span>
                  </div>
                  {d.rationale && (
                    <div style={{ marginTop: 6, fontSize: 11, color: 'var(--color-text-muted)', lineHeight: 1.5 }}>
                      {d.rationale}
                    </div>
                  )}
                  {suggestion && (
                    <div style={{ marginTop: 6, padding: '5px 8px', borderRadius: 5, background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.18)', fontSize: 11, color: 'var(--color-blue)', lineHeight: 1.4 }}>
                      <strong>Improve:</strong> {suggestion.suggestion}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
