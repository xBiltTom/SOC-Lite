import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { AccessDenied, PermissionGate, ProtectedRoute } from './components/RouteGuards'
import AlertDetailPage from './pages/AlertDetail'
import AlertsPage from './pages/Alerts'
import AuditPage from './pages/Audit'
import DashboardPage from './pages/Dashboard'
import IncidentsPage from './pages/Incidents'
import LoginPage from './pages/Login'
import ReportsPage from './pages/Reports'
import RolesPage from './pages/Roles'
import UsersPage from './pages/Users'

function Guarded({ permission, children }: { permission: string; children: ReactNode }) {
  return (
    <PermissionGate permission={permission} fallback={<AccessDenied />}>
      {children}
    </PermissionGate>
  )
}

function NotFound() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-3 text-center">
      <p className="font-mono text-5xl font-semibold text-accent">404</p>
      <h1 className="text-lg font-semibold text-ink">Página no encontrada</h1>
      <p className="max-w-sm text-sm text-slate-500">
        La ruta solicitada no existe en la consola de SOC-Lite.
      </p>
      <a href="/" className="btn-primary mt-2">
        Volver al panel
      </a>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route
          index
          element={
            <Guarded permission="dashboard:read">
              <DashboardPage />
            </Guarded>
          }
        />
        <Route
          path="alerts"
          element={
            <Guarded permission="alerts:read">
              <AlertsPage />
            </Guarded>
          }
        />
        <Route
          path="alerts/:id"
          element={
            <Guarded permission="alerts:read">
              <AlertDetailPage />
            </Guarded>
          }
        />
        <Route
          path="incidents"
          element={
            <Guarded permission="incidents:read">
              <IncidentsPage />
            </Guarded>
          }
        />
        <Route
          path="users"
          element={
            <Guarded permission="users:read">
              <UsersPage />
            </Guarded>
          }
        />
        <Route
          path="roles"
          element={
            <Guarded permission="roles:read">
              <RolesPage />
            </Guarded>
          }
        />
        <Route
          path="audit"
          element={
            <Guarded permission="audit:read">
              <AuditPage />
            </Guarded>
          }
        />
        <Route
          path="reports"
          element={
            <Guarded permission="reports:read">
              <ReportsPage />
            </Guarded>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
