/**
 * Auth API client — real email/password + Google OAuth against the backend.
 */

import { apiFetch, apiUrl, setToken } from '../apiClient'

export interface AuthUser {
  id: string
  email: string
  full_name: string
  role: string
  auth_provider: string
  is_verified: boolean
  avatar_url?: string | null
  onboarding_complete: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
  requires_email_verification: boolean
}

export async function register(input: {
  email: string
  password: string
  full_name: string
}): Promise<AuthResponse> {
  const resp = await apiFetch<AuthResponse>('/api/v1/auth/register', {
    method: 'POST',
    body: input,
  })
  setToken(resp.access_token)
  return resp
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const resp = await apiFetch<AuthResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: { email, password },
  })
  setToken(resp.access_token)
  return resp
}

export async function me(): Promise<AuthUser | null> {
  try {
    return await apiFetch<AuthUser>('/api/v1/auth/me')
  } catch {
    return null
  }
}

export async function verifyEmail(token: string): Promise<AuthUser> {
  const resp = await apiFetch<AuthUser>('/api/v1/auth/verify-email', {
    method: 'POST',
    body: { token },
  })
  return resp
}

export async function forgotPassword(email: string): Promise<void> {
  await apiFetch('/api/v1/auth/forgot-password', { method: 'POST', body: { email } })
}

export async function resetPassword(token: string, new_password: string): Promise<void> {
  await apiFetch('/api/v1/auth/reset-password', {
    method: 'POST',
    body: { token, new_password },
  })
}

/** URL to send the browser to for Google's consent screen. */
export function googleLoginUrl(): string {
  return apiUrl('/api/v1/auth/google')
}
