import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { AuthUser } from '../types/auth'
import {
  apiUrl,
  authHeaders,
  clearAccessToken,
  getAccessToken,
  isAccessTokenExpired,
  markAuthReady,
  refreshAccessToken,
  setAccessToken,
} from '../lib/apiClient'
import { setAiLanguage, normalizeAiLanguage, hasExplicitAiLanguage } from '../lib/ai/language'

function normalizeUser(raw: any): AuthUser | null {
  if (!raw) return null
  const roleStr = raw.role?.value || raw.role || 'student'
  return {
    id: raw.id || '',
    email: raw.email || '',
    fullName: raw.fullName || raw.full_name || raw.name || '',
    role: roleStr === 'doctor' ? 'doctor' : 'student',
    provider: raw.provider || 'google',
    avatarUrl: raw.avatarUrl || raw.avatar_url || raw.picture || null,
    emailVerified: Boolean(raw.emailVerified ?? raw.email_verified ?? true),
    onboardingComplete: Boolean(raw.onboardingComplete ?? raw.onboarding_complete ?? true),
    universityId: raw.universityId || raw.university_id || null,
    facultyId: raw.facultyId || raw.faculty_id || null,
    departmentId: raw.departmentId || raw.department_id || null,
    academicYear: raw.academicYear || raw.academic_year || null,
    semester: raw.semester || null,
    preferredLanguage: raw.preferredLanguage || raw.preferred_language || 'ar',
    studyGoals: raw.studyGoals || raw.study_goals || [],
    weakSubjects: raw.weakSubjects || raw.weak_subjects || [],
    strongSubjects: raw.strongSubjects || raw.strong_subjects || [],
    academicPosition: raw.academicPosition || raw.academic_position || null,
    specialization: raw.specialization || null,
    coursesTaught: raw.coursesTaught || raw.courses_taught || [],
    officeHours: raw.officeHours || raw.office_hours || null,
    xp: raw.xp || 0,
    level: raw.level || 1,
    streakDays: raw.streakDays || raw.streak_days || 0,
    createdAt: raw.createdAt || raw.created_at || new Date().toISOString(),
    lastLogin: raw.lastLogin || raw.last_login || null,
  }
}

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  /** True once the session bootstrap has completed — safe for protected AI calls. */
  authReady: boolean
  isAuthenticated: boolean
  register: (input: {
    fullName: string
    email: string
    password: string
    role: 'student' | 'doctor'
  }) => Promise<AuthUser>
  login: (input: { email: string; password: string; rememberMe: boolean }) => Promise<AuthUser>
  setUserFromAuthResponse: (user: any) => void
  logout: () => Promise<void>
  logoutAllDevices: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const saved = localStorage.getItem('learnx_user')
      return saved ? normalizeUser(JSON.parse(saved)) : null
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState(true)
  const bootstrapped = useRef(false)

  const refreshUser = useCallback(async () => {
    try {
      const token = getAccessToken()
      if (!token) return
      const res = await fetch(apiUrl('/api/v1/auth/me'), {
        headers: authHeaders(),
        credentials: 'include',
      })
      if (res.ok) {
        const raw = await res.json()
        const normalized = normalizeUser(raw)
        setUser(normalized)
        if (normalized) {
          localStorage.setItem('learnx_user', JSON.stringify(normalized))
          if (!hasExplicitAiLanguage()) {
            const preferred = normalizeAiLanguage(normalized.preferredLanguage)
            if (preferred) setAiLanguage(preferred)
          }
        }
      }
    } catch {}
  }, [])

  useEffect(() => {
    if (bootstrapped.current) return
    bootstrapped.current = true
    ;(async () => {
      try {
        // Hydrate the token from storage into the single source of truth.
        const existing = getAccessToken()
        if (existing && !isAccessTokenExpired(existing)) {
          // Session already valid — hydrate the user without a needless (and
          // concurrency-unsafe) refresh rotation.
          await refreshUser()
        } else {
          // Missing or expired access token — refresh through the shared,
          // concurrency-safe lock (never an independent /refresh fetch, which
          // would race the request layer and rotate the refresh token twice).
          const token = await refreshAccessToken()
          if (token) {
            await refreshUser()
          } else if (getAccessToken()) {
            await refreshUser()
          }
        }
      } catch {
        // Bootstrap errors are non-fatal; the request layer will handle 401s.
      } finally {
        markAuthReady()
        setLoading(false)
      }
    })()
  }, [refreshUser])

  const register = useCallback(
    async (input: {
      fullName: string
      email: string
      password: string
      role: 'student' | 'doctor'
    }) => {
      const res = await fetch(apiUrl('/api/v1/auth/register'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          full_name: input.fullName,
          email: input.email,
          password: input.password,
          role: input.role,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || data.message || 'Registration failed')
      const normalized = normalizeUser(data.user || data)!
      setUser(normalized)
      localStorage.setItem('learnx_user', JSON.stringify(normalized))
      if (data.access_token) setAccessToken(data.access_token)
      return normalized
    },
    []
  )

  const login = useCallback(
    async (input: { email: string; password: string; rememberMe: boolean }) => {
      const res = await fetch(apiUrl('/api/v1/auth/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          email: input.email,
          password: input.password,
          remember_me: input.rememberMe,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || data.message || 'Login failed')
      const normalized = normalizeUser(data.user || data)!
      setUser(normalized)
      localStorage.setItem('learnx_user', JSON.stringify(normalized))
      if (data.access_token) setAccessToken(data.access_token)
      return normalized
    },
    []
  )

  const setUserFromAuthResponse = useCallback((nextUser: any) => {
    const normalized = normalizeUser(nextUser)
    setUser(normalized)
    if (normalized) {
      try {
        localStorage.setItem('learnx_user', JSON.stringify(normalized))
      } catch {}
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await fetch(apiUrl('/api/v1/auth/logout'), { method: 'POST', credentials: 'include' })
    } finally {
      localStorage.removeItem('learnx_user')
      clearAccessToken()
      setUser(null)
      window.location.href = '/'
    }
  }, [])

  const logoutAllDevices = useCallback(async () => {
    try {
      await fetch(apiUrl('/api/v1/auth/logout-all'), {
        method: 'POST',
        headers: authHeaders(),
        credentials: 'include',
      })
    } finally {
      localStorage.removeItem('learnx_user')
      clearAccessToken()
      setUser(null)
      window.location.href = '/'
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      authReady: !loading,
      isAuthenticated: user !== null,
      register,
      login,
      setUserFromAuthResponse,
      logout,
      logoutAllDevices,
      refreshUser,
    }),
    [user, loading, register, login, setUserFromAuthResponse, logout, logoutAllDevices, refreshUser]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
