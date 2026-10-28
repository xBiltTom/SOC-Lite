import clsx from 'clsx'
import type { ReactNode } from 'react'
import type { AlertStatus, IncidentPriority, Severity, Verdict } from '../types'
import {
  INCIDENT_PRIORITY_STYLES,
  SEVERITY_LABELS,
  SEVERITY_STYLES,
  STATUS_LABELS,
  STATUS_STYLES,
  VERDICT_LABELS,
  VERDICT_STYLES,
} from '../lib/format'

export function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={clsx('chip', className)}>{children}</span>
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={clsx('chip', SEVERITY_STYLES[severity])}>
      <span className="h-1.5 w-1.5 bg-current" />
      {SEVERITY_LABELS[severity]}
    </span>
  )
}

export function StatusBadge({ status }: { status: AlertStatus }) {
  return <span className={clsx('chip', STATUS_STYLES[status])}>{STATUS_LABELS[status]}</span>
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <span className={clsx('chip', VERDICT_STYLES[verdict])}>{VERDICT_LABELS[verdict]}</span>
}

export function PriorityBadge({ priority }: { priority: IncidentPriority }) {
  return <span className={clsx('chip', INCIDENT_PRIORITY_STYLES[priority])}>{priority}</span>
}

export function Confidence({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden bg-ink/10">
        <div
          className="h-full bg-accent"
          style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }}
        />
      </div>
      <span className="font-mono text-xs text-slate-400">{pct}%</span>
    </div>
  )
}
