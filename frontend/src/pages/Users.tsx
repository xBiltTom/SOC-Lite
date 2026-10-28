import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Loader2, Lock, Pencil, Search, UserPlus, UserX, Users } from 'lucide-react'
import { rolesApi, usersApi } from '../api'
import { apiErrorMessage } from '../api/client'
import { EmptyState, ErrorBanner, Modal, PageHeader, Pagination, Spinner } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { formatDate, initials } from '../lib/format'
import type { User } from '../types'

interface FormState {
  username: string
  full_name: string
  email: string
  password: string
  role_id: number
  is_active: boolean
}

const EMPTY: FormState = {
  username: '',
  full_name: '',
  email: '',
  password: '',
  role_id: 3,
  is_active: true,
}

export default function UsersPage() {
  const { hasPermission, user: currentUser } = useAuth()
  const { push } = useToast()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [mode, setMode] = useState<'create' | 'edit' | null>(null)
  const [selected, setSelected] = useState<User | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY)
  const [resetUser, setResetUser] = useState<User | null>(null)
  const [newPassword, setNewPassword] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search), 350)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => setPage(1), [debounced, roleFilter])

  const users = useQuery({
    queryKey: ['users', { page, q: debounced, role: roleFilter }],
    queryFn: () =>
      usersApi.list({ page, size: 12, q: debounced || undefined, role: roleFilter || undefined }),
    placeholderData: (previous) => previous,
  })
  const roles = useQuery({ queryKey: ['roles'], queryFn: rolesApi.list })

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ['users'] })

  const save = useMutation({
    mutationFn: async () => {
      if (mode === 'edit' && selected) {
        return usersApi.update(selected.id, {
          full_name: form.full_name,
          email: form.email,
          role_id: form.role_id,
          is_active: form.is_active,
        })
      }
      return usersApi.create({
        username: form.username,
        email: form.email,
        full_name: form.full_name,
        password: form.password,
        role_id: form.role_id,
        is_active: form.is_active,
      })
    },
    onSuccess: () => {
      push(mode === 'edit' ? 'Usuario actualizado' : 'Usuario creado', 'success')
      setMode(null)
      setSelected(null)
      setForm(EMPTY)
      invalidate()
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  const deactivate = useMutation({
    mutationFn: (id: string) => usersApi.deactivate(id),
    onSuccess: () => {
      push('Usuario desactivado', 'success')
      invalidate()
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  const reset = useMutation({
    mutationFn: () => usersApi.resetPassword(resetUser!.id, newPassword),
    onSuccess: () => {
      push('Contraseña restablecida; sesiones revocadas', 'success')
      setResetUser(null)
      setNewPassword('')
    },
    onError: (error) => push(apiErrorMessage(error), 'error'),
  })

  const openCreate = () => {
    setMode('create')
    setForm({ ...EMPTY, role_id: roles.data?.find((role) => role.code === 'analyst')?.id ?? 3 })
  }

  const openEdit = (user: User) => {
    setMode('edit')
    setSelected(user)
    setForm({
      username: user.username,
      full_name: user.full_name,
      email: user.email,
      password: '',
      role_id: user.role.id,
      is_active: user.is_active,
    })
  }

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Usuarios"
        subtitle="Cuentas, roles asignados y estado de acceso. Toda modificación queda auditada."
        actions={
          hasPermission('users:create') && (
            <button className="btn-primary" onClick={openCreate}>
              <UserPlus size={15} /> Nuevo usuario
            </button>
          )
        }
      />

      <div className="card mb-4 flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            className="input pl-9"
            placeholder="Buscar por nombre, usuario o correo…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <select className="input sm:w-52" value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
          <option value="">Todos los roles</option>
          {(roles.data ?? []).map((role) => (
            <option key={role.id} value={role.code}>
              {role.name}
            </option>
          ))}
        </select>
      </div>

      {users.isError && <ErrorBanner message={apiErrorMessage(users.error)} />}

      <div className="card overflow-hidden">
        {users.isLoading ? (
          <Spinner label="Cargando usuarios…" />
        ) : (users.data?.items ?? []).length === 0 ? (
          <EmptyState title="Sin usuarios" description="Cree la primera cuenta para el equipo." icon={Users} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="table min-w-[900px]">
                <thead>
                  <tr>
                    <th>Usuario</th>
                    <th>Correo</th>
                    <th>Rol</th>
                    <th>Estado</th>
                    <th>Último acceso</th>
                    <th>Creado</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {(users.data?.items ?? []).map((user) => (
                    <tr key={user.id}>
                      <td>
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center border border-accent/20 bg-accent/10 text-[10px] font-semibold text-accent">
                            {initials(user.full_name)}
                          </div>
                          <div>
                            <p className="text-sm text-slate-200">
                              {user.full_name}
                              {user.id === currentUser?.id && (
                                <span className="ml-2 text-[10px] text-slate-500">(usted)</span>
                              )}
                            </p>
                            <p className="font-mono text-[11px] text-slate-500">@{user.username}</p>
                          </div>
                        </div>
                      </td>
                      <td className="text-xs text-slate-400">{user.email}</td>
                      <td>
                        <span className="chip border-base-700 bg-ink/[0.03] text-slate-300">
                          {user.role.name}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`chip ${
                            user.is_active
                              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                              : 'border-slate-500/30 bg-slate-500/10 text-slate-400'
                          }`}
                        >
                          {user.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                      </td>
                      <td className="text-xs text-slate-500">{formatDate(user.last_login_at)}</td>
                      <td className="text-xs text-slate-500">{formatDate(user.created_at)}</td>
                      <td>
                        <div className="flex items-center gap-1">
                          {hasPermission('users:update') && (
                            <>
                              <button
                                onClick={() => openEdit(user)}
                                className="p-1.5 text-slate-500 hover:bg-ink/5 hover:text-accent"
                                aria-label="Editar"
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                onClick={() => setResetUser(user)}
                                className="p-1.5 text-slate-500 hover:bg-ink/5 hover:text-amber-300"
                                aria-label="Restablecer contraseña"
                              >
                                <KeyRound size={14} />
                              </button>
                            </>
                          )}
                          {hasPermission('users:delete') && user.is_active && user.id !== currentUser?.id && (
                            <button
                              onClick={() => {
                                if (window.confirm(`¿Desactivar la cuenta de ${user.full_name}?`)) {
                                  deactivate.mutate(user.id)
                                }
                              }}
                              className="p-1.5 text-slate-500 hover:bg-rose-500/10 hover:text-rose-300"
                              aria-label="Desactivar"
                            >
                              <UserX size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              pages={users.data?.pages ?? 1}
              total={users.data?.total ?? 0}
              onPage={setPage}
            />
          </>
        )}
      </div>

      <Modal
        open={mode !== null}
        onClose={() => setMode(null)}
        title={mode === 'edit' ? 'Editar usuario' : 'Nuevo usuario'}
        description="La asignación de rol determina los permisos efectivos (RBAC)."
        footer={
          <>
            <button className="btn-secondary" onClick={() => setMode(null)}>
              Cancelar
            </button>
            <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? <Loader2 size={15} className="animate-spin" /> : <UserPlus size={15} />}
              {mode === 'edit' ? 'Guardar cambios' : 'Crear usuario'}
            </button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="label">Nombre completo</label>
            <input
              className="input"
              value={form.full_name}
              onChange={(event) => setForm({ ...form, full_name: event.target.value })}
              placeholder="Nombre y apellidos"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Usuario</label>
              <input
                className="input font-mono"
                value={form.username}
                disabled={mode === 'edit'}
                onChange={(event) => setForm({ ...form, username: event.target.value })}
                placeholder="analista3"
              />
            </div>
            <div>
              <label className="label">Correo</label>
              <input
                className="input"
                type="email"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
                placeholder="usuario@empresa.com"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Rol</label>
              <select
                className="input"
                value={form.role_id}
                onChange={(event) => setForm({ ...form, role_id: Number(event.target.value) })}
              >
                {(roles.data ?? []).map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Estado</label>
              <select
                className="input"
                value={form.is_active ? '1' : '0'}
                onChange={(event) => setForm({ ...form, is_active: event.target.value === '1' })}
              >
                <option value="1">Activo</option>
                <option value="0">Inactivo</option>
              </select>
            </div>
          </div>
          {mode === 'create' && (
            <div>
              <label className="label">Contraseña inicial</label>
              <div className="relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  className="input pl-9"
                  type="password"
                  value={form.password}
                  onChange={(event) => setForm({ ...form, password: event.target.value })}
                  placeholder="Mínimo 10 caracteres, mayúscula, dígito y símbolo"
                />
              </div>
            </div>
          )}
          <p className="border border-base-700 bg-ink/[0.02] p-3 text-[11px] leading-relaxed text-slate-500">
            El alta, la baja y el cambio de rol se registran en la bitácora con usuario, fecha, hora,
            IP y resultado.
          </p>
        </div>
      </Modal>

      <Modal
        open={Boolean(resetUser)}
        onClose={() => setResetUser(null)}
        title="Restablecer contraseña"
        description={resetUser ? `Se revocarán todas las sesiones de ${resetUser.full_name}.` : ''}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setResetUser(null)}>
              Cancelar
            </button>
            <button className="btn-primary" onClick={() => reset.mutate()} disabled={reset.isPending}>
              {reset.isPending ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />}
              Restablecer
            </button>
          </>
        }
      >
        <label className="label">Nueva contraseña</label>
        <input
          className="input"
          type="password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          placeholder="Mínimo 10 caracteres, mayúscula, dígito y símbolo"
        />
      </Modal>
    </div>
  )
}
