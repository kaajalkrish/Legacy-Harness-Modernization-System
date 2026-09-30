import { useEffect, useState } from 'react'

interface Rule {
  rule_id: string
  rule_set: string
  name: string
  category: string
  confidence: string
  requires_sme_review: boolean
  description: string
  condition: { text: string; pattern: string }
  is_duplicated: boolean
  implemented_in_programs: string[]
  primary_source: { program_id: string; paragraph: string; line: number | null }
}

interface Props { outputDir: string }

const CONF_COLOR: Record<string, string> = {
  confirmed: 'var(--color-green)',
  high:      'var(--color-accent)',
  medium:    'var(--color-blue)',
  low:       'var(--color-text-muted)',
}

const CAT_COLOR: Record<string, string> = {
  VALIDATION:  '#3b82f6',
  CALCULATION: '#e8b800',
  LIMIT_CHECK: '#22c55e',
  ROUTING:     '#a78bfa',
}

export default function RulesTab({ outputDir }: Props) {
  const [rules, setRules] = useState<Rule[]>([])
  const [loading, setLoading] = useState(true)
  const [catFilter, setCatFilter] = useState<string>('ALL')
  const [confFilter, setConfFilter] = useState<string>('ALL')
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    fetch(`/api/rules?outputDir=${encodeURIComponent(outputDir)}`)
      .then(r => r.json())
      .then(d => { setRules(d.business_rules || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [outputDir])

  const categories  = ['ALL', ...Array.from(new Set(rules.map(r => r.category)))]
  const confidences = ['ALL', ...Array.from(new Set(rules.map(r => r.confidence)))]

  const filtered = rules.filter(r => {
    if (catFilter  !== 'ALL' && r.category   !== catFilter)  return false
    if (confFilter !== 'ALL' && r.confidence !== confFilter) return false
    if (search && !r.name.toLowerCase().includes(search.toLowerCase()) &&
                  !r.rule_id.toLowerCase().includes(search.toLowerCase()) &&
                  !r.description.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  if (loading) return <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--color-text-muted)' }}>Loading rules…</div>

  return (
    <div>
      <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Rules Explorer</h2>
      <p style={{ margin: '0 0 16px', color: 'var(--color-text-muted)', fontSize: 13 }}>
        {rules.length} business rules extracted from the COBOL source — click any row to expand
      </p>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center' }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search rules…"
          style={{ padding: '6px 12px', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 6, color: 'var(--color-text)', fontSize: 13, width: 200 }}
        />
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {categories.map(c => (
            <button key={c} onClick={() => setCatFilter(c)}
              className={`pill${catFilter === c ? ' active' : ''}`}
              style={{ background: catFilter === c ? (CAT_COLOR[c] || 'var(--color-accent)') : undefined, borderColor: CAT_COLOR[c] || undefined }}
            >{c}</button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {confidences.map(c => (
            <button key={c} onClick={() => setConfFilter(c)}
              className={`pill${confFilter === c ? ' active' : ''}`}
            >{c}</button>
          ))}
        </div>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)', marginLeft: 'auto' }}>
          {filtered.length} of {rules.length} rules
        </span>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: 80 }}>ID</th>
              <th>Name</th>
              <th>Category</th>
              <th>Confidence</th>
              <th>Program</th>
              <th>Paragraph</th>
              <th style={{ width: 40 }}>SME?</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <>
                <tr key={r.rule_id} onClick={() => setExpanded(expanded === r.rule_id ? null : r.rule_id)}
                  style={{ cursor: 'pointer', background: expanded === r.rule_id ? 'var(--color-surface-2)' : undefined }}>
                  <td style={{ fontWeight: 700, color: 'var(--color-accent)', fontFamily: 'monospace', fontSize: 12 }}>{r.rule_id}</td>
                  <td style={{ fontWeight: 500 }}>{r.name}</td>
                  <td>
                    <span style={{ background: `${CAT_COLOR[r.category] || '#555'}22`, color: CAT_COLOR[r.category] || 'var(--color-text)', border: `1px solid ${CAT_COLOR[r.category] || '#555'}44`, padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                      {r.category}
                    </span>
                  </td>
                  <td>
                    <span style={{ color: CONF_COLOR[r.confidence] || 'var(--color-text)', fontWeight: 600, fontSize: 12, textTransform: 'capitalize' }}>
                      {r.confidence}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--color-text-muted)' }}>
                    {r.primary_source?.program_id || (r.implemented_in_programs?.[0] || '—')}
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--color-text-muted)' }}>{r.primary_source?.paragraph || '—'}</td>
                  <td style={{ textAlign: 'center' }}>
                    {r.requires_sme_review && <span style={{ color: 'var(--color-accent)', fontSize: 14 }}>⚑</span>}
                  </td>
                </tr>
                {expanded === r.rule_id && (
                  <tr key={`${r.rule_id}-detail`} style={{ background: 'var(--color-surface-2)' }}>
                    <td colSpan={7} style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, fontSize: 12 }}>
                        <div>
                          <div style={{ color: 'var(--color-text-muted)', fontSize: 10, textTransform: 'uppercase', marginBottom: 4 }}>Description</div>
                          <div style={{ lineHeight: 1.5 }}>{r.description}</div>
                        </div>
                        <div>
                          <div style={{ color: 'var(--color-text-muted)', fontSize: 10, textTransform: 'uppercase', marginBottom: 4 }}>Condition</div>
                          <div style={{ fontFamily: 'monospace', background: 'var(--color-surface)', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--color-border)' }}>
                            {r.condition?.text || '—'}
                          </div>
                          <div style={{ marginTop: 6, color: 'var(--color-text-muted)' }}>Pattern: {r.condition?.pattern || '—'}</div>
                          {r.implemented_in_programs?.length > 1 && (
                            <div style={{ marginTop: 6 }}>Also in: {r.implemented_in_programs.slice(1).join(', ')}</div>
                          )}
                          <div style={{ marginTop: 6, display: 'flex', gap: 8 }}>
                            {r.is_duplicated && <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>⚠ duplicate</span>}
                            {r.requires_sme_review && <span style={{ fontSize: 11, color: 'var(--color-accent)' }}>⚑ needs SME review</span>}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
