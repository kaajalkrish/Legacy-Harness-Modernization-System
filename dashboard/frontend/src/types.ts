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
  programs:         number
  copybooks:        number
  records:          number
  rules:            number
  diagrams:         number
  artifacts:        number
  scenarios?:        number
  scenarios_passed?: number
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
  topology: { nodes: TopoNode[]; edges: TopoEdge[]; all_nodes_count?: number; all_edges_count?: number }
  rules_by_category: Record<string, number>
  rules_by_confidence: Record<string, number>
}

// ── Phase 11 — Synthetic Test Scenarios ─────────────────────────────────────

export interface DeterminismChecklist {
  actor_defined:               boolean
  inputs_defined:              boolean
  expected_behavior_defined:   boolean
  resulting_state_defined:     boolean
  external_dependencies_defined: boolean
  starting_state_defined:      boolean
  business_rules_defined:      boolean
  failure_behavior_defined:    boolean
  downstream_effects_defined:  boolean
  acceptance_test_ready:       boolean
}

export interface Scenario {
  id:              string
  type:            'happy_path' | 'negative_path' | 'boundary' | 'exception' | 'state_transition' | 'integration'
  status:          'pass' | 'with_gaps' | 'failed'
  rule_id:         string
  rule_set:        string
  name:            string
  confidence:      string
  persona:         string
  requirements:    string[]
  condition:       string
  expected_result: string
  why_generated:   string
  what_it_tests:   string[]
  determinism:     DeterminismChecklist
  programs:        string[]
}

export interface CoverageEntry {
  type:         string
  total:        number
  passed:       number
  achieved_pct: number
  min_pct:      number
  meets_target: boolean
}

export interface Deduction {
  label:   string
  penalty: number
}

export interface BlockingFinding {
  id:       string
  severity: string
  scenario: string
  rule_id:  string
  n:        number
}

export interface ScoreBreakdown {
  starting_score:    number
  final_score:       number
  deductions:        Deduction[]
  blocking_count:    number
  blocking_findings: BlockingFinding[]
  quality_rating:    string
}

export interface SyntestStats {
  total:              number
  passed:             number
  with_gaps:          number
  failed:             number
  by_type:            Record<string, number>
  quality_score:      number
  blocking_findings:  number
}

export interface SyntestData {
  scenarios:       Scenario[]
  coverage:        CoverageEntry[]
  score_breakdown: ScoreBreakdown
  stats:           SyntestStats
  generated_at:    string | null
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
