import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  ArrowUpRight,
  Clock3,
  Gauge,
  RefreshCw,
  ShieldAlert,
  Siren,
  Target,
  Timer,
  TrendingDown,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { alertsApi, dashboardApi } from '../api'
import { apiErrorMessage } from '../api/client'
import { SeverityBadge, StatusBadge, VerdictBadge } from '../components/Badges'
import { EmptyState, ErrorBanner, KpiCard, Spinner } from '../components/ui'
import {
  formatDate,
  formatMinutes,
  formatNumber,
  formatShortDate,
  SEVERITY_HEX,
  SEVERITY_LABELS,
  SEVERITY_ORDER,
  truncate,
} from '../lib/format'

const PERIODS = [7, 30, 90]

function Panel({ title, subtitle, index, children }: { title: string; subtitle: string; index: string; children: ReactNode }) {
  return (
    <section className="card flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-base-700 px-5 py-4">
        <div><h2 className="section-title">{title}</h2><p className="mt-1 text-xs text-slate-500">{subtitle}</p></div>
        <span className="eyebrow pt-0.5">{index}</span>
      </div>
      <div className="flex-1 p-5">{children}</div>
    </section>
  )
}

function QueryContent({ loading, error, empty, children, emptyTitle = 'Sin datos en este periodo', emptyDescription = 'Selecciona un periodo más amplio para consultar el historial.' }: { loading: boolean; error: unknown; empty: boolean; children: ReactNode; emptyTitle?: string; emptyDescription?: string }) {
  if (loading) return <Spinner label="Cargando datos…" />
  if (error) return <ErrorBanner message={apiErrorMessage(error)} />
  if (empty) return <EmptyState title={emptyTitle} description={emptyDescription} />
  return <>{children}</>
}

export default function DashboardPage() {
  const [days, setDays] = useState(30)

  const summary = useQuery({
    queryKey: ['dashboard', days, 'summary'],
    queryFn: () => dashboardApi.summary(days),
  })
  const trend = useQuery({
    queryKey: ['dashboard', days, 'trend'],
    queryFn: () => dashboardApi.trend(days),
  })
  const severity = useQuery({
    queryKey: ['dashboard', days, 'severity'],
    queryFn: () => dashboardApi.severity(days),
  })
  const topSources = useQuery({
    queryKey: ['dashboard', days, 'sources'],
    queryFn: () => dashboardApi.topSources(days),
  })
  const mttt = useQuery({
    queryKey: ['dashboard', days, 'mttt'],
    queryFn: () => dashboardApi.mttt(days),
  })
  const fp = useQuery({
    queryKey: ['dashboard', days, 'fp'],
    queryFn: () => dashboardApi.fpRate(days),
  })
  const recent = useQuery({
    queryKey: ['alerts', 'recent'],
    queryFn: () => alertsApi.list({ size: 6, sort: '-received_at' }),
  })

  const data = summary.data
  const fetching = [summary, trend, severity, topSources, mttt, fp, recent].some((query) => query.isFetching)
  const severityTotal = (severity.data ?? []).reduce((total, item) => total + item.count, 0)
  const refreshAll = () => {
    void summary.refetch()
    void trend.refetch()
    void severity.refetch()
    void topSources.refetch()
    void mttt.refetch()
    void fp.refetch()
    void recent.refetch()
  }

  return (
    <div className="animate-fade-up space-y-6">
      <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
        <div>
          <p className="eyebrow mb-3">Operaciones / Vista general</p>
          <h1 className="text-3xl font-semibold tracking-[-0.035em] text-ink sm:text-4xl">El pulso de tu SOC.</h1>
          <p className="mt-2 text-sm text-slate-400">Señales, prioridades y tiempos de respuesta en un solo lugar.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex border border-base-700 bg-base-900 p-1" role="group" aria-label="Periodo del dashboard">
            {PERIODS.map((value) => (
              <button key={value} type="button" onClick={() => setDays(value)} aria-pressed={days === value}
                className={`px-3 py-2 text-xs font-medium transition-colors ${days === value ? 'bg-accent text-base-950' : 'text-slate-500 hover:bg-accent/5 hover:text-accent'}`}>
                {value} días
              </button>
            ))}
          </div>
          <button type="button" onClick={refreshAll} className="btn-secondary !py-3" disabled={fetching} aria-label="Actualizar métricas">
            <RefreshCw size={14} className={fetching ? 'animate-spin' : ''} /><span className="hidden sm:inline">Actualizar</span>
          </button>
        </div>
      </div>

      {summary.isError && <ErrorBanner message={apiErrorMessage(summary.error)} />}
      {summary.isLoading && <Spinner label="Preparando tu resumen operativo…" />}

      {data && (
        <>
          <div className="flex flex-col justify-between gap-4 border border-accent/25 border-l-[3px] border-l-accent bg-accent/5 px-5 py-4 sm:flex-row sm:items-center">
            <div className="flex items-start gap-3">
              <ShieldAlert size={19} className="mt-0.5 shrink-0 text-accent" />
              <div>
                <p className="text-sm font-medium text-ink">{data.totals.pending > 0 ? `${formatNumber(data.totals.pending)} alertas esperan triaje` : 'Sin alertas pendientes en el periodo'}</p>
                <p className="mt-1 text-xs text-slate-400">{formatNumber(data.totals.critical)} críticas y {formatNumber(data.totals.high)} altas recibidas en los últimos {days} días.</p>
              </div>
            </div>
            <Link to="/alerts" className="flex shrink-0 items-center gap-2 text-xs font-semibold text-accent hover:underline">Abrir cola de alertas <ArrowUpRight size={15} /></Link>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Alertas recibidas" value={formatNumber(data.totals.alerts)} hint={`Últimos ${days} días`} icon={ShieldAlert} tone="accent" delta={data.deltas.alerts_pct} />
            <KpiCard label="Tiempo medio de triaje" value={formatMinutes(data.mttt.avg_minutes)} hint={`P95 ${formatMinutes(data.mttt.p95_minutes)} · objetivo ${data.mttt.target_minutes} min`} icon={Timer} tone="violet" delta={data.deltas.mttt_pct} />
            <KpiCard label="Falsos positivos" value={`${data.rates.false_positive.toFixed(1)}%`} hint={`${formatNumber(data.totals.false_positive)} de ${formatNumber(data.totals.triaged)} triajes`} icon={Target} tone="amber" />
            <KpiCard label="Cumplimiento SLA" value={`${data.rates.sla_compliance.toFixed(1)}%`} hint="Triajes dentro del tiempo objetivo" icon={Gauge} tone="emerald" />
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <Panel title="Evolución de alertas" subtitle={`Volumen diario · últimos ${days} días`} index="01">
              <QueryContent loading={trend.isLoading} error={trend.error} empty={!trend.data?.length}>
                <div className="mb-4 flex flex-wrap gap-5 text-[11px] text-slate-500">
                  <span className="flex items-center gap-2"><span className="h-0.5 w-5 bg-accent" />Total de alertas</span>
                  <span className="flex items-center gap-2"><span className="h-0.5 w-5 bg-rose-400" />Críticas</span>
                </div>
                <div className="h-[280px]" role="img" aria-label="Gráfico de evolución diaria del total de alertas y alertas críticas">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={trend.data ?? []} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
                      <defs><linearGradient id="totalFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="rgb(var(--accent))" stopOpacity={0.16} /><stop offset="100%" stopColor="rgb(var(--accent))" stopOpacity={0.01} /></linearGradient></defs>
                      <CartesianGrid stroke="var(--chart-grid)" vertical={false} strokeDasharray="3 4" />
                      <XAxis dataKey="date" tickFormatter={formatShortDate} tick={{ fill: 'var(--chart-label)', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={26} dy={8} />
                      <YAxis tick={{ fill: 'var(--chart-label)', fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <Tooltip labelFormatter={(value) => formatDate(String(value))} contentStyle={{ fontSize: 12 }} />
                      <Area type="monotone" dataKey="total" name="Total" stroke="rgb(var(--accent))" strokeWidth={2} fill="url(#totalFill)" />
                      <Area type="monotone" dataKey="critical" name="Críticas" stroke="var(--chart-critical)" strokeWidth={1.5} fill="transparent" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </QueryContent>
            </Panel>

            <Panel title="Mapa de severidad" subtitle="Distribución de las alertas del periodo" index="02">
              <QueryContent loading={severity.isLoading} error={severity.error} empty={severityTotal === 0}>
                <div className="mb-6 flex items-baseline gap-2"><span className="text-3xl font-semibold tracking-tight text-ink">{formatNumber(severityTotal)}</span><span className="text-xs text-slate-500">alertas registradas</span></div>
                <div className="space-y-5">
                  {SEVERITY_ORDER.map((level) => {
                    const count = severity.data?.find((item) => item.severity === level)?.count ?? 0
                    const percent = severityTotal ? count / severityTotal * 100 : 0
                    return (
                      <div key={level}>
                        <div className="mb-2 flex items-center justify-between text-xs"><span className="text-slate-300">{SEVERITY_LABELS[level]}</span><span className="font-mono text-slate-400">{formatNumber(count)}<span className="ml-3 text-slate-500">{percent.toFixed(0)}%</span></span></div>
                        <div className="h-1.5 bg-base-800"><div className="h-full" style={{ width: `${percent}%`, background: SEVERITY_HEX[level] }} /></div>
                      </div>
                    )
                  })}
                </div>
              </QueryContent>
            </Panel>
          </div>

          <div className="grid grid-cols-1 gap-px border border-base-700 bg-base-700 md:grid-cols-3">
            {[
              { label: 'Alertas triadas', value: formatNumber(data.totals.triaged), detail: `${data.rates.automation.toFixed(1)}% de automatización`, icon: Activity },
              { label: 'Incidentes abiertos', value: formatNumber(data.totals.incidents_open), detail: 'Seguimiento del equipo SOC', icon: Siren },
              { label: 'Revisión humana', value: `${data.rates.human_review.toFixed(1)}%`, detail: 'Triajes que requieren validación', icon: TrendingDown },
            ].map((item) => (
              <div key={item.label} className="flex items-start gap-4 bg-base-900 p-5">
                <item.icon size={18} className="mt-1 text-accent" />
                <div className="min-w-0 flex-1"><p className="eyebrow">{item.label}</p><p className="mt-1 text-xs text-slate-500">{item.detail}</p></div>
                <span className="text-xl font-semibold tracking-tight text-ink">{item.value}</span>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <Panel title="Principales orígenes" subtitle="Direcciones IP con mayor actividad" index="03">
              <QueryContent loading={topSources.isLoading} error={topSources.error} empty={!topSources.data?.length}>
                <div className="h-[250px]" role="img" aria-label="Gráfico de las seis direcciones IP con más alertas">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={(topSources.data ?? []).slice(0, 6)} layout="vertical" margin={{ left: 0, right: 8 }}>
                      <CartesianGrid stroke="var(--chart-grid)" horizontal={false} strokeDasharray="3 4" />
                      <XAxis type="number" hide />
                      <YAxis type="category" dataKey="label" width={110} tick={{ fill: 'var(--chart-label)', fontSize: 10, fontFamily: 'Adwaita Mono, monospace' }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={{ fontSize: 12 }} />
                      <Bar dataKey="count" name="Alertas" fill="rgb(var(--accent))" barSize={12} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </QueryContent>
            </Panel>

            <Panel title="Tiempos de respuesta" subtitle="MTTT promedio / objetivo por severidad" index="04">
              <QueryContent loading={mttt.isLoading} error={mttt.error} empty={!mttt.data?.length}>
                <div className="space-y-5">
                  {(mttt.data ?? []).map((row) => (
                    <div key={row.severity}>
                      <div className="mb-2 flex items-center justify-between gap-2 text-xs"><span className="text-slate-300">{SEVERITY_LABELS[row.severity]}</span><span className="font-mono text-[10px] text-slate-400">{formatMinutes(row.avg_minutes)} / {row.target_minutes} min</span></div>
                      <div className="h-1.5 bg-base-800"><div className="h-full" style={{ width: `${Math.min(Math.max(row.compliance, 0), 100)}%`, background: row.compliance >= 90 ? '#189b78' : row.compliance >= 60 ? 'var(--chart-warning)' : 'var(--chart-critical)' }} /></div>
                      <p className="mt-1.5 text-[10px] text-slate-500">{row.count} triajes · {row.compliance.toFixed(0)}% dentro del SLA</p>
                    </div>
                  ))}
                </div>
              </QueryContent>
            </Panel>

            <Panel title="Calidad del veredicto" subtitle="Tasa diaria de falsos positivos" index="05">
              <QueryContent loading={fp.isLoading} error={fp.error} empty={!fp.data?.length}>
                <div className="h-[250px]" role="img" aria-label="Gráfico del porcentaje de falsos positivos por día">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={fp.data ?? []} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                      <CartesianGrid stroke="var(--chart-grid)" vertical={false} strokeDasharray="3 4" />
                      <XAxis dataKey="date" tickFormatter={formatShortDate} tick={{ fill: 'var(--chart-label)', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={28} dy={8} />
                      <YAxis tick={{ fill: 'var(--chart-label)', fontSize: 10 }} axisLine={false} tickLine={false} unit="%" />
                      <Tooltip formatter={(value: number) => [`${value}%`, 'Tasa FP']} labelFormatter={(value) => formatDate(String(value))} contentStyle={{ fontSize: 12 }} />
                      <Line type="monotone" dataKey="rate" stroke="var(--chart-warning)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </QueryContent>
            </Panel>
          </div>
        </>
      )}

      <section className="card overflow-hidden">
        <div className="flex items-center justify-between gap-4 border-b border-base-700 px-5 py-4">
          <div><h2 className="section-title">Últimas señales</h2><p className="mt-1 text-xs text-slate-500">Los seis eventos más recientes de la cola global</p></div>
          <Link to="/alerts" className="flex items-center gap-2 text-xs font-medium text-accent hover:underline">Ver alertas <ArrowUpRight size={14} /></Link>
        </div>
        <QueryContent loading={recent.isLoading} error={recent.error} empty={!recent.data?.items.length} emptyTitle="No hay alertas registradas" emptyDescription="Los nuevos eventos aparecerán aquí cuando se reciban.">
          <div className="overflow-x-auto">
            <table className="table">
              <caption className="sr-only">Últimas alertas con severidad, origen, activo, veredicto y estado</caption>
              <thead><tr>{['Severidad', 'Alerta', 'Origen', 'Activo', 'Veredicto', 'Estado', 'Recibida'].map((heading) => <th scope="col" key={heading}>{heading}</th>)}</tr></thead>
              <tbody>
                {(recent.data?.items ?? []).map((alert) => (
                  <tr key={alert.id}>
                    <td><SeverityBadge severity={alert.severity} /></td>
                    <td className="max-w-[360px]"><Link to={`/alerts/${alert.id}`} className="block hover:text-accent"><p className="truncate font-medium">{truncate(alert.description, 80)}</p><span className="mt-1 block font-mono text-[10px] text-slate-500">{alert.rule_id ?? 'regla'} · nivel {alert.rule_level ?? '—'}</span></Link></td>
                    <td className="font-mono text-xs">{alert.src_ip ?? '—'}</td>
                    <td className="text-xs">{alert.agent_name ?? '—'}</td>
                    <td>{alert.verdict ? <VerdictBadge verdict={alert.verdict} /> : <span className="text-xs text-slate-500">Pendiente</span>}</td>
                    <td><StatusBadge status={alert.status} /></td>
                    <td className="whitespace-nowrap text-xs">{formatDate(alert.received_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryContent>
      </section>
      {data && <p className="flex items-center gap-2 text-[10px] text-slate-500"><Clock3 size={12} /> Última consulta: {formatDate(data.generated_at)} · Periodo de {days} días</p>}
    </div>
  )
}
