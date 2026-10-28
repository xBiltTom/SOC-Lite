import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { ChevronLeft, ChevronRight, Inbox, Loader2, X, type LucideIcon } from 'lucide-react'
import clsx from 'clsx'
import { formatNumber } from '../lib/format'

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = 'accent',
  delta,
  invertDelta = false,
}: {
  label: string
  value: string
  hint?: string
  icon: LucideIcon
  tone?: 'accent' | 'rose' | 'amber' | 'emerald' | 'violet'
  delta?: number | null
  invertDelta?: boolean
}) {
  const tones = {
    accent: 'text-accent bg-accent/10 border-accent/20',
    rose: 'text-rose-300 bg-rose-500/10 border-rose-500/20',
    amber: 'text-amber-300 bg-amber-500/10 border-amber-500/20',
    emerald: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20',
    violet: 'text-violet-300 bg-violet-500/10 border-violet-500/20',
  }
  const positive = delta !== undefined && delta !== null && delta > 0
  const good = invertDelta ? positive : !positive
  return (
    <div className="card card-hover relative overflow-hidden p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
          <p className="kpi-value mt-5">{value}</p>
          {hint && <p className="mt-1 truncate text-xs text-slate-500">{hint}</p>}
        </div>
        <div className={clsx('border p-2', tones[tone])}>
          <Icon size={18} />
        </div>
      </div>
      {delta !== undefined && delta !== null && (
        <p className={clsx('mt-4 border-t border-base-700 pt-3 text-[11px] font-medium', good ? 'text-emerald-400' : 'text-rose-400')}>
          {delta > 0 ? '▲' : delta < 0 ? '▼' : '■'} {Math.abs(delta).toFixed(1)}% vs. periodo anterior
        </p>
      )}
    </div>
  )
}

export function Spinner({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-slate-400">
      <Loader2 size={18} className="animate-spin text-accent" />
      {label}
    </div>
  )
}

export function EmptyState({
  title = 'Sin resultados',
  description,
  icon: Icon = Inbox,
  action,
}: {
  title?: string
  description?: string
  icon?: LucideIcon
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <div className="border border-base-700 bg-ink/5 p-3 text-slate-500">
        <Icon size={22} />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-300">{title}</p>
        {description && <p className="mt-1 max-w-sm text-xs text-slate-500">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function Pagination({
  page,
  pages,
  total,
  onPage,
}: {
  page: number
  pages: number
  total: number
  onPage: (page: number) => void
}) {
  const window = 5
  const start = Math.max(1, Math.min(page - Math.floor(window / 2), pages - window + 1))
  const numbers = Array.from({ length: Math.min(window, pages) }, (_, index) => start + index)
  return (
    <div className="flex flex-col items-center justify-between gap-3 border-t border-base-700 px-4 py-3 sm:flex-row">
      <p className="text-xs text-slate-500">
        {formatNumber(total)} registros · página {page} de {Math.max(pages, 1)}
      </p>
      <div className="flex items-center gap-1">
        <button
          className="btn-ghost h-8 w-8 !p-0"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          aria-label="Página anterior"
        >
          <ChevronLeft size={16} />
        </button>
        {numbers.map((number) => (
          <button
            key={number}
            onClick={() => onPage(number)}
            className={clsx(
              'h-8 min-w-8 px-2 font-mono text-xs transition',
              number === page
                ? 'bg-accent text-base-950'
                : 'text-slate-400 hover:bg-ink/5 hover:text-slate-200',
            )}
          >
            {number}
          </button>
        ))}
        <button
          className="btn-ghost h-8 w-8 !p-0"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
          aria-label="Página siguiente"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  width = 'max-w-lg',
}: {
  open: boolean
  onClose: () => void
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  width?: string
}) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  useEffect(() => {
    if (!open) return
    const previousFocus = document.activeElement as HTMLElement | null
    const controls = () => dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]')
    controls()?.[0]?.focus()
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCloseRef.current()
      if (event.key !== 'Tab') return
      const items = controls()
      if (!items?.length) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
      previousFocus?.focus()
    }
  }, [open])

  if (!open) return null
  return createPortal(
    <div ref={dialogRef} className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <div className="absolute inset-0 bg-base-950/80 backdrop-blur-sm" onClick={onClose} />
      <div className={clsx('card relative z-10 flex max-h-[calc(100dvh-2rem)] w-full flex-col animate-fade-up', width)}>
        <div className="flex items-start justify-between gap-4 border-b border-base-700 px-5 py-4">
          <div>
            <h2 id={titleId} className="text-base font-semibold text-ink">{title}</h2>
            {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
          </div>
          <button onClick={onClose} className="btn-ghost h-8 w-8 !p-0" aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>
        <div className="min-h-0 overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-base-700 px-5 py-4">{footer}</div>
        )}
      </div>
    </div>,
    document.body,
  )
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div role="alert" className="border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
      {message}
    </div>
  )
}
