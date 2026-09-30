import type { Scenario, DeterminismChecklist } from '../types'

interface Props {
  scenario: Scenario
  onClose: () => void
}

const TYPE_LABELS: Record<string, string> = {
  happy_path:       'Happy Path',
  negative_path:    'Negative Path',
  boundary:         'Boundary',
  exception:        'Exception',
  state_transition: 'State Transition',
  integration:      'Integration',
}

const TYPE_COLORS: Record<string, string> = {
  happy_path:       'var(--color-green)',
  negative_path:    'var(--color-red)',
  boundary:         'var(--color-blue)',
  exception:        'var(--color-orange)',
  state_transition: '#a78bfa',
  integration:      'var(--color-accent)',
}

const CHECKLIST_LABELS: Array<[keyof DeterminismChecklist, string]> = [
  ['actor_defined',               'actor defined'],
  ['starting_state_defined',      'starting state defined'],
  ['inputs_defined',              'required inputs defined'],
  ['business_rules_defined',      'business rules defined'],
  ['expected_behavior_defined',   'expected behavior defined'],
  ['failure_behavior_defined',    'failure behavior defined'],
  ['resulting_state_defined',     'resulting state defined'],
  ['downstream_effects_defined',  'downstream effects defined'],
  ['external_dependencies_defined','external dependencies defined'],
  ['acceptance_test_ready',       'acceptance test ready'],
]

export default function ScenarioModal({ scenario: s, onClose }: Props) {
  const color  = TYPE_COLORS[s.type] || 'var(--color-text-muted)'
  const label  = TYPE_LABELS[s.type] || s.type
  const passed = Object.values(s.determinism).filter(Boolean).length
  const total  = Object.values(s.determinism).length

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--color-surface)',
          border: `1px solid ${color}`,
          borderLeft: `4px solid ${color}`,
          borderRadius: 10,
          width: '100%', maxWidth: 680,
          maxHeight: '90vh', overflowY: 'auto',
          padding: 28,
          position: 'relative',
        }}
      >
        {/* Close */}
        <button
          onClick={onClose}
          style={{ position: 'absolute', top: 14, right: 16, background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', fontSize: 20, lineHeight: 1 }}
        >×</button>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
          <span className={`badge badge-${s.status === 'pass' ? 'pass' : 'pending'}`} style={{ fontSize: 11, fontWeight: 700 }}>
            {s.status === 'pass' ? '✓ PASS' : '~ WITH GAPS'}
          </span>
          <span style={{ fontWeight: 800, fontSize: 17, color: 'var(--color-text)' }}>{s.id}</span>
          <span style={{ background: `${color}22`, color, border: `1px solid ${color}44`, padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600 }}>
            {label}
          </span>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)', background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', padding: '2px 10px', borderRadius: 99 }}>
            {s.persona}
          </span>
          {s.determinism.acceptance_test_ready && (
            <span className="badge badge-done" style={{ fontSize: 11 }}>✓ Test-ready</span>
          )}
        </div>

        {/* Requirements */}
        {s.requirements.length > 0 && (
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 6 }}>Requirements</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {s.requirements.map(r => (
                <span key={r} style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-blue)', color: 'var(--color-blue)', padding: '3px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600 }}>
                  {r}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Condition */}
        <Section title="Condition (Given / When / Then)">
          <div style={{ fontWeight: 500, lineHeight: 1.6, fontSize: 13 }}>{s.condition}</div>
        </Section>

        {/* Expected Result */}
        <Section title="Expected Result">
          <div style={{ fontWeight: 500, lineHeight: 1.6, fontSize: 13 }}>{s.expected_result}</div>
        </Section>

        {/* Why Generated */}
        <Section title="Why Generated">
          <div style={{ lineHeight: 1.6, fontSize: 13, color: 'var(--color-text-muted)' }}>{s.why_generated}</div>
        </Section>

        {/* What it tests */}
        {s.what_it_tests.length > 0 && (
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 8 }}>What it tests</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {s.what_it_tests.map(tag => (
                <span key={tag} style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', color: 'var(--color-text)', padding: '3px 10px', borderRadius: 6, fontSize: 12 }}>
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Determinism checklist */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 10 }}>
            Determinism Checklist — {passed}/{total}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 24px' }}>
            {CHECKLIST_LABELS.map(([key, label]) => {
              const ok = s.determinism[key]
              return (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <span style={{
                    width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
                    background: ok ? 'var(--color-green)' : 'var(--color-border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, color: ok ? '#111' : 'var(--color-text-muted)',
                    fontWeight: 800,
                  }}>
                    {ok ? '✓' : '–'}
                  </span>
                  <span style={{ color: ok ? 'var(--color-text)' : 'var(--color-text-muted)' }}>{label}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Programs */}
        {s.programs.length > 0 && (
          <div style={{ marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--color-border)' }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 6 }}>Programs</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {s.programs.map(p => (
                <span key={p} style={{ fontFamily: 'monospace', fontSize: 11, background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', padding: '2px 8px', borderRadius: 4 }}>
                  {p}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: 6 }}>{title}</div>
      <div style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 6, padding: '10px 14px' }}>
        {children}
      </div>
    </div>
  )
}
