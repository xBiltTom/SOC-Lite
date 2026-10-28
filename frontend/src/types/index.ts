export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type AlertStatus =
  | 'pending'
  | 'triaging'
  | 'triaged'
  | 'in_review'
  | 'escalated'
  | 'closed'
  | 'false_positive'
  | 'discarded'
export type Verdict = 'true_positive' | 'false_positive' | 'suspicious' | 'benign' | 'inconclusive'
export type IncidentStatus = 'open' | 'investigating' | 'contained' | 'resolved' | 'closed'
export type IncidentPriority = 'P1' | 'P2' | 'P3' | 'P4'
export type ReportType = 'operational' | 'management' | 'audit'
export type ReportFormat = 'pdf' | 'docx' | 'xlsx'
export type AuditResult = 'success' | 'failure' | 'denied'

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface Permission {
  id: number
  code: string
  module: string
  action: string
  description?: string | null
}

export interface Role {
  id: number
  code: string
  name: string
  description?: string | null
  is_system?: boolean
  permissions: Permission[]
  user_count: number
}

export interface User {
  id: string
  username: string
  email: string
  full_name: string
  role: { id: number; code: string; name: string }
  is_active: boolean
  mfa_enabled: boolean
  last_login_at: string | null
  created_at: string
  permissions: string[]
}

export interface Triage {
  id: string
  verdict: Verdict
  severity: Severity
  confidence: number
  summary: string
  reasoning: string | null
  recommended_actions: { action: string; priority: number; owner: string }[]
  mitre_techniques: string[]
  model: string | null
  prompt_version: string | null
  latency_ms: number | null
  status: 'completed' | 'degraded' | 'failed' | 'pending'
  needs_human: boolean
  fallback_used: boolean
  triaged_at: string
}

export interface Enrichment {
  id: number
  provider: string
  indicator: string
  indicator_type: string
  verdict: string | null
  score: number | null
  country: string | null
  asn: string | null
  raw: Record<string, unknown>
  fetched_at: string
}

export interface Feedback {
  id: number
  user_id: string | null
  is_false_positive: boolean
  comment: string | null
  created_at: string
}

export interface Incident {
  id: string
  alert_id: string | null
  ticket_id: string | null
  title: string
  description: string | null
  status: IncidentStatus
  priority: IncidentPriority
  assignee_id: string | null
  assignee_name: string | null
  alert_severity: Severity | null
  alert_description: string | null
  sla_due_at: string | null
  opened_at: string
  closed_at: string | null
  resolution: string | null
  created_at: string
}

export interface AlertListItem {
  id: string
  external_id: string | null
  source: string
  rule_id: string | null
  rule_level: number | null
  description: string
  src_ip: string | null
  dst_ip: string | null
  agent_name: string | null
  asset_criticality: number
  severity: Severity
  status: AlertStatus
  received_at: string
  occurred_at: string
  dedup_count: number
  verdict: Verdict | null
  confidence: number | null
  summary: string | null
  triaged_at: string | null
  mttt_minutes: number | null
  incident_id: string | null
  ticket_id: string | null
}

export interface AlertDetail extends AlertListItem {
  src_port: number | null
  dst_port: number | null
  protocol: string | null
  fingerprint: string
  raw_payload: Record<string, unknown>
  tags: string[]
  last_seen_at: string
  created_at: string
  triage_results: Triage[]
  enrichments: Enrichment[]
  feedback: Feedback[]
  incident: Incident | null
}

export interface DashboardSummary {
  period: { days: number; date_from: string; date_to: string }
  totals: {
    alerts: number
    critical: number
    high: number
    medium: number
    low: number
    info: number
    triaged: number
    pending: number
    incidents_open: number
    false_positive: number
  }
  rates: { automation: number; false_positive: number; sla_compliance: number; human_review: number }
  mttt: { avg_minutes: number; p95_minutes: number; target_minutes: number }
  deltas: { alerts_pct: number; mttt_pct: number }
  generated_at: string
}

export interface TrendPoint {
  date: string
  total: number
  critical: number
  high: number
  medium: number
  low: number
  false_positive: number
}

export interface SeveritySlice {
  severity: Severity
  count: number
}

export interface TopSource {
  key: string
  label: string
  count: number
  critical: number
}

export interface MtttRow {
  severity: Severity
  count: number
  avg_minutes: number
  p95_minutes: number
  target_minutes: number
  compliance: number
}

export interface SlaRow {
  severity: Severity
  target_minutes: number
  total: number
  within_sla: number
  compliance: number
  breaches: number
}

export interface FpPoint {
  date: string
  triaged: number
  false_positive: number
  rate: number
}

export interface AnalystRow {
  username: string
  full_name: string
  actions: number
  triages: number
}

export interface AuditEntry {
  id: number
  occurred_at: string
  user_id: string | null
  username: string | null
  module: string
  action: string
  entity_type: string | null
  entity_id: string | null
  result: AuditResult
  detail: Record<string, unknown>
  ip: string | null
  user_agent: string | null
  request_id: string | null
  duration_ms: number | null
  hash: string | null
}

export interface Report {
  id: string
  type: ReportType
  format: ReportFormat
  status: 'queued' | 'generating' | 'ready' | 'failed'
  params: Record<string, unknown>
  file_size: number | null
  requested_by: string | null
  created_at: string
  completed_at: string | null
  error: string | null
}

export interface ChainVerify {
  valid: boolean
  checked: number
  broken_at: number | null
  message: string
}
