/**
 * AuthContext — real session state backed by the LearnX backend.
 * Token lives in localStorage (see src/lib/apiClient.ts) and is attached
 * to every API call; this context holds the authenticated user.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { getToken, setToken } from '../lib/apiClient'
import {
  login as apiLogin,
  register as apiRegister,
  me as apiMe,
  type AuthUser,
} from '../lib/auth/apiClient'

interface AuthContextValue {
  user: AuthUser | null
  /** True once the initial session check has finished. */
  ready: boolean
  login: (email: string, password: string) => Promise<AuthUser>
  register: (input: { email: string; password: string; full_name: string }) => Promise<AuthUser>
  /** Completes the Google OAuth flow with the JWT returned by the callback. */
  completeGoogleAuth: (token: string) => Promise<AuthUser | null>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (getToken()) {
        const u = await apiMe()
        if (!cancelled) setUser(u)
      }
      if (!cancelled) setReady(true)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const resp = await apiLogin(email, password)
    setUser(resp.user)
    return resp.user
  }, [])

  const register = useCallback(
    async (input: { email: string; password: string; full_name: string }) => {
      const resp = await apiRegister(input)
      setUser(resp.user)
      return resp.user
    },
    [],
  )

  const completeGoogleAuth = useCallback(async (token: string) => {
    setToken(token)
    const u = await apiMe()
    setUser(u)
    return u
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, ready, login, register, completeGoogleAuth, logout }),
    [user, ready, login, register, completeGoogleAuth, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
