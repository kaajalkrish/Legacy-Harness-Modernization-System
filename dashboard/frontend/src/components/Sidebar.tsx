import type { PhaseDef } from '../types'

interface Props {
  phases: PhaseDef[]
  open: boolean
  onToggle: () => void
}

export default function Sidebar({ phases, open, onToggle }: Props) {
  return (
    <div className={`sidebar${open ? '' : ' collapsed'}`}>
      {/* Logo */}
      <div style={{ padding: '16px 14px 12px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8, background: 'var(--color-accent)', color: '#111',
          fontWeight: 800, fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
        }}>RE</div>
        {open && (
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--color-text)' }}>Harness Pipeline</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Reverse Engineering</div>
          </div>
        )}
        <button
          onClick={onToggle}
          style={{
            marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--color-text-muted)', fontSize: 16, padding: 4, flexShrink: 0,
            transform: open ? 'none' : 'rotate(180deg)', transition: 'transform 0.2s'
          }}
          title={open ? 'Collapse sidebar' : 'Expand sidebar'}
        >‹</button>
      </div>

      {/* Phase list */}
      <div style={{ flex: 1, overflow: 'auto', padding: '12px 0' }}>
        {open && (
          <div style={{ padding: '4px 14px 10px', fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>
            Pipeline · {phases.length} Phases
          </div>
        )}
        {phases.map(phase => (
          <div
            key={phase.id}
            style={{ padding: open ? '8px 14px' : '8px 13px', display: 'flex', alignItems: 'center', gap: 10 }}
          >
            <div className={`phase-circle${phase.status === 'done' ? '' : ' pending'}`}>
              {phase.num}
            </div>
            {open && (
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {phase.name}
                  </span>
                  <span className={`badge ${phase.status === 'done' ? 'badge-done' : 'badge-pending'}`} style={{ flexShrink: 0 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: phase.status === 'done' ? 'var(--color-green)' : 'var(--color-text-muted)', display: 'inline-block' }} />
                    {phase.status}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 1 }}>{phase.agent}</div>
                <div className="progress-bar" style={{ marginTop: 5 }}>
                  <div className="progress-bar-fill" style={{ width: phase.status === 'done' ? '100%' : '0%', background: phase.status === 'done' ? 'var(--color-green)' : 'var(--color-border)' }} />
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
