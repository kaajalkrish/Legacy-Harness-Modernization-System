import { useEffect, useState } from 'react'
import type { CallTraceData, CallTraceEntry } from '../../types'

interface Props { outputDir: string }

const KIND_STYLE: Record<string, { bg: string; color: string }> = {
  control_flow:  { bg: 'rgba(59,130,246,0.15)',  color: 'var(--color-blue)' },
  program_call:  { bg: 'rgba(59,130,246,0.2)',   color: '#60a5fa' },
  database:      { bg: 'rgba(34,197,94,0.15)',   color: 'var(--color-green)' },
}

export default function CallTraceTab({ outputDir }: Props) {
  const [data, setData] = useState<CallTraceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [program, setProgram] = useState<string>('all')
  const [category, setCategory] = useState<string>('all')

  useEffect(() => {
    const prog = program === 'all' ? '' : program
    fetch(`/api/call-trace?outputDir=${encodeURIComponent(outputDir)}${prog ? `&program=${prog}` : ''}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [outputDir, program])

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 0', gap: 16 }}>
      <div style={{ width: 36, height: 36, border: '3px solid var(--color-border)', borderTopColor: 'var(--color-accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <div style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Reading control-flow graph for all programs…</div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
  if (!data) return <div style={{ color: 'var(--color-red)', padding: 24 }}>Failed to load call trace.</div>

  const entries: CallTraceEntry[] = category === 'all'
    ? data.entries
    : data.entries.filter(e => e.category === category)

  const counts = data.counts

  return (
    <div>
      <h2 style={{ margin: '0 0 6px', fontSize: 18, fontWeight: 700 }}>Call trace</h2>
      <p style={{ margin: '0 0 14px', color: 'var(--color-text-muted)', fontSize: 13, maxWidth: 800 }}>
        A source-ordered record of every operation each program performs: internal routines it runs, programs it calls, and database requests it issues.
      </p>

      {/* Info box */}
      <div style={{ borderLeft: '3px solid var(--color-accent)', paddingLeft: 14, marginBottom: 16, fontSize: 12, color: 'var(--color-text-muted)' }}>
        <div><strong style={{ color: 'var(--color-text)' }}>How to read it</strong></div>
        <div>PERFORM, CALL, and SQL return here after the step finishes.</div>
        <div>GO TO moves control away and does not come back to this point.</div>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 20, marginBottom: 14, fontSize: 13, color: 'var(--color-text-muted)' }}>
        <span><strong style={{ color: 'var(--color-text)' }}>{counts.total}</strong> operations</span>
        <span><strong style={{ color: 'var(--color-text)' }}>{counts.returns_here}</strong> return here</span>
        <span><strong style={{ color: 'var(--color-text)' }}>{counts.no_return}</strong> do not return</span>
      </div>

      {/* Program selector */}
      {data.programs.length > 1 && (
        <div style={{ marginBottom: 12 }}>
          <select
            value={program}
            onChange={e => { setProgram(e.target.value); setLoading(true) }}
            style={{ padding: '5px 10px', border: '1px solid var(--color-border)', borderRadius: 6, background: 'var(--color-surface-2)', color: 'var(--color-text)', fontSize: 13 }}
          >
            <option value="all">All programs ({data.programs.length})</option>
            {data.programs.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      )}

      {/* Filter pills */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {[
          { key: 'all',          label: `All ${counts.total}`,              extra: '' },
          { key: 'control_flow', label: `Control flow ${counts.control_flow}`, extra: 'blue' },
          { key: 'program_call', label: `Program call ${counts.program_call}`,  extra: 'blue' },
          { key: 'database',     label: `Database ${counts.database}`,          extra: 'green' },
        ].map(({ key, label, extra }) => (
          <button
            key={key}
            className={`pill${category === key ? ' active' : ''}${extra ? ` ${extra}` : ''}`}
            onClick={() => setCategory(key)}
          >
            {category !== key && extra && (
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: extra === 'green' ? 'var(--color-green)' : 'var(--color-blue)', display: 'inline-block', marginRight: 5 }} />
            )}
            {label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', maxHeight: 'calc(100vh - 380px)', overflowY: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Step</th>
              <th>Program</th>
              <th>Source line</th>
              <th>In paragraph</th>
              <th>Kind</th>
              <th>Operation</th>
              <th>Target</th>
              <th>Returns?</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(e => {
              const style = KIND_STYLE[e.category] || KIND_STYLE.control_flow
              return (
                <tr key={`${e.program}-${e.step}`}>
                  <td style={{ color: 'var(--color-text-muted)', fontWeight: 600 }}>{e.step}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{e.program}</td>
                  <td style={{ color: 'var(--color-text-muted)' }}>{e.source_line}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{e.from_para}</td>
                  <td>
                    <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, background: style.bg, color: style.color }}>
                      {e.kind}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--color-accent)' }}>{e.operation}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{e.to_target}</td>
                  <td style={{ fontSize: 11 }}>
                    {e.returns
                      ? <span style={{ color: 'var(--color-green)' }}>Returns here</span>
                      : <span style={{ color: 'var(--color-orange)' }}>Moves away</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
