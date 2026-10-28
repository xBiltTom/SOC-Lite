import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Filter, Search, ShieldAlert } from 'lucide-react'
import clsx from 'clsx'
import { alertsApi, type AlertFilters } from '../api'
import { apiErrorMessage } from '../api/client'
import { SeverityBadge, StatusBadge, VerdictBadge } from '../components/Badges'
import { EmptyState, ErrorBanner, PageHeader, Pagination, Spinner } from '../components/ui'
import {
  formatDate,
  formatMinutes,
  formatNumber,
  SEVERITY_LABELS,
  SEVERITY_ORDER,
  STATUS_LABELS,
  truncate,
} from '../lib/format'
import type { AlertStatus } from '../types'

const STATUSES: AlertStatus[] = [
  'pending',
  'triaging',
  'triage_failed',
  'triaged',
  'escalated',
  'in_review',
  'false_positive',
  'closed',
]

export default function AlertsPage() {
  const [page, setPage] = useState(1)
  const [severity, setSeverity] = useState('')
  const [status, setStatus] = useState('')
  const [source, setSource] = useState('')
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search), 350)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    setPage(1)
  }, [severity, status, source, debounced])

  const filters: AlertFilters = {
    page,
    size: 15,
    severity: severity || undefined,
    status: status || undefined,
    source: source || undefined,
    q: debounced || undefined,
    sort: '-received_at',
  }

  const query = useQuery({
    queryKey: ['alerts', filters],
    queryFn: () => alertsApi.list(filters),
    placeholderData: (previous) => previous,
  })

  const items = query.data?.items ?? []
  const totalPages = query.data?.pages ?? 1

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Alertas"
        subtitle="Cola operativa priorizada por severidad, con veredicto del triaje y tiempos de respuesta."
        actions={
          <div className="flex items-center gap-2 border border-base-700 bg-base-900 px-3 py-2 text-xs text-slate-400">
            <ShieldAlert size={14} className="text-accent" />
            {formatNumber(query.data?.total ?? 0)} alertas en el filtro
          </div>
        }
      />

      <div className="card mb-4 p-4">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                onClick={() => setSeverity('')}
                className={clsx(
                  'chip transition',
                  severity === ''
                    ? 'border-accent/40 bg-accent/10 text-accent'
                    : 'border-base-700 bg-ink/[0.02] text-slate-400 hover:text-slate-200',
                )}
              >
                Todas
              </button>
              {SEVERITY_ORDER.map((level) => (
                <button
                  key={level}
                  onClick={() => setSeverity(severity === level ? '' : level)}
                  className={clsx(
                    'chip transition',
                    severity === level
                      ? 'border-accent/40 bg-accent/10 text-accent'
                      : 'border-base-700 bg-ink/[0.02] text-slate-400 hover:text-slate-200',
                  )}
                >
                  {SEVERITY_LABELS[level]}
                </button>
              ))}
            </div>

            <div className="relative w-full lg:w-72">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                className="input pl-9"
                placeholder="Buscar descripción, IP, regla…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-2 border-t border-base-700 pt-3 sm:flex-row sm:items-center">
            <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-slate-500">
              <Filter size={12} /> Filtros
            </span>
            <select className="input sm:w-44" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Todos los estados</option>
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {STATUS_LABELS[value]}
                </option>
              ))}
            </select>
            <select className="input sm:w-40" value={source} onChange={(event) => setSource(event.target.value)}>
              <option value="">Todas las fuentes</option>
              <option value="wazuh">Wazuh</option>
              <option value="opnsense">OPNsense</option>
              <option value="suricata">Suricata</option>
            </select>
            <span className="text-[11px] text-slate-600">
              Ordenadas por fecha de recepción descendente
            </span>
          </div>
        </div>
      </div>

      {query.isError && <ErrorBanner message={apiErrorMessage(query.error)} />}

      <div className="card overflow-hidden">
        {query.isLoading ? (
          <Spinner label="Consultando alertas…" />
        ) : items.length === 0 ? (
          <EmptyState
            title="No hay alertas que coincidan"
            description="Ajuste los filtros o espere la próxima ingesta del SIEM."
            icon={ShieldAlert}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="table min-w-[1080px]">
                <thead>
                  <tr>
                    <th>Severidad</th>
                    <th>Alerta</th>
                    <th>Origen</th>
                    <th>Activo</th>
                    <th>Veredicto IA</th>
                    <th>Estado</th>
                    <th>MTTT</th>
                    <th>Recibida</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {items.map((alert) => (
                    <tr key={alert.id} className="group">
                      <td>
                        <SeverityBadge severity={alert.severity} />
                      </td>
                      <td className="max-w-[430px]">
                        <Link to={`/alerts/${alert.id}`} className="block">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-[10px] uppercase tracking-wide text-slate-500">
                              {alert.rule_id ?? 'sin regla'}
                            </span>
                            <span className="text-[10px] text-slate-600">nivel {alert.rule_level ?? '—'}</span>
                            {alert.dedup_count > 1 && (
                              <span className="bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-300">
                                ×{alert.dedup_count} duplicados
                              </span>
                            )}
                          </div>
                          <p className="mt-0.5 truncate text-sm text-slate-200 group-hover:text-ink">
                            {truncate(alert.description, 100)}
                          </p>
                        </Link>
                      </td>
                      <td className="font-mono text-xs text-slate-400">
                        {alert.src_ip ?? '—'}
                        <span className="mt-0.5 block text-[10px] uppercase text-slate-600">{alert.source}</span>
                      </td>
                      <td className="text-xs text-slate-400">
                        {alert.agent_name ?? '—'}
                        <span className="mt-0.5 block text-[10px] text-slate-600">
                          criticidad {alert.asset_criticality}/5
                        </span>
                      </td>
                      <td>
                        {alert.verdict ? (
                          <div className="space-y-1">
                            <VerdictBadge verdict={alert.verdict} />
                          </div>
                        ) : (
                          <span className="text-xs text-slate-600">sin triaje</span>
                        )}
                      </td>
                      <td>
                        <StatusBadge status={alert.status} />
                      </td>
                      <td className="whitespace-nowrap font-mono text-xs text-slate-400">
                        {alert.mttt_minutes !== null ? formatMinutes(alert.mttt_minutes) : '—'}
                      </td>
                      <td className="whitespace-nowrap text-xs text-slate-500">{formatDate(alert.received_at)}</td>
                      <td>
                        <Link
                          to={`/alerts/${alert.id}`}
                          className="p-1.5 text-slate-600 transition hover:bg-ink/5 hover:text-accent"
                          aria-label="Ver detalle"
                        >
                          <ArrowRight size={15} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pages={totalPages} total={query.data?.total ?? 0} onPage={setPage} />
          </>
        )}
      </div>
    </div>
  )
}
