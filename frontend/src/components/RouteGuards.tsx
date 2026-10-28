import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ShieldX } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { Spinner } from './ui'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Validando sesión…" />
      </div>
    )
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}

export function PermissionGate({
  permission,
  children,
  fallback = null,
}: {
  permission: string
  children: ReactNode
  fallback?: ReactNode
}) {
  const { hasPermission } = useAuth()
  return hasPermission(permission) ? <>{children}</> : <>{fallback}</>
}

export function AccessDenied() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <div className="border border-rose-500/30 bg-rose-500/10 p-4 text-rose-300">
        <ShieldX size={26} />
      </div>
      <h1 className="text-lg font-semibold text-ink">Acceso restringido</h1>
      <p className="max-w-md text-sm text-slate-400">
        Su rol no tiene el permiso necesario para ver este módulo. Solicite acceso al administrador
        del SOC; la consulta quedó registrada en la bitácora.
      </p>
    </div>
  )
}
