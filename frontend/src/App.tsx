import { useState } from 'react'
import SetupForm from './components/SetupForm'
import RealtimeInterviewRoom from './components/RealtimeInterviewRoom'
import ReportView from './components/ReportView'
import { AppState, SetupData } from './types'

export default function App() {
  const [appState, setAppState] = useState<AppState>('setup')
  const [setupData, setSetupData] = useState<SetupData | null>(null)
  const [completedSessionId, setCompletedSessionId] = useState<string | null>(null)

  const handleSetupComplete = (data: SetupData) => {
    setSetupData(data)
    setAppState('interview')
  }

  const handleInterviewComplete = (sessionId: string) => {
    setCompletedSessionId(sessionId)
    setAppState('report')
  }

  const handleRestart = () => {
    setSetupData(null)
    setCompletedSessionId(null)
    setAppState('setup')
  }

  return (
    <div className="min-h-screen bg-slate-950">
      {appState === 'setup' && (
        <SetupForm onComplete={handleSetupComplete} />
      )}

      {appState === 'interview' && setupData && (
        <RealtimeInterviewRoom
          setup={setupData}
          onComplete={handleInterviewComplete}
        />
      )}

      {appState === 'report' && completedSessionId && (
        <ReportView
          sessionId={completedSessionId}
          onRestart={handleRestart}
        />
      )}
    </div>
  )
}
