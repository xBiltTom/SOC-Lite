import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  ChevronDown,
  FileBarChart,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../context/AuthContext'
import { initials } from '../lib/format'
import ThemeToggle from './ThemeToggle'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  permission: string
  end?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Panel de control', icon: LayoutDashboard, permission: 'dashboard:read', end: true },
  { to: '/alerts', label: 'Alertas', icon: ShieldAlert, permission: 'alerts:read' },
  { to: '/incidents', label: 'Incidentes', icon: Siren, permission: 'incidents:read' },
  { to: '/users', label: 'Usuarios', icon: Users, permission: 'users:read' },
  { to: '/roles', label: 'Roles y permisos', icon: KeyRound, permission: 'roles:read' },
  { to: '/audit', label: 'Auditoría', icon: ScrollText, permission: 'audit:read' },
  { to: '/reports', label: 'Reportes', icon: FileBarChart, permission: 'reports:read' },
]

const TITLES: Record<string, string> = {
  '/': 'Panel de control',
  '/alerts': 'Alertas',
  '/incidents': 'Incidentes',
  '/users': 'Usuarios',
  '/roles': 'Roles y permisos',
  '/audit': 'Bitácora de auditoría',
  '/reports': 'Reportes',
}

function Clock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  return (
    <div className="hidden text-right lg:block">
      <p className="font-mono text-sm text-slate-200">
        {now.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })}
      </p>
      <p className="text-[10px] uppercase tracking-wider text-slate-500">
        {now.toLocaleDateString('es-PE', { weekday: 'short', day: '2-digit', month: 'short' })}
      </p>
    </div>
  )
}

export default function Layout() {
  const { user, logout, hasPermission } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)
  const mobileMenuRef = useRef<HTMLElement>(null)
  const menuTriggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const dismiss = (event: PointerEvent) => {
      if (!userMenuRef.current?.contains(event.target as Node)) setMenuOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('keydown', escape)
    }
  }, [menuOpen])

  useEffect(() => {
    if (!mobileOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    mobileMenuRef.current?.querySelector('button')?.focus()
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false)
      if (event.key !== 'Tab') return
      const controls = mobileMenuRef.current?.querySelectorAll<HTMLElement>('button, a[href]')
      if (!controls?.length) return
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKey)
      menuTriggerRef.current?.focus()
    }
  }, [mobileOpen])

  useEffect(() => {
    setMobileOpen(false)
    setMenuOpen(false)
  }, [location.pathname])

  const title =
    TITLES[location.pathname] ??
    (location.pathname.startsWith('/alerts/') ? 'Detalle de alerta' : 'SOC-Lite')
  const visibleNav = NAV.filter((item) => hasPermission(item.permission))

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-5 py-7">
        <div className="relative">
          <div className="border border-accent/30 bg-accent/10 p-2 text-accent">
            <ShieldCheck size={20} />
          </div>
        </div>
        <div>
          <p className="text-sm font-semibold tracking-tight text-ink">SOC / LITE</p>
          <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Centro de operaciones</p>
        </div>
      </div>

      <div className="mx-5 mb-5 border-b border-base-700 pb-5">
        <p className="eyebrow">Espacio de trabajo</p>
        <p className="mt-2 text-xs text-slate-400">Monitoreo y respuesta</p>
      </div>

      <nav aria-label="Navegación principal" className="flex-1 space-y-1 overflow-y-auto px-3">
        {visibleNav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              clsx(
                'group relative flex items-center gap-3 px-3 py-2.5 text-sm transition',
                isActive
                  ? 'bg-accent/[0.08] font-semibold text-accent'
                  : 'text-slate-400 hover:bg-accent/5 hover:text-accent',
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 bg-accent" />
                )}
                <item.icon
                  size={17}
                  className={isActive ? 'text-accent' : 'text-slate-500 group-hover:text-slate-300'}
                />
                <span className="flex-1">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-base-700 p-3">
        <div className="flex items-center gap-3 px-2 py-2">
          <div className="flex h-9 w-9 items-center justify-center border border-accent/25 bg-accent/10 text-xs font-semibold text-accent">
            {initials(user?.full_name)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-200">{user?.full_name}</p>
            <p className="truncate text-[11px] text-slate-500">{user?.role.name}</p>
          </div>
          <button
            onClick={() => void logout().then(() => navigate('/login'))}
            className="p-1.5 text-slate-500 hover:bg-rose-500/10 hover:text-rose-300"
            title="Cerrar sesión"
            aria-label="Cerrar sesión"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[236px] border-r border-base-700 bg-base-900 lg:block">
        {sidebar}
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-base-950/80 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <aside ref={mobileMenuRef} id="mobile-navigation" role="dialog" aria-modal="true" aria-label="Menú de navegación" className="absolute inset-y-0 left-0 w-[280px] animate-fade-up border-r border-base-700 bg-base-900">
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute right-3 top-4 p-1 text-slate-400"
              aria-label="Cerrar menú"
            >
              <X size={18} />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="lg:pl-[236px]">
        <header className="sticky top-0 z-20 flex h-20 items-center justify-between gap-4 border-b border-base-700 bg-base-900 px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              className="btn-ghost h-9 w-9 !p-0 lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Abrir menú"
              aria-expanded={mobileOpen}
              aria-controls="mobile-navigation"
              ref={menuTriggerRef}
            >
              <Menu size={18} />
            </button>
            <div>
              <p className="text-[10px] uppercase tracking-[0.2em] text-slate-600">SOC-Lite</p>
              <h2 className="text-sm font-medium text-slate-200">{title}</h2>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Clock />
            <div ref={userMenuRef} className="relative">
              <button
                onClick={() => setMenuOpen((open) => !open)}
                aria-label="Menú de usuario"
                aria-expanded={menuOpen}
                className="flex items-center gap-2 border border-base-700 bg-ink/[0.02] px-2 py-1.5"
              >
                <span className="flex h-7 w-7 items-center justify-center bg-accent/15 text-[10px] font-semibold text-accent">
                  {initials(user?.full_name)}
                </span>
                <ChevronDown size={14} className="text-slate-500" />
              </button>
              {menuOpen && (
                <div className="absolute right-0 mt-2 w-56 animate-fade-up border border-base-700 bg-base-850 p-2 shadow-glow">
                  <div className="border-b border-base-700 px-3 py-2">
                    <p className="truncate text-sm text-slate-200">{user?.full_name}</p>
                    <p className="truncate text-[11px] text-slate-500">{user?.email}</p>
                    <p className="mt-1 inline-flex bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">
                      {user?.role.name}
                    </p>
                  </div>
                  <button
                    onClick={() => void logout().then(() => navigate('/login'))}
                    className="mt-1 flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-slate-400 hover:bg-ink/5 hover:text-rose-300"
                  >
                    <LogOut size={14} /> Cerrar sesión
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1680px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>

        <footer className="border-t border-base-700 px-6 py-4 text-center text-[11px] text-slate-600">
          SOC-Lite / Consola de operaciones de seguridad · Entorno de demostración
        </footer>
      </div>
    </div>
  )
}
