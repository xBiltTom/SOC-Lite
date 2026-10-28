import { format, formatDistanceToNowStrict, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'
import type { AlertStatus, IncidentPriority, IncidentStatus, Severity, Verdict } from '../types'

export const SEVERITY_LABELS: Record<Severity, string> = {
  critical: 'Crítica',
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
  info: 'Info',
}

export const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low', 'info']

export const SEVERITY_STYLES: Record<Severity, string> = {
  critical: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
  high: 'border-orange-500/40 bg-orange-500/10 text-orange-300',
  medium: 'border-yellow-500/40 bg-yellow-500/10 text-yellow-200',
  low: 'border-sky-500/40 bg-sky-500/10 text-sky-300',
  info: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
}

export const SEVERITY_HEX: Record<Severity, string> = {
  critical: 'var(--chart-critical)',
  high: '#d77c38',
  medium: 'var(--chart-warning)',
  low: '#299ac2',
  info: '#8b9cad',
}

export const STATUS_LABELS: Record<AlertStatus, string> = {
  pending: 'Pendiente',
  triaging: 'En triaje',
  triage_failed: 'Error de triaje',
  triaged: 'Triada',
  in_review: 'En revisión',
  escalated: 'Escalada',
  closed: 'Cerrada',
  false_positive: 'Falso positivo',
  discarded: 'Descartada',
}

export const STATUS_STYLES: Record<AlertStatus, string> = {
  pending: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
  triaging: 'border-cyan-500/40 bg-cyan-500/10 text-cyan-300',
  triage_failed: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
  triaged: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  in_review: 'border-indigo-500/40 bg-indigo-500/10 text-indigo-300',
  escalated: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
  closed: 'border-slate-500/30 bg-slate-500/5 text-slate-400',
  false_positive: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  discarded: 'border-slate-600/40 bg-slate-700/20 text-slate-500',
}

export const VERDICT_LABELS: Record<Verdict, string> = {
  true_positive: 'Verdadero positivo',
  false_positive: 'Falso positivo',
  suspicious: 'Sospechoso',
  benign: 'Benigno',
  inconclusive: 'Inconcluso',
}

export const VERDICT_STYLES: Record<Verdict, string> = {
  true_positive: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
  false_positive: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  suspicious: 'border-orange-500/40 bg-orange-500/10 text-orange-300',
  benign: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  inconclusive: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
}

export const INCIDENT_STATUS_LABELS: Record<IncidentStatus, string> = {
  open: 'Abierto',
  investigating: 'En investigación',
  contained: 'Contenido',
  resolved: 'Resuelto',
  closed: 'Cerrado',
}

export const INCIDENT_PRIORITY_STYLES: Record<IncidentPriority, string> = {
  P1: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
  P2: 'border-orange-500/40 bg-orange-500/10 text-orange-300',
  P3: 'border-yellow-500/40 bg-yellow-500/10 text-yellow-200',
  P4: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
}

export function formatDate(value?: string | null): string {
  if (!value) return '—'
  try {
    return format(parseISO(value), 'dd MMM yyyy, HH:mm', { locale: es })
  } catch {
    return value
  }
}

export function formatShortDate(value?: string | null): string {
  if (!value) return '—'
  try {
    return format(parseISO(value), 'dd MMM', { locale: es })
  } catch {
    return value
  }
}

export function relativeTime(value?: string | null): string {
  if (!value) return '—'
  try {
    return formatDistanceToNowStrict(parseISO(value), { addSuffix: true, locale: es })
  } catch {
    return value
  }
}

export function formatMinutes(value?: number | null): string {
  if (value === null || value === undefined) return '—'
  if (value < 1) return '< 1 min'
  if (value < 60) return `${value.toFixed(1)} min`
  const hours = Math.floor(value / 60)
  const minutes = Math.round(value % 60)
  return `${hours} h ${minutes} min`
}

export function formatNumber(value?: number | null): string {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('es-PE').format(value)
}

export function formatBytes(value?: number | null): string {
  if (!value) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(2)} MB`
}

export function initials(name?: string | null): string {
  if (!name) return 'SL'
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

export function truncate(value: string, max = 120): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}
