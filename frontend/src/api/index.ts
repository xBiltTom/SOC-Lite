import { api } from './client'
import type {
  AlertDetail,
  AlertListItem,
  AuditEntry,
  ChainVerify,
  DashboardSummary,
  FpPoint,
  Incident,
  MtttRow,
  Page,
  Report,
  ReportFormat,
  ReportType,
  SeveritySlice,
  SlaRow,
  TopSource,
  TrendPoint,
  Triage,
  User,
} from '../types'

// ---------------------------------------------------------------------------
// Autenticación
// ---------------------------------------------------------------------------
export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

export const authApi = {
  login: (username: string, password: string) =>
    api.post<LoginResponse>('/auth/login', { username, password }).then((r) => r.data),
  me: () => api.get<User>('/auth/me').then((r) => r.data),
  logout: () => api.post('/auth/logout', {}).then((r) => r.data),
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------
export const dashboardApi = {
  summary: (days: number) =>
    api.get<DashboardSummary>('/dashboard/summary', { params: { days } }).then((r) => r.data),
  trend: (days: number) =>
    api.get<TrendPoint[]>('/dashboard/trend', { params: { days } }).then((r) => r.data),
  severity: (days: number) =>
    api
      .get<{ items: SeveritySlice[]; total: number }>('/dashboard/severity', { params: { days } })
      .then((r) => r.data.items),
  topSources: (days: number, by = 'ip') =>
    api
      .get<TopSource[]>('/dashboard/top-sources', { params: { days, by, limit: 8 } })
      .then((r) => r.data),
  mttt: (days: number) => api.get<MtttRow[]>('/dashboard/mttt', { params: { days } }).then((r) => r.data),
  sla: (days: number) => api.get<SlaRow[]>('/dashboard/sla', { params: { days } }).then((r) => r.data),
  fpRate: (days: number) =>
    api.get<FpPoint[]>('/dashboard/fp-rate', { params: { days } }).then((r) => r.data),
}

// ---------------------------------------------------------------------------
// Alertas
// ---------------------------------------------------------------------------
export interface AlertFilters {
  page?: number
  size?: number
  severity?: string
  status?: string
  source?: string
  q?: string
  date_from?: string
  date_to?: string
  sort?: string
}

export const alertsApi = {
  list: (filters: AlertFilters) =>
    api.get<Page<AlertListItem>>('/alerts', { params: filters }).then((r) => r.data),
  get: (id: string) => api.get<AlertDetail>(`/alerts/${id}`).then((r) => r.data),
  triage: (id: string, force = false) =>
    api.post<Triage>(`/alerts/${id}/triage`, null, { params: { force } }).then((r) => r.data),
  feedback: (id: string, isFalsePositive: boolean, comment?: string) =>
    api
      .post(`/alerts/${id}/feedback`, { is_false_positive: isFalsePositive, comment })
      .then((r) => r.data),
  createIncident: (id: string, payload: { title?: string; priority?: string }) =>
    api.post<Incident>(`/alerts/${id}/incident`, payload).then((r) => r.data),
  update: (id: string, payload: { status?: string; tags?: string[]; asset_criticality?: number }) =>
    api.patch<AlertDetail>(`/alerts/${id}`, payload).then((r) => r.data),
}

// ---------------------------------------------------------------------------
// Incidentes
// ---------------------------------------------------------------------------
export const incidentsApi = {
  get: (id: string) => api.get<Incident>(`/incidents/${id}`).then((r) => r.data),
  assignees: () => api.get<{ id: string; username: string; full_name: string }[]>('/incidents/assignees').then((r) => r.data),
  list: (params: {
    page?: number
    size?: number
    status?: string
    priority?: string
    q?: string
  }) => api.get<Page<Incident>>('/incidents', { params }).then((r) => r.data),
  update: (
    id: string,
    payload: { status?: string; priority?: string; resolution?: string; assignee_id?: string },
  ) => api.patch<Incident>(`/incidents/${id}`, payload).then((r) => r.data),
}

// ---------------------------------------------------------------------------
// Usuarios y roles
// ---------------------------------------------------------------------------
export const usersApi = {
  list: (params: { page?: number; size?: number; q?: string; role?: string; is_active?: boolean }) =>
    api.get<Page<User>>('/users', { params }).then((r) => r.data),
  create: (payload: {
    username: string
    email: string
    full_name: string
    password: string
    role_id: number
    is_active: boolean
  }) => api.post<User>('/users', payload).then((r) => r.data),
  update: (
    id: string,
    payload: { email?: string; full_name?: string; role_id?: number; is_active?: boolean },
  ) => api.patch<User>(`/users/${id}`, payload).then((r) => r.data),
  deactivate: (id: string) => api.delete(`/users/${id}`).then((r) => r.data),
  resetPassword: (id: string, newPassword: string) =>
    api.post(`/users/${id}/reset-password`, { new_password: newPassword }).then((r) => r.data),
}

export const rolesApi = {
  list: () => api.get<import('../types').Role[]>('/roles').then((r) => r.data),
  permissions: () =>
    api.get<import('../types').Permission[]>('/permissions').then((r) => r.data),
  updatePermissions: (roleId: number, codes: string[]) =>
    api.put(`/roles/${roleId}/permissions`, { permission_codes: codes }).then((r) => r.data),
}

// ---------------------------------------------------------------------------
// Auditoría
// ---------------------------------------------------------------------------
export interface AuditFilters {
  page?: number
  size?: number
  module?: string
  action?: string
  username?: string
  result?: string
  q?: string
  date_from?: string
  date_to?: string
}

export const auditApi = {
  list: (params: AuditFilters) =>
    api.get<Page<AuditEntry>>('/audit', { params }).then((r) => r.data),
  modules: () =>
    api.get<{ module: string; total: number }[]>('/audit/modules').then((r) => r.data),
  verify: () => api.get<ChainVerify>('/audit/verify-chain').then((r) => r.data),
  export: (params: AuditFilters, format: 'csv' | 'xlsx') =>
    api
      .get('/audit/export', { params: { ...params, format }, responseType: 'blob' })
      .then((r) => r.data as Blob),
}

// ---------------------------------------------------------------------------
// Reportes
// ---------------------------------------------------------------------------
export const reportsApi = {
  types: () =>
    api
      .get<{ type: ReportType; name: string; description: string }[]>('/reports/types')
      .then((r) => r.data),
  create: (payload: {
    type: ReportType
    format: ReportFormat
    date_from?: string
    date_to?: string
    title?: string
  }) => api.post<Report>('/reports', payload).then((r) => r.data),
  list: (params: { page?: number; size?: number }) =>
    api.get<Page<Report>>('/reports', { params }).then((r) => r.data),
  download: (id: string) =>
    api.get(`/reports/${id}/download`, { responseType: 'blob' }).then((r) => r.data as Blob),
}
