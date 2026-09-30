interface Props {
  rulesByCategory:   Record<string, number>
  rulesByConfidence: Record<string, number>
  totalRules:        number
}

function QualityScore(conf: Record<string, number>, total: number): number {
  if (!total) return 0
  const weighted =
    (conf['confirmed'] || 0) * 1.0 +
    (conf['high']      || 0) * 0.9 +
    (conf['medium']    || 0) * 0.5 +
    (conf['low']       || 0) * 0.2
  return Math.round((weighted / total) * 100)
}

const CONF_COLORS: Record<string, string> = {
  confirmed: 'var(--color-green)',
  high:      'var(--color-accent)',
  medium:    'var(--color-blue)',
  low:       'var(--color-text-muted)',
}
const CAT_COLORS: Record<string, string> = {
  VALIDATION:  'var(--color-blue)',
  CALCULATION: 'var(--color-accent)',
  LIMIT_CHECK: 'var(--color-green)',
  ROUTING:     '#a78bfa',
}

export default function SyntheticTestingTab({ rulesByCategory, rulesByConfidence, totalRules }: Props) {
  const score = QualityScore(rulesByConfidence, totalRules)
  const confirmed = rulesByConfidence['confirmed'] || 0
  const high      = rulesByConfidence['high']      || 0
  const needsReview = (rulesByConfidence['medium'] || 0) + (rulesByConfidence['low'] || 0)
  const coveragePct = totalRules ? Math.round((confirmed + high) / totalRules * 100) : 0

  const catTotal = Object.values(rulesByCategory).reduce((a, b) => a + b, 0)
  const confTotal = Object.values(rulesByConfidence).reduce((a, b) => a + b, 0)

  return (
    <div>
      <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Synthetic Testing</h2>
      <p style={{ margin: '0 0 20px', color: 'var(--color-text-muted)', fontSize: 13 }}>
        Business rule coverage analysis — quality gate derived from {totalRules} extracted rules
      </p>

      {/* Quality score hero */}
      <div className="card" style={{ marginBottom: 20, borderColor: score >= 70 ? 'var(--color-green)' : score >= 40 ? 'var(--color-accent)' : 'var(--color-red)', display: 'flex', alignItems: 'center', gap: 32 }}>
        <div style={{ textAlign: 'center', minWidth: 100 }}>
          <div style={{ fontSize: 48, fontWeight: 800, color: score >= 70 ? 'var(--color-green)' : 'var(--color-accent)', lineHeight: 1 }}>{score}</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>QUALITY SCORE</div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ marginBottom: 8, fontSize: 13 }}>
            <strong>{coveragePct}% testable</strong> — {confirmed + high} of {totalRules} rules have confirmed or high-confidence evidence and can be turned into test scenarios.
          </div>
          <div className="progress-bar" style={{ height: 10 }}>
            <div className="progress-bar-fill" style={{ width: `${coveragePct}%`, background: 'var(--color-green)' }} />
          </div>
          <div style={{ display: 'flex', gap: 20, marginTop: 10, fontSize: 12, color: 'var(--color-text-muted)' }}>
            <span style={{ color: 'var(--color-green)' }}>✓ {confirmed} confirmed</span>
            <span style={{ color: 'var(--color-accent)' }}>↑ {high} high</span>
            <span>~ {rulesByConfidence['medium'] || 0} medium</span>
            <span>↓ {rulesByConfidence['low'] || 0} low</span>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, minWidth: 220 }}>
          {[
            { label: 'TOTAL RULES',    val: totalRules,   color: 'var(--color-text)' },
            { label: 'NEEDS REVIEW',   val: needsReview,  color: 'var(--color-accent)' },
            { label: 'TEST-READY',     val: confirmed + high, color: 'var(--color-green)' },
            { label: 'COVERAGE',       val: `${coveragePct}%`, color: 'var(--color-blue)' },
          ].map(t => (
            <div key={t.label} style={{ background: 'var(--color-surface-2)', borderRadius: 8, padding: '10px 12px' }}>
              <div style={{ fontSize: 10, color: 'var(--color-text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 2 }}>{t.label}</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: t.color }}>{t.val}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
        {/* Confidence breakdown */}
        <div className="card">
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 14 }}>Rules by confidence</div>
          {Object.entries(rulesByConfidence).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
            <div key={k} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ textTransform: 'capitalize', color: CONF_COLORS[k] || 'var(--color-text)' }}>{k}</span>
                <span style={{ color: 'var(--color-text-muted)' }}>{v} · {confTotal ? Math.round(v/confTotal*100) : 0}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-bar-fill" style={{ width: `${confTotal ? v/confTotal*100 : 0}%`, background: CONF_COLORS[k] || 'var(--color-blue)' }} />
              </div>
            </div>
          ))}
        </div>

        {/* Category breakdown */}
        <div className="card">
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 14 }}>Rules by category</div>
          {Object.entries(rulesByCategory).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
            <div key={k} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: CAT_COLORS[k] || 'var(--color-text)' }}>{k}</span>
                <span style={{ color: 'var(--color-text-muted)' }}>{v} · {catTotal ? Math.round(v/catTotal*100) : 0}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-bar-fill" style={{ width: `${catTotal ? v/catTotal*100 : 0}%`, background: CAT_COLORS[k] || 'var(--color-blue)' }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Blocking findings callout */}
      {needsReview > 0 && (
        <div style={{ background: 'rgba(234,179,8,0.08)', border: '1px solid rgba(234,179,8,0.25)', borderRadius: 8, padding: '14px 18px', fontSize: 13 }}>
          <strong style={{ color: 'var(--color-accent)' }}>⚠ {needsReview} rules need SME review</strong> before they can be turned into test scenarios.
          These have medium or low confidence — the branch condition is documented but the business meaning needs confirmation.
          Open the <strong>Rules</strong> tab to browse and annotate them.
        </div>
      )}
    </div>
  )
}
