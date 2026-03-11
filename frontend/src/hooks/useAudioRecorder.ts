import { useRef, useState, useCallback } from 'react'

const SILENCE_THRESHOLD = 0.008   // RMS energy — below this = silence
const SILENCE_DURATION_MS = 10000  // 10 seconds of silence triggers end-of-speech
const CHUNK_INTERVAL_MS = 200      // send audio chunk every 200 ms

export interface AudioRecorderControls {
  isRecording: boolean
  silenceCountdown: number   // seconds remaining before auto-trigger (0 = not in silence)
  startRecording: () => Promise<void>
  stopRecording: () => void
}

export function useAudioRecorder(
  onChunk: (chunk: Blob) => void,
  onSilenceDetected: () => void,
): AudioRecorderControls {
  const [isRecording, setIsRecording] = useState(false)
  const [silenceCountdown, setSilenceCountdown] = useState(0)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const animFrameRef = useRef<number>(0)
  const silenceStartRef = useRef<number | null>(null)
  const triggeredRef = useRef(false)

  const stopRecording = useCallback(() => {
    triggeredRef.current = false
    silenceStartRef.current = null
    setSilenceCountdown(0)

    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    if (mediaRecorderRef.current?.state !== 'inactive') mediaRecorderRef.current?.stop()
    if (audioCtxRef.current) { audioCtxRef.current.close(); audioCtxRef.current = null }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null }

    setIsRecording(false)
  }, [])

  const startRecording = useCallback(async () => {
    triggeredRef.current = false
    silenceStartRef.current = null
    setSilenceCountdown(0)

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    streamRef.current = stream

    // Web Audio API for VAD
    const audioCtx = new AudioContext()
    audioCtxRef.current = audioCtx
    const source = audioCtx.createMediaStreamSource(stream)
    const analyser = audioCtx.createAnalyser()
    analyser.fftSize = 512
    source.connect(analyser)

    // MediaRecorder for audio chunks
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm'
    const recorder = new MediaRecorder(stream, { mimeType })
    mediaRecorderRef.current = recorder

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) onChunk(e.data)
    }
    recorder.start(CHUNK_INTERVAL_MS)
    setIsRecording(true)

    // VAD loop via requestAnimationFrame
    const dataArray = new Uint8Array(analyser.frequencyBinCount)

    const tick = () => {
      if (!audioCtxRef.current) return

      analyser.getByteTimeDomainData(dataArray)

      // Calculate RMS energy
      let sum = 0
      for (let i = 0; i < dataArray.length; i++) {
        const norm = (dataArray[i] - 128) / 128
        sum += norm * norm
      }
      const rms = Math.sqrt(sum / dataArray.length)

      if (rms > SILENCE_THRESHOLD) {
        // Voice detected — reset silence timer
        silenceStartRef.current = null
        setSilenceCountdown(0)
      } else {
        // Silence
        if (silenceStartRef.current === null) {
          silenceStartRef.current = performance.now()
        } else {
          const elapsed = performance.now() - silenceStartRef.current
          const remaining = Math.max(0, Math.ceil((SILENCE_DURATION_MS - elapsed) / 1000))
          setSilenceCountdown(remaining)

          if (elapsed >= SILENCE_DURATION_MS && !triggeredRef.current) {
            triggeredRef.current = true
            setSilenceCountdown(0)
            onSilenceDetected()
            return // stop VAD loop — caller will stopRecording
          }
        }
      }

      animFrameRef.current = requestAnimationFrame(tick)
    }

    animFrameRef.current = requestAnimationFrame(tick)
  }, [onChunk, onSilenceDetected])

  return { isRecording, silenceCountdown, startRecording, stopRecording }
}
