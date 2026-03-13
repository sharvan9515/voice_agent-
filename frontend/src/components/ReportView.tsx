import { useEffect, useState } from 'react'
import { getReport, generateReport } from '../api/client'
import { Report, QADetail } from '../types'

interface Props {
  sessionId: string
  onRestart: () => void
}

// ── Score badge for individual Q&A ──────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 8 ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' :
    score >= 6 ? 'bg-blue-500/20 text-blue-400 border-blue-500/40' :
    score >= 4 ? 'bg-amber-500/20 text-amber-400 border-amber-500/40' :
    'bg-red-500/20 text-red-400 border-red-500/40'
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${color}`}>
      {score.toFixed(1)}/10
    </span>
  )
}

// ── Collapsible Q&A card ──────────────────────────────────────────────────

function QACard({ qa, defaultOpen = false }: { qa: QADetail; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  const eval_ = qa.evaluation

  return (
    <div className="border border-slate-700 rounded-xl overflow-hidden">
      {/* Header — always visible */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-slate-800/50 transition-colors"
      >
        <span className="text-slate-500 text-xs font-mono mt-0.5 w-5 flex-shrink-0">Q{qa.index}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-200 leading-snug">{qa.question}</p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {qa.skill && (
              <span className="text-[10px] text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
                {qa.skill}
              </span>
            )}
            {qa.difficulty && (
              <span className="text-[10px] text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700 capitalize">
                {qa.difficulty}
              </span>
            )}
            {eval_ && <ScoreBadge score={eval_.score} />}
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded content */}
      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-slate-700/60">
          {/* Candidate answer */}
          <div className="pt-3">
            <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1.5">Candidate Answer</p>
            <p className="text-sm text-slate-300 leading-relaxed bg-slate-800/50 rounded-lg px-3 py-2 border border-slate-700/50">
              {qa.answer || <span className="text-slate-600 italic">No answer recorded</span>}
            </p>
          </div>

          {eval_ && (
            <>
              {/* Feedback */}
              <div>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1.5">Feedback</p>
                <p className="text-sm text-slate-300 leading-relaxed">{eval_.feedback}</p>
              </div>

              {/* Evaluation reasoning */}
              {eval_.evaluation_reasoning && (
                <div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1.5">
                    Why This Score
                  </p>
                  <p className="text-sm text-slate-400 leading-relaxed italic">
                    {eval_.evaluation_reasoning}
                  </p>
                </div>
              )}

              {/* Metrics used */}
              {eval_.metrics_used.length > 0 && (
                <div>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold mb-1.5">
                    Evaluation Metrics
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {eval_.metrics_used.map((m, i) => (
                      <span
                        key={i}
                        className="text-[10px] text-indigo-300 bg-indigo-900/30 border border-indigo-500/30 px-2 py-0.5 rounded-full capitalize"
                      >
                        {m.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Strengths / Weaknesses for this answer */}
              {(eval_.strengths.length > 0 || eval_.weaknesses.length > 0) && (
                <div className="grid grid-cols-2 gap-3">
                  {eval_.strengths.length > 0 && (
                    <div>
                      <p className="text-[10px] text-emerald-400 uppercase tracking-wider font-semibold mb-1">Strengths</p>
                      <ul className="space-y-0.5">
                        {eval_.strengths.map((s, i) => (
                          <li key={i} className="text-xs text-slate-400 flex items-start gap-1">
                            <span className="text-emerald-500 flex-shrink-0">+</span>{s}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {eval_.weaknesses.length > 0 && (
                    <div>
                      <p className="text-[10px] text-amber-400 uppercase tracking-wider font-semibold mb-1">Gaps</p>
                      <ul className="space-y-0.5">
                        {eval_.weaknesses.map((w, i) => (
                          <li key={i} className="text-xs text-slate-400 flex items-start gap-1">
                            <span className="text-amber-500 flex-shrink-0">−</span>{w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── Score ring ────────────────────────────────────────────────────────────

function ScoreRing({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, (score / 10) * 100))
  const radius = 42
  const circ = 2 * Math.PI * radius
  const dash = (pct / 100) * circ
  const color = pct >= 70 ? '#34d399' : pct >= 45 ? '#fbbf24' : '#f87171'

  return (
    <div className="relative inline-flex items-center justify-center w-28 h-28">
      <svg className="w-28 h-28 -rotate-90" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#1e293b" strokeWidth="8" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ - dash}`}
          style={{ transition: 'stroke-dasharray 1s ease-out' }}
        />
      </svg>
      <div className="absolute text-center">
        <span className="text-2xl font-bold text-white">{score.toFixed(1)}</span>
        <span className="block text-xs text-slate-400">/ 10</span>
      </div>
    </div>
  )
}

export default function ReportView({ sessionId, onRestart }: Props) {
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retries, setRetries] = useState(0)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    const fetchReport = async () => {
      try {
        const data = await getReport(sessionId)
        if (!cancelled) {
          setReport(data)
          setLoading(false)
        }
      } catch {
        // Report might still be generating — retry up to 6 times (30 s)
        if (retries < 6 && !cancelled) {
          timer = setTimeout(() => setRetries(r => r + 1), 5000)
        } else if (!cancelled) {
          // Try to trigger manual generation
          try {
            const data = await generateReport(sessionId)
            if (!cancelled) {
              setReport(data)
              setLoading(false)
            }
          } catch (err2) {
            if (!cancelled) {
              setError(err2 instanceof Error ? err2.message : 'Failed to load report')
              setLoading(false)
            }
          }
        }
      }
    }

    fetchReport()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [sessionId, retries])

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-6 animate-fade-in">
        <div className="w-16 h-16 rounded-full border-2 border-indigo-500/30 border-t-indigo-500 animate-spin" />
        <div className="text-center">
          <p className="text-white font-semibold">Generating your report…</p>
          <p className="text-slate-500 text-sm mt-1">This may take a few seconds</p>
        </div>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 animate-fade-in">
        <p className="text-red-400">{error ?? 'Report not available'}</p>
        <button onClick={onRestart} className="btn-primary">
          Start New Interview
        </button>
      </div>
    )
  }

  const scoreLabel =
    report.total_score >= 8 ? { text: 'Excellent', color: 'text-emerald-400' } :
    report.total_score >= 6 ? { text: 'Good', color: 'text-blue-400' } :
    report.total_score >= 4 ? { text: 'Fair', color: 'text-amber-400' } :
    { text: 'Needs Work', color: 'text-red-400' }

  return (
    <div className="min-h-screen py-12 px-6 animate-fade-in">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-600/20 border border-emerald-500/30 mb-4">
            <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white">Interview Complete</h1>
          <p className="text-slate-400 mt-1 text-sm">Here's the evaluation summary</p>
        </div>

        {/* Score card */}
        <div className="card p-8 flex items-center gap-8 animate-slide-up">
          <ScoreRing score={report.total_score} />
          <div>
            <p className="text-slate-400 text-sm mb-1">Overall Score</p>
            <p className={`text-3xl font-bold ${scoreLabel.color}`}>{scoreLabel.text}</p>
            <p className="text-slate-500 text-sm mt-1">
              {report.total_score.toFixed(1)} out of 10
            </p>
          </div>
        </div>

        {/* Summary */}
        <div className="card p-6 animate-slide-up">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Summary</h2>
          <p className="text-slate-200 leading-relaxed">{report.summary}</p>
        </div>

        {/* Strengths & Weaknesses */}
        <div className="grid grid-cols-2 gap-4 animate-slide-up">
          <div className="card p-5">
            <h2 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              Strengths
            </h2>
            <ul className="space-y-2">
              {report.strengths.length > 0 ? (
                report.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <span className="text-emerald-500 mt-0.5 flex-shrink-0">•</span>
                    {s}
                  </li>
                ))
              ) : (
                <li className="text-slate-500 text-sm">No specific strengths noted.</li>
              )}
            </ul>
          </div>

          <div className="card p-5">
            <h2 className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
              </svg>
              Areas to Improve
            </h2>
            <ul className="space-y-2">
              {report.weaknesses.length > 0 ? (
                report.weaknesses.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <span className="text-amber-500 mt-0.5 flex-shrink-0">•</span>
                    {w}
                  </li>
                ))
              ) : (
                <li className="text-slate-500 text-sm">No specific areas noted.</li>
              )}
            </ul>
          </div>
        </div>

        {/* Q&A Breakdown */}
        {report.qa_details && report.qa_details.length > 0 && (
          <div className="animate-slide-up">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
              </svg>
              Question-by-Question Breakdown
              <span className="text-slate-600 font-normal normal-case tracking-normal">
                ({report.qa_details.length} {report.qa_details.length === 1 ? 'question' : 'questions'})
              </span>
            </h2>
            <div className="space-y-2">
              {report.qa_details.map((qa, i) => (
                <QACard key={i} qa={qa} defaultOpen={i === 0} />
              ))}
            </div>
          </div>
        )}

        {/* Session ID */}
        <p className="text-center text-xs text-slate-600">
          Session ID: {sessionId}
        </p>

        {/* Actions */}
        <div className="flex justify-center gap-3 pt-2">
          <button onClick={onRestart} className="btn-primary">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            New Interview
          </button>
          <button
            onClick={() => {
              const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
              const a = document.createElement('a')
              a.href = URL.createObjectURL(blob)
              a.download = `report-${sessionId.slice(0, 8)}.json`
              a.click()
            }}
            className="btn-ghost border border-slate-700"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Export JSON
          </button>
        </div>
      </div>
    </div>
  )
}
