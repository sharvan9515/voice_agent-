export type AppState = 'setup' | 'interview' | 'report'

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

export interface ConversationEntry {
  role: 'agent' | 'candidate'
  text: string
  topic?: string
  timestamp: number
}

export interface QAEvaluation {
  score: number
  feedback: string
  evaluation_reasoning: string
  metrics_used: string[]
  strengths: string[]
  weaknesses: string[]
}

export interface QADetail {
  index: number
  question: string
  skill: string
  difficulty: string
  answer: string
  evaluation: QAEvaluation | null
}

export interface Report {
  id: string
  session_id: string
  candidate_id: string
  total_score: number
  strengths: string[]
  weaknesses: string[]
  summary: string
  qa_details: QADetail[] | null
  created_at: string
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  message?: string
  error?: { code: string; message: string }
}

export interface ScreeningResult {
  fit_score: number
  verdict: 'qualified' | 'unqualified'
  matched_skills: string[]
  missing_skills: string[]
  experience_match: boolean
  breakdown: {
    skills_score: number
    experience_score: number
    domain_score: number
  }
}

export interface InterviewSetupResponse {
  status: 'ready' | 'screened_out'
  session_id?: string
  realtime_ws_url?: string
  candidate: {
    id?: string
    name: string
    email: string
    experience_level?: string
    skills?: string[]
    experience_years?: number
  }
  screening: ScreeningResult
  first_question?: {
    question_id: string
    text: string
    topic: string
  }
  config: {
    max_questions: number
    max_follow_ups_per_topic: number
    depth: string
    style: string
    focus_areas: string[]
    screen_threshold: number
    tts_voice: string
  }
}
