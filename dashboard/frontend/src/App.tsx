import { useState, useEffect } from 'react'
import { useAppState } from './useAppState'
import Sidebar from './components/Sidebar'
import StatsRow from './components/StatsRow'
import PipelineTab from './components/tabs/PipelineTab'
import AgentsTab from './components/tabs/AgentsTab'
import ArtifactsTab from './components/tabs/ArtifactsTab'
import CallTraceTab from './components/tabs/CallTraceTab'
import TimelineTab from './components/tabs/TimelineTab'
import WorkflowTab from './components/tabs/WorkflowTab'
import StateTab from './components/tabs/StateTab'
import StubTab from './components/tabs/StubTab'

const TABS = [
  { id: 'pipeline',   label: 'Pipeline' },
  { id: 'agents',     label: 'Agents' },
  { id: 'artifacts',  label: 'Artifacts' },
  { id: 'calltrace',  label: 'Call Trace' },
  { id: 'syntest',    label: 'Synthetic Testing' },
  { id: 'workflow',   label: 'Interactive Workflow' },
  { id: 'timeline',   label: 'Timeline' },
  { id: 'conversation', label: 'Conversation' },
  { id: 'state',      label: 'State' },
]

export default function App() {
  const { state, loading, error, outputDir } = useAppState()
  const [activeTab, setActiveTab] = useState('pipeline')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try { return (localStorage.getItem('theme') as 'dark' | 'light') || 'dark' }
    catch { return 'dark' }
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

  const meta = state?.meta
  const truncate = (s: string, n = 38) => s && s.length > n ? '…' + s.slice(-n) : s

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
      {/* Sidebar */}
      <Sidebar
        phases={state?.phases || []}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(o => !o)}
      />

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

        {/* Header */}
        <div style={{ padding: '16px 24px 0', background: 'var(--color-surface)', borderBottom: '1px solid var(--color-border)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: 'var(--color-text)' }}>
              Mainframe-Source COBOL Reverse Engineering
            </h1>
            <div className="header-actions" style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0, marginLeft: 16 }}>
              <span className="badge badge-done" style={{ fontSize: 12 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--color-green)', display: 'inline-block' }} />
                live · {meta?.status || 'complete'}
              </span>
              <button
                onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
                style={{ padding: '4px 12px', border: '1px solid var(--color-border)', borderRadius: 6, background: 'var(--color-surface-2)', color: 'var(--color-text)', cursor: 'pointer', fontSize: 12 }}
              >
                {theme === 'dark' ? 'Light theme' : 'Dark theme'}
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
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 14 }}>
            {[
              ['PROJECT DIRECTORY', truncate(meta?.project_dir || meta?.output_dir || '—')],
              ['ENTRY POINT',       truncate(meta?.entry_point || '—')],
              ['OUTPUT DIRECTORY',  truncate(meta?.output_dir || '—')],
              ['BRD NAME',          meta?.brd_name || '—'],
            ].map(([label, val]) => (
              <div key={label}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 2 }}>{label}</div>
                <div style={{ fontSize: 12, color: 'var(--color-text)', wordBreak: 'break-all' }}>{val}</div>
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

        {/* Tab content */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
          {activeTab === 'pipeline'      && <PipelineTab phases={state?.phases || []} overallPct={state?.overall_pct || 0} verdict={state?.verdict} />}
          {activeTab === 'agents'        && <AgentsTab phases={state?.phases || []} />}
          {activeTab === 'artifacts'     && <ArtifactsTab outputDir={outputDir} />}
          {activeTab === 'calltrace'     && <CallTraceTab outputDir={outputDir} />}
          {activeTab === 'syntest'       && <StubTab title="Synthetic Testing" description="Automated Given/When/Then scenario generation and coverage scoring against business rules will appear here once Phase 11 (Synthetic Testing) is added to the pipeline." />}
          {activeTab === 'workflow'      && <WorkflowTab topology={state?.topology} />}
          {activeTab === 'timeline'      && <TimelineTab timeline={state?.timeline || []} />}
          {activeTab === 'conversation'  && <StubTab title="Conversation & Feedback" description="SME feedback submissions and their pipeline corrections will appear here. The feedback-loop mechanism is planned for v2." />}
          {activeTab === 'state'         && <StateTab state={state} />}
        </div>
      </div>
    </div>
  )
}
