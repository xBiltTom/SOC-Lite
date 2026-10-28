import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, Check, Eye, EyeOff, Fingerprint, Loader2, Lock, ShieldCheck, User2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { apiErrorMessage } from '../api/client'
import ThemeToggle from '../components/ThemeToggle'

const DEMO_USERS = [
  { username: 'admin', password: 'Admin123!', role: 'Administrador' },
  { username: 'gerente', password: 'Gerente123!', role: 'Jefe de SOC' },
  { username: 'analista1', password: 'Analista123!', role: 'Analista' },
  { username: 'auditor', password: 'Auditor123!', role: 'Auditor' },
  { username: 'visor', password: 'Visor123!', role: 'Solo lectura' },
]

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('analista1')
  const [password, setPassword] = useState('Analista123!')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(username.trim(), password)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from && from !== '/login' ? from : '/', { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-base-900">
      <header className="flex h-20 items-center justify-between border-b border-base-700 px-6 sm:px-10">
        <a href="/" className="flex items-center gap-3" aria-label="SOC-Lite, inicio">
          <span className="flex h-10 w-10 items-center justify-center bg-accent text-base-950"><ShieldCheck size={23} /></span>
          <span className="text-lg font-bold tracking-tight text-ink">SOC<span className="font-normal text-slate-500"> / </span>LITE</span>
        </a>
        <div className="flex items-center gap-5">
          <span className="eyebrow hidden md:block">Centro de operaciones de seguridad</span>
          <ThemeToggle />
        </div>
      </header>

      <main className="grid min-h-[calc(100svh-5rem)] lg:grid-cols-[1.1fr_1fr]">
        <section className="login-grid relative hidden flex-col justify-between border-r border-base-700 bg-base-850 px-16 py-14 lg:flex">
          <div>
            <p className="eyebrow flex items-center gap-2"><span className="h-1.5 w-1.5 bg-accent" /> Inteligencia para actuar</p>
            <h1 className="mt-6 max-w-lg text-4xl font-semibold leading-[1.08] tracking-[-0.045em] text-ink sm:text-5xl xl:text-6xl">
              Cada alerta.<br />Una decisión<br /><span className="text-accent">más clara.</span>
            </h1>
            <p className="mt-6 max-w-sm text-sm leading-7 text-slate-400">
              Conecta los eventos. Entiende el riesgo. Prioriza la respuesta desde una sola consola de operaciones.
            </p>
          </div>

          <div className="my-10 hidden max-w-lg lg:block" aria-hidden="true">
            <div className="mb-4 flex justify-between border-b border-base-700 pb-3">
              <span className="eyebrow">Flujo de análisis</span><span className="eyebrow text-accent">SOC / 01</span>
            </div>
            <div className="grid grid-cols-[1fr_28px_1fr_28px_1fr] items-center">
              <div className="border border-base-600 bg-base-900 p-4"><p className="eyebrow">01 / Entrada</p><p className="mt-3 text-sm font-semibold text-ink">Eventos</p><p className="mt-1 text-[11px] text-slate-500">Wazuh · OPNsense</p></div>
              <ArrowRight size={16} className="mx-auto text-accent" />
              <div className="border border-accent/50 bg-base-900 p-4"><p className="eyebrow text-accent">02 / Análisis</p><p className="mt-3 text-sm font-semibold text-ink">Triaje</p><p className="mt-1 text-[11px] text-slate-500">Contexto y veredicto</p></div>
              <ArrowRight size={16} className="mx-auto text-accent" />
              <div className="border border-base-600 bg-base-900 p-4"><p className="eyebrow">03 / Acción</p><p className="mt-3 text-sm font-semibold text-ink">Respuesta</p><p className="mt-1 text-[11px] text-slate-500">Decisión del analista</p></div>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 border-t border-base-700 pt-5 text-xs text-slate-400">
            <span className="flex items-center gap-2"><Check size={14} className="text-accent" /> Acceso por roles</span>
            <span className="flex items-center gap-2"><Check size={14} className="text-accent" /> Auditoría trazable</span>
            <span className="flex items-center gap-2"><Check size={14} className="text-accent" /> Reportes integrados</span>
          </div>
        </section>

        <section className="flex flex-col justify-between px-6 py-10 sm:px-10 lg:px-16 lg:py-14">
          <div className="mx-auto w-full max-w-sm">
            <div className="mb-7 flex h-12 w-12 items-center justify-center border border-base-700 text-accent"><Fingerprint size={25} /></div>
            <p className="eyebrow">Acceso a la plataforma</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-ink">Bienvenido de nuevo.</h2>
            <p className="mt-3 text-sm leading-6 text-slate-500">Ingresa tus credenciales para continuar a tu espacio de operaciones.</p>

            <form onSubmit={submit} className="mt-8 space-y-5" aria-busy={loading}>
              <div>
                <label className="label" htmlFor="username">Usuario</label>
                <div className="relative">
                  <User2 size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input id="username" name="username" className="input !py-3 pl-10" value={username}
                    onChange={(event) => setUsername(event.target.value)} autoComplete="username" autoCapitalize="none" spellCheck={false} required disabled={loading} />
                </div>
              </div>
              <div>
                <label className="label" htmlFor="password">Contraseña</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input id="password" name="password" type={showPassword ? 'text' : 'password'} className="input !py-3 pl-10 pr-12"
                    value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required disabled={loading} />
                  <button type="button" onClick={() => setShowPassword((value) => !value)} className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-slate-500 hover:text-ink"
                    aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={showPassword}>
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              {error && <div role="alert" className="border border-rose-500/30 bg-rose-500/10 px-3 py-3 text-sm text-rose-300">{error}</div>}
              <button type="submit" className="btn-primary w-full justify-between !px-4 !py-3.5" disabled={loading}>
                {loading ? 'Verificando acceso…' : 'Entrar a la consola'}
                {loading ? <Loader2 size={17} className="animate-spin" /> : <ArrowRight size={17} />}
              </button>
            </form>

            <details className="mt-8 border-t border-base-700 pt-5">
              <summary className="cursor-pointer text-xs font-medium text-slate-500">Explorar con una cuenta de demostración</summary>
              <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {DEMO_USERS.map((demo) => (
                  <button key={demo.username} type="button" disabled={loading}
                    onClick={() => { setUsername(demo.username); setPassword(demo.password); setError(null) }}
                    className="border border-base-700 px-3 py-2.5 text-left transition-colors hover:border-accent hover:bg-accent/5 disabled:opacity-50">
                    <span className="block text-xs font-medium text-slate-200">{demo.role}</span>
                    <span className="mt-1 block font-mono text-[10px] text-slate-500">{demo.username}</span>
                  </button>
                ))}
              </div>
              <p className="mt-3 text-xs text-slate-500">Cuentas exclusivas del entorno de laboratorio.</p>
            </details>
          </div>
          <p className="mx-auto mt-12 flex w-full max-w-sm items-center gap-2 text-[11px] text-slate-500"><Lock size={12} /> Acceso autorizado · SOC-Lite</p>
        </section>
      </main>
    </div>
  )
}
