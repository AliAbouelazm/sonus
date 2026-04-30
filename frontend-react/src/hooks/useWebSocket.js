import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

const BASE_RETRY_MS = 1000
const MAX_RETRY_MS  = 30000

export function useWebSocket() {
  const [status, setStatus]           = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const wsRef           = useRef(null)
  const reconnectTimer  = useRef(null)
  const pingTimer       = useRef(null)
  const mountedRef      = useRef(true)
  const retryCount      = useRef(0)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')
    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        if (!mountedRef.current) return
        retryCount.current = 0
        setStatus('connected')
        pingTimer.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
        }, 30000)
      }

      ws.onmessage = (evt) => {
        if (!mountedRef.current) return
        try {
          const msg = JSON.parse(evt.data)
          setLastMessage(msg)
        } catch (_) {}
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setStatus('disconnected')
        clearInterval(pingTimer.current)
        // Exponential backoff: 1s, 2s, 4s, 8s … capped at 30s
        const delay = Math.min(MAX_RETRY_MS, BASE_RETRY_MS * Math.pow(2, retryCount.current))
        retryCount.current += 1
        reconnectTimer.current = setTimeout(connect, delay)
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch (_) {
      setStatus('disconnected')
      const delay = Math.min(MAX_RETRY_MS, BASE_RETRY_MS * Math.pow(2, retryCount.current))
      retryCount.current += 1
      reconnectTimer.current = setTimeout(connect, delay)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      clearTimeout(reconnectTimer.current)
      clearInterval(pingTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  return { status, lastMessage, send }
}
