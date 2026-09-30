import { useEffect, useRef, useState } from 'react'
import { marked } from 'marked'

interface Props {
  outputDir: string
  onClose: () => void
}

marked.setOptions({ gfm: true, breaks: false })

const BRD_CSS = `
.brd-body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.75; color: var(--color-text); }
.brd-body h1 { font-size: 24px; font-weight: 800; margin: 0 0 16px; padding-bottom: 10px; border-bottom: 2px solid var(--color-accent); color: var(--color-accent); }
.brd-body h2 { font-size: 18px; font-weight: 700; margin: 32px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--color-border); }
.brd-body h3 { font-size: 15px; font-weight: 700; margin: 20px 0 8px; }
.brd-body h4 { font-size: 12px; font-weight: 700; margin: 14px 0 6px; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.brd-body p  { margin: 0 0 12px; }
.brd-body ul, .brd-body ol { margin: 0 0 12px; padding-left: 22px; }
.brd-body li { margin-bottom: 4px; }
.brd-body blockquote { margin: 14px 0; padding: 10px 18px; background: rgba(232,184,0,0.07); border-left: 3px solid var(--color-accent); border-radius: 0 6px 6px 0; color: var(--color-text-muted); font-size: 13px; }
.brd-body blockquote strong { color: var(--color-accent); }
.brd-body code { background: var(--color-surface-2); padding: 2px 6px; border-radius: 4px; font-family: 'Fira Mono', monospace; font-size: 12px; }
.brd-body pre  { background: var(--color-surface-2); border: 1px solid var(--color-border); border-radius: 8px; padding: 14px 16px; overflow-x: auto; margin: 12px 0; }
.brd-body pre code { background: none; padding: 0; font-size: 12px; }
.brd-body hr   { border: none; border-top: 1px solid var(--color-border); margin: 28px 0; }
.brd-body strong { font-weight: 700; }
.brd-body em { font-style: italic; }
.brd-body a  { color: var(--color-accent); text-decoration: none; }
.brd-body table { width: 100%; border-collapse: collapse; margin: 12px 0 20px; font-size: 13px; }
.brd-body th  { background: var(--color-surface-2); padding: 8px 12px; text-align: left; font-weight: 700; border: 1px solid var(--color-border); color: var(--color-text-muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; white-space: nowrap; }
.brd-body td  { padding: 8px 12px; border: 1px solid var(--color-border); vertical-align: top; }
.brd-body tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
.brd-mermaid  { overflow-x: auto; margin: 16px 0; background: var(--color-surface-2); border: 1px solid var(--color-border); border-radius: 8px; padding: 20px 16px; text-align: center; }
.brd-mermaid svg { max-width: 100%; height: auto; }
.brd-mermaid-pending { color: var(--color-text-muted); font-size: 12px; padding: 20px; text-align: center; background: var(--color-surface-2); border: 1px dashed var(--color-border); border-radius: 8px; margin: 16px 0; }
`

interface TocEntry { id: string; text: string; level: number }

export default function BRDModal({ outputDir, onClose }: Props) {
  const [html, setHtml]         = useState<string | null>(null)
  const [rawMd, setRawMd]       = useState('')
  const [sizeKb, setSizeKb]     = useState(0)
  const [name, setName]         = useState('brd.md')
  const [loading, setLoading]   = useState(true)
  const [diagStatus, setDiagStatus] = useState('')
  const [toc, setToc]           = useState<TocEntry[]>([])
  const [activeId, setActiveId] = useState('')
  const contentRef = useRef<HTMLDivElement>(null)
  const scrollRef  = useRef<HTMLDivElement>(null)

  // Fetch and parse BRD
  useEffect(() => {
    fetch(`/api/brd?outputDir=${encodeURIComponent(outputDir)}`)
      .then(r => r.json())
      .then(d => {
        setRawMd(d.content)
        setSizeKb(d.size_kb)
        setName(d.name)
        setHtml(typeof marked.parse(d.content) === 'string'
          ? marked.parse(d.content) as string
          : '')
        setLoading(false)
      })
      .catch(() => { setHtml('<p>Could not load BRD.</p>'); setLoading(false) })
  }, [outputDir])

  // Build TOC from headings after HTML is injected
  useEffect(() => {
    if (!html || !contentRef.current) return
    const entries: TocEntry[] = []
    contentRef.current.querySelectorAll('h1,h2,h3').forEach((el, i) => {
      const level = parseInt(el.tagName[1])
      const text  = el.textContent || ''
      const id    = `brd-h-${i}`
      el.id = id
      entries.push({ id, text, level })
    })
    setToc(entries)
    if (entries.length) setActiveId(entries[0].id)
  }, [html])

  // Track active heading on scroll
  useEffect(() => {
    const scroller = scrollRef.current
    if (!scroller || !toc.length) return
    const handler = () => {
      for (let i = toc.length - 1; i >= 0; i--) {
        const el = document.getElementById(toc[i].id)
        if (el && el.getBoundingClientRect().top <= 120) {
          setActiveId(toc[i].id)
          return
        }
      }
      setActiveId(toc[0]?.id || '')
    }
    scroller.addEventListener('scroll', handler, { passive: true })
    return () => scroller.removeEventListener('scroll', handler)
  }, [toc])

  // Render Mermaid diagrams after HTML is injected into the DOM
  useEffect(() => {
    if (!html || !contentRef.current) return

    const blocks = Array.from(
      contentRef.current.querySelectorAll('pre code.language-mermaid, code.language-mermaid')
    )
    if (!blocks.length) return

    setDiagStatus(`Rendering ${blocks.length} diagrams…`)

    import('mermaid').then(m => {
      const isDark = document.documentElement.getAttribute('data-theme') !== 'light'
      m.default.initialize({
        startOnLoad: false,
        theme: isDark ? 'dark' : 'default',
        securityLevel: 'loose',
        flowchart: { useMaxWidth: true, curve: 'basis' },
        er: { useMaxWidth: true },
      })

      let done = 0
      blocks.forEach(async (block, i) => {
        const container = block.closest('pre') || block.parentElement
        if (!container) return
        const diagram = (block.textContent || '').trim()
        if (!diagram) return

        // Show a placeholder while rendering
        const placeholder = document.createElement('div')
        placeholder.className = 'brd-mermaid-pending'
        placeholder.textContent = `Rendering diagram ${i + 1}…`
        container.replaceWith(placeholder)

        try {
          const id = `brd-diag-${Date.now()}-${i}`
          const { svg } = await m.default.render(id, diagram)
          const wrapper = document.createElement('div')
          wrapper.className = 'brd-mermaid'
          wrapper.innerHTML = svg
          placeholder.replaceWith(wrapper)
        } catch {
          placeholder.textContent = `⚠ Diagram ${i + 1} could not be rendered`
        }
        done++
        if (done === blocks.length) setDiagStatus(`${blocks.length} diagrams rendered`)
      })
    })
  }, [html])

  function download() {
    const b = new Blob([rawMd], { type: 'text/markdown' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(b)
    a.download = name
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.82)', zIndex: 1000, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '24px 16px', overflowY: 'auto' }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <style>{BRD_CSS}</style>
      <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, width: '100%', maxWidth: 980, display: 'flex', flexDirection: 'column', maxHeight: 'calc(100vh - 48px)' }}>

        {/* Sticky header */}
        <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0, background: 'var(--color-surface)', borderRadius: '12px 12px 0 0' }}>
          <div>
            <div style={{ fontWeight: 800, fontSize: 16 }}>Business Requirements Document</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>
              {sizeKb > 0 ? `${sizeKb} KB · ` : ''}{name}
              {diagStatus && <span style={{ marginLeft: 10, color: 'var(--color-accent)' }}>· {diagStatus}</span>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={download}
              style={{ padding: '6px 14px', border: '1px solid var(--color-border)', borderRadius: 6, background: 'var(--color-surface-2)', color: 'var(--color-text)', cursor: 'pointer', fontSize: 12 }}>
              Download .md
            </button>
            <button onClick={onClose}
              style={{ padding: '6px 14px', border: 'none', borderRadius: 6, background: 'var(--color-accent)', color: '#111', cursor: 'pointer', fontSize: 12, fontWeight: 700 }}>
              Close
            </button>
          </div>
        </div>

        {/* Body: TOC sidebar + scrollable content */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

          {/* TOC sidebar */}
          {toc.length > 0 && (
            <div style={{ width: 220, flexShrink: 0, borderRight: '1px solid var(--color-border)', overflowY: 'auto', padding: '16px 0' }}>
              <div style={{ padding: '0 14px 10px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--color-text-muted)' }}>Contents</div>
              {toc.map(entry => (
                <button
                  key={entry.id}
                  onClick={() => {
                    document.getElementById(entry.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                    setActiveId(entry.id)
                  }}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer',
                    padding: `5px 14px 5px ${entry.level === 1 ? 14 : entry.level === 2 ? 22 : 30}px`,
                    fontSize: entry.level === 1 ? 13 : 12,
                    fontWeight: entry.level === 1 ? 700 : 400,
                    color: activeId === entry.id ? 'var(--color-accent)' : 'var(--color-text-muted)',
                    borderLeft: activeId === entry.id ? '2px solid var(--color-accent)' : '2px solid transparent',
                    lineHeight: 1.4,
                    transition: 'color 0.15s',
                  }}
                >
                  {entry.text}
                </button>
              ))}
            </div>
          )}

          {/* Main content */}
          <div ref={scrollRef} style={{ overflowY: 'auto', padding: '28px 36px', flex: 1 }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '80px 0', color: 'var(--color-text-muted)' }}>Loading BRD…</div>
            ) : (
              <div
                ref={contentRef}
                className="brd-body"
                dangerouslySetInnerHTML={{ __html: html || '' }}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
