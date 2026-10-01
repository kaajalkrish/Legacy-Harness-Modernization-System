import { useEffect, useRef, useState, useMemo } from 'react'
import type { TopoNode, TopoEdge } from '../../types'

interface Props {
  topology?: { nodes: TopoNode[]; edges: TopoEdge[]; all_nodes_count?: number; all_edges_count?: number }
}

function buildMermaid(nodes: TopoNode[], edges: TopoEdge[]): string {
  const lines = ['flowchart LR']
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
    const from  = String(e.from).replace(/[^a-zA-Z0-9_]/g, '_')
    const to    = String(e.to).replace(/[^a-zA-Z0-9_]/g, '_')
    const typ   = String(e.type || '').toLowerCase()
    const arrow = typ.includes('copy') ? '-.->|copy|' : typ.includes('call') ? '-->|call|' : '-->'
    lines.push(`  ${from} ${arrow} ${to}`)
  }
  return lines.join('\n')
}

function filterForProgram(
  nodes: TopoNode[], edges: TopoEdge[], program: string
): { nodes: TopoNode[]; edges: TopoEdge[] } {
  if (program === 'ALL') return { nodes, edges }
  const connected = new Set<string>([program])
  edges.forEach(e => {
    if (String(e.from) === program) connected.add(String(e.to))
    if (String(e.to)   === program) connected.add(String(e.from))
  })
  return {
    nodes: nodes.filter(n => connected.has(String(n.id))),
    edges: edges.filter(e => connected.has(String(e.from)) && connected.has(String(e.to))),
  }
}

export default function WorkflowTab({ topology }: Props) {
  const ref             = useRef<HTMLDivElement>(null)
  const lastDiagramRef  = useRef<string>('')   // tracks last actually-rendered diagram
  const lastThemeRef    = useRef<string>('')   // tracks last rendered theme
  const [error, setError]           = useState<string | null>(null)
  const [selected, setSelected]     = useState<TopoNode | null>(null)
  const [theme, setTheme]           = useState(() => document.documentElement.getAttribute('data-theme') || 'dark')
  const [program, setProgram]       = useState('ALL')

  // Watch theme changes only — not every poll
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme(document.documentElement.getAttribute('data-theme') || 'dark')
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  // Sorted program list for the dropdown
  const programNames = useMemo(() => {
    if (!topology) return []
    return [...topology.nodes]
      .map(n => String(n.id))
      .sort()
  }, [topology?.nodes.length]) // only recompute if node count changes

  // Filtered view
  const view = useMemo(() => {
    if (!topology) return { nodes: [], edges: [] }
    return filterForProgram(topology.nodes, topology.edges, program)
  }, [topology?.nodes.length, topology?.edges.length, program])

  // Render Mermaid — ONLY if diagram content or theme actually changed
  useEffect(() => {
    if (!view.nodes.length || !ref.current) return

    const diagram = buildMermaid(view.nodes, view.edges)

    // Skip if nothing changed — prevents re-render on every 5s poll
    if (diagram === lastDiagramRef.current && theme === lastThemeRef.current) return

    lastDiagramRef.current = diagram
    lastThemeRef.current   = theme

    import('mermaid').then(m => {
      m.default.initialize({
        startOnLoad: false,
        theme: theme === 'light' ? 'default' : 'dark',
        flowchart: { curve: 'basis', useMaxWidth: true },
        securityLevel: 'loose',
      })
      // Use a unique id so Mermaid doesn't reuse a stale cached element
      const svgId = `workflow-svg-${Date.now()}`
      m.default.render(svgId, diagram).then(({ svg }) => {
        if (ref.current) {
          ref.current.innerHTML = svg
          ref.current.querySelectorAll('.node').forEach(el => {
            (el as HTMLElement).style.cursor = 'pointer'
            el.addEventListener('click', () => {
              const label = el.querySelector('span,text')?.textContent?.trim() || ''
              const node  = view.nodes.find(n =>
                String(n.id) === label ||
                String(n.id).replace(/[^a-zA-Z0-9_]/g, '_') === label.replace(/[^a-zA-Z0-9_]/g, '_')
              )
              if (node) setSelected(node)
            })
          })
        }
      }).catch(e => setError(String(e)))
    }).catch(e => setError('Could not load Mermaid: ' + String(e)))
  }, [view, theme])

  if (!topology || !topology.nodes.length) {
    return <div style={{ color: 'var(--color-text-muted)', padding: '40px 0', textAlign: 'center' }}>No topology data available.</div>
  }

  return (
    <div>
      {/* Header + controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
        <div>
          <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Interactive Workflow</h2>
          <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: 13 }}>
            {program === 'ALL'
              ? `Full call graph — ${topology.nodes.length} programs · ${topology.edges.length} edges`
              : `${program} — ${view.nodes.length} programs · ${view.edges.length} edges (direct connections only)`
            }
            {topology.all_nodes_count && topology.all_nodes_count > topology.nodes.length
              ? ` · filtered from ${topology.all_nodes_count} total`
              : ''}
            . Click a node for details.
          </p>
        </div>

        {/* Program filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <label style={{ fontSize: 12, color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
            Show program:
          </label>
          <select
            value={program}
            onChange={e => { setProgram(e.target.value); setSelected(null) }}
            style={{
              padding: '5px 10px', borderRadius: 6, fontSize: 12,
              background: 'var(--color-surface-2)', border: '1px solid var(--color-border)',
              color: 'var(--color-text)', cursor: 'pointer', maxWidth: 200,
            }}
          >
            <option value="ALL">All programs</option>
            {programNames.map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          {program !== 'ALL' && (
            <button
              onClick={() => { setProgram('ALL'); setSelected(null) }}
              style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
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
            {/* Quick filter to this program */}
            {program !== String(selected.id) && (
              <button
                onClick={() => setProgram(String(selected.id))}
                style={{ width: '100%', marginBottom: 12, padding: '5px 0', borderRadius: 6, fontSize: 11, cursor: 'pointer', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-accent)', fontWeight: 600 }}
              >
                Show only this program's connections
              </button>
            )}
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
