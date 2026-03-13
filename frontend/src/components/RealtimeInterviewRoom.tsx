/**
 * RealtimeInterviewRoom — conversational voice interview powered by
 * OpenAI Realtime API. Audio streams bidirectionally via WebSocket.
 * No manual "send answer" — the model uses VAD to detect speech turns.
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

export default function RealtimeInterviewRoom({ setup, onComplete }: Props) {
  const [conversation, setConversation] = useState<ConversationEntry[]>([])
  const [phase, setPhase] = useState<SessionPhase>('connecting')
  const [isEnding, setIsEnding] = useState(false)
  const [currentAssistantText, setCurrentAssistantText] = useState('')
  const [questionsAsked, setQuestionsAsked] = useState(0)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const conversationEndRef = useRef<HTMLDivElement>(null)
  const rt = useRealtimeSocket()

  // Auto-scroll
  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation, currentAssistantText])

  // ── Handle events from the realtime session ──────────────────────────────

  const handleEvent = useCallback((event: RealtimeEvent) => {
    switch (event.type) {
      case 'session_ready':
        setPhase('ready')
        break

      case 'assistant_transcript_delta':
        setCurrentAssistantText(prev => prev + (event.delta ?? ''))
        if (phase !== 'active') setPhase('active')
        break

      case 'assistant_transcript':
        if (event.text) {
          setConversation(prev => [
            ...prev,
            { role: 'agent', text: event.text!, timestamp: Date.now() },
          ])
        }
        setCurrentAssistantText('')
        break

      case 'user_transcript':
        if (event.text) {
          setConversation(prev => [
            ...prev,
            { role: 'candidate', text: event.text!, timestamp: Date.now() },
          ])
          setQuestionsAsked(prev => prev + 1)
        }
        break

      case 'interview_complete':
        setPhase('evaluating')
        rt.stopMic()
        if (event.questions_asked !== undefined) setQuestionsAsked(event.questions_asked)
        // Wait for post-interview evaluation to complete, then navigate
        setTimeout(() => onComplete(setup.sessionId), 5000)
        break

      case 'error':
        setErrorMsg(event.message ?? 'An error occurred')
        break
    }
  }, [phase, setup.sessionId, onComplete, rt])

  // ── Connect + start mic on mount ──────────────────────────────────────────

  useEffect(() => {
    rt.connect(setup.sessionId, handleEvent)
    const timer = setTimeout(async () => {
      try {
        await rt.startMic()
      } catch (err) {
        setErrorMsg('Could not access microphone. Please allow mic access and reload.')
      }
    }, 500)

    return () => {
      clearTimeout(timer)
      rt.stopMic()
      rt.disconnect()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Force end ─────────────────────────────────────────────────────────────

  const handleForceEnd = async () => {
    if (!confirm('End the interview now and generate the report?')) return
    setIsEnding(true)
    setPhase('evaluating')
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

  const statusText = (() => {
    if (phase === 'connecting') return 'Connecting to interviewer…'
    if (phase === 'ready') return 'Connected — start speaking'
    if (phase === 'evaluating') return 'Evaluating your responses…'
    if (phase === 'ended') return 'Interview complete'
    if (rt.assistantSpeaking) return 'Interviewer speaking…'
    if (rt.micActive) return 'Listening…'
    return 'Ready'
  })()

  const statusColor = (() => {
    if (phase === 'connecting') return 'text-amber-400'
    if (phase === 'evaluating') return 'text-indigo-400'
    if (rt.assistantSpeaking) return 'text-purple-400'
    if (rt.micActive) return 'text-emerald-400'
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

        {/* Error */}
        {errorMsg && (
          <p className="text-xs text-red-400 text-center bg-red-900/20 border border-red-800/40 rounded-xl px-4 py-2">
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

        {/* Status + Mic visualizer */}
        <div className="flex flex-col items-center gap-4 pb-4">
          <p className={`text-xs font-medium uppercase tracking-wider ${statusColor}`}>
            {statusText}
          </p>

          {/* Mic indicator */}
          <div className="relative">
            <div className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 ${
              phase === 'ended' || phase === 'evaluating'
                ? 'bg-slate-800 text-slate-500'
                : rt.assistantSpeaking
                ? 'bg-purple-600/30 text-purple-300'
                : rt.micActive
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-700 text-slate-500'
            }`}>
              {phase === 'evaluating' ? (
                /* Checkmark icon */
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                </svg>
              ) : rt.assistantSpeaking ? (
                /* Speaker icon */
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.757 3.63 8.25 4.51 8.25H6.75Z" />
                </svg>
              ) : (
                /* Mic icon */
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
                </svg>
              )}
            </div>

            {/* Pulse ring when recording */}
            {rt.micActive && !rt.assistantSpeaking && phase === 'active' && (
              <div className="absolute inset-0 rounded-full border-2 border-indigo-400/50 animate-ping" />
            )}
          </div>

          <p className="text-xs text-slate-600 text-center max-w-sm">
            {phase === 'evaluating'
              ? 'Your responses are being evaluated by our AI. This may take a moment.'
              : phase === 'ended'
              ? 'Thank you for completing the interview.'
              : rt.assistantSpeaking
              ? 'The interviewer is speaking. You can interrupt at any time.'
              : 'Speak naturally — the interviewer will respond automatically.'}
          </p>
        </div>
      </div>
    </div>
  )
}