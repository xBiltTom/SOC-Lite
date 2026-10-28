import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Loader2, Lock, Save, ShieldCheck, Users } from 'lucide-react'
import clsx from 'clsx'
import { rolesApi } from '../api'
import { apiErrorMessage } from '../api/client'
import { ErrorBanner, PageHeader, Spinner } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

const MODULE_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  alerts: 'Alertas',
  triage: 'Triaje',
  incidents: 'Incidentes',
  users: 'Usuarios',
  roles: 'Roles',
  audit: 'Auditoría',
  reports: 'Reportes',
}

const ACTION_LABELS: Record<string, string> = {
  read: 'Ver',
  create: 'Crear',
  update: 'Editar',
  delete: 'Eliminar',
  export: 'Exportar',
  run: 'Ejecutar',
  feedback: 'Validar',
  close: 'Cerrar',
}

export default function RolesPage() {
  const { hasPermission } = useAuth()
  const { push } = useToast()
  const queryClient = useQueryClient()
  const roles = useQuery({ queryKey: ['roles'], queryFn: rolesApi.list })
  const permissions = useQuery({ queryKey: ['permissions'], queryFn: rolesApi.permissions })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [codes, setCodes] = useState<string[]>([])

  const selected = useMemo(
    () => roles.data?.find((role) => role.id === selectedId) ?? roles.data?.[0],
    [roles.data, selectedId],
  )

  useEffect(() => {
    if (selected) setCodes(selected.permissions.map((permission) => permission.code))
  }, [selected])

  const grouped = useMemo(() => {
    const map = new Map<string, { code: string; action: string; description?: string | null }[]>()
    for (const permission of permissions.data ?? []) {
      const list = map.get(permission.module) ?? []
      list.push(permission)
      map.set(permission.module, list)
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [permissions.data])

  const save = useMutation({
    mutationFn: () => rolesApi.updatePermissions(selected!.id, codes),
    onSuccess: () => {
      push('Matriz de permisos actualizada', 'success')
      void queryClient.invalidateQueries({ queryKey: ['roles'] })
      void queryClient.invalidateQueries({ queryKey: ['permissions'] })
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  const toggle = (code: string) => {
    setCodes((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    )
  }

  if (roles.isLoading) return <Spinner label="Cargando matriz de permisos…" />
  if (roles.isError) return <ErrorBanner message={apiErrorMessage(roles.error)} />

  const immutable = selected?.code === 'admin'
  const dirty =
    selected && [...codes].sort().join('|') !== [...selected.permissions.map((item) => item.code)].sort().join('|')

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Roles y permisos"
        subtitle="Matriz RBAC: cada rol agrupa permisos módulo:acción que el backend valida en cada endpoint."
        actions={
          hasPermission('roles:update') && (
            <button
              className="btn-primary"
              disabled={!selected || immutable || !dirty || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
              Guardar matriz
            </button>
          )
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[300px_1fr]">
        <aside className="card h-fit overflow-hidden">
          <div className="border-b border-base-700 px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Roles</p>
          </div>
          <div className="p-2">
            {(roles.data ?? []).map((role) => (
              <button
                key={role.id}
                onClick={() => setSelectedId(role.id)}
                className={clsx(
                  'mb-1 flex w-full items-center gap-3 px-3 py-3 text-left transition',
                  selected?.id === role.id ? 'bg-accent/[0.08]' : 'hover:bg-ink/[0.03]',
                )}
              >
                <div
                  className={clsx(
                    'border p-2',
                    selected?.id === role.id
                      ? 'border-accent/30 bg-accent/10 text-accent'
                      : 'border-base-700 bg-ink/[0.02] text-slate-500',
                  )}
                >
                  <ShieldCheck size={15} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-slate-200">{role.name}</p>
                  <p className="font-mono text-[10px] text-slate-500">{role.code}</p>
                </div>
                <span className="flex items-center gap-1 text-[10px] text-slate-500">
                  <Users size={11} /> {role.user_count}
                </span>
              </button>
            ))}
          </div>
        </aside>

        <section className="card">
          <div className="flex items-start justify-between border-b border-base-700 px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-ink">{selected?.name ?? 'Seleccione un rol'}</h2>
              <p className="mt-0.5 text-xs text-slate-500">{selected?.description}</p>
            </div>
            <div className="text-right">
              <p className="font-mono text-lg text-ink">{codes.length}</p>
              <p className="text-[10px] uppercase tracking-wider text-slate-500">permisos</p>
            </div>
          </div>

          {immutable && (
            <div className="mx-5 mt-4 flex items-start gap-2 border border-amber-500/20 bg-amber-500/5 px-3 py-2.5 text-xs text-amber-200">
              <Lock size={14} className="mt-0.5" />
              El rol Administrador es inmutable para evitar bloquear el sistema. Use otro rol para
              delegar permisos.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2">
            {grouped.map(([module, items]) => (
              <div key={module} className="border border-base-700 bg-ink/[0.015] p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    {MODULE_LABELS[module] ?? module}
                  </p>
                  <span className="font-mono text-[10px] text-slate-600">{items.length}</span>
                </div>
                <div className="space-y-1">
                  {items.map((permission) => {
                    const active = codes.includes(permission.code)
                    return (
                      <label
                        key={permission.code}
                        className={clsx(
                          'flex cursor-pointer items-center gap-2.5 px-2 py-1.5 text-xs transition',
                          active ? 'bg-accent/[0.06] text-slate-200' : 'text-slate-500 hover:bg-ink/[0.03]',
                          immutable && 'cursor-not-allowed opacity-70',
                        )}
                      >
                        <span
                          className={clsx(
                            'flex h-4 w-4 items-center justify-center border',
                            active ? 'border-accent bg-accent text-base-950' : 'border-base-600',
                          )}
                        >
                          {active && <Check size={11} strokeWidth={3} />}
                        </span>
                        <input
                          type="checkbox"
                          className="sr-only"
                          checked={active}
                          disabled={immutable || !hasPermission('roles:update')}
                          onChange={() => toggle(permission.code)}
                        />
                        <span className="flex-1">{ACTION_LABELS[permission.action] ?? permission.action}</span>
                        <span className="font-mono text-[9px] text-slate-600">{permission.code}</span>
                      </label>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
