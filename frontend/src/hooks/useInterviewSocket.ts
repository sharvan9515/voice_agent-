import { useRef, useState, useCallback } from 'react'
import { WsMessage } from '../types'

// Use same host but switch protocol to ws/wss — Vite proxy handles it
function getWsUrl(sessionId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/api/v1/interviews/${sessionId}/stream`
}

export interface SocketControls {
  connected: boolean
  connect: (sessionId: string, onMessage: (msg: WsMessage) => void) => void
  disconnect: () => void
  sendAudioChunk: (chunk: Blob) => void
  sendEndOfSpeech: () => void
}

export function useInterviewSocket(): SocketControls {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)

  const disconnect = useCallback(() => {
    wsRef.current?.close(1000, 'client disconnect')
    wsRef.current = null
    setConnected(false)
  }, [])

  const connect = useCallback(
    (sessionId: string, onMessage: (msg: WsMessage) => void) => {
      if (wsRef.current) disconnect()

      const ws = new WebSocket(getWsUrl(sessionId))
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => setConnected(false)
      ws.onerror = (e) => console.error('[WS] error', e)

      ws.onmessage = (e) => {
        try {
          const msg: WsMessage = JSON.parse(e.data as string)
          onMessage(msg)
        } catch {
          console.warn('[WS] non-JSON message', e.data)
        }
      }
    },
    [disconnect],
  )

  const sendAudioChunk = useCallback((chunk: Blob) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(chunk)
    }
  }, [])

  const sendEndOfSpeech = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'end_of_speech' }))
    }
  }, [])

  return { connected, connect, disconnect, sendAudioChunk, sendEndOfSpeech }
}
