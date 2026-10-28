import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

type Theme = 'light' | 'dark'
const STORAGE_KEY = 'soclite.theme.v1'
const ThemeContext = createContext<{ theme: Theme; toggleTheme: () => void } | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light',
  )

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      'content', theme === 'light' ? '#f4f6f8' : '#0b1118',
    )
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // El selector sigue funcionando cuando el navegador bloquea el almacenamiento.
    }
  }, [theme])

  useEffect(() => {
    const syncTheme = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY) setTheme(event.newValue === 'dark' ? 'dark' : 'light')
    }
    window.addEventListener('storage', syncTheme)
    return () => window.removeEventListener('storage', syncTheme)
  }, [])

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme: () => setTheme((value) => value === 'light' ? 'dark' : 'light') }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme debe usarse dentro de ThemeProvider')
  return context
}
