import { useState, useRef } from 'react'
import { setupInterview } from '../api/client'
import { SetupData, InterviewSetupResponse, ScreeningResult } from '../types'

interface Props {
  onComplete: (data: SetupData) => void
}

interface StepStatus {
  label: string
  status: 'idle' | 'loading' | 'done' | 'error'
  error?: string
}

type Phase = 'upload' | 'confirm' | 'starting' | 'screened_out'

export default function SetupForm({ onComplete }: Props) {
  const [phase, setPhase] = useState<Phase>('upload')
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [jdText, setJdText] = useState('')
  const [steps, setSteps] = useState<StepStatus[]>([])
  const [screeningResult, setScreeningResult] = useState<ScreeningResult | null>(null)
  const [candidateInfo, setCandidateInfo] = useState<InterviewSetupResponse['candidate'] | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (file: File) => {
    setResumeFile(file)
    setPhase('confirm')
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file) handleFileChange(file)
  }

  const handleStartInterview = async () => {
    if (!resumeFile) return
    setPhase('starting')

    setSteps([
      { label: 'Parsing resume & job description…', status: 'loading' },
      { label: 'Screening candidate…', status: 'idle' },
      { label: 'Generating first question…', status: 'idle' },
    ])

    const updateStep = (index: number, patch: Partial<StepStatus>) =>
      setSteps(prev => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)))

    try {
      updateStep(0, { status: 'loading' })

      const result = await setupInterview(resumeFile, jdText.trim())

      // Step 1 done — parsing complete
      updateStep(0, { status: 'done', label: 'Resume & JD parsed' })

      // Step 2 — screening
      updateStep(1, { status: 'loading' })
      setScreeningResult(result.screening)
      setCandidateInfo(result.candidate)

      if (result.status === 'screened_out') {
        updateStep(1, { status: 'done', label: `Screening: ${result.screening.fit_score}/100 (below threshold)` })
        updateStep(2, { status: 'error', error: 'Candidate did not meet screening threshold' })
        setPhase('screened_out')
        return
      }

      updateStep(1, { status: 'done', label: `Screening passed: ${result.screening.fit_score}/100` })

      // Step 3 — first question ready
      updateStep(2, { status: 'done', label: 'First question ready' })

      onComplete({
        jobId: '',
        candidateId: result.candidate.id ?? '',
        sessionId: result.session_id ?? '',
        firstQuestion: {
          question_id: result.first_question?.question_id ?? '',
          text: result.first_question?.text ?? '',
          topic: result.first_question?.topic ?? '',
        },
      })
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setSteps(prev => {
        const idx = prev.findIndex(s => s.status === 'loading')
        if (idx === -1) return prev
        return prev.map((s, i) => (i === idx ? { ...s, status: 'error', error: msg } : s))
      })
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-lg animate-fade-in">

        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 mb-4">
            <svg className="w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white">Voice Interview Agent</h1>
          <p className="text-slate-400 mt-2 text-sm">Upload your resume to get started</p>
        </div>

        {/* Phase: upload */}
        {phase === 'upload' && (
          <div className="card p-8 space-y-6">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,application/pdf,text/plain"
              className="hidden"
              onChange={e => {
                const file = e.target.files?.[0]
                if (file) handleFileChange(file)
              }}
            />

            {/* Drop zone */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              onDragOver={e => e.preventDefault()}
              onDrop={handleDrop}
              className="w-full border-2 border-dashed rounded-2xl py-14 px-6 text-center transition-all duration-200 border-slate-700 hover:border-indigo-500/60 hover:bg-indigo-500/5 cursor-pointer"
            >
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-slate-800 flex items-center justify-center">
                  <svg className="w-6 h-6 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m6.75 12-3-3m0 0-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                  </svg>
                </div>
                <div>
                  <p className="text-slate-300 font-medium">Drop your resume here</p>
                  <p className="text-slate-500 text-sm mt-1">or click to browse — PDF or TXT</p>
                </div>
              </div>
            </button>
          </div>
        )}

        {/* Phase: confirm */}
        {phase === 'confirm' && resumeFile && (
          <div className="card p-8 space-y-6 animate-slide-up">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-8 h-8 rounded-full bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center">
                <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <p className="text-white font-semibold text-sm">Resume selected</p>
                <p className="text-slate-500 text-xs">{resumeFile.name}</p>
              </div>
            </div>

            {/* Job Description textarea */}
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                </svg>
                Job Description
                <span className="text-slate-600 normal-case font-normal tracking-normal">(optional)</span>
              </label>
              <textarea
                value={jdText}
                onChange={e => setJdText(e.target.value)}
                placeholder="Paste the job description here to tailor the interview questions to the role…"
                rows={5}
                className="w-full bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 resize-none focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/30 transition-colors"
              />
            </div>

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => { setPhase('upload'); setResumeFile(null); setJdText('') }}
                className="btn-ghost flex-1"
              >
                Upload different resume
              </button>
              <button
                type="button"
                onClick={handleStartInterview}
                className="btn-primary flex-1"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 3l14 9-14 9V3z" />
                </svg>
                Start Interview
              </button>
            </div>
          </div>
        )}

        {/* Phase: starting (progress steps) */}
        {phase === 'starting' && (
          <div className="card p-8 space-y-4 animate-slide-up">
            <p className="text-white font-semibold text-center mb-6">Setting up your interview…</p>
            {steps.map((step, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                {step.status === 'loading' && (
                  <svg className="w-4 h-4 text-indigo-400 animate-spin flex-shrink-0" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
                  </svg>
                )}
                {step.status === 'done' && (
                  <svg className="w-4 h-4 text-emerald-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {step.status === 'error' && (
                  <svg className="w-4 h-4 text-red-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                )}
                {step.status === 'idle' && (
                  <div className="w-4 h-4 rounded-full border border-slate-600 flex-shrink-0" />
                )}
                <span className={
                  step.status === 'done' ? 'text-emerald-400' :
                  step.status === 'error' ? 'text-red-400' :
                  step.status === 'loading' ? 'text-white' :
                  'text-slate-500'
                }>
                  {step.label}
                  {step.error && <span className="ml-2 text-red-300">— {step.error}</span>}
                </span>
              </div>
            ))}
            {steps.some(s => s.status === 'error') && (
              <button
                type="button"
                onClick={() => { setPhase('confirm'); setSteps([]) }}
                className="btn-ghost w-full mt-4"
              >
                Try again
              </button>
            )}
          </div>
        )}

        {/* Phase: screened_out */}
        {phase === 'screened_out' && screeningResult && (
          <div className="card p-8 space-y-6 animate-slide-up">
            <div className="text-center mb-4">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-amber-600/20 border border-amber-500/30 mb-3">
                <svg className="w-6 h-6 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-white">Screening Result</h2>
              <p className="text-slate-400 text-sm mt-1">Candidate does not meet the minimum threshold for this role</p>
            </div>

            {/* Fit score */}
            <div className="bg-slate-800/60 rounded-xl px-5 py-4 text-center">
              <p className="text-xs text-slate-500 mb-1">Fit Score</p>
              <p className="text-3xl font-bold text-amber-400">{screeningResult.fit_score}<span className="text-lg text-slate-500">/100</span></p>
            </div>

            {/* Score breakdown */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-slate-800/40 rounded-lg px-3 py-3 text-center">
                <p className="text-xs text-slate-500 mb-1">Skills</p>
                <p className="text-lg font-semibold text-slate-200">{screeningResult.breakdown.skills_score}</p>
              </div>
              <div className="bg-slate-800/40 rounded-lg px-3 py-3 text-center">
                <p className="text-xs text-slate-500 mb-1">Experience</p>
                <p className="text-lg font-semibold text-slate-200">{screeningResult.breakdown.experience_score}</p>
              </div>
              <div className="bg-slate-800/40 rounded-lg px-3 py-3 text-center">
                <p className="text-xs text-slate-500 mb-1">Domain</p>
                <p className="text-lg font-semibold text-slate-200">{screeningResult.breakdown.domain_score}</p>
              </div>
            </div>

            {/* Matched / Missing skills */}
            {screeningResult.matched_skills.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Matched Skills</p>
                <div className="flex flex-wrap gap-1.5">
                  {screeningResult.matched_skills.map(s => (
                    <span key={s} className="px-2 py-0.5 text-xs rounded-full bg-emerald-900/40 text-emerald-300 border border-emerald-800/40">{s}</span>
                  ))}
                </div>
              </div>
            )}
            {screeningResult.missing_skills.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Missing Skills</p>
                <div className="flex flex-wrap gap-1.5">
                  {screeningResult.missing_skills.map(s => (
                    <span key={s} className="px-2 py-0.5 text-xs rounded-full bg-red-900/40 text-red-300 border border-red-800/40">{s}</span>
                  ))}
                </div>
              </div>
            )}

            <button
              type="button"
              onClick={() => { setPhase('upload'); setResumeFile(null); setJdText(''); setScreeningResult(null) }}
              className="btn-primary w-full"
            >
              Try with a different resume
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
