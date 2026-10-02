import type { Stats, PhaseDef } from '../types'

interface Props {
  stats: Stats
  overallPct: number
  phases: PhaseDef[]
}

export default function StatsRow({ stats, overallPct, phases }: Props) {
  const done = phases.filter(p => p.status === 'done').length
  const total = phases.length

  const scenarioTile = stats.scenarios != null
    ? { label: 'SCENARIOS', value: stats.scenarios.toLocaleString(), sub: `${stats.scenarios_passed ?? 0} passed` }
    : { label: 'ARTIFACTS', value: stats.artifacts.toLocaleString(), sub: 'produced' }

  const tiles = [
    { label: 'OVERALL',   value: `${overallPct}%`,                  sub: `${done}/${total} phases done`,  accent: 'var(--color-accent)' },
    { label: 'PROGRAMS',  value: stats.programs.toLocaleString(),    sub: 'reachable',                     accent: 'var(--color-blue)'   },
    { label: 'COPYBOOKS', value: stats.copybooks.toLocaleString(),   sub: 'expanded',                      accent: '#a78bfa'             },
    { label: 'RECORDS',   value: stats.records.toLocaleString(),     sub: 'in dictionary',                 accent: 'var(--color-green)'  },
    { label: 'RULES',     value: stats.rules.toLocaleString(),       sub: 'catalogued',                    accent: 'var(--color-orange)' },
    { ...scenarioTile,                                                                                       accent: 'var(--color-red)'    },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10, marginBottom: 4 }}>
      {tiles.map(t => (
        <div key={t.label} className="kpi-tile" style={{ borderTop: `3px solid ${t.accent}` }}>
          <div className="kpi-label">{t.label}</div>
          <div className="kpi-value" style={{ color: t.accent }}>{t.value}</div>
          <div className="kpi-sub">{t.sub}</div>
        </div>
      ))}
    </div>
  )
}
