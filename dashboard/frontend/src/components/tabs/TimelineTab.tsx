import type { TimelineEntry } from '../../types'

interface Props { timeline: TimelineEntry[] }

function fmtTs(ts: string | null): string {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString() } catch { return ts }
}

export default function TimelineTab({ timeline }: Props) {
  return (
    <div style={{ maxWidth: 860 }}>
      <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Timeline</h2>
      <p style={{ margin: '0 0 24px', color: 'var(--color-text-muted)', fontSize: 13 }}>
        Pipeline events as agents progress through the {timeline.length} phases.
      </p>

      <div style={{ position: 'relative' }}>
        {/* Vertical line */}
        <div style={{ position: 'absolute', left: 9, top: 8, bottom: 8, width: 2, background: 'var(--color-border)' }} />

        {timeline.map((entry, i) => (
          <div key={entry.phase_id} style={{ display: 'flex', gap: 20, marginBottom: 28, position: 'relative' }}>
            {/* Dot */}
            <div style={{
              width: 20, height: 20, borderRadius: '50%', flexShrink: 0, marginTop: 2,
              background: entry.status === 'done' ? 'var(--color-green)' : 'var(--color-border)',
              border: '2px solid var(--color-bg)', zIndex: 1, position: 'relative',
            }} />

            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace', marginBottom: 4 }}>
                {fmtTs(entry.generated_at)}
              </div>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 3 }}>
                Phase {entry.phase_num}: {entry.phase_name} completed successfully
                {entry.duration_fmt && entry.duration_fmt !== '—' && (
                  <span style={{ fontWeight: 400, color: 'var(--color-text-muted)', fontSize: 13 }}>
                    {' '}in {entry.duration_fmt}
                  </span>
                )}
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                Produced{' '}
                <span style={{ fontFamily: 'monospace', color: 'var(--color-text)' }}>{entry.artifact}</span>
                {entry.artifact_kb > 0 && <span> ({entry.artifact_kb} KB)</span>}
              </div>
            </div>
          </div>
        ))}
      </div>

      {timeline.length === 0 && (
        <div style={{ color: 'var(--color-text-muted)', padding: '40px 0', textAlign: 'center' }}>
          No timeline data available. Run the pipeline to populate timestamps.
        </div>
      )}
    </div>
  )
}
