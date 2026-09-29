import { useEffect, useRef, useState } from 'react'
import type { TopoNode, TopoEdge } from '../../types'

interface Props {
  topology?: { nodes: TopoNode[]; edges: TopoEdge[] }
}

function buildMermaid(nodes: TopoNode[], edges: TopoEdge[]): string {
  const lines = ['flowchart LR']

  // Dedupe nodes
  const seen = new Set<string>()
  for (const n of nodes) {
    const id = String(n.id).replace(/[^a-zA-Z0-9_]/g, '_')
    if (seen.has(id)) continue
    seen.add(id)
    const label = String(n.id)
    const typ = String(n.type || 'program').toLowerCase()
    if (typ.includes('copy')) {
      lines.push(`  ${id}([${label}])`)
    } else if (typ.includes('db') || typ.includes('sql')) {
      lines.push(`  ${id}[(${label})]`)
    } else {
      lines.push(`  ${id}[${label}]`)
    }
  }

  for (const e of edges) {
    const from = String(e.from).replace(/[^a-zA-Z0-9_]/g, '_')
    const to   = String(e.to).replace(/[^a-zA-Z0-9_]/g, '_')
    const typ  = String(e.type || '').toLowerCase()
    const arrow = typ.includes('copy') ? '-.->|copy|' : typ.includes('call') ? '-->|call|' : '-->'
    lines.push(`  ${from} ${arrow} ${to}`)
  }

  return lines.join('\n')
}

export default function WorkflowTab({ topology }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<TopoNode | null>(null)

  useEffect(() => {
    if (!topology || !ref.current) return
    const { nodes, edges } = topology
    if (!nodes.length) return

    import('mermaid').then(m => {
      m.default.initialize({
        startOnLoad: false,
        theme: document.documentElement.getAttribute('data-theme') === 'light' ? 'default' : 'dark',
        flowchart: { curve: 'basis', useMaxWidth: true },
        securityLevel: 'loose',
      })
      const diagram = buildMermaid(nodes, edges)
      m.default.render('workflow-svg', diagram).then(({ svg }) => {
        if (ref.current) {
          ref.current.innerHTML = svg
          // Click handler on nodes
          ref.current.querySelectorAll('.node').forEach((el) => {
            (el as HTMLElement).style.cursor = 'pointer'
            el.addEventListener('click', () => {
              const label = el.querySelector('span,text')?.textContent?.trim() || ''
              const node = nodes.find(n => String(n.id) === label || String(n.id).replace(/[^a-zA-Z0-9_]/g, '_') === label.replace(/[^a-zA-Z0-9_]/g, '_'))
              if (node) setSelected(node)
            })
          })
        }
      }).catch(e => setError(String(e)))
    }).catch(e => setError('Could not load Mermaid: ' + String(e)))
  }, [topology])

  if (!topology || !topology.nodes.length) {
    return <div style={{ color: 'var(--color-text-muted)', padding: '40px 0', textAlign: 'center' }}>No topology data available.</div>
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Interactive Workflow</h2>
          <p style={{ margin: '0 0 16px', color: 'var(--color-text-muted)', fontSize: 13 }}>
            System dependency graph — {topology.nodes.length} nodes · {topology.edges.length} edges. Click a node for details.
          </p>
          {error && <div style={{ color: 'var(--color-red)', marginBottom: 12, fontSize: 13 }}>{error}</div>}
          <div
            ref={ref}
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, padding: 16, overflow: 'auto', minHeight: 300 }}
          />
        </div>

        {/* Side panel */}
        {selected && (
          <div className="card" style={{ width: 260, flexShrink: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{String(selected.id)}</div>
              <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', fontSize: 16 }}>×</button>
            </div>
            {Object.entries(selected).filter(([k]) => k !== 'id').map(([k, v]) => (
              <div key={k} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', marginBottom: 2 }}>{k}</div>
                <div style={{ fontSize: 12, wordBreak: 'break-all' }}>{String(v)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
