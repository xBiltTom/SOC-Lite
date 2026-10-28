import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="btn-secondary h-9 gap-2 !px-2.5 text-xs"
      aria-label={theme === 'light' ? 'Activar modo oscuro' : 'Activar modo claro'}
      title={theme === 'light' ? 'Activar modo oscuro' : 'Activar modo claro'}
    >
      {theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}
      <span className="hidden sm:inline">{theme === 'light' ? 'Modo oscuro' : 'Modo claro'}</span>
    </button>
  )
}
