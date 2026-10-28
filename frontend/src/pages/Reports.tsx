import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CalendarDays,
  Download,
  FileBarChart,
  FileSpreadsheet,
  FileText,
  Loader2,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import clsx from 'clsx'
import { reportsApi } from '../api'
import { apiErrorMessage, downloadBlob } from '../api/client'
import { EmptyState, ErrorBanner, PageHeader, Pagination, Spinner } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { formatBytes, formatDate } from '../lib/format'
import type { Report, ReportFormat, ReportType } from '../types'

const TYPES: { type: ReportType; name: string; description: string; icon: typeof FileText }[] = [
  {
    type: 'operational',
    name: 'Operacional',
    description: 'Volumen, MTTT, SLA, orígenes e incidentes del periodo.',
    icon: ShieldCheck,
  },
  {
    type: 'management',
    name: 'De gestión',
    description: 'Evolución mensual, automatización, carga y riesgos.',
    icon: FileBarChart,
  },
  {
    type: 'audit',
    name: 'De auditoría',
    description: 'Bitácora de accesos, acciones y cadena de integridad.',
    icon: FileText,
  },
]

const FORMATS: { value: ReportFormat; label: string }[] = [
  { value: 'pdf', label: 'PDF' },
  { value: 'docx', label: 'Word' },
  { value: 'xlsx', label: 'Excel' },
]

const TYPE_LABELS: Record<ReportType, string> = {
  operational: 'Operacional',
  management: 'De gestión',
  audit: 'De auditoría',
}

const STATUS_LABELS: Record<Report['status'], string> = {
  queued: 'En cola',
  generating: 'Generando',
  ready: 'Listo',
  failed: 'Fallido',
}

const STATUS_STYLES: Record<Report['status'], string> = {
  queued: 'border-slate-500/30 bg-slate-500/10 text-slate-300',
  generating: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300',
  ready: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  failed: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
}

function isoDate(offsetDays = 0): string {
  const date = new Date()
  date.setDate(date.getDate() - offsetDays)
  return date.toISOString().slice(0, 10)
}

export default function ReportsPage() {
  const { hasPermission } = useAuth()
  const { push } = useToast()
  const queryClient = useQueryClient()
  const [type, setType] = useState<ReportType>('operational')
  const [format, setFormat] = useState<ReportFormat>('pdf')
  const [dateFrom, setDateFrom] = useState(isoDate(29))
  const [dateTo, setDateTo] = useState(isoDate(0))
  const [page, setPage] = useState(1)

  const types = useQuery({ queryKey: ['report-types'], queryFn: reportsApi.types })
  const history = useQuery({
    queryKey: ['reports', page],
    queryFn: () => reportsApi.list({ page, size: 10 }),
    placeholderData: (previous) => previous,
  })

  const create = useMutation({
    mutationFn: () =>
      reportsApi.create({ type, format, date_from: dateFrom, date_to: dateTo }),
    onSuccess: (report) => {
      push(`Reporte ${FORMATS.find((item) => item.value === report.format)?.label} generado`, 'success')
      void queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  const download = useMutation({
    mutationFn: (report: Report) => reportsApi.download(report.id),
    onSuccess: (blob, report) => {
      downloadBlob(blob, `SOC-Lite_${report.type}_${report.id.slice(0, 8)}.${report.format}`)
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Reportes"
        subtitle="Documentos operativos y de gestión exportables en PDF, Word y Excel, con datos del periodo seleccionado."
      />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.2fr_1fr]">
        <section className="card p-5">
          <div className="mb-4 flex items-center gap-2">
            <Sparkles size={16} className="text-accent" />
            <h2 className="text-sm font-semibold text-ink">Nuevo reporte</h2>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {TYPES.map((item) => (
              <button
                key={item.type}
                onClick={() => setType(item.type)}
                className={clsx(
                  'border p-3 text-left transition',
                  type === item.type
                    ? 'border-accent/40 bg-accent/[0.06]'
                    : 'border-base-700 bg-ink/[0.01] hover:border-base-700',
                )}
              >
                <item.icon size={17} className={type === item.type ? 'text-accent' : 'text-slate-500'} />
                <p className="mt-2 text-sm font-medium text-slate-200">{item.name}</p>
                <p className="mt-1 text-[11px] leading-snug text-slate-500">{item.description}</p>
              </button>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label className="label">Desde</label>
              <div className="relative">
                <CalendarDays size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="date"
                  className="input pl-9"
                  value={dateFrom}
                  max={dateTo}
                  onChange={(event) => setDateFrom(event.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="label">Hasta</label>
              <div className="relative">
                <CalendarDays size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="date"
                  className="input pl-9"
                  value={dateTo}
                  min={dateFrom}
                  max={isoDate(0)}
                  onChange={(event) => setDateTo(event.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="label">Formato</label>
              <div className="flex h-[38px] border border-base-700 bg-base-950/70 p-0.5">
                {FORMATS.map((item) => (
                  <button
                    key={item.value}
                    onClick={() => setFormat(item.value)}
                    className={clsx(
                      'flex-1 text-[11px] font-medium transition',
                      format === item.value
                        ? 'bg-accent/15 text-accent'
                        : 'text-slate-500 hover:text-slate-300',
                    )}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-col items-start justify-between gap-3 border-t border-base-700 pt-4 sm:flex-row sm:items-center">
            <p className="flex items-center gap-1.5 text-[11px] text-slate-500">
              <FileSpreadsheet size={13} />
              Incluye KPIs, tendencias, MTTT/SLA, orígenes e incidentes.
            </p>
            {hasPermission('reports:create') ? (
              <button
                className="btn-primary"
                onClick={() => create.mutate()}
                disabled={create.isPending || Boolean(types.isError)}
              >
                {create.isPending ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
                {create.isPending ? 'Generando…' : 'Generar reporte'}
              </button>
            ) : (
              <span className="text-xs text-slate-500">Su rol no permite generar reportes.</span>
            )}
          </div>
        </section>

        <section className="card p-5">
          <h2 className="mb-3 text-sm font-semibold text-ink">Contenido por tipo</h2>
          <div className="space-y-2">
            {(types.data ?? []).map((item) => (
              <div key={item.type} className="border border-base-700 bg-ink/[0.015] p-3">
                <p className="text-xs font-medium text-slate-200">{item.name}</p>
                <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">{item.description}</p>
              </div>
            ))}
            {types.isLoading && <Spinner label="Cargando tipos…" />}
          </div>
          <p className="mt-3 border border-amber-500/20 bg-amber-500/5 p-3 text-[11px] leading-relaxed text-amber-200/80">
            Los reportes se generan en el servidor y se conservan en el historial. La descarga queda
            registrada en la bitácora.
          </p>
        </section>
      </div>

      <div className="card mt-5 overflow-hidden">
        <div className="flex items-center justify-between border-b border-base-700 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-ink">Historial de reportes</h2>
            <p className="text-xs text-slate-500">Generados por el equipo en este entorno</p>
          </div>
        </div>

        {history.isError && <div className="p-4"><ErrorBanner message={apiErrorMessage(history.error)} /></div>}

        {history.isLoading ? (
          <Spinner label="Cargando historial…" />
        ) : (history.data?.items ?? []).length === 0 ? (
          <EmptyState
            title="Aún no hay reportes"
            description="Genere el primero con el formulario superior."
            icon={FileBarChart}
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="table min-w-[900px]">
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th>Formato</th>
                    <th>Periodo</th>
                    <th>Estado</th>
                    <th>Tamaño</th>
                    <th>Creado</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {(history.data?.items ?? []).map((report) => (
                    <tr key={report.id}>
                      <td className="text-xs text-slate-300">{TYPE_LABELS[report.type]}</td>
                      <td>
                        <span className="chip border-base-700 bg-ink/[0.03] font-mono uppercase text-slate-300">
                          {report.format}
                        </span>
                      </td>
                      <td className="text-xs text-slate-400">
                        {String(report.params.date_from ?? '—')} → {String(report.params.date_to ?? '—')}
                      </td>
                      <td>
                        <span className={`chip ${STATUS_STYLES[report.status]}`}>
                          {STATUS_LABELS[report.status]}
                        </span>
                        {report.error && (
                          <p className="mt-1 max-w-[220px] truncate text-[10px] text-rose-300">{report.error}</p>
                        )}
                      </td>
                      <td className="font-mono text-xs text-slate-400">{formatBytes(report.file_size)}</td>
                      <td className="whitespace-nowrap text-xs text-slate-500">{formatDate(report.created_at)}</td>
                      <td>
                        {report.status === 'ready' && hasPermission('reports:export') && (
                          <button
                            onClick={() => download.mutate(report)}
                            disabled={download.isPending}
                            className="btn-secondary px-2.5 py-1.5 text-xs"
                          >
                            {download.isPending && download.variables?.id === report.id ? (
                              <Loader2 size={13} className="animate-spin" />
                            ) : (
                              <Download size={13} />
                            )}
                            Descargar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              pages={history.data?.pages ?? 1}
              total={history.data?.total ?? 0}
              onPage={setPage}
            />
          </>
        )}
      </div>
    </div>
  )
}
