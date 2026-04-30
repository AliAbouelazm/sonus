import { createContext, useContext } from 'react'
import { useWebSocket } from '../hooks/useWebSocket.js'

const WebSocketContext = createContext(null)

export function WebSocketProvider({ children }) {
  const ws = useWebSocket()
  return (
    <WebSocketContext.Provider value={ws}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWS() {
  const ctx = useContext(WebSocketContext)
  if (!ctx) throw new Error('useWS must be used within WebSocketProvider')
  return ctx
}
