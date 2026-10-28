import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Loader2, Pencil, Search, Siren } from 'lucide-react'
import { incidentsApi } from '../api'
import { apiErrorMessage } from '../api/client'
import { PriorityBadge, SeverityBadge } from '../components/Badges'
import { EmptyState, ErrorBanner, Modal, PageHeader, Pagination, Spinner } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import {
  formatDate,
  INCIDENT_STATUS_LABELS,
  truncate,
} from '../lib/format'
import type { Incident, IncidentPriority, IncidentStatus } from '../types'

const STATUSES: IncidentStatus[] = ['open', 'investigating', 'contained', 'resolved', 'closed']
const PRIORITIES: IncidentPriority[] = ['P1', 'P2', 'P3', 'P4']

export default function IncidentsPage() {
  const { hasPermission } = useAuth()
  const { push } = useToast()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedId = searchParams.get('incident')
  const canUpdate = hasPermission('incidents:update')
  const canClose = hasPermission('incidents:close')
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [selected, setSelected] = useState<Incident | null>(null)
  const [form, setForm] = useState<{ status: IncidentStatus; priority: IncidentPriority; resolution: string; assignee_id: string }>({
    status: 'open',
    priority: 'P3',
    resolution: '',
    assignee_id: '',
  })

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search), 350)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => setPage(1), [status, priority, debounced])

  const query = useQuery({
    queryKey: ['incidents', { page, status, priority, q: debounced }],
    queryFn: () =>
      incidentsApi.list({
        page,
        size: 15,
        status: status || undefined,
        priority: priority || undefined,
        q: debounced || undefined,
      }),
    placeholderData: (previous) => previous,
  })

  const requested = useQuery({
    queryKey: ['incident', requestedId],
    queryFn: () => incidentsApi.get(requestedId!),
    enabled: Boolean(requestedId),
    retry: false,
  })
  const assignees = useQuery({
    queryKey: ['incident-assignees'],
    queryFn: incidentsApi.assignees,
    enabled: Boolean(selected) && canUpdate,
  })

  useEffect(() => {
    if (!requested.data || selected?.id === requested.data.id) return
    const incident = requested.data
    setSelected(incident)
    setForm({ status: incident.status, priority: incident.priority, resolution: incident.resolution ?? '', assignee_id: incident.assignee_id ?? '' })
  }, [requested.data, selected?.id])

  const closeEdit = () => {
    setSelected(null)
    setSearchParams((current) => { const next = new URLSearchParams(current); next.delete('incident'); return next })
  }

  const update = useMutation({
    mutationFn: () =>
      incidentsApi.update(selected!.id, {
        status: form.status !== selected!.status || !canUpdate ? form.status : undefined,
        priority: form.priority !== selected!.priority ? form.priority : undefined,
        assignee_id: form.assignee_id && form.assignee_id !== selected!.assignee_id ? form.assignee_id : undefined,
        resolution: form.resolution !== (selected!.resolution ?? '') ? form.resolution : undefined,
      }),
    onSuccess: () => {
      push('Incidente actualizado', 'success')
      closeEdit()
      void queryClient.invalidateQueries({ queryKey: ['incidents'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      void queryClient.invalidateQueries({ queryKey: ['alert'] })
      void queryClient.invalidateQueries({ queryKey: ['incident'] })
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  const openEdit = (incident: Incident) => {
    setSelected(incident)
    setSearchParams((current) => { const next = new URLSearchParams(current); next.set('incident', incident.id); return next })
    setForm({
      status: incident.status,
      priority: incident.priority,
      resolution: incident.resolution ?? '',
      assignee_id: incident.assignee_id ?? '',
    })
  }

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Incidentes"
        subtitle="Casos locales vinculados a alertas, con prioridad, responsable y vencimiento de SLA. No se crean tickets externos."
      />

      <div className="card mb-4 flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <select className="input sm:w-48" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">Todos los estados</option>
          {STATUSES.map((value) => (
            <option key={value} value={value}>
              {INCIDENT_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
        <select className="input sm:w-36" value={priority} onChange={(event) => setPriority(event.target.value)}>
          <option value="">Toda prioridad</option>
          {PRIORITIES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            className="input pl-9"
            placeholder="Buscar por ID local o título…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      {query.isError && <ErrorBanner message={apiErrorMessage(query.error)} />}
      {requested.isError && <ErrorBanner message={apiErrorMessage(requested.error)} />}

      <div className="card overflow-hidden">
        {query.isLoading ? (
          <Spinner label="Cargando incidentes…" />
        ) : (query.data?.items ?? []).length === 0 ? (
          <EmptyState title="Sin incidentes" description="Los incidentes se crean desde el detalle de una alerta." icon={Siren} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="table min-w-[1020px]">
                <thead>
                  <tr>
                    <th>ID local</th>
                    <th>Incidente</th>
                    <th>Severidad</th>
                    <th>Prioridad</th>
                    <th>Estado</th>
                    <th>Responsable</th>
                    <th>SLA</th>
                    <th>Apertura</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {(query.data?.items ?? []).map((incident) => {
                    const overdue =
                      incident.sla_due_at &&
                      new Date(incident.sla_due_at) < new Date() &&
                      !['resolved', 'closed'].includes(incident.status)
                    return (
                      <tr key={incident.id}>
                        <td className="font-mono text-xs text-accent">{incident.ticket_id ?? '—'}</td>
                        <td className="max-w-[340px]">
                          <p className="truncate text-sm text-slate-200">{truncate(incident.title, 80)}</p>
                          {incident.alert_id && (
                            <Link
                              to={`/alerts/${incident.alert_id}`}
                              className="text-[10px] text-slate-500 hover:text-accent"
                            >
                              ver alerta origen
                            </Link>
                          )}
                        </td>
                        <td>{incident.alert_severity ? <SeverityBadge severity={incident.alert_severity} /> : '—'}</td>
                        <td>
                          <PriorityBadge priority={incident.priority} />
                        </td>
                        <td>
                          <span className="chip border-base-700 bg-ink/[0.03] text-slate-300">
                            {INCIDENT_STATUS_LABELS[incident.status]}
                          </span>
                        </td>
                        <td className="text-xs text-slate-400">{incident.assignee_name ?? 'sin asignar'}</td>
                        <td className={`whitespace-nowrap text-xs ${overdue ? 'text-rose-400' : 'text-slate-400'}`}>
                          {formatDate(incident.sla_due_at)}
                          {overdue && <span className="ml-1 text-[10px] uppercase">vencido</span>}
                        </td>
                        <td className="whitespace-nowrap text-xs text-slate-500">{formatDate(incident.opened_at)}</td>
                        <td>
                          {hasPermission('incidents:read') && (
                            <button
                              onClick={() => openEdit(incident)}
                              className="p-1.5 text-slate-500 hover:bg-ink/5 hover:text-accent"
                              aria-label="Abrir incidente"
                            >
                              <Pencil size={14} />
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              pages={query.data?.pages ?? 1}
              total={query.data?.total ?? 0}
              onPage={setPage}
            />
          </>
        )}
      </div>

      <Modal
        open={Boolean(selected)}
        onClose={closeEdit}
        title={`Incidente ${selected?.ticket_id ?? ''}`}
        description={selected ? truncate(selected.title, 90) : ''}
        footer={
          <>
            <button className="btn-secondary" onClick={closeEdit}>
              Cerrar
            </button>
            {(canUpdate || canClose) && <button className="btn-primary" onClick={() => update.mutate()} disabled={update.isPending || (['resolved', 'closed'].includes(form.status) && !form.resolution.trim())}>
              {update.isPending ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              Guardar cambios
            </button>}
          </>
        }
      >
        {selected && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label" htmlFor="incident-status">Estado</label>
                <select
                  id="incident-status"
                  className="input"
                  value={form.status}
                  onChange={(event) => setForm({ ...form, status: event.target.value as IncidentStatus })}
                  disabled={!canUpdate && !canClose}
                >
                  {STATUSES.map((value) => (
                    <option key={value} value={value} disabled={value !== selected.status && (['resolved', 'closed'].includes(value) ? !canClose : !canUpdate)}>
                      {INCIDENT_STATUS_LABELS[value]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="incident-edit-priority">Prioridad</label>
                <select
                  id="incident-edit-priority"
                  className="input"
                  value={form.priority}
                  onChange={(event) => setForm({ ...form, priority: event.target.value as IncidentPriority })}
                  disabled={!canUpdate}
                >
                  {PRIORITIES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="label" htmlFor="incident-assignee">Responsable</label>
              <select id="incident-assignee" className="input" value={form.assignee_id} disabled={!canUpdate || assignees.isLoading || assignees.isError} onChange={(event) => setForm({ ...form, assignee_id: event.target.value })}>
                {!form.assignee_id && <option value="" disabled>Selecciona un responsable</option>}
                {form.assignee_id && !assignees.data?.some((user) => user.id === form.assignee_id) && <option value={form.assignee_id}>{selected.assignee_name ?? 'Responsable actual'}</option>}
                {assignees.data?.map((user) => <option key={user.id} value={user.id}>{user.full_name} ({user.username})</option>)}
              </select>
              {assignees.isError && <p className="mt-1 text-xs text-rose-400">No se pudieron cargar los responsables.</p>}
            </div>
            <div className="border border-base-700 bg-ink/[0.02] p-3 text-xs text-slate-400">
              <p>
                <span className="text-slate-500">Alerta origen:</span> {selected.alert_description ?? '—'}
              </p>
              {selected.alert_id && hasPermission('alerts:read') && <Link to={`/alerts/${selected.alert_id}`} className="mt-1 inline-block text-accent underline">Abrir alerta</Link>}
              <p className="mt-1">
                <span className="text-slate-500">Apertura:</span> {formatDate(selected.opened_at)} ·{' '}
                <span className="text-slate-500">SLA:</span> {formatDate(selected.sla_due_at)}
              </p>
            </div>
            <div>
              <label className="label" htmlFor="incident-resolution">Resolución / notas{['resolved', 'closed'].includes(form.status) ? ' (obligatoria)' : ''}</label>
              <textarea
                id="incident-resolution"
                className="input min-h-[110px]"
                value={form.resolution}
                onChange={(event) => setForm({ ...form, resolution: event.target.value })}
                placeholder="Describe la investigación y su resultado…"
                maxLength={4000}
                disabled={!canUpdate && !canClose}
              />
              {['resolved', 'closed'].includes(form.status) && !form.resolution.trim() && <p className="mt-1 text-xs text-amber-400">Escribe una resolución para guardar este estado.</p>}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
