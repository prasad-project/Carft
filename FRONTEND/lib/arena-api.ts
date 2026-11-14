export type ArenaPlayer = {
  user_id: string
  display_name: string
  avatar_url: string | null
  is_ready: boolean
  is_host: boolean
}

export type ArenaRoom = {
  id: string
  room_code: string
  invite_link: string
  host_id: string
  domain_id: string
  duration_seconds: number
  question_count: number
  status: string
  expires_at: string
  max_players: number
  players: ArenaPlayer[]
}

export type ArenaSession = { access_token: string; user_id: string }
export type ArenaDomain = { id: string; name: string; slug: string; is_active: boolean; available_questions: number }

const API_URL = process.env.NEXT_PUBLIC_ARENA_API_URL ?? 'http://localhost:8002/api/v1'
const SESSION_KEY = 'devportfolio-arena-session'

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_URL}${path}`, { ...init, headers })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(body?.error?.message ?? body?.detail?.message ?? body?.detail ?? `Arena request failed (${response.status})`)
  }
  return body as T
}

export async function getArenaSession(): Promise<ArenaSession> {
  const stored = window.sessionStorage.getItem(SESSION_KEY)
  if (stored) return JSON.parse(stored) as ArenaSession
  const username = `arena-${crypto.randomUUID().slice(0, 8)}`
  const session = await request<ArenaSession>('/auth/dev-login', {
    method: 'POST',
    body: JSON.stringify({ username, display_name: 'Arena Player' }),
  })
  window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
  return session
}

export async function getArenaDomains(token: string): Promise<ArenaDomain[]> {
  return request<ArenaDomain[]>('/domains', {}, token)
}

export async function createArenaRoom(token: string, input: { domain_id: string; duration_seconds: number; question_count: number }) {
  return request<ArenaRoom>('/rooms', { method: 'POST', body: JSON.stringify(input) }, token)
}

export async function joinArenaRoom(token: string, roomCode: string) {
  return request<ArenaRoom>('/rooms/join', { method: 'POST', body: JSON.stringify({ room_code: roomCode }) }, token)
}

export async function startArenaRoom(token: string, roomId: string) {
  return request<{ match_id: string; room: ArenaRoom }>(`/rooms/${roomId}/start`, { method: 'POST' }, token)
}

export async function readyArenaRoom(token: string, roomId: string, ready = true) {
  return request<ArenaRoom>(`/rooms/${roomId}/ready`, {
    method: 'POST',
    body: JSON.stringify({ ready }),
  }, token)
}

export async function cancelArenaRoom(token: string, roomId: string) {
  return request<ArenaRoom>(`/rooms/${roomId}/cancel`, { method: 'POST' }, token)
}

export function arenaWebSocketUrl(roomId: string, token: string) {
  const base = API_URL.replace(/^http/, 'ws').replace(/\/api\/v1$/, '')
  return `${base}/ws/game/${roomId}?token=${encodeURIComponent(token)}`
}
