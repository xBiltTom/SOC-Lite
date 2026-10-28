import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

type ToastKind = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  kind: ToastKind
  message: string
  href?: string
}

interface ToastContextValue {
  push: (message: string, kind?: ToastKind, href?: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
}

const STYLES = {
  success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  error: 'border-rose-500/30 bg-rose-500/10 text-rose-200',
  info: 'border-accent/30 text-accent',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const push = useCallback((message: string, kind: ToastKind = 'info', href?: string) => {
    const id = Date.now() + Math.random()
    setItems((current) => [...current, { id, kind, message, href }])
    window.setTimeout(() => {
      setItems((current) => current.filter((item) => item.id !== id))
    }, 4500)
  }, [])

  const value = useMemo(() => ({ push }), [push])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[100] flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2">
        {items.map((item) => {
          const Icon = ICONS[item.kind]
          return (
            <div
              key={item.id}
              className={`pointer-events-auto flex animate-fade-up items-start gap-3 border bg-base-900 px-4 py-3 text-sm shadow-glow ${STYLES[item.kind]}`}
              role="status"
            >
              <Icon size={18} className="mt-0.5 shrink-0" />
              <div className="flex-1 leading-snug">
                <p>{item.message}</p>
                {item.href && <Link to={item.href} className="mt-1 inline-block underline" onClick={() => setItems((current) => current.filter((entry) => entry.id !== item.id))}>Ver alerta</Link>}
              </div>
              <button
                onClick={() => setItems((current) => current.filter((entry) => entry.id !== item.id))}
                className="p-0.5 opacity-60 hover:opacity-100"
                aria-label="Cerrar notificación"
              >
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast debe usarse dentro de ToastProvider')
  return context
}
