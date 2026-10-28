import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowLeft,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  ExternalLink,
  Fingerprint,
  Globe2,
  Loader2,
  Play,
  Siren,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react'
import { alertsApi } from '../api'
import { apiErrorMessage } from '../api/client'
import { SeverityBadge, StatusBadge, VerdictBadge, Confidence } from '../components/Badges'
import { EmptyState, ErrorBanner, Modal, PageHeader, Spinner } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import {
  formatDate,
  formatMinutes,
  SEVERITY_LABELS,
  STATUS_LABELS,
  truncate,
  VERDICT_LABELS,
} from '../lib/format'
import type { AlertStatus } from '../types'

const STATUSES: AlertStatus[] = [
  'pending',
  'triaging',
  'triaged',
  'in_review',
  'escalated',
  'closed',
  'false_positive',
  'discarded',
]

export default function AlertDetailPage() {
  const { id = '' } = useParams()
  const { hasPermission } = useAuth()
  const { push } = useToast()
  const queryClient = useQueryClient()
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedbackFp, setFeedbackFp] = useState(true)
  const [comment, setComment] = useState('')

  const query = useQuery({
    queryKey: ['alert', id],
    queryFn: () => alertsApi.get(id),
    enabled: Boolean(id),
  })

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['alert', id] })
    void queryClient.invalidateQueries({ queryKey: ['alerts'] })
    void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
  }

  const triage = useMutation({
    mutationFn: () => alertsApi.triage(id, true),
    onSuccess: (result) => {
      push(`Triaje completado: ${VERDICT_LABELS[result.verdict]}`, 'success')
      invalidate()
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  const feedback = useMutation({
    mutationFn: () => alertsApi.feedback(id, feedbackFp, comment || undefined),
    onSuccess: () => {
      push('Validación registrada. La memoria del triaje fue actualizada.', 'success')
      setFeedbackOpen(false)
      setComment('')
      invalidate()
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  const incident = useMutation({
    mutationFn: () => alertsApi.createIncident(id),
    onSuccess: (created) => {
      push(`Incidente ${created.ticket_id ?? ''} creado`, 'success')
      invalidate()
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  const update = useMutation({
    mutationFn: (status: string) => alertsApi.update(id, { status }),
    onSuccess: () => {
      push('Estado de la alerta actualizado', 'success')
      invalidate()
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  if (query.isLoading) return <Spinner label="Cargando alerta…" />
  if (query.isError || !query.data) {
    return (
      <div className="space-y-4">
        <Link to="/alerts" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-ink">
          <ArrowLeft size={15} /> Volver a alertas
        </Link>
        <ErrorBanner message={query.isError ? apiErrorMessage(query.error) : 'Alerta no encontrada'} />
      </div>
    )
  }

  const alert = query.data
  const latest = alert.triage_results[0]
  const busy = triage.isPending || feedback.isPending || incident.isPending || update.isPending

  return (
    <div className="animate-fade-up">
      <Link to="/alerts" className="mb-4 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-ink">
        <ArrowLeft size={15} /> Volver a alertas
      </Link>

      <PageHeader
        title={truncate(alert.description, 110)}
        subtitle={`${alert.source} · regla ${alert.rule_id ?? '—'} · ${alert.agent_name ?? 'activo desconocido'} · ${formatDate(alert.received_at)}`}
        actions={
          <>
            <SeverityBadge severity={alert.severity} />
            <StatusBadge status={alert.status} />
            {hasPermission('triage:run') && (
              <button className="btn-primary" onClick={() => triage.mutate()} disabled={busy}>
                {triage.isPending ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                {latest ? 'Re-ejecutar triaje' : 'Ejecutar triaje'}
              </button>
            )}
          </>
        }
      />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.65fr_1fr]">
        <div className="space-y-5">
          <section className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-base-700 px-5 py-4">
              <div className="flex items-center gap-2">
                <BrainCircuit size={17} className="text-accent" />
                <h2 className="text-sm font-semibold text-ink">Resumen del triaje</h2>
                {latest?.fallback_used && (
                  <span className="chip border-amber-500/30 bg-amber-500/10 text-amber-300">
                    modo degradado
                  </span>
                )}
              </div>
              {latest && <Confidence value={latest.confidence} />}
            </div>

            {latest ? (
              <div className="space-y-5 p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <VerdictBadge verdict={latest.verdict} />
                  <span className="chip border-base-700 bg-ink/[0.03] text-slate-300">
                    severidad {SEVERITY_LABELS[latest.severity]}
                  </span>
                  {latest.needs_human && (
                    <span className="chip border-orange-500/30 bg-orange-500/10 text-orange-300">
                      requiere revisión humana
                    </span>
                  )}
                  {latest.mitre_techniques.map((technique) => (
                    <span
                      key={technique}
                      className="chip border-violet-500/30 bg-violet-500/10 font-mono text-violet-300"
                    >
                      {technique}
                    </span>
                  ))}
                </div>

                <p className="text-sm leading-relaxed text-slate-200">{latest.summary}</p>

                {latest.reasoning && (
                  <div className="border border-base-700 bg-ink/[0.02] p-3">
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                      Razonamiento
                    </p>
                    <p className="text-xs leading-relaxed text-slate-400">{latest.reasoning}</p>
                  </div>
                )}

                <div>
                  <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    <ClipboardList size={13} /> Acciones recomendadas
                  </p>
                  <ol className="space-y-2">
                    {latest.recommended_actions.map((action, index) => (
                      <li
                        key={`${action.action}-${index}`}
                        className="flex items-start gap-3 border border-base-700 bg-base-950/40 px-3 py-2.5"
                      >
                        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center bg-accent/10 font-mono text-[10px] text-accent">
                          {index + 1}
                        </span>
                        <div className="flex-1">
                          <p className="text-sm text-slate-200">{action.action}</p>
                          <p className="text-[10px] uppercase tracking-wide text-slate-500">
                            prioridad {action.priority} · {action.owner}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-base-700 pt-3 text-[10px] text-slate-500">
                  <span>modelo: <span className="font-mono text-slate-400">{latest.model ?? '—'}</span></span>
                  <span>prompt: <span className="font-mono text-slate-400">{latest.prompt_version ?? '—'}</span></span>
                  <span>latencia: <span className="font-mono text-slate-400">{latest.latency_ms ?? 0} ms</span></span>
                  <span>triaje: {formatDate(latest.triaged_at)}</span>
                  <span>
                    MTTT alerta:{' '}
                    <span className="font-mono text-slate-400">
                      {alert.mttt_minutes !== null ? formatMinutes(alert.mttt_minutes) : '—'}
                    </span>
                  </span>
                </div>
              </div>
            ) : (
              <EmptyState
                title="Esta alerta aún no fue triada"
                description="Ejecute el triaje para obtener veredicto, severidad y acciones recomendadas."
                icon={Sparkles}
              />
            )}
          </section>

          <section className="card overflow-hidden">
            <div className="flex items-center justify-between border-b border-base-700 px-5 py-4">
              <div className="flex items-center gap-2">
                <Globe2 size={16} className="text-accent" />
                <h2 className="text-sm font-semibold text-ink">Enriquecimiento de indicadores</h2>
              </div>
              <span className="text-[11px] text-slate-500">{alert.enrichments.length} fuentes</span>
            </div>
            {alert.enrichments.length === 0 ? (
              <EmptyState
                title="Sin enriquecimiento registrado"
                description="El agente consulta VirusTotal, AbuseIPDB y GeoIP durante el triaje."
                icon={Globe2}
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="table min-w-[700px]">
                  <thead>
                    <tr>
                      <th>Proveedor</th>
                      <th>Indicador</th>
                      <th>Veredicto</th>
                      <th>Score</th>
                      <th>País / ASN</th>
                      <th>Consultado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {alert.enrichments.map((item) => (
                      <tr key={item.id}>
                        <td className="font-mono text-xs text-slate-300">{item.provider}</td>
                        <td className="font-mono text-xs text-slate-400">{item.indicator}</td>
                        <td>
                          <span
                            className={`chip ${
                              ['malicious', 'suspicious'].includes(item.verdict ?? '')
                                ? 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                                : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                            }`}
                          >
                            {item.verdict ?? '—'}
                          </span>
                        </td>
                        <td className="font-mono text-xs text-slate-400">
                          {item.score !== null ? item.score : '—'}
                        </td>
                        <td className="text-xs text-slate-400">
                          {[item.country, item.asn].filter(Boolean).join(' · ') || '—'}
                        </td>
                        <td className="text-xs text-slate-500">{formatDate(item.fetched_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="card p-5">
            <details>
              <summary className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-ink">
                <ChevronDown size={15} className="text-slate-500" />
                Payload original del SIEM
              </summary>
              <pre className="mt-3 max-h-[360px] overflow-auto border border-base-700 bg-base-950 p-4 font-mono text-[11px] leading-relaxed text-slate-400">
                {JSON.stringify(alert.raw_payload, null, 2)}
              </pre>
            </details>
          </section>
        </div>

        <div className="space-y-5">
          <section className="card p-5">
            <h2 className="mb-4 text-sm font-semibold text-ink">Acciones del analista</h2>
            <div className="space-y-2.5">
              {hasPermission('triage:feedback') && (
                <>
                  <button
                    className="btn-secondary w-full justify-start"
                    onClick={() => {
                      setFeedbackFp(false)
                      setFeedbackOpen(true)
                    }}
                    disabled={busy}
                  >
                    <ThumbsUp size={15} className="text-emerald-400" /> Confirmar verdadero positivo
                  </button>
                  <button
                    className="btn-secondary w-full justify-start"
                    onClick={() => {
                      setFeedbackFp(true)
                      setFeedbackOpen(true)
                    }}
                    disabled={busy}
                  >
                    <ThumbsDown size={15} className="text-amber-400" /> Marcar falso positivo
                  </button>
                </>
              )}

              {hasPermission('incidents:create') && !alert.incident && (
                <button
                  className="btn-secondary w-full justify-start"
                  onClick={() => incident.mutate()}
                  disabled={busy}
                >
                  {incident.isPending ? <Loader2 size={15} className="animate-spin" /> : <Siren size={15} className="text-rose-400" />}
                  Crear incidente y ticket
                </button>
              )}

              {hasPermission('alerts:update') && (
                <div>
                  <label className="label mt-2">Cambiar estado</label>
                  <select
                    className="input"
                    value={alert.status}
                    onChange={(event) => update.mutate(event.target.value)}
                    disabled={busy}
                  >
                    {STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {STATUS_LABELS[status]}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <div className="mt-5 border-t border-base-700 pt-4">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Historial de validación
              </p>
              {alert.feedback.length === 0 ? (
                <p className="text-xs text-slate-600">Sin validaciones humanas registradas.</p>
              ) : (
                <ul className="space-y-2">
                  {alert.feedback.map((entry) => (
                    <li key={entry.id} className="border border-base-700 bg-ink/[0.02] p-2.5">
                      <div className="flex items-center justify-between">
                        <span
                          className={`text-xs font-medium ${
                            entry.is_false_positive ? 'text-amber-300' : 'text-emerald-300'
                          }`}
                        >
                          {entry.is_false_positive ? 'Falso positivo' : 'Verdadero positivo'}
                        </span>
                        <span className="text-[10px] text-slate-600">{formatDate(entry.created_at)}</span>
                      </div>
                      {entry.comment && <p className="mt-1 text-[11px] text-slate-400">{entry.comment}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className="card p-5">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
              <AlertTriangle size={15} className="text-amber-400" /> Contexto del evento
            </h2>
            <dl className="space-y-2.5 text-xs">
              {[
                ['ID externo', alert.external_id ?? '—'],
                ['IP origen', alert.src_ip ?? '—'],
                ['IP destino', alert.dst_ip ?? '—'],
                ['Puertos', `${alert.src_port ?? '—'} → ${alert.dst_port ?? '—'}`],
                ['Protocolo', alert.protocol ?? '—'],
                ['Criticidad', `${alert.asset_criticality}/5`],
                ['Duplicados', String(alert.dedup_count)],
                ['Ocurrió', formatDate(alert.occurred_at)],
              ].map(([label, value]) => (
                <div key={label} className="flex items-start justify-between gap-3">
                  <dt className="text-slate-500">{label}</dt>
                  <dd className="text-right font-mono text-slate-300">{value}</dd>
                </div>
              ))}
            </dl>
            {alert.tags.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5 border-t border-base-700 pt-3">
                {alert.tags.map((tag) => (
                  <span key={tag} className="chip border-base-700 bg-ink/[0.03] text-slate-400">
                    {tag}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-3 flex items-start gap-2 border border-base-700 bg-base-950/50 p-2.5">
              <Fingerprint size={13} className="mt-0.5 shrink-0 text-slate-600" />
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-600">Huella de correlación</p>
                <p className="break-all font-mono text-[10px] text-slate-500">{alert.fingerprint}</p>
              </div>
            </div>
          </section>

          {alert.incident && (
            <section className="card p-5">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
                  <Siren size={15} className="text-rose-400" /> Incidente vinculado
                </h2>
                <Link to="/incidents" className="text-slate-500 hover:text-accent">
                  <ExternalLink size={14} />
                </Link>
              </div>
              <p className="font-mono text-xs text-accent">{alert.incident.ticket_id ?? 'sin ticket'}</p>
              <p className="mt-1 text-sm text-slate-200">{alert.incident.title}</p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <p className="text-slate-500">Estado</p>
                  <p className="text-slate-300">{alert.incident.status}</p>
                </div>
                <div>
                  <p className="text-slate-500">Prioridad</p>
                  <p className="text-slate-300">{alert.incident.priority}</p>
                </div>
                <div>
                  <p className="text-slate-500">Responsable</p>
                  <p className="text-slate-300">{alert.incident.assignee_name ?? 'sin asignar'}</p>
                </div>
                <div>
                  <p className="text-slate-500">SLA</p>
                  <p className="text-slate-300">{formatDate(alert.incident.sla_due_at)}</p>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>

      <Modal
        open={feedbackOpen}
        onClose={() => setFeedbackOpen(false)}
        title={feedbackFp ? 'Marcar como falso positivo' : 'Confirmar verdadero positivo'}
        description="La validación alimenta la memoria de triaje y las métricas de calidad."
        footer={
          <>
            <button className="btn-secondary" onClick={() => setFeedbackOpen(false)}>
              Cancelar
            </button>
            <button
              className={feedbackFp ? 'btn-danger' : 'btn-primary'}
              onClick={() => feedback.mutate()}
              disabled={feedback.isPending}
            >
              {feedback.isPending ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}
              Registrar validación
            </button>
          </>
        }
      >
        <label className="label">Comentario (opcional)</label>
        <textarea
          className="input min-h-[100px]"
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Justifique la decisión para el resto del equipo…"
          maxLength={1000}
        />
      </Modal>
    </div>
  )
}
