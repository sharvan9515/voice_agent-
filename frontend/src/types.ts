export type AppState = 'setup' | 'starting' | 'interview' | 'finishing' | 'report'

export interface SetupData {
  jobId: string
  candidateId: string
  sessionId: string
  firstQuestion: {
    question_id: string
    text: string
    topic: string
  }
}

export interface WsMessage {
  type: 'question' | 'follow_up' | 'complete' | 'error' | 'pong'
  text?: string
  topic?: string
  question_id?: string
  message?: string
}

export interface ConversationEntry {
  role: 'agent' | 'candidate'
  text: string
  topic?: string
  timestamp: number
}

export interface Report {
  id: string
  session_id: string
  candidate_id: string
  total_score: number
  strengths: string[]
  weaknesses: string[]
  summary: string
  created_at: string
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  message?: string
  error?: { code: string; message: string }
}
