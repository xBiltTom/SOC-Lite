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
}

export default function LiveNotifications() {
  const { user, hasPermission } = useAuth()
  const { push } = useToast()
  const queryClient = useQueryClient()
  const [connected, setConnected] = useState(false)
  const [sound, setSound] = useState(false)
  const soundRef = useRef(false)
  const audioRef = useRef<AudioContext | null>(null)
  const alarmRef = useRef<OscillatorNode | null>(null)
  const canRead = hasPermission('alerts:read')

  const toggleSound = async () => {
    if (soundRef.current) {
      soundRef.current = false
      setSound(false)
      alarmRef.current?.stop()
      alarmRef.current = null
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

  useEffect(() => () => {
    alarmRef.current?.stop()
    alarmRef.current = null
    void audioRef.current?.close()
    audioRef.current = null
  }, [])

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
          push(`${severity}: ${event.description ?? 'Nueva alerta'}`, 'info', `/alerts/${event.alert_id}`)
          if (soundRef.current && ['high', 'critical'].includes(event.severity) && audioRef.current?.state === 'running') {
            const context = audioRef.current
            alarmRef.current?.stop()
            const oscillator = context.createOscillator()
            const gain = context.createGain()
            const start = context.currentTime
            oscillator.type = 'triangle'
            gain.gain.setValueAtTime(0.001, start)
            gain.gain.linearRampToValueAtTime(0.22, start + 0.05)
            for (let pulse = 0; pulse < 10; pulse += 1) {
              const at = start + pulse * 0.5
              oscillator.frequency.setValueAtTime(650, at)
              oscillator.frequency.linearRampToValueAtTime(1050, at + 0.25)
              oscillator.frequency.linearRampToValueAtTime(650, at + 0.5)
            }
            gain.gain.setValueAtTime(0.22, start + 4.9)
            gain.gain.linearRampToValueAtTime(0.001, start + 5)
            oscillator.connect(gain).connect(context.destination)
            alarmRef.current = oscillator
            oscillator.onended = () => {
              if (alarmRef.current === oscillator) alarmRef.current = null
              oscillator.disconnect()
              gain.disconnect()
            }
            oscillator.start(start)
            oscillator.stop(start + 5)
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
