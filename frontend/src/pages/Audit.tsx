import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  BadgeCheck,
  Download,
  FileSpreadsheet,
  Fingerprint,
  Loader2,
  ScrollText,
  Search,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { auditApi } from '../api'
import { apiErrorMessage, downloadBlob } from '../api/client'
import { EmptyState, ErrorBanner, Modal, PageHeader, Pagination, Spinner } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { formatDate, formatNumber } from '../lib/format'
import type { AuditEntry } from '../types'

const RESULT_STYLES: Record<string, string> = {
  success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  failure: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
  denied: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
}

export default function AuditPage() {
  const { hasPermission } = useAuth()
  const { push } = useToast()
  const [page, setPage] = useState(1)
  const [module, setModule] = useState('')
  const [result, setResult] = useState('')
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [selected, setSelected] = useState<AuditEntry | null>(null)
  const [chain, setChain] = useState<{ valid: boolean; checked: number; message: string } | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search), 350)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => setPage(1), [module, result, debounced])

  const query = useQuery({
    queryKey: ['audit', { page, module, result, q: debounced }],
    queryFn: () =>
      auditApi.list({
        page,
        size: 20,
        module: module || undefined,
        result: result || undefined,
        q: debounced || undefined,
      }),
    placeholderData: (previous) => previous,
  })
  const modules = useQuery({ queryKey: ['audit-modules'], queryFn: auditApi.modules })

  const verify = useMutation({
    mutationFn: auditApi.verify,
    onSuccess: (data) => {
      setChain(data)
      push(data.message, data.valid ? 'success' : 'error')
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  const exportAudit = useMutation({
    mutationFn: (format: 'csv' | 'xlsx') =>
      auditApi.export({ module: module || undefined, result: result || undefined, q: debounced || undefined }, format),
    onSuccess: (blob, format) => {
      downloadBlob(blob, `soc-lite-auditoria.${format}`)
      push('Exportación generada', 'success')
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Bitácora de auditoría"
        subtitle="Registro append-only de entradas y salidas por módulo, con usuario, fecha, hora, acción y cadena de hashes."
        actions={
          <>
            <button className="btn-secondary" onClick={() => verify.mutate()} disabled={verify.isPending}>
              {verify.isPending ? <Loader2 size={15} className="animate-spin" /> : <Fingerprint size={15} />}
              Verificar cadena
            </button>
            {hasPermission('audit:export') && (
              <>
                <button
                  className="btn-secondary"
                  onClick={() => exportAudit.mutate('csv')}
                  disabled={exportAudit.isPending}
                >
                  <Download size={15} /> CSV
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => exportAudit.mutate('xlsx')}
                  disabled={exportAudit.isPending}
                >
                  <FileSpreadsheet size={15} /> Excel
                </button>
              </>
            )}
          </>
        }
      />

      {chain && (
        <div
          className={`mb-4 flex items-center gap-3 border px-4 py-3 text-sm ${
            chain.valid
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
              : 'border-rose-500/30 bg-rose-500/10 text-rose-200'
          }`}
        >
          {chain.valid ? <ShieldCheck size={17} /> : <ShieldAlert size={17} />}
          <span>
            {chain.message} · {formatNumber(chain.checked)} eventos verificados
          </span>
        </div>
      )}

      <div className="card mb-4 flex flex-col gap-3 p-4 lg:flex-row lg:items-center">
        <select className="input lg:w-48" value={module} onChange={(event) => setModule(event.target.value)}>
          <option value="">Todos los módulos</option>
          {(modules.data ?? []).map((item) => (
            <option key={item.module} value={item.module}>
              {item.module} ({item.total})
            </option>
          ))}
        </select>
        <select className="input lg:w-40" value={result} onChange={(event) => setResult(event.target.value)}>
          <option value="">Todo resultado</option>
          <option value="success">Éxito</option>
          <option value="failure">Fallo</option>
          <option value="denied">Denegado</option>
        </select>
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            className="input pl-9"
            placeholder="Buscar usuario, entidad o request-id…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      {query.isError && <ErrorBanner message={apiErrorMessage(query.error)} />}

      <div className="card overflow-hidden">
        {query.isLoading ? (
          <Spinner label="Consultando bitácora…" />
        ) : (query.data?.items ?? []).length === 0 ? (
          <EmptyState title="Sin eventos" description="No hay registros que coincidan con el filtro." icon={ScrollText} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="table min-w-[1080px]">
                <thead>
                  <tr>
                    <th>Fecha y hora</th>
                    <th>Usuario</th>
                    <th>Módulo</th>
                    <th>Acción</th>
                    <th>Entidad</th>
                    <th>Resultado</th>
                    <th>IP</th>
                    <th>Duración</th>
                    <th>Hash</th>
                  </tr>
                </thead>
                <tbody>
                  {(query.data?.items ?? []).map((entry) => (
                    <tr key={entry.id} className="cursor-pointer" onClick={() => setSelected(entry)}>
                      <td className="whitespace-nowrap font-mono text-[11px] text-slate-400">
                        {formatDate(entry.occurred_at)}
                      </td>
                      <td className="text-xs text-slate-300">
                        {entry.username ?? <span className="text-slate-600">sistema</span>}
                      </td>
                      <td>
                        <span className="chip border-base-700 bg-ink/[0.03] text-slate-300">{entry.module}</span>
                      </td>
                      <td className="font-mono text-[11px] text-accent">{entry.action}</td>
                      <td className="max-w-[220px] truncate text-xs text-slate-500">
                        {entry.entity_type ? `${entry.entity_type}:${entry.entity_id ?? ''}` : '—'}
                      </td>
                      <td>
                        <span className={`chip ${RESULT_STYLES[entry.result]}`}>{entry.result}</span>
                      </td>
                      <td className="font-mono text-[11px] text-slate-500">{entry.ip ?? '—'}</td>
                      <td className="font-mono text-[11px] text-slate-500">
                        {entry.duration_ms !== null ? `${entry.duration_ms} ms` : '—'}
                      </td>
                      <td className="font-mono text-[10px] text-slate-600">
                        {entry.hash ? `${entry.hash.slice(0, 10)}…` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pages={query.data?.pages ?? 1} total={query.data?.total ?? 0} onPage={setPage} />
          </>
        )}
      </div>

      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={`Evento #${selected?.id ?? ''}`}
        description={selected ? `${selected.module} · ${selected.action}` : ''}
        width="max-w-2xl"
      >
        {selected && (
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-3">
              {[
                ['Fecha y hora', formatDate(selected.occurred_at)],
                ['Usuario', selected.username ?? 'sistema'],
                ['Módulo', selected.module],
                ['Acción', selected.action],
                ['Resultado', selected.result],
                ['IP', selected.ip ?? '—'],
                ['Request ID', selected.request_id ?? '—'],
                ['Duración', selected.duration_ms !== null ? `${selected.duration_ms} ms` : '—'],
                ['Entidad', `${selected.entity_type ?? '—'}:${selected.entity_id ?? ''}`],
                ['User agent', selected.user_agent ?? '—'],
              ].map(([label, value]) => (
                <div key={label}>
                  <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
                  <p className="mt-0.5 break-all font-mono text-slate-300">{value}</p>
                </div>
              ))}
            </div>
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">Detalle</p>
              <pre className="max-h-64 overflow-auto border border-base-700 bg-base-950 p-3 font-mono text-[11px] text-slate-400">
                {JSON.stringify(selected.detail, null, 2)}
              </pre>
            </div>
            <div className="flex items-start gap-2 border border-emerald-500/20 bg-emerald-500/5 p-3 text-emerald-200">
              <BadgeCheck size={15} className="mt-0.5 shrink-0" />
              <div>
                <p className="text-[10px] uppercase tracking-wider text-emerald-400/80">Hash del evento</p>
                <p className="break-all font-mono text-[10px]">{selected.hash ?? '—'}</p>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
