import { useState } from 'react'
import type { DashboardState } from '../../types'

interface Props { state: DashboardState | null }

export default function StateTab({ state }: Props) {
  const [copied, setCopied] = useState(false)
  const json = JSON.stringify(state, null, 2)

  function copy() {
    navigator.clipboard.writeText(json).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div style={{ maxWidth: 960 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Raw state</h2>
          <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: 13 }}>
            Snapshot of the in-memory data model backing this dashboard.
          </p>
        </div>
        <button
          onClick={copy}
          style={{ padding: '6px 14px', border: '1px solid var(--color-border)', borderRadius: 6, background: 'var(--color-surface-2)', color: 'var(--color-text)', cursor: 'pointer', fontSize: 12 }}
        >
          {copied ? '✓ Copied' : 'Copy JSON'}
        </button>
      </div>
      <pre style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 8,
        padding: 16,
        fontSize: 11.5,
        lineHeight: 1.6,
        overflow: 'auto',
        maxHeight: 'calc(100vh - 280px)',
        color: 'var(--color-text)',
        fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
      }}>
        {json}
      </pre>
    </div>
  )
}
