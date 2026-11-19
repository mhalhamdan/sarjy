// Typed client for the backend. Requests are same-origin, so the session cookie is sent
// automatically.

export interface Memory {
  id: number
  content: string
  created_at: string
  updated_at: string
}

export interface RealtimeSession {
  client_secret: string
  expires_at: number
  model: string
}

export interface RememberResult {
  status: 'saved' | 'updated'
  memory: Memory
}

export interface ForgetResult {
  status: 'forgotten' | 'not_found'
}

export interface WebSearchResult {
  answer: string
  sources: { title: string; url: string }[]
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type UnauthorizedListener = () => void
let onUnauthorized: UnauthorizedListener = () => {}

/** Called whenever the backend answers 401, e.g. when the cookie has gone. */
export function setUnauthorizedListener(listener: UnauthorizedListener): void {
  onUnauthorized = listener
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/passcode') onUnauthorized()
    throw new ApiError(response.status, await errorMessage(response))
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
  } catch {
    // Not JSON; fall through to a generic message.
  }
  return `Request failed (${response.status}).`
}

export const api = {
  authStatus: () => request<{ authenticated: boolean }>('GET', '/auth/status'),
  enterPasscode: (passcode: string) =>
    request<{ authenticated: boolean }>('POST', '/auth/passcode', { passcode }),
  createRealtimeSession: () => request<RealtimeSession>('POST', '/realtime/session'),
  listMemories: () => request<Memory[]>('GET', '/memories'),
  deleteMemory: (id: number) => request<void>('DELETE', `/memories/${id}`),
  deleteAllMemories: () => request<{ deleted: number }>('DELETE', '/memories'),
  remember: (args: unknown) => request<RememberResult>('POST', '/tools/remember', args),
  forget: (args: unknown) => request<ForgetResult>('POST', '/tools/forget', args),
  webSearch: (args: unknown) => request<WebSearchResult>('POST', '/tools/web_search', args),
}
