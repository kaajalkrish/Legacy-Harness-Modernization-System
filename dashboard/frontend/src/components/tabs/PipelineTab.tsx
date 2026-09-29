import { useState } from 'react'
import type { PhaseDef, Verdict } from '../../types'

interface Props {
  phases: PhaseDef[]
  overallPct: number
  verdict?: Verdict
}

export default function PipelineTab({ phases, overallPct, verdict }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)

  return (
    <div style={{ maxWidth: 960 }}>
      <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Pipeline overview</h2>
      <p style={{ margin: '0 0 16px', color: 'var(--color-text-muted)', fontSize: 13 }}>Overall progress</p>

      {/* Full-width progress bar */}
      <div className="progress-bar" style={{ height: 8, marginBottom: 20 }}>
        <div className="progress-bar-fill" style={{ width: `${overallPct}%` }} />
      </div>

      {/* Phase summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 28 }}>
        {phases.map(phase => (
          <div
            key={phase.id}
            className="card"
            style={{ cursor: 'pointer', borderColor: expanded === phase.id ? 'var(--color-accent)' : 'var(--color-border)' }}
            onClick={() => setExpanded(expanded === phase.id ? null : phase.id)}
          >
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 4 }}>
              Phase {phase.num}
            </div>
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>{phase.name}</div>
            <span className={`badge ${phase.status === 'done' ? 'badge-done' : 'badge-pending'}`}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: phase.status === 'done' ? 'var(--color-green)' : 'var(--color-text-muted)', display: 'inline-block' }} />
              {phase.status}
            </span>
          </div>
        ))}
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
            {Object.entries(verdict.dimensions).map(([dim, d]) => (
              <div key={dim} className="card" style={{ padding: '10px 12px' }}>
                <div style={{ fontSize: 10, textTransform: 'capitalize', color: 'var(--color-text-muted)', marginBottom: 4 }}>{dim}</div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{d.score}<span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>/5</span></div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
