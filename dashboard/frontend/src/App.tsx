import { useState, useEffect } from 'react'
import { useAppState } from './useAppState'
import Sidebar from './components/Sidebar'
import StatsRow from './components/StatsRow'
import BRDModal from './components/BRDModal'
import PipelineTab from './components/tabs/PipelineTab'
import AgentsTab from './components/tabs/AgentsTab'
import ArtifactsTab from './components/tabs/ArtifactsTab'
import CallTraceTab from './components/tabs/CallTraceTab'
import SyntheticTestingTab from './components/tabs/SyntheticTestingTab'
import TimelineTab from './components/tabs/TimelineTab'
import WorkflowTab from './components/tabs/WorkflowTab'
import RulesTab from './components/tabs/RulesTab'
import StateTab from './components/tabs/StateTab'

const TABS = [
  { id: 'pipeline',  label: 'Pipeline' },
  { id: 'agents',    label: 'Agentic Workflow' },
  { id: 'artifacts', label: 'Artifacts' },
  { id: 'rules',     label: 'Rules' },
  { id: 'syntest',   label: 'Synthetic Testing' },
  { id: 'timeline',  label: 'Timeline' },
  { id: 'workflow',  label: 'Interactive Workflow' },
  { id: 'calltrace', label: 'Call Trace' },
  { id: 'state',     label: 'State' },
]

export default function App() {
  const { state, loading, error, outputDir, lastUpdated } = useAppState()
  const [activeTab, setActiveTab] = useState('pipeline')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [showBRD, setShowBRD] = useState(false)
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try { return (localStorage.getItem('theme') as 'dark' | 'light') || 'light' }
    catch { return 'light' }
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try { localStorage.setItem('theme', theme) } catch {}
  }, [theme])

  function exportJson() {
    window.open(`/api/state?outputDir=${encodeURIComponent(outputDir)}`)
  }

  function exportPdf() {
    window.print()
  }

  const meta    = state?.meta
  const verdict = state?.verdict
  const truncate = (s: string, n = 38) => s && s.length > n ? '…' + s.slice(-n) : s

  // Fix #3 — derive verdict badge for header
  const verdictBadge = verdict?.verdict && verdict.verdict !== '—'
    ? verdict.verdict
    : null

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--color-text-muted)', fontSize: 15 }}>
      Loading artifacts…
    </div>
  )

  if (error) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--color-red)', fontSize: 15 }}>
      Error: {error}. Is the FastAPI server running?
    </div>
  )

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {showBRD && <BRDModal outputDir={outputDir} onClose={() => setShowBRD(false)} />}
      {/* Sidebar */}
      <Sidebar
        phases={state?.phases || []}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(o => !o)}
      />

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

        {/* Header */}
        <div style={{ background: 'var(--color-surface)', borderBottom: '1px solid var(--color-border)', borderTop: '3px solid var(--color-accent)' }}>
          <div style={{ padding: '14px 24px 0' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: 'var(--color-text)', letterSpacing: '-0.5px' }}>
                  COBOL Reverse Engineering
                </h1>
                {/* Fix #3 — live status + judge verdict side-by-side in header */}
                <span className="badge badge-done" style={{ fontSize: 11 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-green)', display: 'inline-block' }} />
                  live · {meta?.status || 'complete'}
                </span>
                {verdictBadge && (
                  <span
                    className={`badge ${verdictBadge === 'PASS' ? 'badge-pass' : 'badge-revise'}`}
                    style={{ fontSize: 11, fontWeight: 800 }}
                    title={`BRD Judge: ${verdictBadge} · Score ${verdict?.weighted_score?.toFixed(2)}/5.0`}
                  >
                    {verdictBadge === 'PASS' ? '✓' : '⚠'} BRD {verdictBadge}
                  </span>
                )}
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 3 }}>
                Legacy Modernisation Intelligence Platform
                {lastUpdated && <span style={{ marginLeft: 10, opacity: 0.7 }}>· updated {lastUpdated.toLocaleTimeString()}</span>}
              </div>
            </div>
            <div className="header-actions" style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0, marginLeft: 16 }}>
              <button
                onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
                style={{ padding: '5px 12px', border: '1px solid var(--color-border)', borderRadius: 6, background: 'var(--color-surface-2)', color: 'var(--color-text)', cursor: 'pointer', fontSize: 12 }}
              >
                {theme === 'dark' ? '☀ Light' : '☾ Dark'}
              </button>
              <button
                onClick={() => setShowBRD(true)}
                style={{ padding: '4px 12px', border: '1px solid var(--color-border)', borderRadius: 6, background: 'var(--color-surface-2)', color: 'var(--color-text)', cursor: 'pointer', fontSize: 12 }}
              >
                View BRD
              </button>
              <button
                onClick={exportJson}
                style={{ padding: '4px 12px', border: '1px solid var(--color-border)', borderRadius: 6, background: 'var(--color-surface-2)', color: 'var(--color-text)', cursor: 'pointer', fontSize: 12 }}
              >
                Export JSON
              </button>
              <button
                onClick={exportPdf}
                style={{ padding: '4px 14px', border: 'none', borderRadius: 6, background: 'var(--color-accent)', color: '#111', cursor: 'pointer', fontSize: 12, fontWeight: 700 }}
              >
                Export PDF
              </button>
            </div>
          </div>

          {/* Meta strip */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 14 }}>
            {[
              { label: 'SOURCE ROOT',      val: truncate(meta?.project_dir || '—'),                               icon: '📁' },
              { label: 'OUTPUT DIRECTORY', val: truncate(meta?.output_dir || '—'),                                icon: '📂' },
              { label: 'FILES SCANNED',    val: meta?.files_scanned != null ? String(meta.files_scanned) : '—',   icon: '🔍' },
              { label: 'BRD NAME',         val: meta?.brd_name || '—',                                            icon: '📄' },
            ].map(({ label, val, icon }) => (
              <div key={label} style={{
                padding: '8px 12px', borderRadius: 8,
                background: 'var(--color-surface-2)',
                border: '1px solid var(--color-border)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3 }}>
                  <span style={{ fontSize: 11 }}>{icon}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>{label}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--color-text)', wordBreak: 'break-all', fontFamily: 'monospace' }}>{val}</div>
              </div>
            ))}
          </div>

          {/* Stats row */}
          {state && <StatsRow stats={state.stats} overallPct={state.overall_pct} phases={state.phases} />}

          {/* Tab bar */}
          <div className="tab-bar" style={{ marginTop: 12 }}>
            {TABS.map(t => (
              <button
                key={t.id}
                className={`tab-btn${activeTab === t.id ? ' active' : ''}`}
                onClick={() => setActiveTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          </div>
        </div>

        {/* Tab content */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
          {activeTab === 'pipeline'  && <PipelineTab phases={state?.phases || []} overallPct={state?.overall_pct || 0} verdict={state?.verdict} />}
          {activeTab === 'agents'    && <AgentsTab phases={state?.phases || []} />}
          {activeTab === 'artifacts' && <ArtifactsTab outputDir={outputDir} />}
          {activeTab === 'calltrace' && <CallTraceTab outputDir={outputDir} />}
          {activeTab === 'syntest'   && <SyntheticTestingTab outputDir={outputDir} />}
          {activeTab === 'workflow'  && <WorkflowTab topology={state?.topology} />}
          {activeTab === 'timeline'  && <TimelineTab timeline={state?.timeline || []} />}
          {activeTab === 'rules'     && <RulesTab outputDir={outputDir} />}
          {activeTab === 'state'     && <StateTab state={state} />}
        </div>
      </div>
    </div>
  )
}
