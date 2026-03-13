/**
 * RealtimeInterviewRoom — conversational voice interview powered by
 * OpenAI Realtime API. Audio streams bidirectionally via WebSocket.
 *
 * Audio phases:
 *  - Assistant speaking  → mic is muted (gated at frame level)
 *  - Candidate's turn    → mic unmuted, 60-second countdown timer shown
 *  - Timer expires       → mic muted, backend notified to move on
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { forceEndInterview } from '../api/client'
import { useRealtimeSocket, RealtimeEvent } from '../hooks/useRealtimeSocket'
import { ConversationEntry, SetupData } from '../types'

interface Props {
  setup: SetupData
  onComplete: (sessionId: string) => void
}

type SessionPhase = 'connecting' | 'ready' | 'active' | 'ended' | 'evaluating'

const ANSWER_SECONDS = 60

// ── Countdown ring SVG ────────────────────────────────────────────────────

function CountdownRing({ secondsLeft }: { secondsLeft: number }) {
  const radius = 32
  const circ = 2 * Math.PI * radius
  const pct = secondsLeft / ANSWER_SECONDS
  const dash = pct * circ
  const color = secondsLeft > 30 ? '#34d399' : secondsLeft > 10 ? '#fbbf24' : '#f87171'

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative inline-flex items-center justify-center w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r={radius} fill="none" stroke="#1e293b" strokeWidth="6" />
          <circle
            cx="40"
            cy="40"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circ - dash}`}
            style={{ transition: 'stroke-dasharray 0.5s linear, stroke 0.5s' }}
          />
        </svg>
        <div className="absolute text-center">
          <span className="text-xl font-bold text-white">{secondsLeft}</span>
          <span className="block text-[10px] text-slate-400 leading-none">sec</span>
        </div>
      </div>
      <p className="text-xs font-medium text-emerald-400 uppercase tracking-wider">
        Your turn — answer now
      </p>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────

export default function RealtimeInterviewRoom({ setup, onComplete }: Props) {
  const [conversation, setConversation] = useState<ConversationEntry[]>([])
  const [phase, setPhase] = useState<SessionPhase>('connecting')
  const [isEnding, setIsEnding] = useState(false)
  const [currentAssistantText, setCurrentAssistantText] = useState('')
  const [questionsAsked, setQuestionsAsked] = useState(0)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Answer timer state — null means timer is not running
  const [answerTimeLeft, setAnswerTimeLeft] = useState<number | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const timerStartedRef = useRef(false)

  const conversationEndRef = useRef<HTMLDivElement>(null)
  const rt = useRealtimeSocket()

  // Auto-scroll
  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation, currentAssistantText])

  // ── Timer management ───────────────────────────────────────────────────

  const clearAnswerTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    setAnswerTimeLeft(null)
    timerStartedRef.current = false
  }, [])

  const startAnswerTimer = useCallback(() => {
    // Prevent double-starting
    if (timerStartedRef.current) return
    timerStartedRef.current = true

    setAnswerTimeLeft(ANSWER_SECONDS)

    timerRef.current = setInterval(() => {
      setAnswerTimeLeft(prev => {
        if (prev === null || prev <= 1) {
          clearInterval(timerRef.current!)
          timerRef.current = null
          timerStartedRef.current = false
          // Time's up — mute mic and notify backend
          rt.sendAnswerTimeout()
          return null
        }
        return prev - 1
      })
    }, 1000)
  }, [rt])

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  // ── Handle events from the realtime session ──────────────────────────────

  const handleEvent = useCallback((event: RealtimeEvent) => {
    switch (event.type) {
      case 'session_ready':
        setPhase('ready')
        break

      case 'assistant_transcript_delta':
        setCurrentAssistantText(prev => prev + (event.delta ?? ''))
        if (phase !== 'active') setPhase('active')
        // Assistant is speaking — clear any running answer timer
        clearAnswerTimer()
        rt.muteAudio()
        break

      case 'assistant_transcript':
        if (event.text) {
          setConversation(prev => [
            ...prev,
            { role: 'agent', text: event.text!, timestamp: Date.now() },
          ])
        }
        setCurrentAssistantText('')
        // Assistant finished speaking — open candidate's 1-minute window
        // Small delay to let audio finish playing
        setTimeout(() => {
          rt.unmuteAudio()
          startAnswerTimer()
        }, 800)
        break

      case 'user_transcript':
        if (event.text) {
          setConversation(prev => [
            ...prev,
            { role: 'candidate', text: event.text!, timestamp: Date.now() },
          ])
          setQuestionsAsked(prev => prev + 1)
        }
        // Candidate answered — clear the timer (backend will handle next question flow)
        clearAnswerTimer()
        rt.muteAudio()
        break

      case 'speech_started':
        // Candidate started speaking — timer keeps running but stop blinking
        break

      case 'interview_complete':
        setPhase('evaluating')
        clearAnswerTimer()
        rt.stopMic()
        if (event.questions_asked !== undefined) setQuestionsAsked(event.questions_asked)
        setTimeout(() => onComplete(setup.sessionId), 5000)
        break

      case 'guardrail_violation':
        // Server detected a violation — show brief notice
        setErrorMsg(`⚠️ ${event.message ?? 'Please respond in English and stay on topic.'}`)
        setTimeout(() => setErrorMsg(null), 4000)
        break

      case 'error':
        setErrorMsg(event.message ?? 'An error occurred')
        break
    }
  }, [phase, setup.sessionId, onComplete, rt, startAnswerTimer, clearAnswerTimer])

  // ── Connect + start mic on mount ──────────────────────────────────────────

  useEffect(() => {
    rt.connect(setup.sessionId, handleEvent)
    const timer = setTimeout(async () => {
      try {
        await rt.startMic()
        // Mic starts muted — will unmute when assistant finishes first message
      } catch (err) {
        setErrorMsg('Could not access microphone. Please allow mic access and reload.')
      }
    }, 500)

    return () => {
      clearTimeout(timer)
      clearAnswerTimer()
      rt.stopMic()
      rt.disconnect()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Force end ─────────────────────────────────────────────────────────────

  const handleForceEnd = async () => {
    if (!confirm('End the interview now and generate the report?')) return
    setIsEnding(true)
    setPhase('evaluating')
    clearAnswerTimer()
    rt.stopMic()
    rt.disconnect()
    try {
      await forceEndInterview(setup.sessionId)
    } catch (err) {
      console.error('Force end error', err)
    }
    onComplete(setup.sessionId)
  }

  // ── Status indicator ──────────────────────────────────────────────────────

  const isCandidateTurn = answerTimeLeft !== null && !rt.assistantSpeaking
  const isAssistantTurn = rt.assistantSpeaking || (answerTimeLeft === null && phase === 'active' && !isCandidateTurn)

  const statusText = (() => {
    if (phase === 'connecting') return 'Connecting to interviewer…'
    if (phase === 'ready') return 'Connected — waiting for interviewer'
    if (phase === 'evaluating') return 'Evaluating your responses…'
    if (phase === 'ended') return 'Interview complete'
    if (rt.assistantSpeaking) return 'Interviewer speaking…'
    if (isCandidateTurn) return 'Your turn — speak now'
    return 'Ready'
  })()

  const statusColor = (() => {
    if (phase === 'connecting') return 'text-amber-400'
    if (phase === 'evaluating') return 'text-indigo-400'
    if (rt.assistantSpeaking) return 'text-purple-400'
    if (isCandidateTurn) return 'text-emerald-400'
    return 'text-slate-400'
  })()

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-slate-900 border-b border-slate-700 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full animate-pulse ${
            phase === 'connecting' ? 'bg-amber-400' :
            phase === 'evaluating' ? 'bg-indigo-400' :
            phase === 'ended' ? 'bg-slate-500' :
            'bg-emerald-400'
          }`} />
          <span className="text-sm font-semibold text-white">
            {phase === 'evaluating' ? 'Evaluating…' :
             phase === 'ended' ? 'Interview Complete' : 'Live Interview'}
          </span>
          {questionsAsked > 0 && (
            <span className="text-xs text-slate-400 bg-slate-800 px-2.5 py-0.5 rounded-full border border-slate-700">
              {questionsAsked} responses
            </span>
          )}
        </div>
        <button
          onClick={handleForceEnd}
          disabled={isEnding || phase === 'ended' || phase === 'evaluating'}
          className="px-4 py-2 rounded-lg text-sm font-semibold bg-red-600/20 text-red-400 border border-red-500/30 hover:bg-red-600/30 hover:text-red-300 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {isEnding ? 'Ending…' : 'End Interview'}
        </button>
      </header>

      <div className="flex-1 flex flex-col max-w-3xl mx-auto w-full px-6 py-6 gap-6">
        {/* Conversation */}
        <div className="flex-1 overflow-y-auto space-y-3 min-h-0 pr-1">
          {conversation.map((entry, i) => (
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

          {/* Live streaming assistant text */}
          {currentAssistantText && (
            <div className="flex gap-3 animate-fade-in">
              <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold bg-indigo-600/20 border border-indigo-500/40 text-indigo-400">
                AI
              </div>
              <div className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-tl-sm text-sm leading-relaxed bg-slate-800 text-slate-200">
                {currentAssistantText}
                <span className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse ml-0.5 align-text-bottom" />
              </div>
            </div>
          )}

          <div ref={conversationEndRef} />
        </div>

        {/* Guardrail / Error notice */}
        {errorMsg && (
          <p className="text-xs text-amber-400 text-center bg-amber-900/20 border border-amber-800/40 rounded-xl px-4 py-2">
            {errorMsg}
          </p>
        )}

        {/* Evaluating banner */}
        {phase === 'evaluating' && (
          <div className="flex items-center justify-center gap-3 bg-indigo-900/20 border border-indigo-500/30 rounded-xl px-4 py-3">
            <svg className="w-5 h-5 text-indigo-400 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
            </svg>
            <span className="text-sm text-indigo-300">Evaluating your responses and generating report…</span>
          </div>
        )}

        {/* Status + visualizer */}
        <div className="flex flex-col items-center gap-4 pb-4">
          <p className={`text-xs font-medium uppercase tracking-wider ${statusColor}`}>
            {statusText}
          </p>

          {/* Countdown timer (candidate's turn) OR mic/speaker indicator */}
          {isCandidateTurn ? (
            <CountdownRing secondsLeft={answerTimeLeft!} />
          ) : (
            <div className="relative">
              <div className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 ${
                phase === 'ended' || phase === 'evaluating'
                  ? 'bg-slate-800 text-slate-500'
                  : rt.assistantSpeaking
                  ? 'bg-purple-600/30 text-purple-300'
                  : rt.micActive
                  ? 'bg-slate-700 text-slate-400'
                  : 'bg-slate-700 text-slate-500'
              }`}>
                {phase === 'evaluating' ? (
                  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                  </svg>
                ) : rt.assistantSpeaking ? (
                  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.757 3.63 8.25 4.51 8.25H6.75Z" />
                  </svg>
                ) : (
                  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
                  </svg>
                )}
              </div>

              {/* Pulse ring when assistant is speaking */}
              {rt.assistantSpeaking && (
                <div className="absolute inset-0 rounded-full border-2 border-purple-400/50 animate-ping" />
              )}
            </div>
          )}

          <p className="text-xs text-slate-600 text-center max-w-sm">
            {phase === 'evaluating'
              ? 'Your responses are being evaluated by our AI. This may take a moment.'
              : phase === 'ended'
              ? 'Thank you for completing the interview.'
              : rt.assistantSpeaking
              ? 'The interviewer is speaking…'
              : isCandidateTurn
              ? 'Speak your answer clearly. The timer stops when you finish.'
              : 'Waiting for the interviewer…'}
          </p>
        </div>
      </div>
    </div>
  )
}