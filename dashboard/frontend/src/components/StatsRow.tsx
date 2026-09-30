import type { Stats, PhaseDef } from '../types'

interface Props {
  stats: Stats
  overallPct: number
  phases: PhaseDef[]
}

export default function StatsRow({ stats, overallPct, phases }: Props) {
  const done = phases.filter(p => p.status === 'done').length
  const total = phases.length

  const tiles = [
    { label: 'OVERALL',   value: `${overallPct}%`,                  sub: `${done}/${total} phases done` },
    { label: 'PROGRAMS',  value: stats.programs.toLocaleString(),    sub: 'reachable' },
    { label: 'COPYBOOKS', value: stats.copybooks.toLocaleString(),   sub: 'expanded' },
    { label: 'RECORDS',   value: stats.records.toLocaleString(),     sub: 'in dictionary' },
    { label: 'RULES',     value: stats.rules.toLocaleString(),       sub: 'catalogued' },
    { label: 'ARTIFACTS', value: stats.artifacts.toLocaleString(),   sub: 'produced' },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10, marginBottom: 4 }}>
      {tiles.map(t => (
        <div key={t.label} className="kpi-tile">
          <div className="kpi-label">{t.label}</div>
          <div className="kpi-value">{t.value}</div>
          <div className="kpi-sub">{t.sub}</div>
        </div>
      ))}
    </div>
  )
}
