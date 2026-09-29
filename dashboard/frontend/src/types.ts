export interface PhaseDef {
  id: string
  num: number
  name: string
  type: 'Deterministic' | 'LLM + Python'
  agent: string
  module: string
  status: 'done' | 'pending' | 'running'
  artifact: string
  artifact_kb: number
  generated_at: string | null
  duration_sec: number | null
  duration_fmt: string
}

export interface Stats {
  programs: number
  copybooks: number
  records: number
  rules: number
  diagrams: number
  artifacts: number
}

export interface Verdict {
  verdict: string
  rating: string
  weighted_score: number | null
  dimensions: Record<string, { score: number; rationale: string }>
  feedback: Array<{ dimension: string; severity: string; suggestion: string }>
  groundedness_failures: string[]
}

export interface TimelineEntry {
  phase_id: string
  phase_name: string
  phase_num: number
  status: string
  generated_at: string | null
  duration_sec: number | null
  duration_fmt: string
  artifact: string
  artifact_kb: number
}

export interface TopoNode {
  id: string
  type: string
  [key: string]: unknown
}

export interface TopoEdge {
  from: string
  to: string
  type: string
  [key: string]: unknown
}

export interface DashboardState {
  meta: {
    project: string
    domain: string
    entry_point: string
    project_dir: string
    output_dir: string
    brd_name: string
    status: string
    updated: string
  }
  stats: Stats
  overall_pct: number
  phases: PhaseDef[]
  timeline: TimelineEntry[]
  verdict: Verdict
  topology: { nodes: TopoNode[]; edges: TopoEdge[] }
  rules_by_category: Record<string, number>
  rules_by_confidence: Record<string, number>
}

export interface ArtifactEntry {
  name: string
  path: string
  phase: string
  size_kb: number
  ext: string
}

export interface CallTraceEntry {
  step: number
  program: string
  source_line: number
  from_para: string
  to_target: string
  kind: string
  category: 'control_flow' | 'program_call' | 'database'
  operation: string
  returns: boolean
  resolved: boolean
  unstructured: boolean
}

export interface CallTraceData {
  programs: string[]
  counts: {
    total: number
    control_flow: number
    program_call: number
    database: number
    returns_here: number
    no_return: number
  }
  entries: CallTraceEntry[]
}
