import { useState, useRef } from 'react'
import {
  uploadJobDescription,
  createCandidate,
  uploadResume,
  createSession,
  startInterview,
} from '../api/client'
import { SetupData } from '../types'

interface Props {
  onComplete: (data: SetupData) => void
}

interface StepStatus {
  label: string
  status: 'idle' | 'loading' | 'done' | 'error'
  error?: string
}

const EXPERIENCE_LEVELS = ['junior', 'mid', 'senior', 'lead', 'principal']

export default function SetupForm({ onComplete }: Props) {
  // Form fields
  const [jobTitle, setJobTitle] = useState('')
  const [company, setCompany] = useState('')
  const [candidateName, setCandidateName] = useState('')
  const [candidateEmail, setCandidateEmail] = useState('')
  const [experienceLevel, setExperienceLevel] = useState('mid')
  const [jdFile, setJdFile] = useState<File | null>(null)
  const [resumeFile, setResumeFile] = useState<File | null>(null)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [steps, setSteps] = useState<StepStatus[]>([])

  const jdInputRef = useRef<HTMLInputElement>(null)
  const resumeInputRef = useRef<HTMLInputElement>(null)

  const updateStep = (index: number, patch: Partial<StepStatus>) =>
    setSteps(prev => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!jdFile || !resumeFile || !jobTitle || !candidateName || !candidateEmail) return

    setIsSubmitting(true)
    setSteps([
      { label: 'Uploading job description…', status: 'loading' },
      { label: 'Creating candidate profile…', status: 'idle' },
      { label: 'Parsing resume…', status: 'idle' },
      { label: 'Creating interview session…', status: 'idle' },
      { label: 'Generating first question…', status: 'idle' },
    ])

    try {
      // Step 0 — JD
      const job = await uploadJobDescription(jdFile, jobTitle, company || undefined)
      updateStep(0, { status: 'done', label: 'Job description uploaded ✓' })

      // Step 1 — Candidate
      updateStep(1, { status: 'loading' })
      const candidate = await createCandidate(candidateName, candidateEmail, experienceLevel)
      updateStep(1, { status: 'done', label: 'Candidate profile created ✓' })

      // Step 2 — Resume
      updateStep(2, { status: 'loading' })
      await uploadResume(candidate.id, resumeFile)
      updateStep(2, { status: 'done', label: 'Resume parsed ✓' })

      // Step 3 — Session
      updateStep(3, { status: 'loading' })
      const session = await createSession(candidate.id, job.id)
      updateStep(3, { status: 'done', label: 'Interview session created ✓' })

      // Step 4 — Start interview
      updateStep(4, { status: 'loading' })
      const interview = await startInterview(session.id, candidate.id)
      updateStep(4, { status: 'done', label: 'First question generated ✓' })

      onComplete({
        jobId: job.id,
        candidateId: candidate.id,
        sessionId: session.id,
        firstQuestion: {
          question_id: interview.first_question?.question_id ?? '',
          text: interview.first_question?.text ?? '',
          topic: interview.first_question?.topic ?? '',
        },
      })
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setSteps(prev => {
        const loadingIdx = prev.findIndex(s => s.status === 'loading')
        if (loadingIdx === -1) return prev
        return prev.map((s, i) =>
          i === loadingIdx ? { ...s, status: 'error', error: msg } : s,
        )
      })
      setIsSubmitting(false)
    }
  }

  const isFormValid = jdFile && resumeFile && jobTitle && candidateName && candidateEmail

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-2xl animate-fade-in">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 mb-4">
            <svg className="w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white">Voice Interview Agent</h1>
          <p className="text-slate-400 mt-2">Upload the job description and resume to begin</p>
        </div>

        {/* Steps overlay */}
        {steps.length > 0 && (
          <div className="card p-6 mb-6 animate-slide-up space-y-3">
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
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="card p-8 space-y-8">
          {/* Job Description */}
          <section>
            <h2 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-5 flex items-center gap-2">
              <span className="inline-block w-5 h-5 rounded-full bg-indigo-600 text-white text-xs flex items-center justify-center font-bold">1</span>
              Job Description
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Job Title *</label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. Senior Backend Engineer"
                    value={jobTitle}
                    onChange={e => setJobTitle(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="label">Company (optional)</label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. Acme Corp"
                    value={company}
                    onChange={e => setCompany(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label className="label">JD PDF *</label>
                <input
                  ref={jdInputRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  className="hidden"
                  onChange={e => setJdFile(e.target.files?.[0] ?? null)}
                />
                <button
                  type="button"
                  onClick={() => jdInputRef.current?.click()}
                  className={`w-full border-2 border-dashed rounded-xl py-6 px-4 text-center transition-colors duration-150 ${
                    jdFile
                      ? 'border-indigo-500 bg-indigo-500/10 text-indigo-300'
                      : 'border-slate-700 hover:border-slate-500 text-slate-500 hover:text-slate-400'
                  }`}
                >
                  {jdFile ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      {jdFile.name}
                    </span>
                  ) : (
                    <span>Click to upload job description PDF</span>
                  )}
                </button>
              </div>
            </div>
          </section>

          <div className="border-t border-slate-800" />

          {/* Candidate */}
          <section>
            <h2 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-5 flex items-center gap-2">
              <span className="inline-block w-5 h-5 rounded-full bg-indigo-600 text-white text-xs flex items-center justify-center font-bold">2</span>
              Candidate
            </h2>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Full Name *</label>
                  <input
                    type="text"
                    className="input"
                    placeholder="Jane Smith"
                    value={candidateName}
                    onChange={e => setCandidateName(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="label">Email *</label>
                  <input
                    type="email"
                    className="input"
                    placeholder="jane@example.com"
                    value={candidateEmail}
                    onChange={e => setCandidateEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="label">Experience Level</label>
                <div className="flex gap-2 flex-wrap">
                  {EXPERIENCE_LEVELS.map(level => (
                    <button
                      key={level}
                      type="button"
                      onClick={() => setExperienceLevel(level)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150 capitalize ${
                        experienceLevel === level
                          ? 'bg-indigo-600 text-white'
                          : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                      }`}
                    >
                      {level}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="label">Resume PDF *</label>
                <input
                  ref={resumeInputRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  className="hidden"
                  onChange={e => setResumeFile(e.target.files?.[0] ?? null)}
                />
                <button
                  type="button"
                  onClick={() => resumeInputRef.current?.click()}
                  className={`w-full border-2 border-dashed rounded-xl py-6 px-4 text-center transition-colors duration-150 ${
                    resumeFile
                      ? 'border-indigo-500 bg-indigo-500/10 text-indigo-300'
                      : 'border-slate-700 hover:border-slate-500 text-slate-500 hover:text-slate-400'
                  }`}
                >
                  {resumeFile ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      {resumeFile.name}
                    </span>
                  ) : (
                    <span>Click to upload resume PDF</span>
                  )}
                </button>
              </div>
            </div>
          </section>

          <button
            type="submit"
            disabled={!isFormValid || isSubmitting}
            className="btn-primary w-full py-4 text-base"
          >
            {isSubmitting ? (
              <>
                <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
                </svg>
                Setting up interview…
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 3l14 9-14 9V3z" />
                </svg>
                Start Interview
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
