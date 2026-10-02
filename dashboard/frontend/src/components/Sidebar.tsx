import type { PhaseDef } from '../types'

interface Props {
  phases: PhaseDef[]
  open: boolean
  onToggle: () => void
}

export default function Sidebar({ phases, open, onToggle }: Props) {
  return (
    <div className={`sidebar${open ? '' : ' collapsed'}`}>
      {/* Header — full when open, just the expand button when collapsed */}
      {open ? (
        <div style={{ padding: '16px 14px 12px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 8, background: 'var(--color-accent)', color: '#111',
            fontWeight: 800, fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, letterSpacing: '-0.5px'
          }}>C→B</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--color-text)' }}>COBOL → BRD</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Pipeline Dashboard</div>
          </div>
          <button
            onClick={onToggle}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', fontSize: 18, padding: '0 2px', flexShrink: 0 }}
            title="Collapse sidebar"
          >‹</button>
        </div>
      ) : (
        <div style={{ padding: '12px 0', borderBottom: '1px solid var(--color-border)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 6, background: 'var(--color-accent)', color: '#111',
            fontWeight: 800, fontSize: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', letterSpacing: '-0.5px'
          }}>C→B</div>
          <button
            onClick={onToggle}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', fontSize: 18, padding: '0 2px' }}
            title="Expand sidebar"
          >›</button>
        </div>
      )}

      {/* Phase list */}
      <div style={{ flex: 1, overflow: 'auto', padding: '12px 0' }}>
        {open && (
          <div style={{ padding: '4px 14px 10px' }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 6 }}>
              Pipeline · {phases.length} Phases
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--color-text-muted)' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-green)', display: 'inline-block' }} />
                Deterministic
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--color-text-muted)' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-blue)', display: 'inline-block' }} />
                Hybrid / LLM
              </span>
            </div>
          </div>
        )}
        {phases.map((phase, idx) => {
          const isLLM  = phase.type === 'LLM + Python'
          const isDone = phase.status === 'done'
          const circleColor = isDone
            ? (isLLM ? 'var(--color-blue)' : 'var(--color-green)')
            : 'var(--color-border)'
          const circleFg = isDone ? '#fff' : 'var(--color-text-muted)'
          const isLast = idx === phases.length - 1

          return (
            <div
              key={phase.id}
              style={{ position: 'relative', padding: open ? '8px 14px' : '8px 13px', display: 'flex', alignItems: 'flex-start', gap: 10 }}
            >
              {/* Vertical connector line to next phase */}
              {!isLast && (
                <div style={{
                  position: 'absolute',
                  left: open ? 26 : 25,
                  top: 34,
                  width: 2,
                  bottom: -8,
                  background: isDone ? 'rgba(34,197,94,0.35)' : 'var(--color-border)',
                  borderRadius: 1,
                }} />
              )}
              <div
                title={`Phase ${phase.num} · ${phase.type}${isDone ? ' · Complete' : ' · Pending'}`}
                style={{
                  width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                  background: circleColor, color: circleFg,
                  fontSize: 11, fontWeight: 800,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  zIndex: 1, marginTop: 1, cursor: 'default',
                  boxShadow: isDone ? `0 0 0 3px ${isLLM ? 'rgba(59,130,246,0.18)' : 'rgba(34,197,94,0.18)'}` : 'none',
                }}
              >
                {phase.num}
              </div>
              {open && (
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {phase.name}
                    </span>
                    <span className={`badge ${isDone ? 'badge-done' : 'badge-pending'}`} style={{ flexShrink: 0 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: isDone ? 'var(--color-green)' : 'var(--color-text-muted)', display: 'inline-block' }} />
                      {phase.status}
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 1 }}>
                    {phase.agent}
                    {isLLM && <span style={{ marginLeft: 5, color: 'var(--color-blue)', fontSize: 9, fontWeight: 700 }}>LLM</span>}
                  </div>
                  <div className="progress-bar" style={{ marginTop: 5 }}>
                    <div className="progress-bar-fill" style={{ width: isDone ? '100%' : '0%', background: isDone ? (isLLM ? 'var(--color-blue)' : 'var(--color-green)') : 'var(--color-border)' }} />
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Footer: completion summary */}
      {open && (
        <div style={{ padding: '10px 14px', borderTop: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
            {phases.filter(p => p.status === 'done').length}/{phases.length} complete
          </div>
          <div style={{ fontSize: 11, fontWeight: 700, color: phases.every(p => p.status === 'done') ? 'var(--color-green)' : 'var(--color-accent)' }}>
            {Math.round(phases.filter(p => p.status === 'done').length / Math.max(phases.length, 1) * 100)}%
          </div>
        </div>
      )}
    </div>
  )
}
