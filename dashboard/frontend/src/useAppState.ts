import { useEffect, useRef, useState } from 'react'
import type { DashboardState } from './types'

function getOutputDir(): string {
  const p = new URLSearchParams(window.location.search)
  return p.get('outputDir') || 'outputs/carddemo'
}

export function useAppState() {
  const [state, setState] = useState<DashboardState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const prevPct = useRef<number | null>(null)
  const outputDir = getOutputDir()

  const fetchState = (initial = false) => {
    if (initial) setLoading(true)
    fetch(`/api/state?outputDir=${encodeURIComponent(outputDir)}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(data => {
        setState(data)
        setLastUpdated(new Date())
        setError(null)
        prevPct.current = data.overall_pct
        if (initial) setLoading(false)
      })
      .catch(e => { setError(e.message); if (initial) setLoading(false) })
  }

  useEffect(() => {
    fetchState(true)
    const id = setInterval(() => fetchState(false), 5000)
    return () => clearInterval(id)
  }, [outputDir])

  return { state, loading, error, outputDir, lastUpdated }
}
