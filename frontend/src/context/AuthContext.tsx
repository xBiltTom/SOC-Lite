import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { authApi, type LoginResponse } from '../api'
import { tokenStore } from '../api/client'
import type { User } from '../types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  hasPermission: (code: string) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const bootstrap = async () => {
      if (!tokenStore.access()) {
        setLoading(false)
        return
      }
      try {
        const profile = await authApi.me()
        if (active) setUser(profile)
      } catch {
        tokenStore.clear()
      } finally {
        if (active) setLoading(false)
      }
    }
    void bootstrap()
    const onLogout = () => setUser(null)
    window.addEventListener('soclite:logout', onLogout)
    return () => {
      active = false
      window.removeEventListener('soclite:logout', onLogout)
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const response: LoginResponse = await authApi.login(username, password)
    tokenStore.set(response.access_token, response.refresh_token)
    setUser(response.user)
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // el cierre local debe funcionar aunque el servidor no responda
    } finally {
      tokenStore.clear()
      setUser(null)
    }
  }, [])

  const hasPermission = useCallback(
    (code: string) => Boolean(user?.permissions?.includes(code)),
    [user],
  )

  const value = useMemo(
    () => ({ user, loading, login, logout, hasPermission }),
    [user, loading, login, logout, hasPermission],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return context
}
