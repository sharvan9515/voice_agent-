/**
 * useRealtimeSocket — manages the bidirectional WebSocket to our server,
 * which relays audio to/from the OpenAI Realtime API.
 *
 * Handles:
 *  - Mic capture → PCM16 24kHz → base64 → WS send (gated by audioMuted ref)
 *  - WS receive → base64 → PCM16 → AudioContext playback
 *  - Transcript events (user + assistant)
 *  - Evaluation and interview_complete events
 *  - 1-minute answer window: muteAudio/unmuteAudio controls
 */
import { useRef, useState, useCallback, useEffect } from 'react'
import {
  float32ToPcm16,
  downsampleTo24k,
  pcm16ToBase64,
  Pcm16Player,
} from '../utils/audio'

// ── Types for events the server sends us ────────────────────────────────────

export interface RealtimeEvent {
  type:
    | 'session_ready'
    | 'audio'
    | 'assistant_transcript_delta'
    | 'assistant_transcript'
    | 'user_transcript'
    | 'speech_started'
    | 'speech_stopped'
    | 'evaluation'
    | 'interview_complete'
    | 'error'
    | 'pong'
    | 'guardrail_violation'
  audio?: string          // base64 PCM16
  delta?: string          // streaming transcript chunk
  text?: string           // full transcript
  message?: string        // error / complete message
  score?: number
  skill?: string
  questions_asked?: number
  total_score?: number
  violation_type?: string
}

export interface RealtimeControls {
  connected: boolean
  micActive: boolean
  assistantSpeaking: boolean
  audioMuted: boolean
  connect: (sessionId: string, onEvent: (e: RealtimeEvent) => void) => void
  disconnect: () => void
  startMic: () => Promise<void>
  stopMic: () => void
  muteAudio: () => void
  unmuteAudio: () => void
  sendAnswerTimeout: () => void
}

// ── AudioWorklet processor source (inline) ──────────────────────────────────
// We inline it as a blob URL so we don't need a separate file.

const WORKLET_CODE = `
class PcmCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0]
    if (input && input[0] && input[0].length > 0) {
      // Clone the Float32 data and post to main thread
      this.port.postMessage(new Float32Array(input[0]))
    }
    return true
  }
}
registerProcessor('pcm-capture', PcmCaptureProcessor)
`

function createWorkletBlobUrl(): string {
  const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' })
  return URL.createObjectURL(blob)
}

// ── Hook ────────────────────────────────────────────────────────────────────

export function useRealtimeSocket(): RealtimeControls {
  const wsRef = useRef<WebSocket | null>(null)
  const playerRef = useRef<Pcm16Player | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const workletNodeRef = useRef<AudioWorkletNode | null>(null)
  const onEventRef = useRef<((e: RealtimeEvent) => void) | null>(null)

  // audioMutedRef gates whether audio frames are forwarded to the WebSocket.
  // The mic stream stays alive (for zero-latency resume) but frames are
  // dropped when muted. Starts muted — unmuteAudio() is called by the
  // interview room when the assistant finishes speaking.
  const audioMutedRef = useRef<boolean>(true)

  const [connected, setConnected] = useState(false)
  const [micActive, setMicActive] = useState(false)
  const [assistantSpeaking, setAssistantSpeaking] = useState(false)
  const [audioMuted, setAudioMuted] = useState(true)

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopMic()
      wsRef.current?.close()
      playerRef.current?.close()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── WebSocket connection ────────────────────────────────────────────────

  const disconnect = useCallback(() => {
    wsRef.current?.close(1000, 'client disconnect')
    wsRef.current = null
    setConnected(false)
  }, [])

  const connect = useCallback(
    (sessionId: string, onEvent: (e: RealtimeEvent) => void) => {
      if (wsRef.current) disconnect()

      onEventRef.current = onEvent

      // Initialize player
      if (!playerRef.current) {
        playerRef.current = new Pcm16Player()
      }

      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${proto}://${window.location.host}/api/v1/interview/${sessionId}/realtime`

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        setMicActive(false)
      }
      ws.onerror = (e) => console.error('[Realtime WS] error', e)

      ws.onmessage = (e) => {
        try {
          const event: RealtimeEvent = JSON.parse(e.data)
          _handleServerEvent(event)
          onEventRef.current?.(event)
        } catch {
          console.warn('[Realtime WS] non-JSON message', e.data)
        }
      }
    },
    [disconnect],
  )

  // ── Handle server events internally ───────────────────────────────────

  function _handleServerEvent(event: RealtimeEvent) {
    switch (event.type) {
      case 'audio':
        // Queue audio for playback; mute candidate mic while assistant speaks
        if (event.audio && playerRef.current) {
          playerRef.current.play(event.audio)
          setAssistantSpeaking(true)
          // Mute candidate mic while assistant is speaking
          audioMutedRef.current = true
          setAudioMuted(true)
        }
        break

      case 'speech_started':
        // User started speaking — interrupt assistant audio
        playerRef.current?.interrupt()
        setAssistantSpeaking(false)
        break

      case 'assistant_transcript':
        // Full assistant turn done — audio may still be playing briefly.
        // The interview room will call unmuteAudio() after a short delay
        // once it detects the assistant has stopped speaking.
        setTimeout(() => {
          if (!playerRef.current?.isPlaying) {
            setAssistantSpeaking(false)
          }
        }, 500)
        break

      case 'interview_complete':
        setAssistantSpeaking(false)
        setMicActive(false)
        // Hard-mute on completion
        audioMutedRef.current = true
        setAudioMuted(true)
        break
    }
  }

  // ── Audio mute controls ───────────────────────────────────────────────

  const muteAudio = useCallback(() => {
    audioMutedRef.current = true
    setAudioMuted(true)
  }, [])

  const unmuteAudio = useCallback(() => {
    audioMutedRef.current = false
    setAudioMuted(false)
  }, [])

  // ── Send answer timeout signal to backend ─────────────────────────────

  const sendAnswerTimeout = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'answer_timeout' }))
    }
    // Mute mic after timeout
    audioMutedRef.current = true
    setAudioMuted(true)
  }, [])

  // ── Microphone capture ────────────────────────────────────────────────

  const startMic = useCallback(async () => {
    if (micActive) return

    // Resume player AudioContext (browser autoplay policy)
    await playerRef.current?.resume()

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: { ideal: 24000 },
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })
    streamRef.current = stream

    const audioCtx = new AudioContext({ sampleRate: stream.getAudioTracks()[0].getSettings().sampleRate || 48000 })
    audioCtxRef.current = audioCtx

    const source = audioCtx.createMediaStreamSource(stream)
    const workletUrl = createWorkletBlobUrl()

    await audioCtx.audioWorklet.addModule(workletUrl)
    URL.revokeObjectURL(workletUrl)

    const workletNode = new AudioWorkletNode(audioCtx, 'pcm-capture')
    workletNodeRef.current = workletNode

    workletNode.port.onmessage = (e: MessageEvent<Float32Array>) => {
      // Drop frames when muted — mic stream stays alive for low-latency resume
      if (audioMutedRef.current) return
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return

      const float32 = e.data
      // Downsample to 24kHz
      const downsampled = downsampleTo24k(float32, audioCtx.sampleRate)
      // Convert to PCM16
      const pcm16 = float32ToPcm16(downsampled)
      // Base64 encode and send
      const base64 = pcm16ToBase64(pcm16)

      wsRef.current.send(JSON.stringify({
        type: 'audio',
        audio: base64,
      }))
    }

    source.connect(workletNode)
    workletNode.connect(audioCtx.destination) // needed to keep the pipeline alive
    setMicActive(true)
  }, [micActive])

  const stopMic = useCallback(() => {
    workletNodeRef.current?.disconnect()
    workletNodeRef.current = null
    audioCtxRef.current?.close()
    audioCtxRef.current = null
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    setMicActive(false)
    audioMutedRef.current = true
    setAudioMuted(true)
  }, [])

  return {
    connected,
    micActive,
    assistantSpeaking,
    audioMuted,
    connect,
    disconnect,
    startMic,
    stopMic,
    muteAudio,
    unmuteAudio,
    sendAnswerTimeout,
  }
}