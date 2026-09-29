import { useEffect, useState } from 'react'
import type { DashboardState } from './types'

function getOutputDir(): string {
  const p = new URLSearchParams(window.location.search)
  return p.get('outputDir') || 'outputs/carddemo'
}

export function useAppState() {
  const [state, setState] = useState<DashboardState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const outputDir = getOutputDir()

  useEffect(() => {
    setLoading(true)
    fetch(`/api/state?outputDir=${encodeURIComponent(outputDir)}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(data => { setState(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [outputDir])

  return { state, loading, error, outputDir }
}
