import { useEffect, useRef, useState, useCallback } from 'react'
import { synthesizeSpeech, forceEndInterview } from '../api/client'
import { useAudioRecorder } from '../hooks/useAudioRecorder'
import { useInterviewSocket } from '../hooks/useInterviewSocket'
import { ConversationEntry, SetupData, WsMessage } from '../types'

interface Props {
  setup: SetupData
  onComplete: (sessionId: string) => void
}

type MicState = 'idle' | 'recording' | 'processing' | 'speaking' | 'waiting'

const MIC_STATE_LABELS: Record<MicState, string> = {
  idle: 'Ready',
  recording: 'Listening…',
  processing: 'Processing answer…',
  speaking: 'Agent speaking…',
  waiting: 'Connecting…',
}

export default function InterviewRoom({ setup, onComplete }: Props) {
  const [conversation, setConversation] = useState<ConversationEntry[]>([])
  const [micState, setMicState] = useState<MicState>('waiting')
  const [currentQuestion, setCurrentQuestion] = useState(setup.firstQuestion.text)
  const [currentTopic, setCurrentTopic] = useState(setup.firstQuestion.topic)
  const [isEnding, setIsEnding] = useState(false)
  const [ttsError, setTtsError] = useState<string | null>(null)

  const conversationEndRef = useRef<HTMLDivElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const socketRef = useInterviewSocket()
  const processingRef = useRef(false)

  // Auto-scroll conversation
  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation])

  // ── TTS: speak a text string, then unlock mic ──────────────────────────────
  const speakText = useCallback(async (text: string) => {
    setMicState('speaking')
    setTtsError(null)
    try {
      const blob = await synthesizeSpeech(text)
      const url = URL.createObjectURL(blob)
      if (audioRef.current) {
        audioRef.current.src = url
        await audioRef.current.play()
      }
    } catch (err) {
      console.error('TTS error', err)
      setTtsError('Audio playback unavailable — read the question above.')
      // Still proceed to recording
      setMicState('recording')
      await recorderControls.startRecording()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── WebSocket message handler ─────────────────────────────────────────────
  const handleWsMessage = useCallback(
    async (msg: WsMessage) => {
      if (msg.type === 'question' || msg.type === 'follow_up') {
        processingRef.current = false
        const text = msg.text ?? ''
        const topic = msg.topic ?? ''

        setCurrentQuestion(text)
        setCurrentTopic(topic)
        setConversation(prev => [
          ...prev,
          { role: 'agent', text, topic, timestamp: Date.now() },
        ])
        await speakText(text)
      } else if (msg.type === 'complete') {
        processingRef.current = false
        setMicState('idle')
        recorderControls.stopRecording()
        socketRef.disconnect()
        onComplete(setup.sessionId)
      } else if (msg.type === 'error') {
        processingRef.current = false
        console.error('[WS] server error:', msg.message)
        // Don't crash — stay in recording state
        setMicState('recording')
      }
    },
    [setup.sessionId, speakText, onComplete], // eslint-disable-line react-hooks/exhaustive-deps
  )

  // ── Audio chunk handler ───────────────────────────────────────────────────
  const handleChunk = useCallback(
    (chunk: Blob) => {
      socketRef.sendAudioChunk(chunk)
    },
    [socketRef],
  )

  // ── Silence detected ──────────────────────────────────────────────────────
  const handleSilence = useCallback(() => {
    if (processingRef.current) return
    processingRef.current = true
    recorderControls.stopRecording()
    setMicState('processing')
    socketRef.sendEndOfSpeech()
  }, [socketRef]) // eslint-disable-line react-hooks/exhaustive-deps

  const recorderControls = useAudioRecorder(handleChunk, handleSilence)

  // ── Agent audio ended → start recording ───────────────────────────────────
  const handleAudioEnded = useCallback(async () => {
    if (micState === 'speaking') {
      setMicState('recording')
      await recorderControls.startRecording()
    }
  }, [micState, recorderControls])

  // ── Initial setup: connect WS + speak first question ─────────────────────
  useEffect(() => {
    socketRef.connect(setup.sessionId, handleWsMessage)
    setConversation([
      {
        role: 'agent',
        text: setup.firstQuestion.text,
        topic: setup.firstQuestion.topic,
        timestamp: Date.now(),
      },
    ])
    speakText(setup.firstQuestion.text)

    return () => {
      socketRef.disconnect()
      recorderControls.stopRecording()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Manual mic toggle ──────────────────────────────────────────────────────
  const handleMicClick = async () => {
    if (micState === 'recording') {
      handleSilence()
    } else if (micState === 'idle' || micState === 'waiting') {
      setMicState('recording')
      await recorderControls.startRecording()
    }
  }

  // ── Force end ─────────────────────────────────────────────────────────────
  const handleForceEnd = async () => {
    if (!confirm('End the interview now and generate the report?')) return
    setIsEnding(true)
    recorderControls.stopRecording()
    socketRef.disconnect()
    try {
      await forceEndInterview(setup.sessionId)
    } catch (err) {
      console.error('Force end error', err)
    }
    onComplete(setup.sessionId)
  }

  const micColors: Record<MicState, string> = {
    idle: 'bg-slate-700 hover:bg-slate-600 text-slate-300',
    waiting: 'bg-slate-700 text-slate-500 cursor-wait',
    speaking: 'bg-purple-600/30 text-purple-300 cursor-default',
    processing: 'bg-amber-600/30 text-amber-300 cursor-wait',
    recording: 'bg-indigo-600 text-white animate-pulse-ring',
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-sm font-medium text-slate-300">Interview in Progress</span>
          <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full capitalize">
            {currentTopic}
          </span>
        </div>
        <button
          onClick={handleForceEnd}
          disabled={isEnding}
          className="btn-ghost text-red-400 hover:text-red-300 hover:bg-red-900/20"
        >
          {isEnding ? 'Ending…' : 'End Interview'}
        </button>
      </header>

      <div className="flex-1 flex flex-col max-w-3xl mx-auto w-full px-6 py-6 gap-6">
        {/* Current question card */}
        <div className="card p-6 animate-slide-up">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center flex-shrink-0 mt-0.5">
              <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z" />
              </svg>
            </div>
            <div>
              <p className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-1">
                Interviewer
              </p>
              <p className="text-slate-100 text-base leading-relaxed">{currentQuestion}</p>
            </div>
          </div>
        </div>

        {/* Conversation history */}
        <div className="flex-1 overflow-y-auto space-y-3 min-h-0 max-h-[340px] pr-1">
          {conversation.slice(0, -1).map((entry, i) => (
            <div
              key={i}
              className={`flex gap-3 animate-fade-in ${entry.role === 'candidate' ? 'flex-row-reverse' : ''}`}
            >
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold ${
                  entry.role === 'agent'
                    ? 'bg-indigo-600/20 border border-indigo-500/40 text-indigo-400'
                    : 'bg-slate-700 text-slate-300'
                }`}
              >
                {entry.role === 'agent' ? 'AI' : 'You'}
              </div>
              <div
                className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  entry.role === 'agent'
                    ? 'bg-slate-800 text-slate-200 rounded-tl-sm'
                    : 'bg-indigo-600/20 border border-indigo-500/30 text-indigo-100 rounded-tr-sm'
                }`}
              >
                {entry.text}
              </div>
            </div>
          ))}
          <div ref={conversationEndRef} />
        </div>

        {/* TTS error notice */}
        {ttsError && (
          <p className="text-xs text-amber-400 text-center">{ttsError}</p>
        )}

        {/* Microphone section */}
        <div className="flex flex-col items-center gap-4">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">
            {MIC_STATE_LABELS[micState]}
            {micState === 'recording' && recorderControls.silenceCountdown > 0 && (
              <span className="ml-2 text-slate-600">
                (auto-send in {recorderControls.silenceCountdown}s)
              </span>
            )}
          </p>

          {/* Mic button */}
          <button
            onClick={handleMicClick}
            disabled={micState === 'speaking' || micState === 'processing' || micState === 'waiting'}
            className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-200 ${micColors[micState]}`}
            title={micState === 'recording' ? 'Click to send answer' : 'Click to speak'}
          >
            {micState === 'processing' ? (
              <svg className="w-8 h-8 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
              </svg>
            ) : micState === 'speaking' ? (
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.757 3.63 8.25 4.51 8.25H6.75Z" />
              </svg>
            ) : (
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
              </svg>
            )}
          </button>

          <p className="text-xs text-slate-600 text-center max-w-xs">
            {micState === 'recording'
              ? 'Speak your answer. Auto-sends after 10 s of silence, or click to send now.'
              : micState === 'speaking'
              ? 'Microphone locked while agent is speaking.'
              : 'Microphone will unlock after the agent finishes speaking.'}
          </p>
        </div>
      </div>

      {/* Hidden audio element for TTS playback */}
      <audio ref={audioRef} onEnded={handleAudioEnded} className="hidden" />
    </div>
  )
}
