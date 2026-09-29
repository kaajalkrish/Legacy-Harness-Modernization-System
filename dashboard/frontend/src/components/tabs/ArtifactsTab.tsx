import { useEffect, useState } from 'react'
import type { ArtifactEntry } from '../../types'

interface Props { outputDir: string }

const EXT_COLORS: Record<string, string> = {
  '.json': 'var(--color-blue)',
  '.md':   'var(--color-green)',
  '.mmd':  'var(--color-accent)',
  '.txt':  'var(--color-text-muted)',
}

export default function ArtifactsTab({ outputDir }: Props) {
  const [artifacts, setArtifacts] = useState<ArtifactEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('All')
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetch(`/api/artifacts?outputDir=${encodeURIComponent(outputDir)}`)
      .then(r => r.json())
      .then(d => { setArtifacts(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [outputDir])

  const phases = ['All', ...Array.from(new Set(artifacts.map(a => a.phase))).sort()]
  const shown = artifacts.filter(a => {
    if (filter !== 'All' && a.phase !== filter) return false
    if (search && !a.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const totalSize = shown.reduce((s, a) => s + a.size_kb, 0)

  if (loading) return <div style={{ color: 'var(--color-text-muted)' }}>Loading artifacts…</div>

  return (
    <div style={{ maxWidth: 960 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Artifacts</h2>
        <div style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>
          {shown.length} files · {totalSize.toFixed(0)} KB total
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          placeholder="Search by name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ padding: '5px 12px', border: '1px solid var(--color-border)', borderRadius: 6, background: 'var(--color-surface-2)', color: 'var(--color-text)', fontSize: 13, width: 200 }}
        />
        {phases.map(ph => (
          <button key={ph} className={`pill${filter === ph ? ' active' : ''}`} onClick={() => setFilter(ph)}>
            {ph}
          </button>
        ))}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>File</th>
              <th>Phase</th>
              <th>Type</th>
              <th>Size (KB)</th>
              <th>Path</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(a => (
              <tr key={a.path}>
                <td style={{ fontWeight: 600 }}>{a.name}</td>
                <td><span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{a.phase}</span></td>
                <td>
                  <span style={{ fontSize: 11, fontWeight: 700, color: EXT_COLORS[a.ext] || 'var(--color-text-muted)' }}>
                    {a.ext.replace('.', '').toUpperCase()}
                  </span>
                </td>
                <td style={{ color: 'var(--color-text-muted)' }}>{a.size_kb.toFixed(1)}</td>
                <td style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--color-text-muted)' }}>{a.path}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
