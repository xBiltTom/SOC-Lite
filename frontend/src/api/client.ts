import axios, { AxiosError, AxiosRequestConfig } from 'axios'

export const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

const ACCESS_KEY = 'soclite.access_token'
const REFRESH_KEY = 'soclite.refresh_token'

export const tokenStore = {
  access: () => localStorage.getItem(ACCESS_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = tokenStore.access()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

interface RetryableConfig extends AxiosRequestConfig {
  _retry?: boolean
}

let refreshPromise: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.refresh()
  if (!refresh) return null
  try {
    const { data } = await axios.post(`${API_BASE}/auth/refresh`, { refresh_token: refresh })
    tokenStore.set(data.access_token, data.refresh_token)
    return data.access_token as string
  } catch {
    tokenStore.clear()
    window.dispatchEvent(new Event('soclite:logout'))
    return null
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryableConfig | undefined
    const status = error.response?.status
    const isAuthCall = config?.url?.includes('/auth/')
    if (status === 401 && config && !config._retry && !isAuthCall) {
      config._retry = true
      refreshPromise = refreshPromise ?? refreshAccessToken()
      const token = await refreshPromise
      refreshPromise = null
      if (token) {
        config.headers = { ...(config.headers || {}), Authorization: `Bearer ${token}` }
        return api.request(config)
      }
    }
    return Promise.reject(error)
  },
)

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: string; errors?: { msg?: string }[] } | undefined
    if (data?.detail) return data.detail
    if (data?.errors?.length) return data.errors.map((item) => item.msg).join(', ')
    if (error.code === 'ECONNABORTED') return 'La operación tardó demasiado. Intente nuevamente.'
    if (!error.response) return 'No se pudo conectar con el servidor.'
    return `Error HTTP ${error.response.status}`
  }
  return (error as Error)?.message || 'Error inesperado'
}

export function downloadBlob(data: Blob, filename: string): void {
  const url = URL.createObjectURL(data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
