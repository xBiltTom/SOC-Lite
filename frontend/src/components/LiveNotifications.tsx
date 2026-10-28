import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Volume2, VolumeX } from 'lucide-react'
import { api, API_BASE, tokenStore } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { SEVERITY_LABELS } from '../lib/format'
import type { Severity } from '../types'

interface LiveEvent {
  type: string
  alert_id?: string
  severity?: Severity
  description?: string
  simulated?: boolean
}

export default function LiveNotifications() {
  const { user, hasPermission } = useAuth()
  const { push } = useToast()
  const queryClient = useQueryClient()
  const [connected, setConnected] = useState(false)
  const [sound, setSound] = useState(false)
  const soundRef = useRef(false)
  const audioRef = useRef<AudioContext | null>(null)
  const canRead = hasPermission('alerts:read')

  const toggleSound = async () => {
    if (soundRef.current) {
      soundRef.current = false
      setSound(false)
      return
    }
    try {
      const context = audioRef.current ?? new AudioContext()
      audioRef.current = context
      await context.resume()
      soundRef.current = true
      setSound(true)
    } catch {
      push('El navegador no pudo activar el sonido.', 'error')
    }
  }

  useEffect(() => () => { void audioRef.current?.close() }, [])

  useEffect(() => {
    if (!user || !canRead) return
    let stopped = false
    let socket: WebSocket | undefined
    let retry: number | undefined
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: ['alerts'] })
      void queryClient.invalidateQueries({ queryKey: ['alert'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    }
    const connect = async () => {
      try {
        // El interceptor renueva el token si caducó, antes de abrir el canal.
        await api.get('/auth/me')
        if (stopped) return
        const url = new URL(`${API_BASE.replace(/\/$/, '')}/live`, window.location.origin)
        url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
        socket = new WebSocket(url)
        socket.onopen = () => socket?.send(JSON.stringify({ token: tokenStore.access() }))
        socket.onmessage = (message) => {
          let event: LiveEvent
          try { event = JSON.parse(message.data) as LiveEvent } catch { return }
          if (event.type === 'connected') {
            setConnected(true)
            refresh()
            return
          }
          if (event.type !== 'alert.created' && event.type !== 'alert.triaged') return
          refresh()
          if (event.type !== 'alert.created' || !event.alert_id || !event.severity) return
          const severity = SEVERITY_LABELS[event.severity] ?? event.severity
          push(`${event.simulated ? 'Simulada · ' : ''}${severity}: ${event.description ?? 'Nueva alerta'}`, 'info', `/alerts/${event.alert_id}`)
          if (soundRef.current && ['high', 'critical'].includes(event.severity) && audioRef.current?.state === 'running') {
            const context = audioRef.current
            const oscillator = context.createOscillator()
            const gain = context.createGain()
            oscillator.frequency.value = 700
            gain.gain.setValueAtTime(0.07, context.currentTime)
            gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.18)
            oscillator.connect(gain).connect(context.destination)
            oscillator.start()
            oscillator.stop(context.currentTime + 0.18)
          }
        }
        socket.onclose = () => {
          if (stopped) return
          setConnected(false)
          retry = window.setTimeout(() => void connect(), 3000)
        }
        socket.onerror = () => socket?.close()
      } catch {
        if (!stopped) retry = window.setTimeout(() => void connect(), 3000)
      }
    }
    void connect()
    return () => {
      stopped = true
      if (retry !== undefined) window.clearTimeout(retry)
      socket?.close()
    }
  }, [user?.id, canRead, push, queryClient])

  if (!canRead) return null
  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-xs text-slate-400 sm:inline" role="status">
        <span className={connected ? 'text-emerald-400' : 'text-amber-400'}>●</span>{' '}
        {connected ? 'En vivo' : 'Reconectando'}
      </span>
      <button type="button" className="btn-ghost h-9 w-9 !p-0" onClick={() => void toggleSound()} aria-label={sound ? 'Silenciar alertas' : 'Activar sonido de alertas'} aria-pressed={sound} title={sound ? 'Silenciar alertas' : 'Activar sonido de alertas'}>
        {sound ? <Volume2 size={17} /> : <VolumeX size={17} />}
      </button>
    </div>
  )
}
