import { useEffect, useState } from 'react'
import { getReport, generateReport } from '../api/client'
import { Report } from '../types'

interface Props {
  sessionId: string
  onRestart: () => void
}

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
