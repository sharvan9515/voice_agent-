import { ApiResponse, Report, SetupData } from '../types'

const BASE = '/api/v1'

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  })

  const json: ApiResponse<T> = await res.json()

  if (!res.ok || !json.success) {
    throw new Error(json.error?.message ?? json.message ?? `HTTP ${res.status}`)
  }

  return json.data as T
}

// ── Job Description ──────────────────────────────────────────────────────────

export async function uploadJobDescription(
  file: File,
  title: string,
  company?: string,
): Promise<{ id: string; title: string; company: string | null }> {
  const form = new FormData()
  form.append('file', file)
  form.append('title', title)
  if (company) form.append('company', company)
  return request('POST', '/documents/job-description/upload', form)
}

// ── Candidate ────────────────────────────────────────────────────────────────

export async function createCandidate(
  name: string,
  email: string,
  experienceLevel: string,
): Promise<{ id: string; name: string; email: string }> {
  return request('POST', '/candidates', {
    name,
    email,
    experience_level: experienceLevel,
  })
}

export async function uploadResume(
  candidateId: string,
  file: File,
): Promise<{ candidate_id: string; resume_parsed: unknown }> {
  const form = new FormData()
  form.append('file', file)
  return request('POST', `/documents/resume/${candidateId}`, form)
}

// ── Session ───────────────────────────────────────────────────────────────────

export async function createSession(
  candidateId: string,
  jobId: string,
): Promise<{ id: string; candidate_id: string; status: string }> {
  return request('POST', '/sessions', { candidate_id: candidateId, job_id: jobId })
}

// ── Interview ─────────────────────────────────────────────────────────────────

export async function startInterview(
  sessionId: string,
  candidateId: string,
): Promise<{ session_id: string; ws_url: string; first_question: SetupData['firstQuestion'] }> {
  return request('POST', '/interviews', {
    session_id: sessionId,
    candidate_id: candidateId,
  })
}

export async function forceEndInterview(sessionId: string): Promise<void> {
  await request('POST', `/interviews/${sessionId}/end`)
}

// ── Speech ────────────────────────────────────────────────────────────────────

export async function synthesizeSpeech(text: string): Promise<Blob> {
  const res = await fetch(`${BASE}/speech/synthesize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`TTS failed: HTTP ${res.status}`)
  return res.blob()
}

// ── Report ────────────────────────────────────────────────────────────────────

export async function getReport(sessionId: string): Promise<Report> {
  return request('GET', `/reports/${sessionId}`)
}

export async function generateReport(sessionId: string): Promise<Report> {
  return request('POST', `/reports/${sessionId}/generate`)
}
