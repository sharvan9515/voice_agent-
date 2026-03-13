import { ApiResponse, InterviewSetupResponse, Report } from '../types'

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

// ── One-Shot Interview Setup ────────────────────────────────────────────────

export async function setupInterview(
  file: File,
  jdText: string,
  config?: Record<string, unknown>,
): Promise<InterviewSetupResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('jd_text', jdText)
  if (config) {
    form.append('config', JSON.stringify(config))
  }
  return request('POST', '/interview', form)
}

// ── Force End Interview ─────────────────────────────────────────────────────

export async function forceEndInterview(sessionId: string): Promise<void> {
  await request('POST', `/interview/${sessionId}/end`)
}

// ── Report ──────────────────────────────────────────────────────────────────

export async function getReport(sessionId: string): Promise<Report> {
  return request('GET', `/reports/${sessionId}`)
}

export async function generateReport(sessionId: string): Promise<Report> {
  return request('POST', `/reports/${sessionId}/generate`)
}
